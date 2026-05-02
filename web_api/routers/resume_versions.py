"""
简历版本管理 API
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


def _rv_to_dict(rv) -> dict:
    def _parse(field):
        if not field:
            return []
        try:
            return json.loads(field)
        except Exception:
            return field

    return {
        "id": rv.id,
        "job_id": rv.job_id,
        "analysis_id": rv.analysis_id,
        "title": rv.title,
        "content": rv.content,
        "format": rv.format,
        "evidence_links": _parse(rv.evidence_links_json),
        "changed_sections": _parse(rv.changed_sections_json),
        "risk_warnings": _parse(rv.risk_warnings_json),
        "keyword_coverage": _parse(rv.keyword_coverage_json) if rv.keyword_coverage_json else {},
        "created_at": rv.created_at.isoformat() if rv.created_at else None,
    }


class GenerateResumeRequest(BaseModel):
    job_id: int
    analysis_id: Optional[int] = None
    use_ai: bool = True


@router.post("/generate")
async def generate_resume(req: GenerateResumeRequest, current_user: User = Depends(get_current_user)):
    """为指定岗位生成定制简历"""
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
            raise HTTPException(status_code=400, detail="请先分析该岗位再生成简历")

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

        profile_path = config.get("profile_path", "config/user_profile.json")
        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                profile = json.load(f)
        except Exception:
            profile = {}

        resume_cfg = config.get("resume", {})
        generator = None
        ai_used = False

        if req.use_ai:
            from src.resume.llm_providers import create_llm_provider
            api_key_env = {
                "claude": "ANTHROPIC_API_KEY",
                "openai": "OPENAI_API_KEY",
                "deepseek": "DEEPSEEK_API_KEY",
                "qwen": "DASHSCOPE_API_KEY",
            }
            provider_type = resume_cfg.get("provider", "qwen")
            api_key = os.environ.get(api_key_env.get(provider_type, ""), "")
            provider_cfg = {
                "model": resume_cfg.get("model", "qwen3.5-plus"),
                "max_tokens": resume_cfg.get("max_tokens", 2000),
                "request_timeout": resume_cfg.get("request_timeout", 90),
            }
            if "enable_thinking" in resume_cfg:
                provider_cfg["enable_thinking"] = resume_cfg["enable_thinking"]
            if "base_url" in resume_cfg:
                provider_cfg["base_url"] = resume_cfg["base_url"]

            from src.resume.generator import ResumeGenerator
            if api_key:
                try:
                    llm = create_llm_provider(provider_type, api_key, provider_cfg)
                    generator = ResumeGenerator(llm, resume_cfg)
                except Exception:
                    generator = None

        job_dict = {"title": job.title, "company": job.company, "city": job.city,
                    "salary": job.salary, "description": job.description or ""}

        if generator:
            gen_result = generator.generate(job_dict, analysis, evidence, profile)
            ai_used = True
        else:
            from src.resume.generator import ResumeGenerator as _RG
            dummy = _RG.__new__(_RG)
            gen_result = dummy._fallback_generate(job_dict, analysis, evidence, profile)

        rv = db.save_resume_version({
            "user_id": current_user.id,
            "job_id": req.job_id,
            "analysis_id": analysis_obj.id,
            "title": f"{job.title} @ {job.company}",
            "content": gen_result.get("content", ""),
            "format": "markdown",
            "evidence_links_json": gen_result.get("evidence_links", []),
            "changed_sections_json": gen_result.get("changed_sections", []),
            "risk_warnings_json": gen_result.get("risk_warnings", []),
            "keyword_coverage_json": gen_result.get("keyword_coverage", {}),
        })

        if not rv:
            raise HTTPException(status_code=500, detail="保存简历版本失败")

        if ai_used:
            consume_ai_trial(current_user.id, db)
            current_user = db.get_user_by_id(current_user.id)

        db.update_job(req.job_id, status="resume_generated")

        return {"success": True, "data": _rv_to_dict(rv),
                "ai_usage_count": current_user.ai_usage_count or 0,
                "ai_trials_remaining": max(0, AI_TRIAL_LIMIT - (current_user.ai_usage_count or 0))}
    finally:
        db.close()


@router.get("")
async def list_resume_versions(
    page: int = 1,
    per_page: int = 20,
    current_user: User = Depends(get_current_user),
):
    """获取所有简历版本（分页）"""
    page = max(1, page)
    per_page = max(1, min(per_page, 100))
    db = get_db()
    try:
        from src.storage.models import ResumeVersion
        from sqlalchemy import desc, func
        total = db.session.query(func.count(ResumeVersion.id)).filter(
            ResumeVersion.user_id == current_user.id
        ).scalar()
        versions = (
            db.session.query(ResumeVersion)
            .filter(ResumeVersion.user_id == current_user.id)
            .order_by(desc(ResumeVersion.created_at))
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        return {
            "success": True,
            "data": [_rv_to_dict(rv) for rv in versions],
            "total": total,
            "page": page,
            "per_page": per_page,
        }
    finally:
        db.close()


@router.get("/{version_id}")
async def get_resume_version(version_id: int, current_user: User = Depends(get_current_user)):
    """获取简历版本详情"""
    db = get_db()
    try:
        rv = db.get_resume_version_by_id(version_id)
        if not rv or rv.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="简历版本不存在")
        return {"success": True, "data": _rv_to_dict(rv)}
    finally:
        db.close()


@router.get("/jobs/{job_id}")
async def get_job_resume_versions(job_id: int, current_user: User = Depends(get_current_user)):
    """获取某岗位的所有简历版本"""
    db = get_db()
    try:
        job = db.get_job_by_id(job_id)
        if not job or job.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="岗位不存在")
        versions = db.get_resume_versions_by_job(job_id)
        return {"success": True, "data": [_rv_to_dict(rv) for rv in versions]}
    finally:
        db.close()
