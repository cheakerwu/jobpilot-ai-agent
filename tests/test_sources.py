"""
数据源单元测试
"""
import pytest
from src.sources.manual_source import ManualJobSource
from src.sources.csv_source import CsvJobSource
from src.sources.browser_capture_source import BrowserCaptureJobSource


def test_manual_source_normalize():
    source = ManualJobSource()
    raw = {"title": "后端工程师", "company": "测试公司", "city": "上海",
           "description": "负责后端开发"}
    result = source.normalize(raw)
    assert result["title"] == "后端工程师"
    assert result["company"] == "测试公司"
    assert result["source"] == "manual"
    assert result["status"] == "new"
    assert result["job_id"].startswith("manual_")


def test_manual_source_generates_job_id():
    source = ManualJobSource()
    r1 = source.normalize({"title": "A", "company": "B"})
    r2 = source.normalize({"title": "A", "company": "B"})
    assert r1["job_id"] != r2["job_id"]


def test_manual_source_copies_description_to_requirements():
    source = ManualJobSource()
    raw = {"title": "A", "company": "B", "description": "JD内容"}
    result = source.normalize(raw)
    assert result["requirements"] == "JD内容"


def test_csv_source_column_aliases():
    import io
    import pandas as pd

    df = pd.DataFrame([
        {"职位": "数据工程师", "公司": "ACME", "城市": "北京", "薪资": "20-30K"},
    ])
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    source = CsvJobSource()
    rows = list(source.fetch({"file_content": csv_bytes, "filename": "test.csv"}))
    assert len(rows) == 1
    assert rows[0]["title"] == "数据工程师"
    assert rows[0]["company"] == "ACME"


def test_csv_source_normalize():
    source = CsvJobSource()
    raw = {"title": "工程师", "company": "ABC", "description": "职责说明"}
    result = source.normalize(raw)
    assert result["source"] == "csv"
    assert result["job_id"].startswith("csv_")
    assert result["requirements"] == "职责说明"


def test_browser_capture_source_normalize_from_page_text():
    source = BrowserCaptureJobSource()
    raw = {
        "page_title": "Agent 应用工程师招聘_星河科技招聘-BOSS直聘",
        "page_url": "https://example.com/jobs/agent-engineer",
        "selected_text": """
        职位名称：Agent 应用工程师
        公司：星河科技
        工作地点：上海
        薪资：30-45K
        岗位职责：负责企业级 Agent 应用开发，建设工具调用和评测体系。
        任职要求：熟悉 Python、FastAPI、LLM 应用开发。
        """,
    }
    result = source.normalize(raw)
    assert result["title"] == "Agent 应用工程师"
    assert result["company"] == "星河科技"
    assert result["city"] == "上海"
    assert result["salary"] == "30-45K"
    assert result["url"] == "https://example.com/jobs/agent-engineer"
    assert result["source"] == "browser_capture"
    assert result["platform"] == "browser_capture"


def test_browser_capture_source_uses_supplied_job_id():
    source = BrowserCaptureJobSource()
    result = source.normalize({
        "job_id": "browser_capture_1_abc",
        "title": "后端工程师",
        "company": "测试公司",
        "page_text": "岗位职责：负责后端服务开发",
    })
    assert result["job_id"] == "browser_capture_1_abc"
    assert result["requirements"] == "负责后端服务开发"
