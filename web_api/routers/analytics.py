"""
数据分析 API — 薪资分析增强版
"""
from fastapi import APIRouter, Depends
from collections import defaultdict
from statistics import median, mean
import sys
import os
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from src.storage.database import DatabaseManager
from src.helpers import load_config, load_user_profile
from src.analyzer.rule_based import _parse_salary_range
from src.auth.dependencies import get_current_user
from src.storage.models import User

router = APIRouter()

SALARY_BUCKETS = [
    (0, 5000, "0-5K"),
    (5000, 10000, "5-10K"),
    (10000, 15000, "10-15K"),
    (15000, 20000, "15-20K"),
    (20000, 25000, "20-25K"),
    (25000, 30000, "25-30K"),
    (30000, 35000, "30-35K"),
    (35000, 40000, "35-40K"),
    (40000, 45000, "40-45K"),
    (45000, 50000, "45-50K"),
    (50000, float("inf"), "50K+"),
]


def _salary_midpoint(salary_str: str) -> int | None:
    result = _parse_salary_range(salary_str)
    if not result:
        return None
    low, high = result
    return (low + high) // 2


def _build_distribution(midpoints: list[int]) -> dict:
    bucket_labels = [label for _, _, label in SALARY_BUCKETS]
    counts = [0] * len(SALARY_BUCKETS)
    for mid in midpoints:
        for i, (lo, hi, _) in enumerate(SALARY_BUCKETS):
            if lo <= mid < hi:
                counts[i] += 1
                break
    return {"buckets": bucket_labels, "counts": counts}


def _group_stats(jobs_with_mid: list, group_field: str) -> dict:
    groups = defaultdict(list)
    for job, mid in jobs_with_mid:
        key = getattr(job, group_field, None) or "未知"
        groups[key].append(mid)
    result = {}
    for key, values in sorted(groups.items(), key=lambda x: -mean(x[1])):
        result[key] = {
            "avg": round(mean(values), 1),
            "min": min(values),
            "max": max(values),
            "count": len(values),
        }
    return result


@router.get("/salary")
async def salary_analysis(current_user: User = Depends(get_current_user)):
    """薪资分析：分布、分组对比、与个人期望对比"""
    config = load_config()
    db = DatabaseManager(config['storage']['db_path'])
    try:
        jobs = db.get_all_jobs(user_id=current_user.id)
        jobs_with_mid = []
        for job in jobs:
            mid = _salary_midpoint(job.salary)
            if mid is not None:
                jobs_with_mid.append((job, mid))

        midpoints = [mid for _, mid in jobs_with_mid]

        # Overall stats
        overall = {"avg": 0, "min": 0, "max": 0, "median": 0, "count": 0}
        if midpoints:
            overall = {
                "avg": round(mean(midpoints), 1),
                "min": min(midpoints),
                "max": max(midpoints),
                "median": round(median(midpoints), 1),
                "count": len(midpoints),
            }

        # Distribution histogram
        distribution = _build_distribution(midpoints)

        # Group by city / platform
        by_city = _group_stats(jobs_with_mid, "city")
        by_platform = _group_stats(jobs_with_mid, "platform")

        # vs expectation
        profile = load_user_profile(config.get("profile_path", "config/user_profile.json"))
        prefs = profile.get("filter_preferences", {})
        user_min = prefs.get("salary_min", 0)
        user_max = prefs.get("salary_max", 0)
        vs_expectation = {"user_min": user_min, "user_max": user_max,
                          "above_count": 0, "within_count": 0, "below_count": 0, "coverage_pct": 0}
        if user_min or user_max:
            for mid in midpoints:
                if user_max and mid > user_max:
                    vs_expectation["above_count"] += 1
                elif user_min and mid < user_min:
                    vs_expectation["below_count"] += 1
                else:
                    vs_expectation["within_count"] += 1
            total = len(midpoints) or 1
            vs_expectation["coverage_pct"] = round(vs_expectation["within_count"] / total * 100, 1)

        return {
            "success": True,
            "data": {
                "overall": overall,
                "distribution": distribution,
                "by_city": by_city,
                "by_platform": by_platform,
                "vs_expectation": vs_expectation,
            },
        }
    finally:
        db.close()
