"""
基于证据库的定制简历生成器
"""
import json
import os
import time
from datetime import datetime
from .llm_providers import BaseLLMProvider
from .cache import PersistentCache


GENERATOR_PROMPT = """你是一位专业的简历生成助手。请根据以下岗位分析结果和候选人证据库，生成一份定制简历。

## 岗位信息
职位: {title}
公司: {company}
城市: {city}
薪资: {salary}

## 岗位分析结果
匹配分: {match_score}
推荐等级: {recommendation_level}
已匹配要求: {matched_requirements}
简历可补强项: {gaps}

## 候选人证据库
{evidence_text}

## 候选人基本信息
{profile_basic}

## 任务
请生成一份针对该岗位的定制简历，输出严格的 JSON，格式如下：
{{
  "content": "<Markdown格式的完整简历内容>",
  "evidence_links": [
    {{"evidence_id": <证据id>, "bullet_text": "<简历中的对应bullet>"}}
  ],
  "changed_sections": ["<修改的章节名>"],
  "risk_warnings": ["<风险提示，例如某点证据不足>"],
  "keyword_coverage": {{"<关键词>": true/false}}
}}

## 重要约束
1. 每个关键成就必须能追溯到证据库中的真实项目/经历
2. 不得创建新的公司、项目名称、职位、学历、证书
3. 允许优化表达方式、突出关键词、量化已有成果
4. 对证据不足的 JD 要求，放入 risk_warnings，不要在简历中编造
5. evidence_links 中的 evidence_id 必须是证据库中真实存在的 id"""


class ResumeGenerator:
    """基于证据库的定制简历生成器"""

    def __init__(self, llm_provider: BaseLLMProvider, config: dict = None):
        self.llm = llm_provider
        self.config = config or {}
        self.cache = PersistentCache() if self.config.get('cache_enabled', True) else None
        self.rate_limit = self.config.get('rate_limit', 10)
        self.daily_limit = self.config.get('daily_limit', 10)
        self._call_times: list[float] = []

    def generate(
        self,
        job: dict,
        analysis: dict,
        evidence: list[dict],
        profile: dict,
    ) -> dict:
        """
        生成定制简历版本。
        返回: {content, evidence_links, changed_sections, risk_warnings, keyword_coverage}
        """
        self._check_rate_limit()

        prompt = self._build_prompt(job, analysis, evidence, profile)
        try:
            raw = self.llm.generate(prompt)
            result = self._parse_json(raw)
            if result:
                return result
        except Exception as e:
            pass

        # 降级：生成基础简历
        return self._fallback_generate(job, analysis, evidence, profile)

    def _build_prompt(self, job: dict, analysis: dict, evidence: list[dict], profile: dict) -> str:
        matched = [ev.get("requirement", "") for ev in analysis.get("matched_evidence", [])]
        gaps = [g.get("requirement", "") for g in analysis.get("gaps", [])]

        ev_lines = []
        for ev in evidence[:12]:
            tags = ev.get("skill_tags", [])
            ev_lines.append(
                f"[id={ev.get('id')}][{ev.get('type')}] {ev.get('title')}"
                f" | 技能: {', '.join(tags)}"
                f"\n  {str(ev.get('content', ''))[:300]}"
            )

        basic = profile.get("basic_info", {})
        profile_basic = json.dumps(basic, ensure_ascii=False)

        return GENERATOR_PROMPT.format(
            title=job.get("title", ""),
            company=job.get("company", ""),
            city=job.get("city", ""),
            salary=job.get("salary", ""),
            match_score=analysis.get("match_score", 0),
            recommendation_level=analysis.get("recommendation_level", "C"),
            matched_requirements=", ".join(matched) or "无",
            gaps=", ".join(gaps) or "无",
            evidence_text="\n".join(ev_lines) or "（暂无证据）",
            profile_basic=profile_basic,
        )

    def _fallback_generate(
        self, job: dict, analysis: dict, evidence: list[dict], profile: dict
    ) -> dict:
        """LLM 失败时的规则降级简历"""
        basic = profile.get("basic_info", {})
        skills = profile.get("skills", [])
        matched = [ev.get("requirement", "") for ev in analysis.get("matched_evidence", [])]

        lines = [
            f"# {basic.get('name', '候选人')}",
            f"",
            f"**教育背景**: {basic.get('education', '')} | {basic.get('school', '')}",
            f"**联系方式**: {basic.get('email', '')} | {basic.get('phone', '')}",
            f"",
            f"## 技能",
            ", ".join(skills[:15]),
            f"",
            f"## 应聘岗位相关技能",
            ", ".join(matched) or "（基于分析结果生成）",
            f"",
        ]
        for ev in evidence:
            if ev.get("type") in ("project", "work_experience"):
                lines += [f"## {ev.get('title', '')}", ev.get("content", ""), ""]

        return {
            "content": "\n".join(lines),
            "evidence_links": [],
            "changed_sections": ["技能", "项目经历"],
            "risk_warnings": ["简历由规则降级生成，建议人工完善"],
            "keyword_coverage": {},
        }

    def _parse_json(self, text: str) -> dict | None:
        try:
            return json.loads(text)
        except Exception:
            pass
        import re
        m = re.search(r'\{[\s\S]*\}', text)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                pass
        return None

    def save_to_file(self, content: str, job_id: int, resume_dir: str = 'data/resumes') -> str | None:
        try:
            os.makedirs(resume_dir, exist_ok=True)
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            path = os.path.join(resume_dir, f"resume_job{job_id}_{ts}.md")
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            return path
        except Exception:
            return None

    def _check_rate_limit(self):
        if self.rate_limit is None:
            return
        now = time.time()
        self._call_times = [t for t in self._call_times if now - t < 60]
        if len(self._call_times) >= self.rate_limit:
            sleep_time = 60 - (now - self._call_times[0])
            if sleep_time > 0:
                time.sleep(sleep_time)
                self._call_times = []
        self._call_times.append(now)
