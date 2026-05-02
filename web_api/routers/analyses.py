"""
岗位分析 API
"""
import sys
import os
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
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


STALE_LLM_ERROR_MARKERS = (
    "LLM 分析失败",
    "codec can't encode",
    "UnicodeEncodeError",
    "illegal multibyte sequence",
)

LEGACY_WORDING_REPLACEMENTS = {
    "补充能力缺口": "补充证据或调整简历表达",
    "能力缺口": "简历可补强项",
    "补充能力": "补充证据",
    "能力不足": "证据暂未充分体现",
}


def _has_stale_llm_error(text: str | None) -> bool:
    if not text:
        return False
    return any(marker in text for marker in STALE_LLM_ERROR_MARKERS)


def _replace_legacy_wording(text: str | None) -> str | None:
    if text is None:
        return None
    cleaned = text
    for old, new in LEGACY_WORDING_REPLACEMENTS.items():
        cleaned = cleaned.replace(old, new)
    return cleaned


def _sanitize_payload(value):
    if isinstance(value, str):
        return _replace_legacy_wording(value)
    if isinstance(value, list):
        return [_sanitize_payload(item) for item in value]
    if isinstance(value, dict):
        return {key: _sanitize_payload(item) for key, item in value.items()}
    return value


def _sanitize_analysis_text(
    summary: str | None,
    action_suggestion: str | None,
    analyzer_type: str | None,
) -> tuple[str | None, str | None, str | None]:
    if _has_stale_llm_error(summary) or _has_stale_llm_error(action_suggestion):
        return (
            "LLM 暂不可用，当前展示基于规则评分的历史结果。建议重新点击“分析”刷新结果。",
            "可作为备选机会，建议先补充证据或调整简历表达后再投递。",
            "rule_fallback",
        )

    return (
        _replace_legacy_wording(summary),
        _replace_legacy_wording(action_suggestion),
        analyzer_type,
    )


