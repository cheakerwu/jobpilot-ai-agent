"""
认证路由：注册、登录、用户信息、修改密码
"""
import sys
import os
import time
from collections import defaultdict
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, EmailStr
from typing import Optional

from src.auth.security import hash_password, verify_password, create_access_token
from src.auth.dependencies import get_current_user
from src.storage.database import DatabaseManager
from src.storage.models import User
from src.helpers import load_config
from web_api.routers._llm_utils import AI_TRIAL_LIMIT

router = APIRouter()

# ── 简易内存限流器 ────────────────────────────────────────────────────────────
_rate_limit_store: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(request: Request, key: str, max_requests: int, window_seconds: int):
    """检查 IP+key 是否超过限流。超过则抛 429。"""
    client_ip = request.client.host if request.client else "unknown"
    store_key = f"{client_ip}:{key}"
    now = time.time()
    # 清理过期记录
    _rate_limit_store[store_key] = [
        t for t in _rate_limit_store[store_key] if now - t < window_seconds
    ]
    if len(_rate_limit_store[store_key]) >= max_requests:
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")
    _rate_limit_store[store_key].append(now)


def get_db():
    config = load_config()
    return DatabaseManager(config['storage']['db_path'])


def _user_dict(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "is_active": user.is_active,
        "ai_usage_count": user.ai_usage_count or 0,
        "ai_trials_remaining": max(0, AI_TRIAL_LIMIT - (user.ai_usage_count or 0)),
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class PasswordRequest(BaseModel):
    old_password: str
    new_password: str


@router.post("/register")
async def register(req: RegisterRequest, request: Request):
    """注册新用户"""
    _check_rate_limit(request, "register", max_requests=3, window_seconds=60)
    if len(req.username) < 2 or len(req.username) > 50:
        raise HTTPException(status_code=400, detail="用户名长度 2-50 个字符")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="密码至少 6 个字符")

    db = get_db()
    try:
        if db.get_user_by_username(req.username):
            raise HTTPException(status_code=409, detail="用户名已存在")
        if db.get_user_by_email(req.email):
            raise HTTPException(status_code=409, detail="邮箱已被注册")

        user = db.create_user(
            username=req.username,
            email=req.email,
            password_hash=hash_password(req.password),
        )
        if not user:
            raise HTTPException(status_code=500, detail="注册失败")

        token = create_access_token({"sub": str(user.id)})
        return {"success": True, "data": {"token": token, "user": _user_dict(user)}}
    finally:
        db.close()


@router.post("/login")
async def login(req: LoginRequest, request: Request):
    """用户登录"""
    _check_rate_limit(request, "login", max_requests=5, window_seconds=60)
    db = get_db()
    try:
        user = db.get_user_by_username(req.username)
        if not user or not verify_password(req.password, user.password_hash):
            raise HTTPException(status_code=401, detail="用户名或密码错误")
        if not user.is_active:
            raise HTTPException(status_code=403, detail="账号已被禁用")

        token = create_access_token({"sub": str(user.id)})
        return {"success": True, "data": {"token": token, "user": _user_dict(user)}}
    finally:
        db.close()


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return {"success": True, "data": _user_dict(current_user)}


@router.put("/password")
async def change_password(req: PasswordRequest, current_user: User = Depends(get_current_user)):
    """修改密码"""
    if len(req.new_password) < 6:
        raise HTTPException(status_code=400, detail="新密码至少 6 个字符")
    if not verify_password(req.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="旧密码错误")

    db = get_db()
    try:
        user = db.get_user_by_id(current_user.id)
        user.password_hash = hash_password(req.new_password)
        db.session.commit()
        return {"success": True, "data": {"message": "密码修改成功"}}
    except Exception as e:
        db.session.rollback()
        raise HTTPException(status_code=500, detail="修改密码失败")
    finally:
        db.close()
