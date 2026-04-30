"""
薪资分析测试
"""
import sys
import os
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.analyzer.rule_based import _parse_salary_range
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
        "job_id": f"sa_{uuid4().hex[:6]}",
        "title": "工程师",
        "company": "测试公司",
        "source": "manual",
    }
    base.update(overrides)
    return db.add_job(base)


def test_parse_salary_range_handles_k_format():
    assert _parse_salary_range("15-25K") == (15000, 25000)
    assert _parse_salary_range("15K-25K") == (15000, 25000)


def test_parse_salary_range_handles_single_value():
    assert _parse_salary_range("20K") == (20000, 20000)


def test_parse_salary_range_returns_none_for_empty():
    assert _parse_salary_range("") is None
    assert _parse_salary_range(None) is None
    assert _parse_salary_range("面议") is None


def test_salary_endpoint_returns_overall_stats(db):
    make_job(db, salary="10-20K", city="上海")
    make_job(db, salary="20-30K", city="上海")
    make_job(db, salary="15-25K", city="深圳")

    from web_api.routers.analytics import _salary_midpoint, _build_distribution
    from statistics import mean, median

    jobs = db.get_all_jobs()
    mids = [_salary_midpoint(j.salary) for j in jobs]
    mids = [m for m in mids if m is not None]

    assert len(mids) == 3
    assert mean(mids) == pytest.approx((15000 + 25000 + 20000) / 3, abs=1)


def test_salary_endpoint_groups_by_city(db):
    make_job(db, salary="10-20K", city="上海")
    make_job(db, salary="20-30K", city="上海")
    make_job(db, salary="15-25K", city="深圳")

    from web_api.routers.analytics import _group_stats, _salary_midpoint
    jobs = db.get_all_jobs()
    mids = []
    for j in jobs:
        mid = _salary_midpoint(j.salary)
        if mid:
            mids.append((j, mid))

    by_city = _group_stats(mids, "city")
    assert "上海" in by_city
    assert by_city["上海"]["count"] == 2
    assert "深圳" in by_city
    assert by_city["深圳"]["count"] == 1


def test_salary_endpoint_vs_expectation(db):
    make_job(db, salary="5-10K")   # mid=7500
    make_job(db, salary="15-25K")  # mid=20000
    make_job(db, salary="30-40K")  # mid=35000

    from web_api.routers.analytics import _salary_midpoint
    jobs = db.get_all_jobs()
    mids = [_salary_midpoint(j.salary) for j in jobs]
    mids = [m for m in mids if m is not None]

    user_min, user_max = 10000, 25000
    above = sum(1 for m in mids if m > user_max)
    below = sum(1 for m in mids if m < user_min)
    within = sum(1 for m in mids if user_min <= m <= user_max)

    assert above == 1  # 35000
    assert below == 1  # 7500
    assert within == 1  # 20000
