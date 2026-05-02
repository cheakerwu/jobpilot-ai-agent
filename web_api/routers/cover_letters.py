"""
求职信 API
"""
import sys
import os
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

from src.storage.database import DatabaseManager
from src.helpers import load_config
from src.auth.dependencies import get_current_user
from src.storage.models import User
from web_api.routers._llm_utils import check_ai_trial, consume_ai_trial, AI_TRIAL_LIMIT

router = APIRouter()


def get_db():
    config = load_config()
    return DatabaseManager(config['storage']['db_path'])


def _cl_to_dict(cl) -> dict:
    def _parse(field):
        if not field:
            return []
        try:
            return json.loads(field)
        except Exception:
            return field

    return {
        "id": cl.id,
        "job_id": cl.job_id,
        "analysis_id": cl.analysis_id,
        "title": cl.title,
        "content": cl.content,
        "format": cl.format,
        "evidence_links": _parse(cl.evidence_links_json),
        "highlights": _parse(cl.highlights_json),
        "tone": cl.tone,
        "created_at": cl.created_at.isoformat() if cl.created_at else None,
    }


class GenerateCoverLetterRequest(BaseModel):
    job_id: int
    analysis_id: Optional[int] = None
    use_ai: bool = True


@router.post("/generate")
async def generate_cover_letter(req: GenerateCoverLetterRequest, current_user: User = Depends(get_current_user)):
    """为指定岗位生成求职信"""
    from web_api.routers._llm_utils import build_llm_provider, get_profile
    from src.cover_letter.generator import CoverLetterGenerator

    db = get_db()
    config = load_config()
    try:
        job = db.get_job_by_id(req.job_id)
        if not job:
            raise HTTPException(status_code=404, detail="岗位不存在")

        if req.use_ai:
            check_ai_trial(current_user)

        analysis_obj = (
            db.get_analysis_by_id(req.analysis_id)
            if req.analysis_id
            else db.get_analysis_by_job(req.job_id)
        )
        if not analysis_obj:
            raise HTTPException(status_code=400, detail="请先分析该岗位再生成求职信")

        analysis = {
            "match_score": analysis_obj.match_score,
            "recommendation_level": analysis_obj.recommendation_level,
            "matched_evidence": json.loads(analysis_obj.matched_evidence_json or "[]"),
            "gaps": json.loads(analysis_obj.gaps_json or "[]"),
        }

        evidence = [
            {"id": ev.id, "type": ev.type, "title": ev.title,
             "content": ev.content, "skill_tags": ev.get_skill_tags()}
            for ev in db.get_evidence_list(user_id=current_user.id)
        ]

        profile = get_profile(config)
        resume_cfg = config.get("resume", {})

        generator = None
        ai_used = False
        if req.use_ai:
            llm, _ = build_llm_provider(config)
            if llm:
                generator = CoverLetterGenerator(llm, resume_cfg)

        job_dict = {"title": job.title, "company": job.company, "city": job.city,
                    "salary": job.salary, "description": job.description or ""}

        if generator:
            gen_result = generator.generate(job_dict, analysis, evidence, profile)
            ai_used = True
        else:
            dummy = CoverLetterGenerator.__new__(CoverLetterGenerator)
            gen_result = dummy._fallback_generate(job_dict, analysis, evidence, profile)

        cl = db.save_cover_letter({
            "user_id": current_user.id,
            "job_id": req.job_id,
            "analysis_id": analysis_obj.id,
            "title": f"Cover Letter - {job.title} @ {job.company}",
            "content": gen_result.get("content", ""),
            "format": "markdown",
            "evidence_links_json": gen_result.get("evidence_links", []),
            "highlights_json": gen_result.get("highlights", []),
        })

        if not cl:
            raise HTTPException(status_code=500, detail="保存求职信失败")

        if ai_used:
            consume_ai_trial(current_user.id, db)
            current_user = db.get_user_by_id(current_user.id)

        return {"success": True, "data": _cl_to_dict(cl),
                "ai_usage_count": current_user.ai_usage_count or 0,
                "ai_trials_remaining": max(0, AI_TRIAL_LIMIT - (current_user.ai_usage_count or 0))}
    finally:
        db.close()


@router.get("/jobs/{job_id}")
async def get_job_cover_letters(job_id: int, current_user: User = Depends(get_current_user)):
    """获取某岗位的所有求职信"""
    db = get_db()
    try:
        job = db.get_job_by_id(job_id)
        if not job or job.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="岗位不存在")
        letters = db.get_cover_letters_by_job(job_id)
        return {"success": True, "data": [_cl_to_dict(cl) for cl in letters]}
    finally:
        db.close()


@router.get("/{cl_id}")
async def get_cover_letter(cl_id: int, current_user: User = Depends(get_current_user)):
    """获取求职信详情"""
    db = get_db()
    try:
        cl = db.get_cover_letter_by_id(cl_id)
        if not cl or cl.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="求职信不存在")
        return {"success": True, "data": _cl_to_dict(cl)}
    finally:
        db.close()
