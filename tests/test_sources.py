"""
数据源单元测试
"""
import pytest
from src.sources.manual_source import ManualJobSource
from src.sources.csv_source import CsvJobSource


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
