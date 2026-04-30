"""
求职信生成测试
"""
import sys
import os
import json
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.cover_letter.generator import CoverLetterGenerator
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
    }
    base.update(kwargs)
    return base


def make_evidence():
    return [
        {"id": 1, "type": "project", "title": "Python项目", "content": "使用Python开发", "skill_tags": ["Python"]},
        {"id": 2, "type": "project", "title": "FastAPI项目", "content": "使用FastAPI开发", "skill_tags": ["FastAPI"]},
    ]


def make_profile():
    return {"basic_info": {"name": "张三", "education": "本科", "phone": "13800000000", "email": "test@test.com"}}


def test_fallback_generate_returns_content():
    generator = CoverLetterGenerator.__new__(CoverLetterGenerator)
    result = generator._fallback_generate(make_job(), make_analysis(), make_evidence(), make_profile())
    assert "content" in result
    assert len(result["content"]) > 100
    assert "evidence_links" in result
    assert "highlights" in result


def test_fallback_covers_matched_evidence():
    generator = CoverLetterGenerator.__new__(CoverLetterGenerator)
    result = generator._fallback_generate(make_job(), make_analysis(), make_evidence(), make_profile())
    assert len(result["evidence_links"]) > 0
    assert len(result["highlights"]) > 0


def test_llm_failure_triggers_fallback():
    class FailingLLM:
        def generate(self, prompt):
            raise TimeoutError("Read timed out")
    gen = CoverLetterGenerator(FailingLLM())
    result = gen.generate(make_job(), make_analysis(), make_evidence(), make_profile())
    assert "content" in result
    assert len(result["content"]) > 100


def test_db_save_and_retrieve_cover_letter(db):
    job = db.add_job({"job_id": "cl_001", "title": "T", "company": "C", "source": "manual"})
    cl = db.save_cover_letter({
        "job_id": job.id, "user_id": 1,
        "title": "Cover Letter - T @ C",
        "content": "Dear hiring team...",
        "evidence_links_json": [{"evidence_id": 1, "bullet_text": "Python"}],
        "highlights_json": ["Python", "FastAPI"],
    })
    assert cl is not None
    fetched = db.get_cover_letter_by_id(cl.id)
    assert json.loads(fetched.highlights_json)[0] == "Python"
    letters = db.get_cover_letters_by_job(job.id)
    assert len(letters) == 1
