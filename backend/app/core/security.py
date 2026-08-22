# AIMETA P=安全模块_JWT令牌和密码处理|R=JWT生成验证_密码哈希|NR=不含用户管理|E=create_token_verify_password|X=internal|A=安全函数|D=jwt,bcrypt|S=none|RD=./README.ai
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import bcrypt
import jwt
from fastapi import HTTPException, status
from jwt.exceptions import InvalidTokenError

from .config import settings


def _password_bytes(password: str) -> bytes:
    encoded = password.encode("utf-8")
    if b"\x00" in encoded:
        raise ValueError("密码不能包含 NUL 字节")
    return encoded


def hash_password(password: str) -> str:
    """对用户密码进行哈希处理，任何时候都不要存储明文密码。"""
    return bcrypt.hashpw(
        _password_bytes(password),
        bcrypt.gensalt(rounds=12, prefix=b"2b"),
    ).decode("ascii")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码是否匹配哈希值。"""
    return bcrypt.checkpw(
        _password_bytes(plain_password),
        hashed_password.encode("ascii"),
    )


def create_access_token(
    subject: str,
    *,
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """生成 JWT 访问令牌，默认过期时间读取自配置。"""
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.access_token_expire_minutes)

    now = datetime.utcnow()
    expire = now + expires_delta

    to_encode: Dict[str, Any] = {"sub": subject, "iat": now, "exp": expire}
    if extra_claims:
        to_encode.update(extra_claims)

    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> Dict[str, Any]:
    """解析并校验 JWT，失败时抛出 401 异常。"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的凭证",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except InvalidTokenError as exc:
        raise credentials_exception from exc

    if "sub" not in payload:
        raise credentials_exception
    return payload
