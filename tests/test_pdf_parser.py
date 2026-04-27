from src.parsers.pdf import (
    detect_skills,
    infer_job_from_jd_text,
    parse_resume_text_to_evidence,
)


def test_detect_skills_from_text():
    skills = detect_skills("熟悉 Python、FastAPI、Redis 和 Docker，了解 LangGraph。")
    assert "Python" in skills
    assert "FastAPI" in skills
    assert "Redis" in skills
    assert "Docker" in skills
    assert "LangGraph" in skills


def test_parse_resume_text_to_evidence_creates_sections():
    text = """
张三
专业技能
Python FastAPI Redis Docker
项目经历
JobPilot 求职 Agent 系统，使用 FastAPI 和 SQLAlchemy 实现岗位池和证据库。
教育经历
某某大学 本科 计算机科学
"""
    evidence = parse_resume_text_to_evidence(text, "resume.pdf")
    types = {item["type"] for item in evidence}
    assert "skill" in types
    assert "project" in types
    assert "education" in types
    assert "portfolio" in types


def test_infer_job_from_jd_text():
    text = """
ACME科技有限公司
AI Agent后端工程师
工作地点：上海
薪资：20-35K
岗位职责：负责 Agent 应用后端开发，使用 Python、FastAPI、Redis。
"""
    job = infer_job_from_jd_text(text, "jd.pdf")
    assert job["title"] == "AI Agent后端工程师"
    assert job["company"] == "ACME科技有限公司"
    assert job["city"] == "上海"
    assert job["salary"] == "20-35K"
    assert "Agent 应用" in job["description"]
