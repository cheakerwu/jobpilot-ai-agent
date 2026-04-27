"""
持久化缓存系统
"""
import os
import json
import hashlib
from datetime import datetime, timedelta


class PersistentCache:
    """持久化缓存"""

    def __init__(self, cache_dir='data/cache', ttl_days=7):
        self.cache_dir = cache_dir
        self.ttl_days = ttl_days
        os.makedirs(cache_dir, exist_ok=True)

    def _get_cache_key(self, job_title, job_description):
        """生成缓存键"""
        # 确保参数是字符串类型
        job_title_str = str(job_title) if job_title is not None else ""
        job_description_str = str(job_description) if job_description is not None else ""
        content = f"{job_title_str}_{job_description_str}"
        return hashlib.md5(content.encode()).hexdigest()

    def _get_cache_path(self, cache_key):
        """获取缓存文件路径"""
        return os.path.join(self.cache_dir, f"{cache_key}.json")

    def get(self, job_title, job_description):
        """获取缓存"""
        cache_key = self._get_cache_key(job_title, job_description)
        cache_path = self._get_cache_path(cache_key)

        if not os.path.exists(cache_path):
            return None

        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 检查是否过期
            cached_time = datetime.fromisoformat(data['timestamp'])
            if datetime.now() - cached_time > timedelta(days=self.ttl_days):
                os.remove(cache_path)
                return None

            return data['content']
        except Exception:
            return None

    def set(self, job_title, job_description, content):
        """设置缓存"""
        cache_key = self._get_cache_key(job_title, job_description)
        cache_path = self._get_cache_path(cache_key)

        data = {
            'timestamp': datetime.now().isoformat(),
            'content': content
        }

        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
