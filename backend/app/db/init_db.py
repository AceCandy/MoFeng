# AIMETA P=数据库初始化_创建表和默认数据|R=创建表_初始化管理员|NR=不含业务逻辑|E=init_db|X=internal|A=初始化函数|D=sqlalchemy|S=db|RD=./README.ai
import asyncio
import logging

from pathlib import Path

from sqlalchemy import inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from alembic import command
from alembic.config import Config as AlembicConfig

from ..core.config import settings
from ..core.security import hash_password
from ..models import Prompt, SystemConfig, User
from .system_config_defaults import SYSTEM_CONFIG_DEFAULTS
from .session import AsyncSessionLocal, engine

logger = logging.getLogger(__name__)
LEGACY_SYSTEM_CONFIG_KEYS_TO_DELETE = (
    "updates.version_check_url",
)


async def init_db() -> None:
    """初始化数据库结构并确保默认管理员存在。"""

    await _ensure_database_exists()

    # ---- 第一步：用 alembic 管理表结构（新库 upgrade head 建表，旧库 stamp head 标记基线）----
    await _run_alembic_upgrade()
    logger.info("数据库表结构已初始化")

    # ---- 第二步：确保管理员账号至少存在一个 ----
    async with AsyncSessionLocal() as session:
        admin_exists = await session.execute(select(User).where(User.is_admin.is_(True)))
        if not admin_exists.scalars().first():
            logger.warning("未检测到管理员账号，正在创建默认管理员 ...")
            admin_user = User(
                username=settings.admin_default_username,
                email=settings.admin_default_email,
                hashed_password=hash_password(settings.admin_default_password),
                is_admin=True,
            )

            session.add(admin_user)
            try:
                await session.commit()
                logger.info("默认管理员创建完成：%s", settings.admin_default_username)
            except IntegrityError:
                await session.rollback()
                logger.exception("默认管理员创建失败，可能是并发启动导致，请检查数据库状态")

        # ---- 第三步：清理已废弃的系统配置键 ----
        for legacy_key in LEGACY_SYSTEM_CONFIG_KEYS_TO_DELETE:
            legacy_config = await session.get(SystemConfig, legacy_key)
            if legacy_config:
                await session.delete(legacy_config)
                logger.info("已清理废弃系统配置键：%s", legacy_key)

        # ---- 第四步：同步系统配置到数据库 ----
        for entry in SYSTEM_CONFIG_DEFAULTS:
            value = entry.value_getter(settings)
            if value is None:
                continue
            existing = await session.get(SystemConfig, entry.key)
            if existing:
                if entry.key == "embedding.provider" and not (existing.value or "").strip():
                    existing.value = value
                if entry.description and existing.description != entry.description:
                    existing.description = entry.description
                continue
            session.add(
                SystemConfig(
                    key=entry.key,
                    value=value,
                    description=entry.description,
                )
            )

        await _ensure_default_prompts(session)
        await _migrate_encrypt_provider_api_keys(session)

        await session.commit()


async def _ensure_database_exists() -> None:
    """在首次连接前确认数据库存在，PostgreSQL 场景按需建库。"""
    url = make_url(settings.sqlalchemy_database_uri)

    database = (url.database or "").strip("/")
    if not database:
        return

    admin_url = URL.create(
        drivername=url.drivername,
        username=url.username,
        password=url.password,
        host=url.host,
        port=url.port,
        database="postgres",  # 连默认库以执行 CREATE DATABASE（PG 不允许无 database 连接）
        query=url.query,
    )

    admin_engine = create_async_engine(
        admin_url.render_as_string(hide_password=False),
        isolation_level="AUTOCOMMIT",
    )
    async with admin_engine.begin() as conn:
        # 先查库是否存在，已存在则跳过 CREATE，避免重复建库报错。
        exists_sql = "SELECT 1 FROM pg_database WHERE datname = :db"
        exists = await conn.execute(text(exists_sql), {"db": database})
        if exists.first() is None:
            await conn.execute(text(f'CREATE DATABASE "{database}"'))
    await admin_engine.dispose()


ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


def _build_alembic_config() -> AlembicConfig:
    """构建 alembic 配置，用应用数据库连接串 + 绝对 script_location（避免运行目录差异）。"""
    cfg = AlembicConfig(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(ALEMBIC_INI.parent / "alembic"))
    cfg.set_main_option("sqlalchemy.url", settings.sqlalchemy_database_uri)
    return cfg


def _needs_alembic_stamp(sync_conn) -> bool:
    """旧库（有业务表但无 alembic_version）需 stamp head 标记基线，避免 upgrade 重复建表报错。"""
    inspector = inspect(sync_conn)
    table_names = set(inspector.get_table_names())
    has_alembic_version = "alembic_version" in table_names
    has_any_table = bool(table_names - {"alembic_version"})
    return has_any_table and not has_alembic_version


def _run_alembic_sync(stamp_first: bool) -> None:
    """同步执行 alembic（在线程池中调用，避免与 async event loop 冲突）。"""
    cfg = _build_alembic_config()
    if stamp_first:
        command.stamp(cfg, "head")
    command.upgrade(cfg, "head")


async def _run_alembic_upgrade() -> None:
    """用 alembic 管理表结构：新库 upgrade head 建全表，旧库先 stamp head 再 upgrade。"""
    async with engine.begin() as conn:
        stamp_first = await conn.run_sync(_needs_alembic_stamp)
    if stamp_first:
        logger.info("检测到旧库无 alembic 版本表，先 stamp head 标记基线")
    await asyncio.to_thread(_run_alembic_sync, stamp_first)


async def _ensure_default_prompts(session: AsyncSession) -> None:
    prompts_dir = Path(__file__).resolve().parents[2] / "prompts"
    if not prompts_dir.is_dir():
        return

    result = await session.execute(select(Prompt.name))
    existing_names = set(result.scalars().all())

    for prompt_file in sorted(prompts_dir.glob("*.md")):
        name = prompt_file.stem
        if name in existing_names:
            continue
        content = prompt_file.read_text(encoding="utf-8")
        session.add(Prompt(name=name, content=content))


async def _migrate_encrypt_provider_api_keys(session: AsyncSession) -> None:
    """将历史明文 API Key 加密回写，已加密的跳过（幂等）。"""
    from ..core.crypto import encrypt, is_encrypted
    from ..models import UserModelProvider

    result = await session.execute(
        select(UserModelProvider).where(UserModelProvider.api_key_encrypted.isnot(None))
    )
    migrated = 0
    for provider in result.scalars():
        stored = provider.api_key_encrypted
        if stored and not is_encrypted(stored):
            provider.api_key_encrypted = encrypt(stored)
            migrated += 1
    if migrated:
        logger.info("已加密迁移 %d 条历史明文 API Key", migrated)
