"""
FastAPI 认证依赖：从请求中解析当前用户
"""
from fastapi import Request, HTTPException
from src.auth.security import decode_access_token
from src.storage.database import DatabaseManager
from src.helpers import load_config


def get_current_user(request: Request):
    """从 Authorization: Bearer <token> 解析当前用户"""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")

    token = auth_header[7:]
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="无效的登录信息")

    config = load_config()
    db = DatabaseManager(config['storage']['db_path'])
    try:
        user = db.get_user_by_id(int(user_id))
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="用户不存在或已禁用")
        return user
    finally:
        db.close()
