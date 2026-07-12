# AIMETA P=敏感字段加解密_对称加密工具|R=API_Key等字段透明加解密|NR=不含业务逻辑|E=encrypt_decrypt|X=internal|A=加密工具|D=cryptography|S=none|RD=./README.ai
"""敏感字段对称加密工具，用于 API Key 等数据的透明加解密。

密钥从 ``SECRET_KEY`` 经 PBKDF2-HMAC-SHA256 派生，密文带 ``v1:`` 版本前缀；
旧明文在读取时原样返回以便平滑迁移，写入时统一加密。
"""

from __future__ import annotations

import base64
import functools

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from .config import settings

# 密文版本前缀，便于未来升级算法时按前缀分派解密逻辑
_PREFIX = "v1:"
# 固定盐值；Fernet 每次加密自带随机 IV 与时间戳，已足够保证密文不可区分
_SALT = b"mofeng-api-key-fernet-v1"
_ITERATIONS = 480_000


@functools.lru_cache(maxsize=1)
def _fernet() -> Fernet:
    """从 SECRET_KEY 派生 Fernet 密钥并缓存。"""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_SALT,
        iterations=_ITERATIONS,
    )
    key = base64.urlsafe_b64encode(kdf.derive(settings.secret_key.encode("utf-8")))
    return Fernet(key)


def is_encrypted(stored: str | None) -> bool:
    """判断存储值是否为加密密文（带版本前缀）。"""
    return bool(stored) and stored.startswith(_PREFIX)


def encrypt(plaintext: str | None) -> str | None:
    """加密明文；空值原样返回 None。"""
    if not plaintext:
        return None
    token = _fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")
    return _PREFIX + token


def decrypt(stored: str | None) -> str | None:
    """解密密文；空值返回 None，旧明文（无前缀）原样返回以兼容历史数据。"""
    if not stored:
        return None
    if not stored.startswith(_PREFIX):
        return stored
    try:
        return _fernet().decrypt(stored[len(_PREFIX):].encode("ascii")).decode("utf-8")
    except InvalidToken:
        # 密钥变更或密文损坏时静默退化为无 Key，避免阻断调用链
        return None
