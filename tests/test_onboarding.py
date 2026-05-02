"""
Onboarding status API tests.
"""
import json

import pytest

from src.storage.database import DatabaseManager
from src.auth.security import hash_password
from web_api.routers import onboarding


class NoCloseDB:
    def __init__(self, db):
        self._db = db

    def __getattr__(self, name):
        return getattr(self._db, name)

    def close(self):
        return None


@pytest.fixture
def db(tmp_path):
    db_path = str(tmp_path / "test.db")
    manager = DatabaseManager(db_path)
    yield manager
    manager.close()


@pytest.fixture
def user(db):
    return db.create_user("onboarding_user", "onboarding@test.com", hash_password("pass123"))


@pytest.mark.asyncio
async def test_onboarding_status_starts_with_evidence_step(db, user, monkeypatch):
    monkeypatch.setattr(onboarding, "get_db", lambda: NoCloseDB(db))

    response = await onboarding.get_onboarding_status(current_user=user)
    data = response["data"]

    assert response["success"] is True
    assert data["is_complete"] is False
    assert data["next_step"]["key"] == "evidence"
    assert [step["key"] for step in data["progress"]] == ["evidence", "jobs", "analysis", "resume"]


@pytest.mark.asyncio
async def test_onboarding_status_advances_through_workflow(db, user, monkeypatch):
    monkeypatch.setattr(onboarding, "get_db", lambda: NoCloseDB(db))

    db.add_evidence({
        "user_id": user.id,
        "type": "project",
        "title": "FastAPI 项目",
        "content": "负责后端接口开发",
        "skill_tags": ["Python", "FastAPI"],
    })
    response = await onboarding.get_onboarding_status(current_user=user)
    assert response["data"]["next_step"]["key"] == "jobs"

    job = db.add_job({
        "job_id": "onboarding_job_001",
        "user_id": user.id,
        "title": "Python 工程师",
        "company": "示例公司",
        "source": "manual",
    })
    response = await onboarding.get_onboarding_status(current_user=user)
    assert response["data"]["next_step"]["key"] == "analysis"

    analysis = db.save_analysis({
        "user_id": user.id,
        "job_id": job.id,
        "match_score": 80,
        "risk_score": 20,
        "recommendation_level": "B",
        "matched_evidence_json": json.dumps([], ensure_ascii=False),
        "gaps_json": json.dumps([], ensure_ascii=False),
    })
    response = await onboarding.get_onboarding_status(current_user=user)
    assert response["data"]["next_step"]["key"] == "resume"

    db.save_resume_version({
        "user_id": user.id,
        "job_id": job.id,
        "analysis_id": analysis.id,
        "title": "Python 工程师 @ 示例公司",
        "content": "# 简历",
    })
    response = await onboarding.get_onboarding_status(current_user=user)

    assert response["data"]["is_complete"] is True
    assert response["data"]["next_step"]["key"] == "review"
