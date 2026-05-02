"""
Onboarding status API for the app workspace.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from fastapi import APIRouter, Depends
from sqlalchemy import func

from src.auth.dependencies import get_current_user
from src.helpers import load_config
from src.storage.database import DatabaseManager
from src.storage.models import EvidenceItem, Job, JobAnalysis, ResumeVersion, User

router = APIRouter()


def get_db():
    config = load_config()
    return DatabaseManager(config['storage']['db_path'])


def _step(key: str, label: str, count: int, completed: bool) -> dict:
    return {
        "key": key,
        "label": label,
        "count": count,
        "completed": completed,
    }


def _next_step(progress: list[dict]) -> dict:
    actions = {
        "evidence": {
            "key": "evidence",
            "label": "补充证据",
            "description": "先准备可引用的经历材料",
            "action_page": "evidence",
            "action_label": "去证据库",
        },
        "jobs": {
            "key": "jobs",
            "label": "导入岗位",
            "description": "放入第一个 JD",
            "action_page": "import",
            "action_label": "去导入",
        },
        "analysis": {
            "key": "analysis",
            "label": "分析岗位",
            "description": "获得匹配分和风险提示",
            "action_page": "jobs",
            "action_label": "去岗位池",
        },
        "resume": {
            "key": "resume",
            "label": "生成简历",
            "description": "产出第一版定制简历",
            "action_page": "jobs",
            "action_label": "去生成",
        },
    }
    for item in progress:
        if not item["completed"]:
            return actions[item["key"]]
    return {
        "key": "review",
        "label": "继续推进",
        "description": "查看岗位池并推进投递状态",
        "action_page": "jobs",
        "action_label": "查看岗位",
    }


@router.get("/status")
async def get_onboarding_status(current_user: User = Depends(get_current_user)):
    """Return current user's setup progress and next suggested action."""
    db = get_db()
    try:
        user_id = current_user.id
        evidence_count = db.session.query(func.count(EvidenceItem.id)).filter(
            EvidenceItem.user_id == user_id
        ).scalar() or 0
        job_count = db.session.query(func.count(Job.id)).filter(
            Job.user_id == user_id
        ).scalar() or 0
        analysis_count = db.session.query(func.count(JobAnalysis.id)).filter(
            JobAnalysis.user_id == user_id
        ).scalar() or 0
        resume_count = db.session.query(func.count(ResumeVersion.id)).filter(
            ResumeVersion.user_id == user_id
        ).scalar() or 0

        progress = [
            _step("evidence", "证据", evidence_count, evidence_count > 0),
            _step("jobs", "岗位", job_count, job_count > 0),
            _step("analysis", "分析", analysis_count, analysis_count > 0),
            _step("resume", "简历", resume_count, resume_count > 0),
        ]
        is_complete = all(item["completed"] for item in progress)

        return {
            "success": True,
            "data": {
                "progress": progress,
                "next_step": _next_step(progress),
                "is_complete": is_complete,
                "counts": {
                    "evidence": evidence_count,
                    "jobs": job_count,
                    "analyses": analysis_count,
                    "resumes": resume_count,
                },
            },
        }
    finally:
        db.close()
