"""
系统设置 API。
"""
import os
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from src.helpers import load_config, invalidate_config_cache
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
    "mimo": {
        "label": "小米 MiMo",
        "env_key": "MIMO_API_KEY",
        "models": ["MiMo-v2.5-Pro", "MiMo-v2.5-Flash"],
        "supports_thinking": False,
        "supports_base_url": True,
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


def _mask_key(key: str) -> str:
    """掩码 API Key，只显示最后 4 位。"""
    if not key or len(key) < 8:
        return "****" if key else ""
    return f"****{key[-4:]}"


def _provider_payload() -> list[dict]:
    providers = []
    for key, meta in PROVIDER_META.items():
        env_key = meta["env_key"]
        raw_key = os.getenv(env_key, "")
        providers.append({
            "key": key,
            "label": meta["label"],
            "env_key": env_key,
            "api_key_configured": bool(raw_key),
            "api_key_masked": _mask_key(raw_key),
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
    raw_key = os.getenv(env_key, "") if env_key else ""

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
            "api_key_configured": bool(raw_key),
            "api_key_masked": _mask_key(raw_key),
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

    invalidate_config_cache()

    return {
        "success": True,
        "message": "模型配置已保存",
        "current": (await get_model_settings())["current"],
    }


@router.post("/models/test")
async def test_api_key(current_user: User = Depends(require_admin)):
    """验证当前配置的 API Key 是否可用（发送一个轻量请求）。"""
    from web_api.routers._llm_utils import build_llm_provider

    provider, config = build_llm_provider()
    if provider is None:
        return {"success": False, "message": "API Key 未配置或 provider 创建失败"}

    try:
        result = provider.generate("回复 OK 即可。")
        return {"success": True, "message": "API Key 验证通过", "response_preview": result[:100]}
    except Exception as e:
        import logging
        logging.getLogger("job_agent").error(f"API Key test failed: {e}")
        return {"success": False, "message": f"API Key 验证失败: {str(e)[:200]}"}


# ── AI 配额管理 ──────────────────────────────────────────────────────────────


class QuotaSettingsUpdate(BaseModel):
    default_limit: int = Field(..., ge=1, le=10000)
    reset_monthly: bool = False


class UserQuotaUpdate(BaseModel):
    ai_quota: int | None = Field(None, ge=1, le=10000)


@router.get("/ai-quota")
async def get_ai_quota(current_user: User = Depends(get_current_user)):
    """读取 AI 配额全局配置。"""
    config = load_config()
    quota_cfg = config.get("ai_quota", {})
    return {
        "success": True,
        "data": {
            "default_limit": quota_cfg.get("default_limit", 10),
            "reset_monthly": quota_cfg.get("reset_monthly", False),
        },
    }


@router.patch("/ai-quota")
async def update_ai_quota(req: QuotaSettingsUpdate, current_user: User = Depends(require_admin)):
    """管理员修改全局 AI 配额。"""
    config = load_config()
    config["ai_quota"] = {
        "default_limit": req.default_limit,
        "reset_monthly": req.reset_monthly,
    }
    try:
        with CONFIG_PATH.open("w", encoding="utf-8") as f:
            yaml.safe_dump(config, f, allow_unicode=True, sort_keys=False)
    except Exception:
        raise HTTPException(status_code=500, detail="保存配置失败")
    invalidate_config_cache()
    return {"success": True, "message": "配额配置已保存"}


@router.get("/users")
async def list_users(current_user: User = Depends(require_admin)):
    """管理员查看所有用户配额与使用情况。"""
    from web_api.deps import get_db
    config = load_config()
    default_limit = config.get("ai_quota", {}).get("default_limit", 10)
    db = get_db()
    try:
        users = db.get_all_users_summary()
        for u in users:
            u["ai_limit"] = u["ai_quota"] if u["ai_quota"] is not None else default_limit
            u["ai_remaining"] = max(0, u["ai_limit"] - u["ai_usage_count"])
        return {"success": True, "data": users, "default_limit": default_limit}
    finally:
        db.close()


@router.patch("/users/{user_id}/quota")
async def set_user_quota(user_id: int, req: UserQuotaUpdate, current_user: User = Depends(require_admin)):
    """管理员设置单个用户的 AI 配额（null = 恢复全局默认）。"""
    from web_api.deps import get_db
    db = get_db()
    try:
        user = db.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        db.update_user_quota(user_id, req.ai_quota)
        return {"success": True, "message": "配额已更新"}
    finally:
        db.close()


@router.post("/users/{user_id}/reset-usage")
async def reset_user_usage(user_id: int, current_user: User = Depends(require_admin)):
    """管理员重置用户的 AI 使用次数。"""
    from web_api.deps import get_db
    db = get_db()
    try:
        user = db.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="用户不存在")
        db.reset_user_ai_usage(user_id)
        return {"success": True, "message": "使用次数已重置"}
    finally:
        db.close()
