"""
分析 API 输出清洗测试
"""
from datetime import datetime
from types import SimpleNamespace

from web_api.routers.analyses import _analysis_to_dict


def make_analysis(**kwargs):
    base = {
        "id": 1,
        "job_id": 7,
        "match_score": 12,
        "risk_score": 15,
        "recommendation_level": "C",
        "summary": "JD 技能证据匹配 1/3 项。",
        "action_suggestion": "可作为备选机会，建议先补充证据或调整简历表达后再投递。",
        "matched_evidence_json": "[]",
        "gaps_json": "[]",
        "risks_json": "[]",
        "do_not_exaggerate_json": "[]",
        "parsed_jd_json": "{}",
        "analyzer_type": "hybrid",
        "created_at": datetime(2026, 4, 27, 10, 0, 0),
    }
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_analysis_to_dict_hides_persisted_llm_error():
    data = _analysis_to_dict(make_analysis(
        summary="LLM 分析失败: 'gbk' codec can't encode character '\\u26a0'",
        action_suggestion="建议先补充能力缺口再考虑投递",
    ))

    assert "LLM 分析失败" not in data["summary"]
    assert "codec can't encode" not in data["summary"]
    assert "能力缺口" not in data["action_suggestion"]
    assert data["analyzer_type"] == "rule_fallback"
    assert data["score_explanation"]["analyzer_type"] == "rule_fallback"


def test_analysis_to_dict_replaces_legacy_wording_recursively():
    data = _analysis_to_dict(make_analysis(
        summary="当前存在能力缺口。",
        action_suggestion="建议先补充能力后再投递。",
        gaps_json='[{"requirement": "Agent", "suggestion": "能力不足，建议补充能力缺口。"}]',
    ))

    rendered = str(data)
    assert "能力缺口" not in rendered
    assert "补充能力" not in rendered
    assert "能力不足" not in rendered
    assert "简历可补强项" in rendered
    assert "补充证据" in rendered
