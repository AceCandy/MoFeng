# AIMETA P=章节候选版本数解析|R=显式值_系统配置_环境兼容_默认值|NR=不生成或持久化章节|E=resolve_chapter_version_count|X=internal|A=settings_resolver|D=sqlalchemy|S=db,env|RD=./README.ai
"""Resolve the shared chapter candidate count contract."""

from __future__ import annotations

import os
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..repositories.system_config_repository import SystemConfigRepository

MIN_CHAPTER_VERSION_COUNT = 1
MAX_CHAPTER_VERSION_COUNT = 2


def clamp_chapter_version_count(value: int) -> int:
    """将候选版本数限制在当前产品支持的 1 到 2 个。"""

    return max(MIN_CHAPTER_VERSION_COUNT, min(MAX_CHAPTER_VERSION_COUNT, int(value)))


async def resolve_chapter_version_count(
    session: AsyncSession,
    requested_count: Optional[int],
) -> int:
    """显式请求优先，缺省时沿用系统配置与历史环境变量兼容顺序。"""

    if requested_count is not None:
        try:
            return clamp_chapter_version_count(int(requested_count))
        except (TypeError, ValueError):
            pass

    repo = SystemConfigRepository(session)
    for key in ("writer.chapter_versions", "writer.version_count"):
        record = await repo.get_by_key(key)
        if record and record.value:
            try:
                value = int(record.value)
                if value >= 1:
                    return clamp_chapter_version_count(value)
            except ValueError:
                pass

    for env_name in (
        "WRITER_CHAPTER_VERSION_COUNT",
        "WRITER_CHAPTER_VERSIONS",
        "WRITER_VERSION_COUNT",
    ):
        value = os.getenv(env_name)
        if value:
            try:
                parsed = int(value)
                if parsed >= 1:
                    return clamp_chapter_version_count(parsed)
            except ValueError:
                pass

    return clamp_chapter_version_count(int(settings.writer_chapter_versions))


__all__ = ["clamp_chapter_version_count", "resolve_chapter_version_count"]
