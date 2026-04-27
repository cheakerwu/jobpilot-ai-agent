"""
分析器单元测试
"""
import pytest
from src.analyzer.rule_based import RuleBasedAnalyzer
from src.analyzer.hybrid import HybridJobAnalyzer


def make_job(**kwargs):
    base = {
        "title": "Python后端工程师",
        "company": "示例公司",
        "city": "上海",
        "salary": "15-25K",
        "description": "需要 Python FastAPI Redis Docker 经验",
        "requirements": "",
    }
    base.update(kwargs)
    return base


def make_profile(**kwargs):
    base = {
        "skills": ["Python", "FastAPI", "Redis"],
        "filter_preferences": {
            "cities": ["上海", "北京"],
            "salary_min": 10000,
            "salary_max": 30000,
        },
    }
    base.update(kwargs)
    return base


def make_evidence():
    return [
        {
            "id": 1,
            "type": "project",
            "title": "求职助手系统",
            "content": "使用 FastAPI 和 Redis 实现的项目",
            "skill_tags": ["Python", "FastAPI", "Redis"],
            "confidence": 0.95,
        }
    ]


def test_rule_analyzer_returns_result():
    analyzer = RuleBasedAnalyzer()
    result = analyzer.analyze(make_job(), make_profile(), make_evidence())
    assert result is not None
    assert 0 <= result.match_score <= 100
    assert 0 <= result.risk_score <= 100
    assert result.recommendation_level in ("A", "B", "C", "D")


def test_rule_analyzer_high_match():
    analyzer = RuleBasedAnalyzer()
    result = analyzer.analyze(make_job(), make_profile(), make_evidence())
    assert result.match_score > 50
    assert result.recommendation_level in ("A", "B")


def test_rule_analyzer_low_match_no_skills():
    analyzer = RuleBasedAnalyzer()
    profile = make_profile(skills=[])
    result = analyzer.analyze(make_job(), profile, [])
    assert result.recommendation_level in ("C", "D")


def test_rule_analyzer_city_mismatch():
    analyzer = RuleBasedAnalyzer()
    job = make_job(city="成都")
    profile = make_profile()
    result = analyzer.analyze(job, profile, [])
    gaps_reqs = [g["requirement"] for g in result.gaps]
    assert any("城市" in r for r in gaps_reqs)


def test_rule_analyzer_matched_evidence_populated():
    analyzer = RuleBasedAnalyzer()
    result = analyzer.analyze(make_job(), make_profile(), make_evidence())
    assert len(result.matched_evidence) > 0


def test_hybrid_falls_back_to_rule_when_llm_fails():
    class FailingLLM:
        def generate(self, prompt):
            raise UnicodeEncodeError("gbk", "⚠", 0, 1, "illegal multibyte sequence")

    analyzer = HybridJobAnalyzer(FailingLLM())
    result = analyzer.analyze(make_job(), make_profile(), make_evidence())
    assert result.analyzer_type == "rule_fallback"
    assert result.match_score > 50
    assert "LLM 分析失败" not in result.summary
    assert "规则评分" in result.summary


def test_hybrid_fallback_explains_timeout_reason():
    class TimeoutLLM:
        def generate(self, prompt):
            raise TimeoutError("Read timed out")

    analyzer = HybridJobAnalyzer(TimeoutLLM())
    result = analyzer.analyze(make_job(), make_profile(), make_evidence())
    assert result.analyzer_type == "rule_fallback"
    assert "模型接口响应超时" in result.summary


def test_hybrid_fallback_explains_free_tier_limit():
    class QuotaLLM:
        def generate(self, prompt):
            raise RuntimeError("AllocationQuota.FreeTierOnly: The free tier of the model has been exhausted")

    analyzer = HybridJobAnalyzer(QuotaLLM())
    result = analyzer.analyze(make_job(), make_profile(), make_evidence())
    assert result.analyzer_type == "rule_fallback"
    assert "免费额度已耗尽" in result.summary


def test_rule_analyzer_uses_evidence_friendly_wording():
    analyzer = RuleBasedAnalyzer()
    profile = make_profile(skills=[])
    result = analyzer.analyze(make_job(), profile, [])
    text = result.action_suggestion + " ".join(g["suggestion"] for g in result.gaps)
    assert "能力不足" not in text
    assert "补充证据" in text or "证据库" in text
