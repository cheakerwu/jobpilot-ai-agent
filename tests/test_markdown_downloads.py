"""
Markdown download tests for generated artifacts.
"""
import json

import pytest
from fastapi import HTTPException

from src.storage.database import DatabaseManager
from web_api.routers import cover_letters, interview_prep, resume_versions
from web_api.routers._download_utils import build_filename, interview_prep_to_markdown


@pytest.fixture
def db(tmp_path):
    db_path = str(tmp_path / "test.db")
    manager = DatabaseManager(db_path)
    yield manager
    manager.close()


@pytest.fixture
def user(db):
    return db.create_user("download_user", "download@test.com", "hash")


def _add_job(db, user_id: int = 1):
    return db.add_job({
        "job_id": f"download_job_{user_id}",
        "user_id": user_id,
        "title": "Python 工程师",
        "company": "示例公司",
        "source": "manual",
    })


def test_build_filename_removes_unsafe_characters():
    filename = build_filename("resume", "A/B:C*D?", default="fallback")

    assert "/" not in filename
    assert ":" not in filename
    assert "*" not in filename
    assert filename.startswith("resume-")


@pytest.mark.asyncio
async def test_resume_version_download_returns_markdown(db, user, monkeypatch):
    job = _add_job(db, user.id)
    version = db.save_resume_version({
        "user_id": user.id,
        "job_id": job.id,
        "title": "Python 工程师 @ 示例公司",
        "content": "# 张三\n\n## 技能\nPython",
    })
    monkeypatch.setattr(resume_versions, "get_db", lambda: db)

    response = await resume_versions.download_resume_version(version.id, current_user=user)

    assert response.status_code == 200
    assert response.media_type == "text/markdown; charset=utf-8"
    assert response.body.decode("utf-8").startswith("# 张三")
    assert "filename*=" in response.headers["content-disposition"]


@pytest.mark.asyncio
async def test_cover_letter_download_returns_markdown(db, user, monkeypatch):
    job = _add_job(db, user.id)
    letter = db.save_cover_letter({
        "user_id": user.id,
        "job_id": job.id,
        "title": "Cover Letter - Python 工程师 @ 示例公司",
        "content": "# 求职信\n\n尊敬的招聘团队：",
    })
    monkeypatch.setattr(cover_letters, "get_db", lambda: db)

    response = await cover_letters.download_cover_letter(letter.id, current_user=user)

    assert response.status_code == 200
    assert "# 求职信" in response.body.decode("utf-8")
    assert "cover-letter" in response.headers["content-disposition"]


@pytest.mark.asyncio
async def test_interview_prep_download_builds_structured_markdown(db, user, monkeypatch):
    job = _add_job(db, user.id)
    prep = db.save_interview_prep({
        "user_id": user.id,
        "job_id": job.id,
        "title": "Python 工程师 @ 示例公司",
        "questions_json": [
            {
                "category": "技术",
                "question": "请介绍 FastAPI 项目经验。",
                "answer": "按项目背景、贡献和结果说明。",
                "evidence_refs": [1, 2],
            }
        ],
        "company_insights_json": {"tech_stack": "Python / FastAPI"},
        "preparation_tips_json": ["准备项目复盘"],
        "risk_areas_json": [{"area": "Docker", "suggestion": "准备诚实的学习计划"}],
    })
    monkeypatch.setattr(interview_prep, "get_db", lambda: db)

    response = await interview_prep.download_interview_prep(prep.id, current_user=user)
    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert "## 面试问题" in body
    assert "请介绍 FastAPI 项目经验" in body
    assert "证据引用" in body
    assert "Docker" in body


def test_interview_prep_to_markdown_handles_bad_json(db, user):
    job = _add_job(db, user.id)
    prep = db.save_interview_prep({
        "user_id": user.id,
        "job_id": job.id,
        "title": "空面试准备",
        "questions_json": "not-json",
        "company_insights_json": json.dumps({"culture": "务实"}, ensure_ascii=False),
    })

    markdown = interview_prep_to_markdown(prep)

    assert "空面试准备" in markdown
    assert "暂无面试问题" in markdown
    assert "务实" in markdown


@pytest.mark.asyncio
async def test_download_requires_owner(db, user, monkeypatch):
    other_user = db.create_user("other_download_user", "other_download@test.com", "hash")
    job = _add_job(db, user.id)
    version = db.save_resume_version({
        "user_id": user.id,
        "job_id": job.id,
        "title": "Private Resume",
        "content": "# Private",
    })
    monkeypatch.setattr(resume_versions, "get_db", lambda: db)

    with pytest.raises(HTTPException) as exc:
        await resume_versions.download_resume_version(version.id, current_user=other_user)

    assert exc.value.status_code == 404
