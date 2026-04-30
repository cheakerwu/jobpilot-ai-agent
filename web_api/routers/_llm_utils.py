"""
共享 LLM provider 构建工具，供各路由复用
"""
import os
import sys
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from src.helpers import load_config, load_user_profile
from src.resume.llm_providers import create_llm_provider

API_KEY_ENV_MAP = {
    "claude": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "qwen": "DASHSCOPE_API_KEY",
}


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
