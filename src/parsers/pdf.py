"""
PDF 文本抽取与简历/JD 轻量解析。

这里先使用规则解析作为稳定兜底：它不追求完美理解 PDF，但能把用户最常见的
PDF 简历和 PDF JD 转成系统可用的结构化数据。后续可以在这些函数外层接 LLM
增强解析，但核心导入链路不依赖模型。
"""
from __future__ import annotations

import io
import re
from collections import OrderedDict


COMMON_SKILLS = [
    "Python", "Java", "Go", "Rust", "C++", "C#", "JavaScript", "TypeScript",
    "FastAPI", "Django", "Flask", "Spring", "Node.js", "React", "Vue",
    "MySQL", "PostgreSQL", "MongoDB", "Redis", "SQLite", "SQLAlchemy",
    "Docker", "Kubernetes", "Linux", "Git", "CI/CD", "RESTful", "gRPC",
    "LangChain", "LangGraph", "LlamaIndex", "RAG", "LLM", "AI Agent",
    "Pandas", "NumPy", "PyTorch", "TensorFlow", "Spark", "Flink",
]


SECTION_ALIASES = OrderedDict([
    ("skill", ["专业技能", "技能", "技能栈", "技术栈", "skills"]),
    ("project", ["项目经历", "项目经验", "项目", "projects"]),
    ("work_experience", ["工作经历", "实习经历", "工作经验", "experience"]),
    ("education", ["教育经历", "教育背景", "education"]),
    ("achievement", ["奖项", "荣誉", "证书", "成果", "achievements"]),
])


SECTION_TITLES = {
    "skill": "PDF 简历 - 技能摘要",
    "project": "PDF 简历 - 项目经历",
    "work_experience": "PDF 简历 - 工作经历",
    "education": "PDF 简历 - 教育经历",
    "achievement": "PDF 简历 - 成果/证书",
}


CITY_NAMES = [
    "北京", "上海", "广州", "深圳", "杭州", "成都", "南京", "武汉", "西安",
    "苏州", "天津", "重庆", "长沙", "郑州", "合肥", "厦门", "青岛", "大连",
]


def extract_text_from_pdf(file_content: bytes) -> str:
    """从 PDF bytes 中抽取文本。"""
    if not file_content:
        return ""

    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("缺少 PDF 解析依赖 pypdf，请先安装 requirements.txt") from exc

    reader = PdfReader(io.BytesIO(file_content))
    pages = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            pages.append(text)
    return normalize_text("\n".join(pages))


def normalize_text(text: str) -> str:
    """清理 PDF 抽取文本中的空白和不可见字符。"""
    text = (text or "").replace("\x00", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def detect_skills(text: str) -> list[str]:
    """从文本中识别常见技能关键词，保持预定义顺序。"""
    lowered = text.lower()
    found = []
    for skill in COMMON_SKILLS:
        pattern = re.escape(skill.lower()).replace(r"\ ", r"\s+")
        if re.search(rf"(?<![a-z0-9+#.]){pattern}(?![a-z0-9+#.])", lowered):
            found.append(skill)
    return found


def parse_resume_text_to_evidence(text: str, filename: str = "resume.pdf") -> list[dict]:
    """
    将 PDF 简历文本拆成证据条目。

    返回值可直接传给 DatabaseManager.add_evidence。
    """
    text = normalize_text(text)
    if not text:
        return []

    skills = detect_skills(text)
    sections = _split_resume_sections(text)
    evidence = []

    if skills:
        evidence.append({
            "user_id": 1,
            "type": "skill",
            "title": "PDF 简历 - 技能摘要",
            "content": "从 PDF 简历中识别到的技能：" + "、".join(skills),
            "skill_tags": skills,
            "source": f"resume_pdf:{filename}",
            "confidence": 0.85,
        })

    for section_type, content in sections.items():
        content = content.strip()
        min_len = 8 if section_type in ("education", "achievement", "skill") else 20
        if len(content) < min_len:
            continue
        evidence.append({
            "user_id": 1,
            "type": section_type,
            "title": SECTION_TITLES.get(section_type, f"PDF 简历 - {section_type}"),
            "content": content[:6000],
            "skill_tags": detect_skills(content),
            "source": f"resume_pdf:{filename}",
            "confidence": 0.82,
        })

    evidence.append({
        "user_id": 1,
        "type": "portfolio",
        "title": f"PDF 简历全文 - {filename}",
        "content": text[:12000],
        "skill_tags": skills,
        "source": f"resume_pdf:{filename}",
        "confidence": 0.75,
    })

    return evidence


def infer_job_from_jd_text(text: str, filename: str = "jd.pdf") -> dict:
    """从 PDF JD 文本中推断岗位字段。"""
    text = normalize_text(text)
    lines = [line.strip(" -:：\t") for line in text.splitlines() if line.strip()]
    compact = "\n".join(lines)

    title = _infer_title(lines, filename)
    company = _infer_company(lines)
    city = _infer_city(compact)
    salary = _infer_salary(compact)

    return {
        "title": title,
        "company": company,
        "city": city,
        "salary": salary,
        "description": compact[:12000],
        "requirements": compact[:12000],
        "url": "",
        "source": "pdf_jd",
        "platform": "pdf_jd",
        "status": "new",
    }


def _split_resume_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current_type: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        heading_type = _match_section_heading(line)
        if heading_type:
            current_type = heading_type
            sections.setdefault(current_type, [])
            continue
        if current_type:
            sections.setdefault(current_type, []).append(line)

    return {key: "\n".join(value) for key, value in sections.items()}


def _match_section_heading(line: str) -> str | None:
    normalized = re.sub(r"[\s:：|｜/\\-]+", "", line).lower()
    if len(normalized) > 24:
        return None
    for section_type, aliases in SECTION_ALIASES.items():
        for alias in aliases:
            if normalized == alias.lower() or normalized.startswith(alias.lower()):
                return section_type
    return None


def _infer_title(lines: list[str], filename: str) -> str:
    title_keywords = [
        "工程师", "开发", "实习", "算法", "数据", "产品", "运营", "设计",
        "架构", "测试", "前端", "后端", "全栈", "Agent", "LLM",
    ]
    for line in lines[:12]:
        if 2 <= len(line) <= 80 and any(keyword.lower() in line.lower() for keyword in title_keywords):
            return line
    if lines:
        return lines[0][:80]
    return filename.rsplit(".", 1)[0] or "未命名岗位"


def _infer_company(lines: list[str]) -> str:
    company_keywords = ["公司", "科技", "集团", "有限", "股份", "Inc", "Ltd", "Corporation"]
    for line in lines[:20]:
        if 2 <= len(line) <= 80 and any(keyword.lower() in line.lower() for keyword in company_keywords):
            return line
    return "未知公司"


def _infer_city(text: str) -> str:
    for city in CITY_NAMES:
        if city in text:
            return city
    return ""


def _infer_salary(text: str) -> str:
    patterns = [
        r"\d+\s*[-~至到]\s*\d+\s*[kK]",
        r"\d+\s*[kK]\s*[-~至到]\s*\d+\s*[kK]",
        r"\d+\s*[-~至到]\s*\d+\s*万",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return re.sub(r"\s+", "", match.group())
    return ""
