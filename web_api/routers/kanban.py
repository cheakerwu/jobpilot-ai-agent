"""
求职进度看板 API
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from src.storage.database import DatabaseManager
from src.helpers import load_config
from src.auth.dependencies import get_current_user
from src.storage.models import User

router = APIRouter()

VALID_STATUSES = [
    "new", "analyzed", "recommended", "resume_generated",
    "to_apply", "applied", "screening", "interviewing",
    "offer", "rejected", "archived",
]


def get_db():
    config = load_config()
    return DatabaseManager(config['storage']['db_path'])


def _job_card_dict(j) -> dict:
    return {
        "id": j.id,
        "title": j.title,
        "company": j.company,
        "city": j.city,
        "salary": j.salary,
        "match_score": j.match_score,
        "status": j.status,
        "created_at": j.created_at.isoformat() if j.created_at else None,
    }


@router.get("/board")
async def kanban_board(current_user: User = Depends(get_current_user)):
    """返回所有岗位按状态分组，用于看板渲染"""
    db = get_db()
    try:
        jobs = db.get_all_jobs(user_id=current_user.id)
        board = {status: [] for status in VALID_STATUSES}
        for job in jobs:
            key = job.status if job.status in board else "new"
            board[key].append(_job_card_dict(job))
        return {"success": True, "data": board}
    finally:
        db.close()


class MoveJobRequest(BaseModel):
    new_status: str


@router.patch("/jobs/{job_id}/move")
async def move_job(job_id: int, req: MoveJobRequest, current_user: User = Depends(get_current_user)):
    """拖拽移动岗位到新状态列"""
    if req.new_status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"无效状态: {req.new_status}，可选: {VALID_STATUSES}")
    db = get_db()
    try:
        job = db.get_job_by_id(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="岗位不存在")
        if job.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权访问")

        job = db.update_job(job_id, status=req.new_status)
        if not job:
            raise HTTPException(status_code=404, detail="岗位不存在")
        return {"success": True, "data": _job_card_dict(job)}
    finally:
        db.close()
