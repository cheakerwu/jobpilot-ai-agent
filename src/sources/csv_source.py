"""
CSV / Excel 岗位导入数据源
"""
import uuid
import io
from typing import Iterable
from .base import JobSource

# 标准列名映射：允许中英文列名
COLUMN_ALIASES = {
    "title": ["title", "职位", "职位名称", "岗位", "岗位名称", "job_title"],
    "company": ["company", "公司", "公司名称", "企业", "企业名称"],
    "city": ["city", "城市", "工作城市", "地点", "工作地点", "location"],
    "salary": ["salary", "薪资", "薪酬", "工资", "薪资范围"],
    "description": ["description", "描述", "职位描述", "岗位描述", "jd", "job_description"],
    "requirements": ["requirements", "要求", "任职要求", "招聘要求"],
    "url": ["url", "链接", "岗位链接", "职位链接"],
    "job_id": ["job_id", "岗位id", "id"],
}


def _find_col(columns: list[str], field: str) -> str | None:
    lower_cols = {c.lower().strip(): c for c in columns}
    for alias in COLUMN_ALIASES.get(field, []):
        if alias.lower() in lower_cols:
            return lower_cols[alias.lower()]
    return None


class CsvJobSource(JobSource):
    name = "csv"

    def fetch(self, query: dict) -> Iterable[dict]:
        """
        query 参数:
          - file_path: str  文件路径（csv 或 xlsx）
          - file_content: bytes  文件内容（与 file_path 二选一）
          - filename: str  文件名（用于判断格式）
        """
        import pandas as pd

        file_path = query.get("file_path")
        file_content = query.get("file_content")
        filename = query.get("filename", "")

        if file_path:
            ext = file_path.rsplit(".", 1)[-1].lower()
            if ext in ("xlsx", "xls"):
                df = pd.read_excel(file_path)
            else:
                df = pd.read_csv(file_path, encoding="utf-8-sig")
        elif file_content:
            ext = filename.rsplit(".", 1)[-1].lower() if filename else "csv"
            buf = io.BytesIO(file_content)
            if ext in ("xlsx", "xls"):
                df = pd.read_excel(buf)
            else:
                df = pd.read_csv(buf, encoding="utf-8-sig")
        else:
            return

        df.columns = [str(c).strip() for c in df.columns]
        columns = df.columns.tolist()

        col_map = {field: _find_col(columns, field) for field in COLUMN_ALIASES}

        for _, row in df.iterrows():
            def get(field: str) -> str:
                col = col_map.get(field)
                if col and col in row:
                    val = row[col]
                    return "" if (val != val) else str(val).strip()  # handle NaN
                return ""

            yield {
                "job_id": get("job_id"),
                "title": get("title"),
                "company": get("company"),
                "city": get("city"),
                "salary": get("salary"),
                "description": get("description"),
                "requirements": get("requirements"),
                "url": get("url"),
            }

    def normalize(self, raw: dict) -> dict:
        job_id = raw.get("job_id") or f"csv_{uuid.uuid4().hex[:12]}"
        description = raw.get("description", "").strip()
        requirements = raw.get("requirements", "").strip()
        if description and not requirements:
            requirements = description
        return {
            "job_id": job_id,
            "title": raw.get("title", "").strip(),
            "company": raw.get("company", "").strip(),
            "city": raw.get("city", "").strip(),
            "salary": raw.get("salary", "").strip(),
            "description": description,
            "requirements": requirements,
            "url": raw.get("url", "").strip(),
            "source": self.name,
            "platform": self.name,
            "status": "new",
        }
