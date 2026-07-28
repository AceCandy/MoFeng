# AIMETA P=数据库显式引导_版本化默认数据与历史迁移|R=引导步骤执行_幂等互斥|NR=不含Schema迁移|E=run_bootstrap|X=internal|A=版本执行器|D=sqlalchemy|S=db|RD=./README.ai
from __future__ import annotations

import asyncio
import hashlib
import logging
from collections.abc import Awaitable, Callable, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..core.config import Settings, assert_production_security, settings
from ..core.crypto import encrypt, is_encrypted
from ..core.security import hash_password
from ..models.ai_model_config import UserModelProvider
from ..models.database_bootstrap import DatabaseBootstrapVersion
from ..models.prompt import Prompt
from ..models.system_config import SystemConfig
from ..models.user import User
from .session import AsyncSessionLocal
from .system_config_defaults import SYSTEM_CONFIG_DEFAULTS

logger = logging.getLogger(__name__)

CURRENT_BOOTSTRAP_BINARY_VERSION = 1
_BOOTSTRAP_LOCK_KEY = 0x4D4F46454E47
_NON_POSTGRES_PROCESS_LOCK = asyncio.Lock()
_DEFAULT_PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"

_LEGACY_SYSTEM_CONFIG_KEYS = (
    "updates.version_check_url",
    "embedding.provider",
    "embedding.api_key",
    "embedding.base_url",
    "embedding.model",
    "embedding.model_vector_size",
    "ollama.embedding_base_url",
    "ollama.embedding_model",
)
_LEGACY_PROMPT_NAMES = ("character_dna_guide",)


class BootstrapContractError(RuntimeError):
    """数据库 ledger 与当前不可变 bootstrap 注册表不一致。"""


BootstrapHandler = Callable[[AsyncSession, Settings, Path], Awaitable[None]]


@dataclass(frozen=True)
class BootstrapStep:
    """一个不可变、可审计的数据引导步骤。"""

    version: int
    name: str
    checksum: str
    minimum_binary_version: int
    handler: BootstrapHandler


@dataclass(frozen=True)
class BootstrapResult:
    """一次 bootstrap 调用完成和跳过的版本集合。"""

    completed_versions: tuple[int, ...]
    skipped_versions: tuple[int, ...]


def _contract_checksum(contract: str) -> str:
    return hashlib.sha256(contract.encode("utf-8")).hexdigest()


async def _bootstrap_core_defaults(
    session: AsyncSession,
    config: Settings,
    prompts_dir: Path,
) -> None:
    if config.bootstrap_create_default_admin:
        admin = await session.scalar(select(User.id).where(User.is_admin.is_(True)).limit(1))
        if admin is None:
            session.add(
                User(
                    username=config.admin_default_username,
                    email=config.admin_default_email,
                    hashed_password=hash_password(config.admin_default_password),
                    is_admin=True,
                )
            )

    await session.execute(
        delete(SystemConfig).where(SystemConfig.key.in_(_LEGACY_SYSTEM_CONFIG_KEYS))
    )
    existing_config_keys = set((await session.scalars(select(SystemConfig.key))).all())
    for entry in SYSTEM_CONFIG_DEFAULTS:
        value = entry.value_getter(config)
        if value is None or entry.key in existing_config_keys:
            continue
        session.add(
            SystemConfig(
                key=entry.key,
                value=value,
                description=entry.description,
            )
        )

    await session.execute(delete(Prompt).where(Prompt.name.in_(_LEGACY_PROMPT_NAMES)))
    if not prompts_dir.is_dir():
        return

    existing_prompt_names = set((await session.scalars(select(Prompt.name))).all())
    for prompt_file in sorted(prompts_dir.glob("*.md")):
        if prompt_file.stem in existing_prompt_names:
            continue
        session.add(
            Prompt(
                name=prompt_file.stem,
                content=prompt_file.read_text(encoding="utf-8"),
            )
        )


async def _encrypt_historical_provider_keys(
    session: AsyncSession,
    _config: Settings,
    _prompts_dir: Path,
) -> None:
    providers = await session.scalars(
        select(UserModelProvider).where(UserModelProvider.api_key_encrypted.isnot(None))
    )
    migrated = 0
    for provider in providers:
        stored = provider.api_key_encrypted
        if stored and not is_encrypted(stored):
            provider.api_key_encrypted = encrypt(stored)
            migrated += 1
    if migrated:
        logger.info("数据库 bootstrap 已迁移 provider key，count=%d", migrated)


BOOTSTRAP_STEPS: tuple[BootstrapStep, ...] = (
    BootstrapStep(
        version=2026072801,
        name="core-defaults-v1",
        checksum=_contract_checksum(
            "create-admin-if-enabled;delete-legacy-config-and-prompt;"
            "insert-missing-system-config-and-prompt"
        ),
        minimum_binary_version=1,
        handler=_bootstrap_core_defaults,
    ),
    BootstrapStep(
        version=2026072802,
        name="encrypt-historical-provider-keys-v1",
        checksum=_contract_checksum("encrypt-non-v1-user-model-provider-api-key"),
        minimum_binary_version=1,
        handler=_encrypt_historical_provider_keys,
    ),
)


