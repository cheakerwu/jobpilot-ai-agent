"""
粘贴版 JD 文本解析。

这里复用 PDF JD 的轻量推断规则，同时补充粘贴文本里常见的标签字段、
岗位链接提取，以及岗位描述/任职要求的简单分段。
"""
from __future__ import annotations

import re

from src.parsers.pdf import (
    _infer_city,
    _infer_company,
    _infer_salary,
    _infer_title,
    normalize_text,
)


JD_FIELD_NAMES = (
    "title",
    "company",
    "city",
    "salary",
    "description",
    "requirements",
    "url",
)

TITLE_LABELS = ("职位", "职位名称", "岗位", "岗位名称", "招聘岗位")
COMPANY_LABELS = ("公司", "公司名称", "招聘方", "企业", "企业名称")
CITY_LABELS = ("城市", "地点", "工作地点", "办公地点", "工作城市")
SALARY_LABELS = ("薪资", "薪酬", "薪水", "薪资范围", "薪资待遇")

DESCRIPTION_HEADINGS = (
    "岗位职责",
    "工作职责",
    "职位描述",
    "岗位描述",
    "工作内容",
    "职责描述",
    "主要职责",
    "你将负责",
)
REQUIREMENT_HEADINGS = (
    "任职要求",
    "职位要求",
    "岗位要求",
    "任职资格",
    "资格要求",
    "能力要求",
    "我们希望你",
    "你需要具备",
    "基本要求",
)

URL_PATTERN = re.compile(r"https?://[^\s，。；;）)】\]>'\"]+", re.IGNORECASE)


def parse_jd_text(raw_text: str) -> dict:
    """
    从粘贴的 JD 原文中提取结构化字段。

    返回字段：
    {title, company, city, salary, description, requirements, url}
    """
    text = normalize_text(raw_text)
    if not text:
        return {field: "" for field in JD_FIELD_NAMES}

    lines = [line.strip(" -:：\t") for line in text.splitlines() if line.strip()]
    compact = "\n".join(lines)

    title = (
        _extract_labeled_field(lines, TITLE_LABELS)
        or _infer_title(lines, "pasted_jd.txt")
        or ""
    )
    company = (
        _extract_labeled_field(lines, COMPANY_LABELS)
        or _infer_company(lines)
        or ""
    )
    labeled_city = _extract_labeled_field(lines, CITY_LABELS)
    labeled_salary = _extract_labeled_field(lines, SALARY_LABELS)
    city_text = labeled_city or compact
    salary_text = labeled_salary or compact
    sections = _split_jd_sections(lines)

    description = sections.get("description") or compact
    requirements = sections.get("requirements") or description

    return {
        "title": _clean_value(title)[:200],
        "company": _clean_company(company)[:200],
        "city": (_infer_city(city_text) or _clean_value(labeled_city))[:50],
        "salary": (_infer_salary(salary_text) or _clean_value(labeled_salary))[:100],
        "description": description[:12000],
        "requirements": requirements[:12000],
        "url": _extract_url(text)[:500],
    }


def build_jd_confidence(parsed: dict) -> dict:
    """给前端展示每个字段是否由系统自动识别到。"""
    confidence = {}
    for field in JD_FIELD_NAMES:
        value = (parsed.get(field) or "").strip()
        if field == "company" and value == "未知公司":
            value = ""
        if field == "title" and value == "pasted_jd":
            value = ""
        confidence[field] = "auto_extracted" if value else "unrecognized"
    return confidence


def _extract_url(text: str) -> str:
    match = URL_PATTERN.search(text)
    if not match:
        return ""
    return match.group().rstrip(".,，。；;")


def _extract_labeled_field(lines: list[str], labels: tuple[str, ...]) -> str:
    label_pattern = "|".join(re.escape(label) for label in sorted(labels, key=len, reverse=True))
    pattern = re.compile(rf"^(?:【)?(?:{label_pattern})(?:】)?\s*[:：]\s*(.+)$", re.IGNORECASE)
    for line in lines[:30]:
        match = pattern.match(line.strip())
        if match:
            value = _clean_value(match.group(1))
            if value:
                return value
    return ""


def _split_jd_sections(lines: list[str]) -> dict[str, str]:
    sections: dict[str, list[str]] = {"description": [], "requirements": []}
    current: str | None = None

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        heading, rest = _match_jd_heading(line)
        if heading:
            current = heading
            if rest:
                sections[current].append(rest)
            continue
        if current:
            sections[current].append(line)

    return {
        key: "\n".join(value).strip()
        for key, value in sections.items()
        if "\n".join(value).strip()
    }


def _match_jd_heading(line: str) -> tuple[str | None, str]:
    stripped = line.strip()
    normalized = re.sub(r"[\s:：|｜/\\-]+", "", stripped).lower()

    for heading in DESCRIPTION_HEADINGS:
        if normalized == heading.lower():
            return "description", ""
        rest = _heading_inline_rest(stripped, heading)
        if rest is not None:
            return "description", rest

    for heading in REQUIREMENT_HEADINGS:
        if normalized == heading.lower():
            return "requirements", ""
        rest = _heading_inline_rest(stripped, heading)
        if rest is not None:
            return "requirements", rest

    return None, ""


def _heading_inline_rest(line: str, heading: str) -> str | None:
    pattern = re.compile(rf"^{re.escape(heading)}\s*[:：]\s*(.*)$", re.IGNORECASE)
    match = pattern.match(line)
    if match:
        return _clean_value(match.group(1))
    return None


def _clean_company(value: str) -> str:
    value = _clean_value(value)
    value = re.sub(r"^(公司|公司名称|招聘方|企业|企业名称)\s*[:：]\s*", "", value)
    return "" if value == "未知公司" else value


def _clean_value(value: str) -> str:
    value = normalize_text(value)
    value = value.strip(" -:：,，。；;")
    return re.sub(r"\s+", " ", value).strip()
