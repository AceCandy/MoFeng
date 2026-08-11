"""显式数据库 bootstrap 的版本、幂等与并发契约。"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.bootstrap import (
    BOOTSTRAP_STEPS,
    BootstrapContractError,
    BootstrapStep,
    run_bootstrap,
)
from app.models.ai_model_config import UserModelProvider
from app.models.database_bootstrap import DatabaseBootstrapVersion
from app.models.prompt import Prompt
from app.models.system_config import SystemConfig
from app.models.user import User


async def _sqlite_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: DatabaseBootstrapVersion.metadata.create_all(
                sync_connection,
                tables=[
                    User.__table__,
                    SystemConfig.__table__,
                    Prompt.__table__,
                    UserModelProvider.__table__,
                    DatabaseBootstrapVersion.__table__,
                ],
            )
        )
    return engine, async_sessionmaker(engine, expire_on_commit=False)


@pytest.mark.asyncio
async def test_bootstrap_is_versioned_idempotent_and_preserves_user_values(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    engine, session_factory = await _sqlite_factory()
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "sample.md").write_text("seed content", encoding="utf-8")

    try:
        async with session_factory() as session:
            session.add_all(
                [
                    User(id=10, username="reader", hashed_password="hashed", is_admin=False),
                    SystemConfig(key="llm.model", value="user-model", description="user value"),
                    SystemConfig(
                        key="auth.allow_registration",
                        value="true",
                        description="user value",
                    ),
                    SystemConfig(key="updates.version_check_url", value="legacy", description=None),
                    Prompt(name="sample", content="user content"),
                    Prompt(name="character_dna_guide", content="legacy prompt"),
                    UserModelProvider(
                        user_id=10,
                        name="legacy-provider",
                        provider_type="openai_compatible",
                        base_url="https://example.com/v1",
                        api_key_encrypted="plain-secret",
                        capabilities_json={"chat": True},
                        is_enabled=True,
                    ),
                ]
            )
            await session.commit()

        config = settings.model_copy(
            update={
                "bootstrap_create_default_admin": True,
                "admin_default_username": "bootstrap-admin",
                "admin_default_password": "bootstrap-password",
                "admin_default_email": "admin@example.com",
                "openai_model_name": "seed-model",
                "allow_registration": False,
            }
        )
        first = await run_bootstrap(
            session_factory=session_factory,
            config=config,
            prompts_dir=prompts_dir,
        )
        second = await run_bootstrap(
            session_factory=session_factory,
            config=config,
            prompts_dir=prompts_dir,
        )

        assert first.completed_versions == tuple(step.version for step in BOOTSTRAP_STEPS)
        assert second.completed_versions == ()
        assert second.skipped_versions == tuple(step.version for step in BOOTSTRAP_STEPS)

        async with session_factory() as session:
            model_value = await session.scalar(
                select(SystemConfig.value).where(SystemConfig.key == "llm.model")
            )
            registration_value = await session.scalar(
                select(SystemConfig.value).where(SystemConfig.key == "auth.allow_registration")
            )
            prompt_content = await session.scalar(
                select(Prompt.content).where(Prompt.name == "sample")
            )
            legacy_config = await session.get(SystemConfig, "updates.version_check_url")
            legacy_prompt = await session.scalar(
                select(Prompt).where(Prompt.name == "character_dna_guide")
            )
            encrypted_key = await session.scalar(
                select(UserModelProvider.api_key_encrypted).where(
                    UserModelProvider.name == "legacy-provider"
                )
            )
            admin_count = await session.scalar(
                select(func.count()).select_from(User).where(User.is_admin.is_(True))
            )
            ledger_count = await session.scalar(
                select(func.count()).select_from(DatabaseBootstrapVersion)
            )

        assert model_value == "user-model"
        assert registration_value == "true"
        assert prompt_content == "user content"
        assert legacy_config is None
        assert legacy_prompt is None
        assert encrypted_key and encrypted_key.startswith("v1:")
        assert admin_count == 1
        assert ledger_count == len(BOOTSTRAP_STEPS)
        assert "plain-secret" not in caplog.text
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_bootstrap_seeds_registration_setting_from_settings_when_missing(
    tmp_path: Path,
) -> None:
    engine, session_factory = await _sqlite_factory()
    config = settings.model_copy(
        update={
            "bootstrap_create_default_admin": False,
            "allow_registration": False,
        }
    )
    try:
        await run_bootstrap(
            session_factory=session_factory,
            config=config,
            prompts_dir=tmp_path,
        )

        async with session_factory() as session:
            registration_value = await session.scalar(
                select(SystemConfig.value).where(SystemConfig.key == "auth.allow_registration")
            )

        assert registration_value == "false"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_completed_bootstrap_checksum_drift_fails_closed(tmp_path: Path) -> None:
    engine, session_factory = await _sqlite_factory()
    try:
        config = settings.model_copy(update={"bootstrap_create_default_admin": False})
        await run_bootstrap(session_factory=session_factory, config=config, prompts_dir=tmp_path)

        async with session_factory() as session:
            row = await session.get(DatabaseBootstrapVersion, BOOTSTRAP_STEPS[0].version)
            assert row is not None
            row.checksum = "0" * 64
            await session.commit()

        with pytest.raises(BootstrapContractError, match="checksum"):
            await run_bootstrap(
                session_factory=session_factory, config=config, prompts_dir=tmp_path
            )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_sqlite_bootstrap_concurrency_is_serialized(tmp_path: Path) -> None:
    engine, session_factory = await _sqlite_factory()
    calls = 0

    async def handler(session, _config, _prompts_dir) -> None:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.01)

    step = BootstrapStep(
        version=999_002,
        name="test-sqlite-concurrent-bootstrap",
        checksum="e" * 64,
        minimum_binary_version=1,
        handler=handler,
    )
    config = settings.model_copy(update={"bootstrap_create_default_admin": False})
    try:
        first, second = await asyncio.gather(
            run_bootstrap(
                session_factory=session_factory,
                config=config,
                prompts_dir=tmp_path,
                steps=(step,),
            ),
            run_bootstrap(
                session_factory=session_factory,
                config=config,
                prompts_dir=tmp_path,
                steps=(step,),
            ),
        )
        assert calls == 1
        assert sorted(
            [first.completed_versions, second.completed_versions],
            key=len,
        ) == [(), (step.version,)]
    finally:
        await engine.dispose()


@pytest.mark.asyncio(loop_scope="session")
async def test_postgres_bootstrap_advisory_lock_executes_version_once(isolated_pg) -> None:
    """真实 PostgreSQL 验证两个执行者不会重复执行同一 bootstrap version。"""

    session_factory = isolated_pg.session_factory
    calls = 0

    async def handler(session, _config, _prompts_dir) -> None:
        nonlocal calls
        calls += 1
        await session.execute(text("SELECT pg_sleep(0.05)"))

    step = BootstrapStep(
        version=999_001,
        name="test-concurrent-bootstrap",
        checksum="f" * 64,
        minimum_binary_version=1,
        handler=handler,
    )

    try:
        first, second = await asyncio.gather(
            run_bootstrap(session_factory=session_factory, steps=(step,)),
            run_bootstrap(session_factory=session_factory, steps=(step,)),
        )
        assert calls == 1
        assert sorted(
            [first.completed_versions, second.completed_versions],
            key=lambda value: len(value),
        ) == [(), (step.version,)]
    finally:
        async with session_factory() as session:
            await session.execute(
                delete(DatabaseBootstrapVersion).where(
                    DatabaseBootstrapVersion.version == step.version
                )
            )
            await session.commit()
