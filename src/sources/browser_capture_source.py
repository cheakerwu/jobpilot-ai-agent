"""
浏览器/网页采集岗位数据源。

用于承接浏览器插件、书签脚本或前端模拟采集传入的页面标题、链接、
选中文本和页面正文。它只处理用户主动提供的当前页面内容，不做后台爬取。
"""
from __future__ import annotations

import hashlib
import re
from typing import Iterable

from .base import JobSource
from src.parsers.jd_text import parse_jd_text
from src.parsers.pdf import normalize_text


class BrowserCaptureJobSource(JobSource):
    name = "browser_capture"

    def fetch(self, query: dict) -> Iterable[dict]:
        """query 即为一次用户主动采集的网页内容。"""
        yield query

    def normalize(self, raw: dict) -> dict:
        page_title = _clean_value(raw.get("page_title", ""))
        page_url = _clean_value(raw.get("page_url") or raw.get("url") or "")
        captured_text = _clean_capture_text(raw)
        parse_input = "\n".join(part for part in (page_title, captured_text, page_url) if part)
        parsed = parse_jd_text(parse_input) if parse_input else {}

        title = (
            _clean_value(raw.get("title", ""))
            or _clean_value(parsed.get("title", ""))
            or _infer_title_from_page_title(page_title)
        )
        company = (
            _clean_company(raw.get("company", ""))
            or _clean_company(parsed.get("company", ""))
            or _infer_company_from_page_title(page_title)
            or "未知公司"
        )
        city = _clean_value(raw.get("city", "")) or _clean_value(parsed.get("city", ""))
        salary = _clean_value(raw.get("salary", "")) or _clean_value(parsed.get("salary", ""))
        description = (
            _clean_value(raw.get("description", ""))
            or _clean_multiline(parsed.get("description", ""))
            or captured_text
            or page_title
        )
        requirements = (
            _clean_value(raw.get("requirements", ""))
            or _clean_multiline(parsed.get("requirements", ""))
            or description
        )
        url = page_url or _clean_value(parsed.get("url", ""))

        seed = url or f"{title}|{company}|{description[:4000]}"
        job_id = raw.get("job_id") or f"{self.name}_{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:12]}"

        return {
            "job_id": job_id,
            "title": title[:200],
            "company": company[:200],
            "city": city[:50],
            "salary": salary[:100],
            "description": description[:20000],
            "requirements": requirements[:20000],
            "url": url[:500],
            "source": self.name,
            "platform": self.name,
            "status": "new",
        }


def _clean_capture_text(raw: dict) -> str:
    selected_text = raw.get("selected_text") or ""
    page_text = raw.get("page_text") or raw.get("raw_text") or ""
    text = selected_text if selected_text.strip() else page_text
    return _clean_multiline(text)


def _infer_title_from_page_title(page_title: str) -> str:
    title = _clean_value(page_title)
    if not title:
        return ""

    match = re.match(r"(.{2,80}?)(?:招聘|职位|岗位)(?:[_｜|\-\s].*)?$", title)
    if match:
        return _clean_value(match.group(1))

    for separator in ("｜", "|", "_", "-", "—"):
        if separator in title:
            candidate = _clean_value(title.split(separator)[0])
            if 2 <= len(candidate) <= 80:
                return re.sub(r"(招聘|职位|岗位)$", "", candidate).strip()
    return title[:80]


def _infer_company_from_page_title(page_title: str) -> str:
    title = _clean_value(page_title)
    if not title:
        return ""

    patterns = (
        r"[_｜|\-\s]([^_｜|\-]{2,80}?)(?:招聘|公司招聘|官方招聘|校园招聘)",
        r"(.{2,80}?)(?:公司|集团|科技|股份|有限).*?(?:招聘|职位|岗位)",
    )
    for pattern in patterns:
        match = re.search(pattern, title)
        if match:
            return _clean_company(match.group(1))
    return ""


def _clean_company(value: str) -> str:
    value = _clean_value(value)
    if value in {"未知公司", "公司", "招聘方"}:
        return ""
    return re.sub(r"^(公司|公司名称|招聘方|企业|企业名称)\s*[:：]\s*", "", value).strip()


def _clean_multiline(value: str) -> str:
    value = normalize_text(value)
    lines = [line.strip(" -:：\t") for line in value.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def _clean_value(value: str) -> str:
    value = normalize_text(value)
    value = value.strip(" -:：,，。；;")
    return re.sub(r"\s+", " ", value).strip()
