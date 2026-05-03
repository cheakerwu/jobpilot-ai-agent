"""
看板 API 测试
"""
import sys
import os
import json
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.storage.database import DatabaseManager


@pytest.fixture
def db(tmp_path):
    db_path = str(tmp_path / "test.db")
    manager = DatabaseManager(db_path)
    yield manager
    manager.close()


def make_job(db, **overrides):
    from uuid import uuid4
    base = {
        "job_id": f"kb_{uuid4().hex[:6]}",
        "title": "工程师",
        "company": "测试公司",
        "source": "manual",
    }
    base.update(overrides)
    return db.add_job(base)


def test_kanban_board_returns_all_statuses(db):
    """board 应返回所有 11 个状态 key，即使为空"""
    jobs = db.get_all_jobs()
    board = {}
    from web_api.routers.kanban import VALID_STATUSES
    for status in VALID_STATUSES:
        board[status] = []
    for job in jobs:
        key = job.status if job.status in board else "new"
        board[key].append(job)
    assert len(board) == 11
    assert "new" in board
    assert "offer" in board
    assert "archived" in board


def test_kanban_board_groups_jobs_by_status(db):
    """不同状态的岗位应被正确分组"""
    make_job(db, status="new")
    make_job(db, status="applied")
    make_job(db, status="applied")
    make_job(db, status="interviewing")

    from web_api.routers.kanban import VALID_STATUSES
    jobs = db.get_all_jobs()
    board = {s: [] for s in VALID_STATUSES}
    for job in jobs:
        key = job.status if job.status in board else "new"
        board[key].append(job)

    assert len(board["new"]) == 1
    assert len(board["applied"]) == 2
    assert len(board["interviewing"]) == 1
    assert len(board["offer"]) == 0


def test_move_job_updates_status(db):
    """移动岗位应更新其状态"""
    job = make_job(db, status="new")
    updated = db.update_job(job.id, status="applied")
    assert updated is not None
    assert updated.status == "applied"


def test_move_job_invalid_status():
    """无效状态应被拒绝"""
    from web_api.routers.kanban import VALID_STATUSES
    assert "invalid_status" not in VALID_STATUSES


def test_move_job_nonexistent(db):
    """不存在的岗位应返回 None"""
    result = db.update_job(99999, status="applied")
    assert result is None


def test_stats_summary_counts_statuses_and_top_score(db):
    """统计摘要应包含看板横幅需要的核心数字"""
    make_job(db, status="new")
    make_job(db, status="applied", match_score=71)
    make_job(db, status="interviewing", match_score=88)
    make_job(db, status="offer", match_score=82)

    from web_api.routers.stats import build_stats_summary

    summary = build_stats_summary(db.get_all_jobs())
    assert summary["total_jobs"] == 4
    assert summary["by_status"]["applied"] == 1
    assert summary["total_applied"] == 1
    assert summary["total_interviewing"] == 1
    assert summary["total_offers"] == 1
    assert summary["top_match_score"] == 88
