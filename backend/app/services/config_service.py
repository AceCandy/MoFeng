# AIMETA P=配置服务_系统配置业务逻辑|R=配置读写|NR=不含数据访问|E=ConfigService|X=internal|A=服务类|D=sqlalchemy|S=db|RD=./README.ai
import re
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..core.crypto import decrypt, encrypt
from ..models import SystemConfig
from ..repositories.system_config_repository import SystemConfigRepository
from ..schemas.config import SystemConfigCreate, SystemConfigRead, SystemConfigUpdate

WRITER_VERSION_KEYS = {"writer.chapter_versions", "writer.version_count"}
MIN_CHAPTER_VERSION_COUNT = 1
MAX_CHAPTER_VERSION_COUNT = 2
SENSITIVE_CONFIG_KEY_PARTS = frozenset(
    {
        "api_key",
        "apikey",
        "password",
        "secret",
        "credential",
        "credentials",
        "private_key",
        "access_token",
        "refresh_token",
    }
)


def is_sensitive_config_key(key: str) -> bool:
    """按配置键的完整语义段识别秘密，避免把 max_tokens 等普通项误判。"""

    normalized = re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")
    padded = f"_{normalized}_"
    return any(f"_{part}_" in padded for part in SENSITIVE_CONFIG_KEY_PARTS)


class ConfigService:
    """系统配置服务：提供 CRUD 接口，并负责转换 Pydantic 模型。"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = SystemConfigRepository(session)

    def _normalize_config_value(self, key: str, value: str) -> str:
        if key in WRITER_VERSION_KEYS:
            try:
                parsed = int(str(value).strip())
            except (TypeError, ValueError):
                parsed = MIN_CHAPTER_VERSION_COUNT
            clamped = max(MIN_CHAPTER_VERSION_COUNT, min(MAX_CHAPTER_VERSION_COUNT, parsed))
            return str(clamped)
        return value

    @staticmethod
    def _to_read(config: SystemConfig) -> SystemConfigRead:
        sensitive = is_sensitive_config_key(config.key)
        configured = bool(decrypt(config.value)) if sensitive else bool(config.value)
        return SystemConfigRead(
            key=config.key,
            value=None if sensitive else config.value,
            description=config.description,
            is_sensitive=sensitive,
            is_configured=configured,
        )

    def _to_stored_value(self, key: str, value: str) -> str:
        normalized = self._normalize_config_value(key, value)
        if not is_sensitive_config_key(key):
            return normalized
        return encrypt(normalized) or ""

    async def list_configs(self) -> list[SystemConfigRead]:
        configs = await self.repo.list_all()
        return [self._to_read(config) for config in configs]

    async def get_config(self, key: str) -> Optional[SystemConfigRead]:
        config = await self.repo.get_by_key(key)
        return self._to_read(config) if config else None

    async def upsert_config(self, payload: SystemConfigCreate) -> SystemConfigRead:
        stored_value = self._to_stored_value(payload.key, payload.value)
        instance = await self.repo.get_by_key(payload.key)
        if instance:
            await self.repo.update_fields(
                instance, value=stored_value, description=payload.description
            )
        else:
            instance = SystemConfig(**payload.model_copy(update={"value": stored_value}).model_dump())
            await self.repo.add(instance)
        await self.session.commit()
        return self._to_read(instance)

    async def patch_config(
        self, key: str, payload: SystemConfigUpdate
    ) -> Optional[SystemConfigRead]:
        instance = await self.repo.get_by_key(key)
        if not instance:
            return None
        fields = payload.model_dump(exclude_unset=True)
        if "value" in fields and fields["value"] is not None:
            fields["value"] = self._to_stored_value(key, fields["value"])
        await self.repo.update_fields(instance, **fields)
        await self.session.commit()
        return self._to_read(instance)

    async def remove_config(self, key: str) -> bool:
        instance = await self.repo.get_by_key(key)
        if not instance:
            return False
        await self.repo.delete(instance)
        await self.session.commit()
        return True
