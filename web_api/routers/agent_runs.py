"""
Agent 运行记录 API
"""
import sys
import os
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from fastapi import APIRouter, HTTPException, Depends
from src.storage.database import DatabaseManager
from src.helpers import load_config
from src.auth.dependencies import get_current_user
from src.storage.models import User

router = APIRouter()


def get_db():
    config = load_config()
    return DatabaseManager(config['storage']['db_path'])


def _run_to_dict(run) -> dict:
    return {
        "id": run.id,
        "job_id": run.job_id,
        "workflow_name": run.workflow_name,
        "status": run.status,
        "error_message": run.error_message,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
    }


def _step_to_dict(step) -> dict:
    def _parse(field):
        if not field:
            return None
        try:
            return json.loads(field)
        except Exception:
            return field

    return {
        "id": step.id,
        "step_name": step.step_name,
        "status": step.status,
        "output": _parse(step.output_json),
        "error_message": step.error_message,
        "started_at": step.started_at.isoformat() if step.started_at else None,
        "finished_at": step.finished_at.isoformat() if step.finished_at else None,
    }


@router.get("")
async def list_agent_runs(job_id: int = None, limit: int = 20, current_user: User = Depends(get_current_user)):
    """获取 Agent 运行列表"""
    db = get_db()
    try:
        runs = db.get_agent_runs(job_id=job_id, limit=limit, user_id=current_user.id)
        return {"success": True, "data": [_run_to_dict(r) for r in runs]}
    finally:
        db.close()


@router.get("/{run_id}")
async def get_agent_run(run_id: int, current_user: User = Depends(get_current_user)):
    """获取单次 Agent 运行详情"""
    db = get_db()
    try:
        run = db.get_agent_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="运行记录不存在")
        data = _run_to_dict(run)
        data["output"] = json.loads(run.output_json) if run.output_json else None
        return {"success": True, "data": data}
    finally:
        db.close()


@router.get("/{run_id}/steps")
async def get_agent_run_steps(run_id: int, current_user: User = Depends(get_current_user)):
    """获取 Agent 运行的所有步骤"""
    db = get_db()
    try:
        run = db.get_agent_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="运行记录不存在")
        return {"success": True, "data": [_step_to_dict(s) for s in run.steps]}
    finally:
        db.close()
