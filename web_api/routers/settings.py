"""
系统设置 API。
"""
import os
import sys
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from src.helpers import load_config
from src.auth.dependencies import get_current_user, require_admin
from src.storage.models import User

router = APIRouter()

CONFIG_PATH = Path("config/config.yaml")

PROVIDER_META = {
    "qwen": {
        "label": "Qwen / 阿里云百炼",
        "env_key": "DASHSCOPE_API_KEY",
        "models": [
            "qwen3.6-flash",
            "qwen3.6-plus",
            "qwen3.5-plus",
            "qwen-plus",
            "qwen-max",
            "qwen-turbo",
        ],
        "supports_thinking": True,
        "supports_base_url": True,
    },
    "claude": {
        "label": "Claude / Anthropic",
        "env_key": "ANTHROPIC_API_KEY",
        "models": [
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
        ],
        "supports_thinking": False,
        "supports_base_url": False,
    },
    "openai": {
        "label": "OpenAI / Compatible",
        "env_key": "OPENAI_API_KEY",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini"],
        "supports_thinking": False,
        "supports_base_url": True,
    },
    "deepseek": {
        "label": "DeepSeek",
        "env_key": "DEEPSEEK_API_KEY",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "supports_thinking": False,
        "supports_base_url": False,
    },
}


class ModelSettingsUpdate(BaseModel):
    provider: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    max_tokens: int | None = Field(2000, ge=256, le=32000)
    rate_limit: int | None = Field(10, ge=1, le=120)
    daily_limit: int | None = Field(10, ge=1, le=1000)
    cache_enabled: bool = True
    enable_thinking: bool = False
    base_url: str | None = ""

    def model_post_init(self, __context) -> None:
        if self.base_url and not self.base_url.startswith(("http://", "https://")):
            raise ValueError("base_url 必须以 http:// 或 https:// 开头")


def _provider_payload() -> list[dict]:
    providers = []
    for key, meta in PROVIDER_META.items():
        env_key = meta["env_key"]
        providers.append({
            "key": key,
            "label": meta["label"],
            "env_key": env_key,
            "api_key_configured": bool(os.getenv(env_key)),
            "models": meta["models"],
            "supports_thinking": meta["supports_thinking"],
            "supports_base_url": meta["supports_base_url"],
        })
    return providers


@router.get("/models")
async def get_model_settings(current_user: User = Depends(get_current_user)):
    """读取当前模型配置和可选 provider/model 列表。"""
    config = load_config()
    resume_cfg = config.get("resume", {})
    provider = resume_cfg.get("provider", "qwen")
    meta = PROVIDER_META.get(provider, {})
    env_key = meta.get("env_key", "")

    return {
        "success": True,
        "current": {
            "provider": provider,
            "model": resume_cfg.get("model", ""),
            "max_tokens": resume_cfg.get("max_tokens", 2000),
            "rate_limit": resume_cfg.get("rate_limit", 10),
            "daily_limit": resume_cfg.get("daily_limit", 10),
            "cache_enabled": resume_cfg.get("cache_enabled", True),
            "enable_thinking": resume_cfg.get("enable_thinking", False),
            "base_url": resume_cfg.get("base_url", ""),
            "env_key": env_key,
            "api_key_configured": bool(os.getenv(env_key)) if env_key else False,
        },
        "providers": _provider_payload(),
    }


@router.patch("/models")
async def update_model_settings(req: ModelSettingsUpdate, current_user: User = Depends(require_admin)):
    """更新模型配置。API Key 不通过该接口保存，只读取 .env。"""
    provider = req.provider.lower().strip()
    if provider not in PROVIDER_META:
        raise HTTPException(status_code=400, detail="不支持的模型提供商")

    config = load_config()
    resume_cfg = dict(config.get("resume", {}))
    meta = PROVIDER_META[provider]

    resume_cfg.update({
        "provider": provider,
        "model": req.model.strip(),
        "max_tokens": req.max_tokens,
        "rate_limit": req.rate_limit,
        "daily_limit": req.daily_limit,
        "cache_enabled": req.cache_enabled,
        "enable_thinking": req.enable_thinking if meta["supports_thinking"] else False,
    })

    if meta["supports_base_url"] and req.base_url:
        resume_cfg["base_url"] = req.base_url.strip()
    else:
        resume_cfg.pop("base_url", None)

    config["resume"] = resume_cfg
    try:
        with CONFIG_PATH.open("w", encoding="utf-8") as f:
            yaml.safe_dump(config, f, allow_unicode=True, sort_keys=False)
    except Exception:
        raise HTTPException(status_code=500, detail="保存配置失败，请检查服务器日志")

    return {
        "success": True,
        "message": "模型配置已保存",
        "current": (await get_model_settings())["current"],
    }
