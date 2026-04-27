"""
混合分析器：规则分析 + LLM 深度分析
"""
from .base import JobAnalyzerBase, AnalysisResult
from .rule_based import RuleBasedAnalyzer
from .llm_analyzer import LLMJobAnalyzer


def _friendly_llm_error(error: Exception) -> str:
    message = str(error).lower()
    if "timed out" in message or "read timeout" in message or "timeout" in message:
        return "模型接口响应超时"
    if "401" in message or "unauthorized" in message or "invalid api key" in message:
        return "API Key 校验未通过"
    if "404" in message or "model not found" in message or "does not exist" in message:
        return "模型名称或接口地址不匹配"
    if "free tier" in message or "freetieronly" in message:
        return "免费额度已耗尽或账号仅允许使用免费额度"
    if "429" in message or "rate limit" in message or "quota" in message:
        return "调用频率或额度受限"
    if "400" in message or "bad request" in message:
        return "模型请求参数未被服务接受"
    if "connection" in message or "network" in message:
        return "网络连接异常"
    return "模型调用失败"


class HybridJobAnalyzer(JobAnalyzerBase):
    """先做规则分析，再用 LLM 增强"""

    def __init__(self, llm_provider=None):
        self.rule_analyzer = RuleBasedAnalyzer()
        self.llm_analyzer = LLMJobAnalyzer(llm_provider) if llm_provider else None

    def analyze(self, job: dict, profile: dict, evidence: list[dict]) -> AnalysisResult:
        rule_result = self.rule_analyzer.analyze(job, profile, evidence)

        if self.llm_analyzer is None:
            rule_result.analyzer_type = "rule"
            return rule_result

        try:
            llm_result = self.llm_analyzer.analyze(job, profile, evidence)
            return self._merge(rule_result, llm_result)
        except Exception as e:
            reason = _friendly_llm_error(e)
            rule_result.summary += f"（LLM 暂不可用：{reason}，当前展示规则评分结果。）"
            rule_result.analyzer_type = "rule_fallback"
            return rule_result

    def _merge(self, rule: AnalysisResult, llm: AnalysisResult) -> AnalysisResult:
        """融合两个分析结果：LLM 为主，规则分为校验"""
        merged = AnalysisResult(analyzer_type="hybrid")

        # 分数：规则和 LLM 加权平均
        merged.match_score = int(rule.match_score * 0.3 + llm.match_score * 0.7)
        merged.risk_score = int(rule.risk_score * 0.3 + llm.risk_score * 0.7)

        # 推荐等级用 LLM 结果
        merged.recommendation_level = llm.recommendation_level
        merged.summary = llm.summary or rule.summary
        merged.action_suggestion = llm.action_suggestion or rule.action_suggestion

        # 合并证据匹配（去重）
        seen = set()
        for ev in llm.matched_evidence + rule.matched_evidence:
            key = ev.get("requirement", "")
            if key not in seen:
                seen.add(key)
                merged.matched_evidence.append(ev)

        # 合并简历可补强项（LLM 优先）
        seen_gaps = set()
        for gap in llm.gaps + rule.gaps:
            key = gap.get("requirement", "")
            if key not in seen_gaps:
                seen_gaps.add(key)
                merged.gaps.append(gap)

        merged.risks = llm.risks or rule.risks
        merged.do_not_exaggerate = llm.do_not_exaggerate or rule.do_not_exaggerate
        merged.parsed_jd = llm.parsed_jd or rule.parsed_jd

        return merged
