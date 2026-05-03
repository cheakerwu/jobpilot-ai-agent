"""
轻量统计 API。
"""
from fastapi import APIRouter, Depends
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from src.auth.dependencies import get_current_user
from src.helpers import load_config
from src.storage.database import DatabaseManager
from src.storage.models import User
from web_api.routers.kanban import VALID_STATUSES

router = APIRouter()


def get_db():
    config = load_config()
    return DatabaseManager(config['storage']['db_path'])


def build_stats_summary(jobs) -> dict:
    by_status = {status: 0 for status in VALID_STATUSES}
    top_match_score = None

    for job in jobs:
        status = job.status if job.status in by_status else "new"
        by_status[status] += 1
        if job.match_score is not None:
            top_match_score = job.match_score if top_match_score is None else max(top_match_score, job.match_score)

    return {
        "total_jobs": len(jobs),
        "by_status": by_status,
        "top_match_score": top_match_score,
        "total_applied": by_status.get("applied", 0),
        "total_interviewing": by_status.get("interviewing", 0),
        "total_offers": by_status.get("offer", 0),
        "total_analyzed": sum(
            by_status.get(status, 0)
            for status in ("analyzed", "recommended", "resume_generated", "to_apply", "applied", "screening", "interviewing", "offer")
        ),
    }


@router.get("/summary")
async def stats_summary(current_user: User = Depends(get_current_user)):
    """返回看板顶部需要的轻量统计。"""
    db = get_db()
    try:
        jobs = db.get_all_jobs(user_id=current_user.id)
        return {
            "success": True,
            "data": build_stats_summary(jobs),
        }
    finally:
        db.close()
