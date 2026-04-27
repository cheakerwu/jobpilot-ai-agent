"""
岗位数据源抽象基类
"""
import uuid
from abc import ABC, abstractmethod
from typing import Iterable


class JobSource(ABC):
    name: str = "base"

    @abstractmethod
    def fetch(self, query: dict) -> Iterable[dict]:
        """从数据源获取原始岗位数据"""
        raise NotImplementedError

    def normalize(self, raw: dict) -> dict:
        """将原始数据转为内部岗位 schema，子类可覆盖"""
        return {
            "job_id": raw.get("job_id") or f"{self.name}_{uuid.uuid4().hex[:8]}",
            "title": raw.get("title", ""),
            "company": raw.get("company", ""),
            "city": raw.get("city", ""),
            "salary": raw.get("salary", ""),
            "description": raw.get("description", ""),
            "requirements": raw.get("requirements", ""),
            "url": raw.get("url", ""),
            "source": self.name,
            "platform": self.name,
            "status": "new",
        }

    def fetch_normalized(self, query: dict) -> Iterable[dict]:
        for raw in self.fetch(query):
            yield self.normalize(raw)
