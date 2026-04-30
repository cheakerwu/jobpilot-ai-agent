"""
面试准备生成测试
"""
import sys
import os
import json
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.interview.prep import InterviewPrepGenerator
from src.storage.database import DatabaseManager


@pytest.fixture
def db(tmp_path):
    db_path = str(tmp_path / "test.db")
    manager = DatabaseManager(db_path)
    yield manager
    manager.close()


def make_job(**kwargs):
    base = {"title": "Python工程师", "company": "示例公司", "city": "上海", "salary": "15-25K", "description": "负责后端开发"}
    base.update(kwargs)
    return base


def make_analysis(**kwargs):
    base = {
        "match_score": 75,
        "recommendation_level": "B",
        "matched_evidence": [
            {"requirement": "Python", "evidence_id": 1, "evidence_title": "Python项目"},
            {"requirement": "FastAPI", "evidence_id": 2, "evidence_title": "FastAPI项目"},
        ],
        "gaps": [{"requirement": "Docker", "suggestion": "补充容器化经验"}],
        "risks": [{"point": "缺乏大规模系统经验"}],
    }
    base.update(kwargs)
    return base


def make_evidence():
    return [
        {"id": 1, "type": "project", "title": "Python项目", "content": "使用Python开发", "skill_tags": ["Python"]},
        {"id": 2, "type": "project", "title": "FastAPI项目", "content": "使用FastAPI开发", "skill_tags": ["FastAPI"]},
    ]


def make_profile():
    return {"basic_info": {"name": "张三", "education": "本科"}}


def test_fallback_generate_returns_questions():
    generator = InterviewPrepGenerator.__new__(InterviewPrepGenerator)
    result = generator._fallback_generate(make_job(), make_analysis(), make_evidence(), make_profile())
    assert "questions" in result
    assert len(result["questions"]) >= 2
    assert all("category" in q for q in result["questions"])


def test_fallback_references_evidence():
    generator = InterviewPrepGenerator.__new__(InterviewPrepGenerator)
    result = generator._fallback_generate(make_job(), make_analysis(), make_evidence(), make_profile())
    refs = [r for q in result["questions"] for r in q.get("evidence_refs", [])]
    assert len(refs) > 0


def test_llm_failure_triggers_fallback():
    class FailingLLM:
        def generate(self, prompt):
            raise UnicodeEncodeError("gbk", "x", 0, 1, "err")
    gen = InterviewPrepGenerator(FailingLLM())
    result = gen.generate(make_job(), make_analysis(), make_evidence(), make_profile())
    assert "questions" in result
    assert len(result["questions"]) >= 2


def test_db_save_and_retrieve_prep(db):
    job = db.add_job({"job_id": "ip_001", "title": "T", "company": "C", "source": "manual"})
    prep = db.save_interview_prep({
        "job_id": job.id, "user_id": 1,
        "questions_json": [{"category": "tech", "question": "Q1", "answer": "A1", "evidence_refs": []}],
        "preparation_tips_json": ["tip1"],
        "risk_areas_json": [],
    })
    assert prep is not None
    fetched = db.get_interview_prep_by_id(prep.id)
    assert json.loads(fetched.questions_json)[0]["question"] == "Q1"
    preps = db.get_interview_preps_by_job(job.id)
    assert len(preps) == 1
