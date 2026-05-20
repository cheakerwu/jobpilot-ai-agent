"""
岗位管理 API
"""
import csv
import io
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Literal, Optional

from web_api.deps import get_db
from src.auth.dependencies import get_current_user
from src.storage.models import User

router = APIRouter()


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


VALID_STATUSES = Literal[
    "new", "analyzed", "recommended", "resume_generated",
    "to_apply", "applied", "screening", "interviewing",
    "offer", "rejected", "archived",
]


class JobUpdateRequest(BaseModel):
    status: Optional[VALID_STATUSES] = None
    notes: Optional[str] = None


@router.get("")
async def list_jobs(
    page: int = 1,
    per_page: int = 20,
    status: Optional[str] = None,
    city: Optional[str] = None,
    q: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """获取岗位列表（分页，支持搜索和筛选）"""
    page = max(1, page)
    per_page = max(1, min(per_page, 100))
    db = get_db()
    try:
        jobs = db.get_jobs_paginated(page, per_page, status, city, user_id=current_user.id, q=q)
        total = db.get_jobs_count(status, city, user_id=current_user.id, q=q)
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
    q: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    return await list_jobs(page, per_page, status, city, q=q, current_user=current_user)


@router.get("/stats")
async def get_stats(current_user: User = Depends(get_current_user)):
    """获取岗位统计数据"""
    db = get_db()
    try:
        stats = db.get_statistics(user_id=current_user.id)
        return {"success": True, "data": stats}
    finally:
        db.close()


@router.get("/export")
async def export_jobs(
    format: str = "csv",
    current_user: User = Depends(get_current_user),
):
    """导出岗位数据（CSV 或 JSON）"""
    db = get_db()
    try:
        jobs = db.get_all_jobs(user_id=current_user.id)
        rows = []
        for j in jobs:
            rows.append({
                "id": j.id,
                "title": j.title or "",
                "company": j.company or "",
                "city": j.city or "",
                "salary": j.salary or "",
                "status": j.status or "",
                "match_score": j.match_score or "",
                "source": j.source or "",
                "url": j.url or "",
                "created_at": j.created_at.isoformat() if j.created_at else "",
            })

        if format == "json":
            import json
            content = json.dumps(rows, ensure_ascii=False, indent=2)
            return StreamingResponse(
                io.BytesIO(content.encode("utf-8")),
                media_type="application/json",
                headers={"Content-Disposition": "attachment; filename=jobs_export.json"},
            )

        # CSV
        output = io.StringIO()
        if rows:
            writer = csv.DictWriter(output, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode("utf-8-sig")),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=jobs_export.csv"},
        )
    finally:
        db.close()


@router.get("/{job_id}")
async def get_job(job_id: int, current_user: User = Depends(get_current_user)):
    """获取岗位详情（含最新分析结果）"""
    db = get_db()
    try:
        job = db.get_job_by_id(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="岗位不存在")

        if job.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权访问")

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
async def update_job(job_id: int, req: JobUpdateRequest, current_user: User = Depends(get_current_user)):
    """更新岗位状态"""
    db = get_db()
    try:
        job = db.get_job_by_id(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="岗位不存在")
        if job.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权访问")

        updates = {k: v for k, v in req.model_dump().items() if v is not None}
        job = db.update_job(job_id, **updates)
        if not job:
            raise HTTPException(status_code=404, detail="岗位不存在")
        return {"success": True, "data": _job_to_dict(job)}
    finally:
        db.close()


@router.delete("/{job_id}")
async def delete_job(job_id: int, current_user: User = Depends(get_current_user)):
    """删除岗位"""
    db = get_db()
    try:
        from src.storage.models import Job
        job = db.get_job_by_id(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="岗位不存在")
        if job.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权访问")
        db.session.delete(job)
        db.session.commit()
        return {"success": True, "message": "已删除"}
    except HTTPException:
        raise
    except Exception:
        db.session.rollback()
        raise HTTPException(status_code=500, detail="删除岗位失败")
    finally:
        db.close()
