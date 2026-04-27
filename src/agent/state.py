"""
Agent 状态定义
"""
from typing import TypedDict


class JobAgentState(TypedDict, total=False):
    user_id: int
    job_id: int
    job: dict
    profile: dict
    evidence: list[dict]
    parsed_jd: dict
    match_result: dict
    analysis: dict
    resume_version: dict | None
    interview_prep: dict | None
    errors: list[dict]
    steps: list[dict]
