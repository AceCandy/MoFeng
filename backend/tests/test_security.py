# AIMETA P=JWT安全契约测试|R=令牌兼容与失败映射|NR=不测试用户认证流程|E=pytest|X=internal|A=单元测试|D=pytest,stdlib|S=none|RD=../app/core/security.py
import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from fastapi import HTTPException, status

from app.core import security

TEST_SECRET = "test-secret-with-at-least-32-bytes"
LEGACY_SECRET = "legacy-secret-with-at-least-32-bytes"
LEGACY_PASSLIB_HASH = "$2b$12$Q.nv2zEr.yMS2lK5K/ACMOQEN/63Vmu8GBwMw6lKhfTksSFHWxU/C"


def test_bcrypt_password_hash_preserves_format_and_unicode_round_trip() -> None:
    password = "test-unicode-密码"

    hashed = security.hash_password(password)

    assert hashed.startswith("$2b$12$")
    assert security.verify_password(password, hashed) is True
    assert security.verify_password("wrong-password", hashed) is False


def test_bcrypt_password_hash_verifies_existing_passlib_hash() -> None:
    assert security.verify_password("legacy-test-密码", LEGACY_PASSLIB_HASH) is True
    assert security.verify_password("wrong-password", LEGACY_PASSLIB_HASH) is False


def test_bcrypt_password_hash_rejects_nul() -> None:
    hashed = security.hash_password("safe-password")

    with pytest.raises(ValueError):
        security.hash_password("unsafe\x00password")
    with pytest.raises(ValueError):
        security.verify_password("unsafe\x00password", hashed)


def test_bcrypt_password_hash_preserves_72_byte_compatibility() -> None:
    password_72_bytes = "密" * 24
    password_73_bytes = f"{password_72_bytes}a"

    assert len(password_72_bytes.encode("utf-8")) == 72
    assert len(password_73_bytes.encode("utf-8")) == 73
    hashed = security.hash_password(password_72_bytes)

    assert security.verify_password(password_73_bytes, hashed) is True


def test_bcrypt_password_hash_rejects_unknown_hash() -> None:
    with pytest.raises(ValueError):
        security.verify_password("test-password", "not-a-bcrypt-hash")


def _base64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _legacy_hs256_token(
    payload: dict[str, Any],
    secret: str,
    *,
    header_algorithm: str = "HS256",
) -> str:
    header = {"alg": header_algorithm, "typ": "JWT"}
    encoded_header = _base64url(json.dumps(header, separators=(",", ":")).encode())
    encoded_payload = _base64url(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{encoded_header}.{encoded_payload}"
    signature = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    return f"{signing_input}.{_base64url(signature)}"


def _assert_unauthorized(token: str) -> None:
    with pytest.raises(HTTPException) as captured:
        security.decode_access_token(token)

    assert captured.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert captured.value.detail == "无效的凭证"
    assert captured.value.headers == {"WWW-Authenticate": "Bearer"}


def test_access_token_round_trip_preserves_claims(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(security.settings, "secret_key", TEST_SECRET)
    monkeypatch.setattr(security.settings, "jwt_algorithm", "HS256")

    token = security.create_access_token(
        "alice",
        expires_delta=timedelta(minutes=5),
        extra_claims={"is_admin": True},
    )
    payload = security.decode_access_token(token)

    assert payload["sub"] == "alice"
    assert payload["is_admin"] is True
    assert payload["exp"] > payload["iat"]


def test_decodes_existing_hs256_token(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = LEGACY_SECRET
    monkeypatch.setattr(security.settings, "secret_key", secret)
    monkeypatch.setattr(security.settings, "jwt_algorithm", "HS256")
    now = datetime.now(timezone.utc)
    token = _legacy_hs256_token(
        {
            "sub": "legacy-user",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=5)).timestamp()),
            "is_admin": False,
        },
        secret,
    )

    assert security.decode_access_token(token)["sub"] == "legacy-user"


def test_rejects_expired_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(security.settings, "secret_key", TEST_SECRET)
    monkeypatch.setattr(security.settings, "jwt_algorithm", "HS256")
    token = security.create_access_token("alice", expires_delta=timedelta(seconds=-1))

    _assert_unauthorized(token)


def test_rejects_tampered_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(security.settings, "secret_key", TEST_SECRET)
    monkeypatch.setattr(security.settings, "jwt_algorithm", "HS256")
    token = security.create_access_token("alice")
    header, payload, signature = token.split(".")
    replacement = "A" if signature[0] != "A" else "B"

    _assert_unauthorized(f"{header}.{payload}.{replacement}{signature[1:]}")


def test_rejects_token_without_subject(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = TEST_SECRET
    monkeypatch.setattr(security.settings, "secret_key", secret)
    monkeypatch.setattr(security.settings, "jwt_algorithm", "HS256")
    token = _legacy_hs256_token(
        {"exp": int((datetime.now(timezone.utc) + timedelta(minutes=5)).timestamp())},
        secret,
    )

    _assert_unauthorized(token)


def test_rejects_unexpected_algorithm(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = TEST_SECRET
    monkeypatch.setattr(security.settings, "secret_key", secret)
    monkeypatch.setattr(security.settings, "jwt_algorithm", "HS256")
    token = _legacy_hs256_token(
        {
            "sub": "alice",
            "exp": int((datetime.now(timezone.utc) + timedelta(minutes=5)).timestamp()),
        },
        secret,
        header_algorithm="HS512",
    )

    _assert_unauthorized(token)
