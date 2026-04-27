"""
手动粘贴 JD 数据源
"""
import uuid
from typing import Iterable
from .base import JobSource


class ManualJobSource(JobSource):
    name = "manual"

    def fetch(self, query: dict) -> Iterable[dict]:
        """query 即为单个岗位数据字典，直接返回"""
        yield query

    def normalize(self, raw: dict) -> dict:
        title = raw.get("title", "").strip()
        company = raw.get("company", "").strip()
        job_id = raw.get("job_id") or f"manual_{uuid.uuid4().hex[:12]}"

        description = raw.get("description", "").strip()
        requirements = raw.get("requirements", "").strip()
        # 如果只填了 description，自动补充 requirements
        if description and not requirements:
            requirements = description

        return {
            "job_id": job_id,
            "title": title,
            "company": company,
            "city": raw.get("city", "").strip(),
            "salary": raw.get("salary", "").strip(),
            "description": description,
            "requirements": requirements,
            "url": raw.get("url", "").strip(),
            "source": self.name,
            "platform": self.name,
            "status": "new",
        }
