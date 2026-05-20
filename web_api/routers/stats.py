"""
轻量统计 API。
"""
from fastapi import APIRouter, Depends

from web_api.deps import get_db
from src.auth.dependencies import get_current_user
from src.storage.models import User
from web_api.routers.kanban import VALID_STATUSES

router = APIRouter()


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
    """返回看板顶部需要的轻量统计（SQL 聚合，不加载全表）。"""
    db = get_db()
    try:
        raw = db.get_job_stats(user_id=current_user.id)
        by_status = {status: raw["by_status"].get(status, 0) for status in VALID_STATUSES}
        return {
            "success": True,
            "data": {
                "total_jobs": raw["total"],
                "by_status": by_status,
                "top_match_score": raw["top_match_score"],
                "total_applied": by_status.get("applied", 0),
                "total_interviewing": by_status.get("interviewing", 0),
                "total_offers": by_status.get("offer", 0),
                "total_analyzed": sum(
                    by_status.get(status, 0)
                    for status in ("analyzed", "recommended", "resume_generated", "to_apply", "applied", "screening", "interviewing", "offer")
                ),
            },
        }
    finally:
        db.close()
