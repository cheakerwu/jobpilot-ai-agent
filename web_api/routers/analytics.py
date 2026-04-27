"""
数据分析 API
"""
from fastapi import APIRouter
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from src.storage.database import DatabaseManager
from src.helpers import load_config

router = APIRouter()

@router.get("/salary")
async def salary_analysis():
    """薪资分析"""
    db = DatabaseManager(load_config()['storage']['db_path'])
    try:
        jobs = db.get_all_jobs()
        # 简单统计
        salaries = []
        for job in jobs:
            if job.salary:
                # 解析薪资范围
                parts = job.salary.replace('K', '').split('-')
                if len(parts) == 2:
                    try:
                        avg = (int(parts[0]) + int(parts[1])) / 2
                        salaries.append(avg)
                    except:
                        pass

        return {
            "success": True,
            "data": {
                "avg": sum(salaries) / len(salaries) if salaries else 0,
                "min": min(salaries) if salaries else 0,
                "max": max(salaries) if salaries else 0,
                "distribution": salaries
            }
        }
    finally:
        db.close()
