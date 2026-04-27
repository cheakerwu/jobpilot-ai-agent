"""
规则驱动的岗位分析器
"""
import re
from .base import JobAnalyzerBase, AnalysisResult


def _parse_salary_range(salary_str: str) -> tuple[int, int] | None:
    if not salary_str:
        return None
    m = re.search(r'(\d+)[kK·\-\~]*[\-~至到](\d+)[kK]', salary_str)
    if not m:
        m = re.search(r'(\d+)-(\d+)[kK]', salary_str)
    if m:
        return int(m.group(1)) * 1000, int(m.group(2)) * 1000
    m = re.search(r'(\d+)[kK]', salary_str)
    if m:
        v = int(m.group(1)) * 1000
        return v, v
    return None


class RuleBasedAnalyzer(JobAnalyzerBase):
    """规则分析器：硬性条件 + 技能关键词匹配"""

    def analyze(self, job: dict, profile: dict, evidence: list[dict]) -> AnalysisResult:
        result = AnalysisResult(analyzer_type="rule")
        result.parsed_jd = self._parse_jd(job)

        # 收集所有证据技能标签
        evidence_skills = set()
        for ev in evidence:
            tags = ev.get("skill_tags", [])
            if isinstance(tags, list):
                evidence_skills.update(t.lower() for t in tags)
            elif isinstance(tags, str):
                import json
                try:
                    evidence_skills.update(t.lower() for t in json.loads(tags))
                except Exception:
                    pass

        user_skills = {s.lower() for s in profile.get("skills", [])}
        all_skills = evidence_skills | user_skills

        # 技能匹配
        jd_text = f"{job.get('title','')} {job.get('description','')} {job.get('requirements','')}".lower()
        required_skills = result.parsed_jd.get("required_skills", [])
        if not required_skills:
            required_skills = self._extract_skills_from_text(jd_text, list(all_skills))

        matched_skills = [s for s in required_skills if s.lower() in all_skills]
        missing_skills = [s for s in required_skills if s.lower() not in all_skills]

        skill_score = int(len(matched_skills) / max(len(required_skills), 1) * 70)

        # 硬性条件分
        hard_score = 0
        gaps = []

        pref = profile.get("filter_preferences", {})
        cities = pref.get("cities", [])
        job_city = job.get("city", "")
        if cities and job_city:
            if any(c in job_city for c in cities):
                hard_score += 10
            else:
                gaps.append({
                    "requirement": f"城市: {job_city}",
                    "severity": "medium",
                    "suggestion": f"该岗位在{job_city}，与当前偏好城市不同，可确认是否接受异地、远程或调整投递优先级。"
                })

        salary_range = _parse_salary_range(job.get("salary", ""))
        if salary_range:
            sal_min, sal_max = salary_range
            pref_min = pref.get("salary_min", 0)
            pref_max = pref.get("salary_max", 999999)
            if sal_max >= pref_min and sal_min <= pref_max:
                hard_score += 10
            elif sal_max < pref_min:
                gaps.append({
                    "requirement": f"薪资: {job.get('salary')}",
                    "severity": "high",
                    "suggestion": "薪资信息低于当前偏好，可结合福利、年终和成长空间后再判断投递优先级。"
                })

        for skill in missing_skills:
            gaps.append({
                "requirement": skill,
                "severity": "medium",
                "suggestion": f"当前证据库暂未体现 {skill}，可补充真实项目/经历，或在简历中更清晰地呈现已有相关经验。"
            })

        # 证据匹配
        matched_evidence = []
        for ev in evidence:
            ev_tags = ev.get("skill_tags", [])
            if isinstance(ev_tags, str):
                import json
                try:
                    ev_tags = json.loads(ev_tags)
                except Exception:
                    ev_tags = []
            for skill in matched_skills:
                if any(skill.lower() == t.lower() for t in ev_tags):
                    matched_evidence.append({
                        "requirement": skill,
                        "evidence_id": ev.get("id"),
                        "evidence_title": ev.get("title", ""),
                    })
                    break

        total_score = min(skill_score + hard_score, 100)

        # 风险分：待补充证据越多风险越高
        risk_score = min(len(missing_skills) * 10 + len(gaps) * 5, 100)

        # 推荐等级
        if total_score >= 75:
            level = "A"
        elif total_score >= 55:
            level = "B"
        elif total_score >= 35:
            level = "C"
        else:
            level = "D"

        # 不建议夸大的点
        do_not_exaggerate = [
            f"不要把 {s} 写成已熟练掌握，除非能补充真实项目证据。" for s in missing_skills[:3]
        ]

        result.match_score = total_score
        result.risk_score = risk_score
        result.recommendation_level = level
        result.matched_evidence = matched_evidence
        result.gaps = gaps
        result.risks = []
        result.do_not_exaggerate = do_not_exaggerate
        result.summary = (
            f"JD 技能证据匹配 {len(matched_skills)}/{max(len(required_skills), 1)} 项，"
            f"综合得分 {total_score}，推荐等级 {level}"
        )
        if level in ("A", "B"):
            result.action_suggestion = "建议投递，简历中优先突出已匹配证据和相关项目。"
        elif level == "C":
            result.action_suggestion = "可作为备选机会，建议先补充证据或调整简历表达后再投递。"
        else:
            result.action_suggestion = "建议降低投递优先级，优先选择与当前证据库匹配更充分的岗位。"
        return result

    def _parse_jd(self, job: dict) -> dict:
        text = f"{job.get('description','')} {job.get('requirements','')}".lower()
        return {
            "title": job.get("title", ""),
            "company": job.get("company", ""),
            "location": job.get("city", ""),
            "salary_range": job.get("salary", ""),
            "required_skills": self._extract_skills_from_text(text, []),
            "keywords": [],
        }

    def _extract_skills_from_text(self, text: str, known_skills: list[str]) -> list[str]:
        """从文本中提取技能关键词"""
        common_tech = [
            "python", "java", "go", "rust", "c++", "typescript", "javascript",
            "fastapi", "django", "flask", "spring", "node.js",
            "react", "vue", "angular",
            "mysql", "postgresql", "mongodb", "redis",
            "docker", "kubernetes", "linux",
            "langchain", "langgraph", "llm", "pytorch", "tensorflow",
            "ai agent", "fastapi", "sqlalchemy", "celery",
            "git", "ci/cd", "restful", "grpc",
        ]
        found = [s for s in common_tech if s in text]
        for skill in known_skills:
            if skill.lower() in text and skill not in found:
                found.append(skill.lower())
        return list(dict.fromkeys(found))  # deduplicate, preserve order