def _analysis_to_dict(a) -> dict:
    def _parse(field):
        if not field:
            return []
        try:
            return json.loads(field)
        except Exception:
            return field

    matched_evidence = _sanitize_payload(_parse(a.matched_evidence_json))
    gaps = _sanitize_payload(_parse(a.gaps_json))
    risks = _sanitize_payload(_parse(a.risks_json))
    do_not_exaggerate = _sanitize_payload(_parse(a.do_not_exaggerate_json))
    parsed_jd = _sanitize_payload(_parse(a.parsed_jd_json)) if a.parsed_jd_json else {}
    summary, action_suggestion, analyzer_type = _sanitize_analysis_text(
        a.summary,
        a.action_suggestion,
        a.analyzer_type,
    )

    return {
        "id": a.id,
        "job_id": a.job_id,
        "match_score": a.match_score,
        "risk_score": a.risk_score,
        "recommendation_level": a.recommendation_level,
        "summary": summary,
        "action_suggestion": action_suggestion,
        "matched_evidence": matched_evidence,
        "gaps": gaps,
        "risks": risks,
        "do_not_exaggerate": do_not_exaggerate,
        "parsed_jd": parsed_jd,
        "score_explanation": build_score_explanation(
            analyzer_type=analyzer_type,
            match_score=a.match_score,
            risk_score=a.risk_score,
            recommendation_level=a.recommendation_level,
            parsed_jd=parsed_jd if isinstance(parsed_jd, dict) else {},
            matched_evidence=matched_evidence if isinstance(matched_evidence, list) else [],
            gaps=gaps if isinstance(gaps, list) else [],
        ),
        "analyzer_type": analyzer_type,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


def build_score_explanation(
    analyzer_type: str | None,
    match_score: int | None,
    risk_score: int | None,
    recommendation_level: str | None,
    parsed_jd: dict,
    matched_evidence: list,
    gaps: list,
) -> dict:
    """生成前端可展示的评分机制说明。"""
    required_skills = parsed_jd.get("required_skills", []) if isinstance(parsed_jd, dict) else []
    skill_requirements = [str(item) for item in required_skills]
    matched_requirements = [
        str(item.get("requirement", ""))
        for item in matched_evidence
        if isinstance(item, dict) and item.get("requirement")
    ]
    missing_requirements = [
        str(item.get("requirement", ""))
        for item in gaps
        if isinstance(item, dict) and item.get("requirement")
    ]

    analyzer = analyzer_type or "rule"
    if analyzer == "hybrid":
        formula = "混合评分：规则评分占 30%，LLM 深度分析占 70%。规则部分关注 JD 关键词、城市和薪资；LLM 部分关注语义匹配、岗位风险和证据充分性。"
    elif analyzer == "llm":
        formula = "LLM 评分：模型基于 JD、用户技能和证据库综合判断匹配度，并输出风险和简历可补强项。"
    else:
        formula = "规则评分：JD 技能证据匹配最高 70 分，城市偏好最高 10 分，薪资区间最高 10 分；推荐等级为 A≥75、B≥55、C≥35、D<35。"

    return {
        "formula": formula,
        "analyzer_type": analyzer,
        "match_score": match_score,
        "risk_score": risk_score,
        "recommendation_level": recommendation_level,
        "skill_requirements": skill_requirements,
        "matched_requirements": matched_requirements,
        "missing_requirements": missing_requirements,
        "risk_rule": "风险分主要来自 JD 要求在当前简历/证据库中未充分体现、城市/薪资偏好差异和 LLM 识别到的投递风险；分数越高代表越需要优化表达或调整投递优先级。",
    }


def _build_analyzer(config: dict, db):
    """构建分析器（优先 LLM，失败降级到规则）"""
    from src.analyzer.hybrid import HybridJobAnalyzer
    from src.analyzer.rule_based import RuleBasedAnalyzer

    resume_cfg = config.get("resume", {})
    api_key_env = {
        "claude": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "qwen": "DASHSCOPE_API_KEY",
    }
    provider_type = resume_cfg.get("provider", "qwen")
    env_key = api_key_env.get(provider_type, "")
    api_key = os.environ.get(env_key, "")

    if api_key:
        from src.resume.llm_providers import create_llm_provider
        provider_cfg = {
            "model": resume_cfg.get("model", "qwen3.5-plus"),
            "max_tokens": resume_cfg.get("max_tokens", 2000),
            "request_timeout": resume_cfg.get("request_timeout", 90),
        }
        if "enable_thinking" in resume_cfg:
            provider_cfg["enable_thinking"] = resume_cfg["enable_thinking"]
        if "base_url" in resume_cfg:
            provider_cfg["base_url"] = resume_cfg["base_url"]
        try:
            llm = create_llm_provider(provider_type, api_key, provider_cfg)
            return HybridJobAnalyzer(llm)
        except Exception:
            pass

    return RuleBasedAnalyzer()


def _load_profile(config: dict) -> dict:
    profile_path = config.get("profile_path", "config/user_profile.json")
    try:
        with open(profile_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


@router.post("/jobs/{job_id}")
async def analyze_job(job_id: int, use_ai: bool = True, current_user: User = Depends(get_current_user)):
    """对单个岗位执行分析"""
    db = get_db()
    config = load_config()
    try:
        job = db.get_job_by_id(job_id)
        if not job or job.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="岗位不存在")

        if use_ai:
            check_ai_trial(current_user)

        profile = _load_profile(config)
        if use_ai:
            analyzer = _build_analyzer(config, db)
        else:
            from src.analyzer.rule_based import RuleBasedAnalyzer
            analyzer = RuleBasedAnalyzer()

        from src.agent.workflow import JobAnalysisWorkflow
        workflow = JobAnalysisWorkflow(db=db, analyzer=analyzer, profile=profile, user_id=current_user.id)
        result = workflow.run(job_id)

        if result.get("success"):
            analysis_data = result.get("analysis", {})
            analyzer_type = analysis_data.get("analyzer_type", "rule")
            if use_ai and analyzer_type not in ("rule", "rule_fallback"):
                consume_ai_trial(current_user.id, db)
                current_user = db.get_user_by_id(current_user.id)

            analysis_data["score_explanation"] = build_score_explanation(
                analyzer_type=analyzer_type,
                match_score=analysis_data.get("match_score"),
                risk_score=analysis_data.get("risk_score"),
                recommendation_level=analysis_data.get("recommendation_level"),
                parsed_jd=analysis_data.get("parsed_jd") or {},
                matched_evidence=analysis_data.get("matched_evidence") or [],
                gaps=analysis_data.get("gaps") or [],
            )
            return {"success": True, "data": analysis_data,
                    "run_id": result.get("run_id"),
                    "ai_usage_count": current_user.ai_usage_count or 0,
                    "ai_trials_remaining": max(0, AI_TRIAL_LIMIT - (current_user.ai_usage_count or 0))}
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "分析失败"))
    finally:
        db.close()