def _validate_registered_steps(steps: Sequence[BootstrapStep]) -> None:
    versions = [step.version for step in steps]
    if versions != sorted(versions) or len(versions) != len(set(versions)):
        raise BootstrapContractError("bootstrap versions must be unique and ordered")
    for step in steps:
        if len(step.checksum) != 64:
            raise BootstrapContractError(
                f"bootstrap version {step.version} has an invalid checksum"
            )
        if step.minimum_binary_version > CURRENT_BOOTSTRAP_BINARY_VERSION:
            raise BootstrapContractError(
                f"bootstrap version {step.version} requires a newer binary"
            )


def _validate_ledger_contract(
    row: DatabaseBootstrapVersion,
    step: BootstrapStep,
) -> None:
    if row.name != step.name:
        raise BootstrapContractError(f"bootstrap version {step.version} name drift")
    if row.checksum != step.checksum:
        raise BootstrapContractError(f"bootstrap version {step.version} checksum drift")
    if row.minimum_binary_version != step.minimum_binary_version:
        raise BootstrapContractError(
            f"bootstrap version {step.version} minimum binary version drift"
        )


async def _acquire_step_lock(session: AsyncSession) -> None:
    bind = session.get_bind()
    if bind.dialect.name == "postgresql":
        await session.execute(
            text("SELECT pg_advisory_xact_lock(:lock_key)"),
            {"lock_key": _BOOTSTRAP_LOCK_KEY},
        )


@asynccontextmanager
async def _serialize_non_postgres_step(session: AsyncSession):
    if session.get_bind().dialect.name == "postgresql":
        yield
        return
    async with _NON_POSTGRES_PROCESS_LOCK:
        yield


async def _execute_step(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    step: BootstrapStep,
    config: Settings,
    prompts_dir: Path,
) -> bool:
    async with session_factory() as session:
        async with _serialize_non_postgres_step(session):
            try:
                async with session.begin():
                    await _acquire_step_lock(session)
                    row = await session.get(DatabaseBootstrapVersion, step.version)
                    if row is not None:
                        _validate_ledger_contract(row, step)
                        if row.status == "completed":
                            return False
                    else:
                        row = DatabaseBootstrapVersion(
                            version=step.version,
                            name=step.name,
                            checksum=step.checksum,
                            status="running",
                            minimum_binary_version=step.minimum_binary_version,
                        )
                        session.add(row)

                    row.status = "running"
                    row.started_at = datetime.now(timezone.utc)
                    row.completed_at = None
                    row.failed_at = None
                    row.failure_code = None
                    await step.handler(session, config, prompts_dir)
                    row.status = "completed"
                    row.completed_at = datetime.now(timezone.utc)
                return True
            except BootstrapContractError:
                raise
            except Exception as exc:
                await _record_step_failure(
                    session_factory=session_factory,
                    step=step,
                    failure_code=type(exc).__name__,
                )
                logger.error(
                    "数据库 bootstrap 失败，version=%d error_type=%s",
                    step.version,
                    type(exc).__name__,
                )
                raise


async def _record_step_failure(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    step: BootstrapStep,
    failure_code: str,
) -> None:
    async with session_factory() as session:
        async with session.begin():
            await _acquire_step_lock(session)
            row = await session.get(DatabaseBootstrapVersion, step.version)
            if row is not None and row.status == "completed":
                return
            if row is None:
                row = DatabaseBootstrapVersion(
                    version=step.version,
                    name=step.name,
                    checksum=step.checksum,
                    status="failed",
                    minimum_binary_version=step.minimum_binary_version,
                )
                session.add(row)
            else:
                _validate_ledger_contract(row, step)
                row.status = "failed"
            row.failed_at = datetime.now(timezone.utc)
            row.failure_code = failure_code[:64]


async def run_bootstrap(
    *,
    session_factory: async_sessionmaker[AsyncSession] = AsyncSessionLocal,
    config: Settings = settings,
    prompts_dir: Path = _DEFAULT_PROMPTS_DIR,
    steps: Sequence[BootstrapStep] = BOOTSTRAP_STEPS,
) -> BootstrapResult:
    """按注册顺序执行缺失的 bootstrap versions，已完成版本只做契约校验。"""

    assert_production_security(config)
    _validate_registered_steps(steps)
    completed: list[int] = []
    skipped: list[int] = []
    for step in steps:
        changed = await _execute_step(
            session_factory=session_factory,
            step=step,
            config=config,
            prompts_dir=prompts_dir,
        )
        (completed if changed else skipped).append(step.version)
    return BootstrapResult(tuple(completed), tuple(skipped))
