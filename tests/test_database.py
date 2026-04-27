"""
数据库 CRUD 测试（使用内存 SQLite）
"""
import json
import pytest
from src.storage.database import DatabaseManager


@pytest.fixture
def db(tmp_path):
    db_path = str(tmp_path / "test.db")
    manager = DatabaseManager(db_path)
    yield manager
    manager.close()


def test_add_and_get_job(db):
    job = db.add_job({
        "job_id": "test_001",
        "title": "测试工程师",
        "company": "测试公司",
        "source": "manual",
    })
    assert job is not None
    assert job.id > 0
    fetched = db.get_job_by_id(job.id)
    assert fetched.title == "测试工程师"


def test_job_dedup(db):
    db.add_job({"job_id": "dup_001", "title": "A", "company": "B", "source": "manual"})
    existing = db.get_job_by_platform_id("dup_001")
    assert existing is not None


def test_add_evidence(db):
    item = db.add_evidence({
        "user_id": 1,
        "type": "skill",
        "title": "Python",
        "skill_tags": ["Python"],
        "confidence": 0.9,
    })
    assert item is not None
    assert item.get_skill_tags() == ["Python"]


def test_get_evidence_list(db):
    db.add_evidence({"user_id": 1, "type": "skill", "title": "Go", "skill_tags": ["Go"]})
    db.add_evidence({"user_id": 1, "type": "project", "title": "项目A", "skill_tags": []})
    all_items = db.get_evidence_list(user_id=1)
    assert len(all_items) == 2
    skills_only = db.get_evidence_list(user_id=1, type_filter="skill")
    assert len(skills_only) == 1


def test_save_analysis(db):
    job = db.add_job({"job_id": "ana_001", "title": "工程师", "company": "X", "source": "manual"})
    analysis = db.save_analysis({
        "job_id": job.id,
        "match_score": 80,
        "risk_score": 20,
        "recommendation_level": "A",
        "summary": "很匹配",
        "matched_evidence_json": [{"requirement": "Python"}],
        "gaps_json": [],
    })
    assert analysis is not None
    fetched = db.get_analysis_by_job(job.id)
    assert fetched.recommendation_level == "A"


def test_statistics(db):
    db.add_job({"job_id": "s001", "title": "A", "company": "B", "source": "manual", "status": "new"})
    db.add_job({"job_id": "s002", "title": "C", "company": "D", "source": "manual", "status": "analyzed"})
    stats = db.get_statistics()
    assert stats["total"] == 2
    assert stats["new"] == 1
    assert stats["analyzed"] == 1
