"""
岗位分析器抽象基类
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class AnalysisResult:
    match_score: int = 0           # 0-100
    risk_score: int = 0            # 0-100
    recommendation_level: str = "C"  # A/B/C/D
    summary: str = ""
    action_suggestion: str = ""
    matched_evidence: list = field(default_factory=list)
    # [{requirement, evidence_id, evidence_title}]
    gaps: list = field(default_factory=list)
    # [{requirement, severity, suggestion}]
    risks: list = field(default_factory=list)
    # [{point, severity}]
    do_not_exaggerate: list = field(default_factory=list)
    # [str]
    parsed_jd: dict = field(default_factory=dict)
    analyzer_type: str = "base"


class JobAnalyzerBase(ABC):

    @abstractmethod
    def analyze(self, job: dict, profile: dict, evidence: list[dict]) -> AnalysisResult:
        """对单个岗位进行分析，返回结构化结果"""
        raise NotImplementedError
