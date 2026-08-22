# AIMETA P=系统配置安全契约测试|R=敏感键识别_加密写入_响应脱敏|NR=不测试数据库迁移|E=test:config-service-security|X=internal|A=config-security|D=pytest,asyncmock|S=test|RD=../app/services/README.ai
from unittest.mock import AsyncMock

import pytest

from app.core.crypto import decrypt, is_encrypted
from app.models import SystemConfig
from app.schemas.config import SystemConfigCreate, SystemConfigUpdate
from app.services.config_service import ConfigService, is_sensitive_config_key


@pytest.mark.parametrize(
    "key",
    [
        "smtp.password",
        "linuxdo.client_secret",
        "provider.api_key",
        "oauth.access-token",
        "signing.private_key",
    ],
)
def test_sensitive_config_key_recognizes_explicit_secret_segments(key: str) -> None:
    assert is_sensitive_config_key(key) is True


@pytest.mark.parametrize("key", ["writer.max_tokens", "auth.token_url", "updates.api_url"])
def test_sensitive_config_key_does_not_hide_ordinary_settings(key: str) -> None:
    assert is_sensitive_config_key(key) is False


@pytest.mark.asyncio
async def test_sensitive_config_is_encrypted_at_rest_and_never_returned() -> None:
    session = AsyncMock()
    service = ConfigService(session)
    service.repo = AsyncMock()
    service.repo.get_by_key.return_value = None

    result = await service.upsert_config(
        SystemConfigCreate(key="smtp.password", value="fixture-secret", description="SMTP")
    )

    stored = service.repo.add.await_args.args[0]
    assert is_encrypted(stored.value)
    assert decrypt(stored.value) == "fixture-secret"
    assert result.value is None
    assert result.is_sensitive is True
    assert result.is_configured is True
    assert "fixture-secret" not in result.model_dump_json()


@pytest.mark.asyncio
async def test_legacy_plaintext_secret_is_masked_without_rewrite() -> None:
    session = AsyncMock()
    service = ConfigService(session)
    service.repo = AsyncMock()
    service.repo.list_all.return_value = [
        SystemConfig(key="linuxdo.client_secret", value="legacy-fixture", description=None)
    ]

    result = await service.list_configs()

    assert result[0].value is None
    assert result[0].is_sensitive is True
    assert result[0].is_configured is True
    service.repo.update_fields.assert_not_awaited()


@pytest.mark.asyncio
async def test_sensitive_description_patch_preserves_and_masks_stored_value() -> None:
    session = AsyncMock()
    service = ConfigService(session)
    instance = SystemConfig(key="smtp.password", value="legacy-fixture", description=None)
    service.repo = AsyncMock()
    service.repo.get_by_key.return_value = instance

    result = await service.patch_config(instance.key, SystemConfigUpdate(description="SMTP"))

    assert result is not None and result.value is None
    assert result.is_sensitive is True and result.is_configured is True
    service.repo.update_fields.assert_awaited_once_with(instance, description="SMTP")


@pytest.mark.asyncio
async def test_non_sensitive_config_round_trips_and_description_only_patch_preserves_value() -> None:
    session = AsyncMock()
    service = ConfigService(session)
    instance = SystemConfig(key="writer.max_tokens", value="1200", description=None)
    service.repo = AsyncMock()
    service.repo.get_by_key.return_value = instance

    read = await service.get_config(instance.key)
    patched = await service.patch_config(instance.key, SystemConfigUpdate(description="上限"))

    assert read is not None and read.value == "1200" and read.is_sensitive is False
    assert patched is not None and patched.value == "1200"
    service.repo.update_fields.assert_awaited_once_with(instance, description="上限")
