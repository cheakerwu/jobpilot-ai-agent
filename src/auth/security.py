"""
密码哈希 + JWT 工具
"""
import os
import hashlib
import logging
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import jwt, JWTError

logger = logging.getLogger(__name__)

# ── 密码哈希 ──────────────────────────────────────────────────────────────────


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# ── JWT ───────────────────────────────────────────────────────────────────────
_secret = os.environ.get("JOBPILOT_SECRET_KEY")
if not _secret:
    # 生成确定性回退密钥（同一机器重启后不变），避免 token 失效
    import platform
    fallback_seed = f"jobpilot-{platform.node()}-fallback".encode()
    _secret = hashlib.sha256(fallback_seed).hexdigest()
    logger.warning("JOBPILOT_SECRET_KEY 未设置，使用机器绑定的回退密钥。生产环境请设置固定密钥。")

SECRET_KEY = _secret
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
