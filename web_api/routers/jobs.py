"""
岗位管理 API
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from src.storage.database import DatabaseManager
from src.helpers import load_config

router = APIRouter()


def get_db():
    config = load_config()
    return DatabaseManager(config['storage']['db_path'])


def _job_to_dict(j, include_analysis: bool = False) -> dict:
    d = {
        "id": j.id,
        "title": j.title,
        "company": j.company,
        "city": j.city,
        "salary": j.salary,
        "source": j.source,
        "status": j.status,
        "match_score": j.match_score,
        "url": j.url,
        "created_at": j.created_at.isoformat() if j.created_at else None,
    }
    if include_analysis:
        d["description"] = j.description
        d["requirements"] = j.requirements
    return d


class JobUpdateRequest(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None


@router.get("")
async def list_jobs(
    page: int = 1,
    per_page: int = 20,
    status: Optional[str] = None,
    city: Optional[str] = None,
):
    """获取岗位列表（分页）"""
    db = get_db()
    try:
        jobs = db.get_jobs_paginated(page, per_page, status, city)
        total = db.get_jobs_count(status, city)
        return {
            "success": True,
            "data": [_job_to_dict(j) for j in jobs],
            "total": total,
            "page": page,
            "per_page": per_page,
        }
    finally:
        db.close()


# Keep backward-compat alias
@router.get("/list")
async def list_jobs_compat(
    page: int = 1, per_page: int = 20,
    status: Optional[str] = None, city: Optional[str] = None,
):
    return await list_jobs(page, per_page, status, city)


@router.get("/stats")
async def get_stats():
    """获取岗位统计数据"""
    db = get_db()
    try:
        stats = db.get_statistics()
        return {"success": True, "data": stats}
    finally:
        db.close()


@router.get("/{job_id}")
async def get_job(job_id: int):
    """获取岗位详情（含最新分析结果）"""
    db = get_db()
    try:
        job = db.get_job_by_id(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="岗位不存在")

        data = _job_to_dict(job, include_analysis=True)

        # 附带最新分析结果摘要
        analysis = db.get_analysis_by_job(job_id)
        if analysis:
            data["analysis"] = {
                "id": analysis.id,
                "match_score": analysis.match_score,
                "risk_score": analysis.risk_score,
                "recommendation_level": analysis.recommendation_level,
                "summary": analysis.summary,
                "action_suggestion": analysis.action_suggestion,
            }

        return {"success": True, "data": data}
    finally:
        db.close()


@router.patch("/{job_id}")
async def update_job(job_id: int, req: JobUpdateRequest):
    """更新岗位状态"""
    db = get_db()
    try:
        updates = {k: v for k, v in req.model_dump().items() if v is not None}
        job = db.update_job(job_id, **updates)
        if not job:
            raise HTTPException(status_code=404, detail="岗位不存在")
        return {"success": True, "data": _job_to_dict(job)}
    finally:
        db.close()


@router.delete("/{job_id}")
async def delete_job(job_id: int):
    """删除岗位"""
    db = get_db()
    try:
        from src.storage.models import Job
        job = db.get_job_by_id(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="岗位不存在")
        db.session.delete(job)
        db.session.commit()
        return {"success": True, "message": "已删除"}
    except HTTPException:
        raise
    except Exception as e:
        db.session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()
