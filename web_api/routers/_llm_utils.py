"""
共享 LLM provider 构建工具，供各路由复用
"""
import os

from fastapi import HTTPException
from src.helpers import load_config, load_user_profile
from src.resume.llm_providers import create_llm_provider
from src.storage.models import User

API_KEY_ENV_MAP = {
    "claude": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "qwen": "DASHSCOPE_API_KEY",
    "mimo": "MIMO_API_KEY",
}


def get_ai_limit(user: User, config: dict = None) -> int:
    """获取用户的 AI 配额上限。优先用户级，其次全局默认。"""
    if user.ai_quota is not None:
        return user.ai_quota
    if config is None:
        config = load_config()
    return config.get("ai_quota", {}).get("default_limit", 10)


def build_llm_provider(config: dict = None):
    """从配置构建 LLM provider。返回 (provider, config) 或 (None, config)。"""
    if config is None:
        config = load_config()
    resume_cfg = config.get("resume", {})
    provider_type = resume_cfg.get("provider", "qwen")
    env_key = API_KEY_ENV_MAP.get(provider_type, "")
    api_key = os.environ.get(env_key, "")
    if not api_key:
        return None, config
    provider_cfg = {
        "model": resume_cfg.get("model", "qwen-plus"),
        "max_tokens": resume_cfg.get("max_tokens", 2000),
        "request_timeout": resume_cfg.get("request_timeout", 90),
    }
    if "enable_thinking" in resume_cfg:
        provider_cfg["enable_thinking"] = resume_cfg["enable_thinking"]
    if "base_url" in resume_cfg:
        provider_cfg["base_url"] = resume_cfg["base_url"]
    try:
        return create_llm_provider(provider_type, api_key, provider_cfg), config
    except Exception:
        return None, config


def get_profile(config: dict = None) -> dict:
    """加载用户 profile"""
    if config is None:
        config = load_config()
    return load_user_profile(config.get("profile_path", "config/user_profile.json"))


def check_ai_trial(user: User, config: dict = None) -> None:
    """检查用户 AI 试用次数，超限则抛 403"""
    limit = get_ai_limit(user, config)
    if (user.ai_usage_count or 0) >= limit:
        raise HTTPException(
            status_code=403,
            detail=f"AI 试用次数已用完（上限 {limit} 次）。请联系管理员调整配额。"
        )


def consume_ai_trial(user_id: int, db) -> bool:
    """原子性扣减试用次数。返回是否成功（False 表示已用完）。"""
    config = load_config()
    user = db.get_user_by_id(user_id)
    if not user:
        return False
    limit = get_ai_limit(user, config)
    return db.try_consume_ai_trial(user_id, limit)
