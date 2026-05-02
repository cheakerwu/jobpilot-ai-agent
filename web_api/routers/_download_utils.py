"""
Markdown download helpers for generated artifacts.
"""
import json
import re
import unicodedata
from urllib.parse import quote

from fastapi import Response


def parse_json_field(value, default):
    """Parse a JSON-backed DB text field, returning a safe default on bad data."""
    if not value:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def _sanitize_filename_part(value: str, default: str = "jobpilot-export") -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", str(value or ""))
    cleaned = re.sub(r"\s+", "-", cleaned).strip(" .-_")
    return cleaned[:80] or default


def build_filename(*parts: object, default: str = "jobpilot-export") -> str:
    """Build a readable, filesystem-safe markdown filename stem."""
    cleaned_parts = [
        _sanitize_filename_part(str(part), "")
        for part in parts
        if str(part or "").strip()
    ]
    stem = "-".join(part for part in cleaned_parts if part).strip("-")
    return _sanitize_filename_part(stem, default)


def markdown_response(content: str, filename_stem: str) -> Response:
    """Return Markdown as an authenticated browser download."""
    filename_stem = _sanitize_filename_part(filename_stem)
    filename = f"{filename_stem}.md"
    fallback = unicodedata.normalize("NFKD", filename).encode("ascii", "ignore").decode("ascii")
    fallback = _sanitize_filename_part(fallback.removesuffix(".md"), "jobpilot-export") + ".md"
    body = (content or "").rstrip() + "\n"
    return Response(
        content=body,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{fallback}"; '
                f"filename*=UTF-8''{quote(filename)}"
            )
        },
    )


def interview_prep_to_markdown(prep) -> str:
    questions = parse_json_field(prep.questions_json, [])
    insights = parse_json_field(prep.company_insights_json, {})
    tips = parse_json_field(prep.preparation_tips_json, [])
    risks = parse_json_field(prep.risk_areas_json, [])

    lines = [f"# 面试准备 - {prep.title or f'#{prep.id}'}", ""]
    if prep.created_at:
        lines += [f"生成时间：{prep.created_at.isoformat()}", ""]

    if isinstance(insights, dict) and insights:
        lines += ["## 公司与岗位线索", ""]
        labels = {
            "culture": "文化与团队",
            "tech_stack": "技术栈",
            "interview_process": "面试流程",
        }
        for key, label in labels.items():
            value = insights.get(key)
            if value:
                lines += [f"- **{label}**：{value}"]
        lines.append("")

    lines += ["## 面试问题", ""]
    if questions:
        for index, question in enumerate(questions, start=1):
            category = question.get("category") or "通用"
            refs = question.get("evidence_refs") or []
            ref_text = "、".join(f"#{ref}" for ref in refs if ref is not None) or "无"
            lines += [
                f"### Q{index} · {category}",
                "",
                f"**问题**：{question.get('question', '')}",
                "",
                f"**回答思路**：{question.get('answer', '')}",
                "",
                f"**证据引用**：{ref_text}",
                "",
            ]
    else:
        lines += ["暂无面试问题。", ""]

    if tips:
        lines += ["## 准备建议", ""]
        lines += [f"- {tip}" for tip in tips]
        lines.append("")

    if risks:
        lines += ["## 风险领域", ""]
        for risk in risks:
            if isinstance(risk, dict):
                area = risk.get("area") or "待补强项"
                suggestion = risk.get("suggestion") or ""
                lines += [f"- **{area}**：{suggestion}"]
            else:
                lines += [f"- {risk}"]
        lines.append("")

    return "\n".join(lines)
