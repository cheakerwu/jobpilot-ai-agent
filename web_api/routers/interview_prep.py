"""
面试准备 API
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
from web_api.routers._download_utils import build_filename, interview_prep_to_markdown, markdown_response

router = APIRouter()


def get_db():
    config = load_config()
    return DatabaseManager(config['storage']['db_path'])


def _prep_to_dict(prep) -> dict:
    def _parse(field):
        if not field:
            return []
        try:
            return json.loads(field)
        except Exception:
            return field

    return {
        "id": prep.id,
        "job_id": prep.job_id,
        "analysis_id": prep.analysis_id,
        "title": prep.title,
        "questions": _parse(prep.questions_json),
        "company_insights": _parse(prep.company_insights_json) if prep.company_insights_json else {},
        "preparation_tips": _parse(prep.preparation_tips_json),
        "risk_areas": _parse(prep.risk_areas_json),
        "created_at": prep.created_at.isoformat() if prep.created_at else None,
    }


class GeneratePrepRequest(BaseModel):
    job_id: int
    analysis_id: Optional[int] = None
    use_ai: bool = True


@router.post("/generate")
async def generate_interview_prep(req: GeneratePrepRequest, current_user: User = Depends(get_current_user)):
    """为指定岗位生成面试准备材料"""
    from web_api.routers._llm_utils import build_llm_provider, get_profile
    from src.interview.prep import InterviewPrepGenerator

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
            raise HTTPException(status_code=400, detail="请先分析该岗位再生成面试准备")

        analysis = {
            "match_score": analysis_obj.match_score,
            "recommendation_level": analysis_obj.recommendation_level,
            "matched_evidence": json.loads(analysis_obj.matched_evidence_json or "[]"),
            "gaps": json.loads(analysis_obj.gaps_json or "[]"),
            "risks": json.loads(analysis_obj.risks_json or "[]"),
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
                generator = InterviewPrepGenerator(llm, resume_cfg)

        job_dict = {"title": job.title, "company": job.company, "city": job.city,
                    "salary": job.salary, "description": job.description or ""}

        if generator:
            gen_result = generator.generate(job_dict, analysis, evidence, profile)
            ai_used = True
        else:
            dummy = InterviewPrepGenerator.__new__(InterviewPrepGenerator)
            gen_result = dummy._fallback_generate(job_dict, analysis, evidence, profile)

        prep = db.save_interview_prep({
            "user_id": current_user.id,
            "job_id": req.job_id,
            "analysis_id": analysis_obj.id,
            "title": f"{job.title} @ {job.company}",
            "questions_json": gen_result.get("questions", []),
            "company_insights_json": gen_result.get("company_insights", {}),
            "preparation_tips_json": gen_result.get("preparation_tips", []),
            "risk_areas_json": gen_result.get("risk_areas", []),
        })

        if not prep:
            raise HTTPException(status_code=500, detail="保存面试准备失败")

        if ai_used:
            consume_ai_trial(current_user.id, db)
            current_user = db.get_user_by_id(current_user.id)

        return {"success": True, "data": _prep_to_dict(prep),
                "ai_usage_count": current_user.ai_usage_count or 0,
                "ai_trials_remaining": max(0, AI_TRIAL_LIMIT - (current_user.ai_usage_count or 0))}
    finally:
        db.close()


@router.get("/jobs/{job_id}")
async def get_job_interview_preps(job_id: int, current_user: User = Depends(get_current_user)):
    """获取某岗位的所有面试准备"""
    db = get_db()
    try:
        job = db.get_job_by_id(job_id)
        if not job or job.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="岗位不存在")
        preps = db.get_interview_preps_by_job(job_id)
        return {"success": True, "data": [_prep_to_dict(p) for p in preps]}
    finally:
        db.close()


@router.get("/{prep_id}/download")
async def download_interview_prep(prep_id: int, current_user: User = Depends(get_current_user)):
    """下载面试准备 Markdown 文件"""
    db = get_db()
    try:
        prep = db.get_interview_prep_by_id(prep_id)
        if not prep or prep.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="面试准备不存在")
        filename = build_filename("interview-prep", prep.title or f"prep-{prep.id}")
        return markdown_response(interview_prep_to_markdown(prep), filename)
    finally:
        db.close()


@router.get("/{prep_id}")
async def get_interview_prep(prep_id: int, current_user: User = Depends(get_current_user)):
    """获取面试准备详情"""
    db = get_db()
    try:
        prep = db.get_interview_prep_by_id(prep_id)
        if not prep or prep.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="面试准备不存在")
        return {"success": True, "data": _prep_to_dict(prep)}
    finally:
        db.close()