class BatchAnalyzeRequest(BaseModel):
    job_ids: list[int] = Field(..., min_length=1, max_length=20)
    use_ai: bool = True


def _run_batch_analysis(batch_run_id: int, job_ids: list[int], use_ai: bool, user_id: int):
    """后台执行批量分析任务"""
    db = get_db()
    config = load_config()
    try:
        profile = _load_profile(config)
        if use_ai:
            analyzer = _build_analyzer(config, db)
        else:
            from src.analyzer.rule_based import RuleBasedAnalyzer
            analyzer = RuleBasedAnalyzer()

        results = []
        for job_id in job_ids:
            job = db.get_job_by_id(job_id)
            if not job or job.user_id != user_id:
                results.append({"job_id": job_id, "success": False, "error": "岗位不存在"})
                continue
            from src.agent.workflow import JobAnalysisWorkflow
            workflow = JobAnalysisWorkflow(db=db, analyzer=analyzer, profile=profile, user_id=user_id)
            r = workflow.run(job_id)
            if use_ai and r.get("success"):
                analysis_data = r.get("analysis", {})
                at = analysis_data.get("analyzer_type", "rule")
                if at not in ("rule", "rule_fallback"):
                    consume_ai_trial(user_id, db)
            results.append({"job_id": job_id, "success": r.get("success"),
                             "run_id": r.get("run_id")})

        success_count = sum(1 for r in results if r.get("success"))
        db.update_agent_run(batch_run_id,
                            status="completed",
                            output_json=json.dumps({
                                "total": len(results),
                                "success_count": success_count,
                                "results": results,
                            }, ensure_ascii=False))
    except Exception as e:
        db.update_agent_run(batch_run_id,
                            status="failed",
                            error_message=str(e))
    finally:
        db.close()


@router.post("/batch")
async def batch_analyze(req: BatchAnalyzeRequest, background_tasks: BackgroundTasks, current_user: User = Depends(get_current_user)):
    """批量分析岗位（后台执行，立即返回 batch_run_id）"""
    db = get_db()

    if not req.job_ids:
        raise HTTPException(status_code=400, detail="job_ids 不能为空")

    job_ids = req.job_ids[:20]  # 限制单次批量

    if req.use_ai:
        check_ai_trial(current_user)

    # 创建 AgentRun 记录跟踪批次状态
    batch_run = db.create_agent_run({
        "user_id": current_user.id,
        "workflow_name": "batch_analyze",
        "status": "running",
        "input_json": json.dumps({"job_ids": job_ids, "use_ai": req.use_ai}, ensure_ascii=False),
    })
    db.close()

    # 后台执行分析
    background_tasks.add_task(_run_batch_analysis, batch_run.id, job_ids, req.use_ai, current_user.id)

    return {
        "success": True,
        "message": f"批量分析已启动，共 {len(job_ids)} 个岗位",
        "batch_run_id": batch_run.id,
        "total": len(job_ids),
    }


@router.get("/{analysis_id}")
async def get_analysis(analysis_id: int, current_user: User = Depends(get_current_user)):
    """获取分析结果"""
    db = get_db()
    try:
        a = db.get_analysis_by_id(analysis_id)
        if not a:
            raise HTTPException(status_code=404, detail="分析结果不存在")
        job = db.get_job_by_id(a.job_id)
        if not job or job.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="分析结果不存在")
        return {"success": True, "data": _analysis_to_dict(a)}
    finally:
        db.close()


@router.get("/jobs/{job_id}/latest")
async def get_job_analysis(job_id: int, current_user: User = Depends(get_current_user)):
    """获取岗位最新分析结果"""
    db = get_db()
    try:
        job = db.get_job_by_id(job_id)
        if not job or job.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="岗位不存在")
        a = db.get_analysis_by_job(job_id)
        if not a:
            raise HTTPException(status_code=404, detail="该岗位尚未分析")
        return {"success": True, "data": _analysis_to_dict(a)}
    finally:
        db.close()
