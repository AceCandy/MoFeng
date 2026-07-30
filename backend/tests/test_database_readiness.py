"""数据库 migration/bootstrap/readiness 边界契约。"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncConnection, async_sessionmaker, create_async_engine

from alembic import command
from app.core.config import settings
from app.db import migration as migration_module
from app.db.base import Base
from app.db.bootstrap import (
    BOOTSTRAP_STEPS,
    CURRENT_BOOTSTRAP_BINARY_VERSION,
    run_bootstrap,
)
from app.db.cli import build_parser
from app.db.migration import (
    KNOWN_LEGACY_BASELINES,
    LegacyDatabaseRequiresAdoption,
    adopt_legacy_database,
    build_alembic_config,
    canonical_schema_fingerprint,
    classify_database_tables,
    create_database,
    metadata_schema_manifest,
    resolve_legacy_baseline,
    run_migrations,
)
from app.db.readiness import (
    BootstrapLedgerState,
    DatabaseReadiness,
    DatabaseState,
    check_database_readiness,
    evaluate_database_readiness,
)


def _completed_ledger() -> tuple[BootstrapLedgerState, ...]:
    return tuple(
        BootstrapLedgerState(
            version=step.version,
            name=step.name,
            status="completed",
            checksum=step.checksum,
            minimum_binary_version=step.minimum_binary_version,
        )
        for step in BOOTSTRAP_STEPS
    )


@asynccontextmanager
async def _temporary_postgres_database(source_engine, *, create: bool = True):
    database_name = f"mofeng_dbb_{uuid4().hex}"
    admin_engine = create_async_engine(
        source_engine.url.set(database="postgres"),
        isolation_level="AUTOCOMMIT",
    )
    try:
        if create:
            async with admin_engine.connect() as connection:
                quoted_name = connection.dialect.identifier_preparer.quote(database_name)
                await connection.execute(sa.text(f"CREATE DATABASE {quoted_name}"))
        yield source_engine.url.set(database=database_name).render_as_string(hide_password=False)
    finally:
        async with admin_engine.connect() as connection:
            await connection.execute(
                sa.text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :database_name AND pid <> pg_backend_pid()"
                ),
                {"database_name": database_name},
            )
            quoted_name = connection.dialect.identifier_preparer.quote(database_name)
            await connection.execute(sa.text(f"DROP DATABASE IF EXISTS {quoted_name}"))
        await admin_engine.dispose()


def _upgrade_to_revision(connection, database_url: str, revision: str) -> None:
    config = build_alembic_config(database_url)
    config.attributes["connection"] = connection
    command.upgrade(config, revision)


def _downgrade_to_revision(connection, database_url: str, revision: str) -> None:
    config = build_alembic_config(database_url)
    config.attributes["connection"] = connection
    command.downgrade(config, revision)


def test_readiness_requires_schema_head_and_every_bootstrap_contract() -> None:
    current = DatabaseState(
        reachable=True,
        database_revisions=("head-revision",),
        code_heads=("head-revision",),
        bootstrap_rows=_completed_ledger(),
    )
    assert evaluate_database_readiness(current).ready is True

    behind = DatabaseState(
        reachable=True,
        database_revisions=("old-revision",),
        code_heads=("head-revision",),
        bootstrap_rows=_completed_ledger(),
    )
    assert "schema_not_at_head" in evaluate_database_readiness(behind).codes

    missing_bootstrap = DatabaseState(
        reachable=True,
        database_revisions=("head-revision",),
        code_heads=("head-revision",),
        bootstrap_rows=_completed_ledger()[:-1],
    )
    assert "bootstrap_incomplete" in evaluate_database_readiness(missing_bootstrap).codes


def test_readiness_rejects_database_requiring_newer_binary() -> None:
    future = BootstrapLedgerState(
        version=999_999,
        name="future-bootstrap",
        status="completed",
        checksum="f" * 64,
        minimum_binary_version=CURRENT_BOOTSTRAP_BINARY_VERSION + 1,
    )
    state = DatabaseState(
        reachable=True,
        database_revisions=("head-revision",),
        code_heads=("head-revision",),
        bootstrap_rows=(*_completed_ledger(), future),
    )
    assert "binary_below_rollback_floor" in evaluate_database_readiness(state).codes


def test_readiness_rejects_bootstrap_name_drift() -> None:
    completed = list(_completed_ledger())
    first = completed[0]
    completed[0] = BootstrapLedgerState(
        version=first.version,
        name="changed-contract-name",
        status=first.status,
        checksum=first.checksum,
        minimum_binary_version=first.minimum_binary_version,
    )
    state = DatabaseState(
        reachable=True,
        database_revisions=("head-revision",),
        code_heads=("head-revision",),
        bootstrap_rows=tuple(completed),
    )
    assert "bootstrap_contract_mismatch" in evaluate_database_readiness(state).codes


def test_readiness_rejects_checkpoint_schema_or_version_drift() -> None:
    missing_table = DatabaseState(
        reachable=True,
        database_revisions=("head-revision",),
        code_heads=("head-revision",),
        bootstrap_rows=_completed_ledger(),
        checkpoint_tables=frozenset({"checkpoints"}),
    )
    assert "checkpoint_schema_missing" in evaluate_database_readiness(missing_table).codes

    future_version = DatabaseState(
        reachable=True,
        database_revisions=("head-revision",),
        code_heads=("head-revision",),
        bootstrap_rows=_completed_ledger(),
        checkpoint_migration_versions=tuple(range(11)),
    )
    assert "checkpoint_schema_mismatch" in evaluate_database_readiness(future_version).codes


def test_legacy_database_classification_and_fingerprint_are_fail_closed() -> None:
    assert classify_database_tables(set()) == "empty"
    assert classify_database_tables({"alembic_version"}) == "versioned"
    assert classify_database_tables({"users", "prompts"}) == "legacy"

    first = {
        "tables": [
            {
                "name": "users",
                "columns": [
                    {"name": "username", "type": "string:64"},
                    {"name": "id", "type": "integer"},
                ],
            }
        ]
    }
    reordered = {
        "tables": [
            {
                "columns": list(reversed(first["tables"][0]["columns"])),
                "name": "users",
            }
        ]
    }
    assert canonical_schema_fingerprint(first) == canonical_schema_fingerprint(reordered)

    composite_index = {
        "tables": [
            {
                "name": "items",
                "columns": [],
                "indexes": [{"columns": ["owner_id", "position"], "unique": False}],
            }
        ]
    }
    reversed_index = {
        "tables": [
            {
                "name": "items",
                "columns": [],
                "indexes": [{"columns": ["position", "owner_id"], "unique": False}],
            }
        ]
    }
    assert canonical_schema_fingerprint(composite_index) != canonical_schema_fingerprint(
        reversed_index
    )

    with_check = {
        "tables": [
            {
                "name": "items",
                "columns": [],
                "check_constraints": ["position >= 0"],
            }
        ]
    }
    without_check = {"tables": [{"name": "items", "columns": []}]}
    assert canonical_schema_fingerprint(with_check) != canonical_schema_fingerprint(without_check)

    assert KNOWN_LEGACY_BASELINES
    fingerprint, revision = next(iter(KNOWN_LEGACY_BASELINES.items()))
    assert len(fingerprint) == 64
    assert resolve_legacy_baseline(fingerprint) == revision
    with pytest.raises(LegacyDatabaseRequiresAdoption, match="unknown_legacy_schema"):
        resolve_legacy_baseline("0" * 64)


def test_metadata_manifest_captures_check_constraints() -> None:
    metadata = sa.MetaData()
    sa.Table(
        "inventory",
        metadata,
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.CheckConstraint("quantity >= 0"),
    )

    manifest = metadata_schema_manifest(metadata)

    assert manifest["tables"][0]["check_constraints"] == ["quantity >= 0"]


def test_current_metadata_is_not_registered_as_historical_legacy_schema() -> None:
    fingerprint = canonical_schema_fingerprint(metadata_schema_manifest(Base.metadata))

    assert fingerprint not in KNOWN_LEGACY_BASELINES


@pytest.mark.parametrize(
    "command",
    ["db-create", "db-migrate", "db-adopt-legacy", "db-bootstrap", "db-check"],
)
def test_database_cli_exposes_explicit_commands(command: str) -> None:
    parser = build_parser()
    args = [command]
    if command == "db-adopt-legacy":
        fingerprint = next(iter(KNOWN_LEGACY_BASELINES))
        args.extend(
            [
                "--operator",
                "release-operator",
                "--expected-fingerprint",
                fingerprint,
                "--backup-confirmed",
            ]
        )
    assert parser.parse_args(args).command == command


def test_alembic_config_preserves_percent_encoded_database_url() -> None:
    database_url = "postgresql+asyncpg://user:p%40ss%25word@db.example/mofeng"
    config = build_alembic_config(database_url)

    assert config.get_main_option("sqlalchemy.url") == database_url


def test_runtime_and_deploy_files_use_read_only_readiness_boundary() -> None:
    project_root = Path(__file__).resolve().parents[2]
    main_source = (project_root / "backend/app/main.py").read_text(encoding="utf-8")
    compose_source = (project_root / "deploy/docker-compose.yml").read_text(encoding="utf-8")
    dockerfile_source = (project_root / "deploy/Dockerfile").read_text(encoding="utf-8")

    assert "init_db" not in main_source
    assert "check_database_readiness" in main_source
    assert '@app.get("/ready"' in main_source
    assert '@app.get("/health"' in main_source

    assert "migrate:" in compose_source
    assert "bootstrap:" in compose_source
    assert "condition: service_completed_successfully" in compose_source
    assert "/api/ready" in compose_source
    assert "COPY backend/alembic.ini ./alembic.ini" in dockerfile_source
    assert "COPY backend/alembic ./alembic" in dockerfile_source


@pytest.mark.asyncio
async def test_http_readiness_returns_503_with_stable_codes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import main as main_module

    async def not_ready() -> DatabaseReadiness:
        return DatabaseReadiness(False, ("schema_not_at_head",))

    monkeypatch.setattr(main_module, "check_database_readiness", not_ready)

    response = await main_module.readiness_check()

    assert response.status_code == 503
    assert b"schema_not_at_head" in response.body


@pytest.mark.asyncio(loop_scope="session")
async def test_postgres_empty_and_current_database_lifecycle(
    _pg_engine,
    tmp_path: Path,
) -> None:
    async with _temporary_postgres_database(_pg_engine, create=False) as database_url:
        assert await create_database(database_url) is True
        assert await create_database(database_url) is False
        await run_migrations(database_url)
        await run_migrations(database_url)

        engine = create_async_engine(database_url)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        config = settings.model_copy(update={"bootstrap_create_default_admin": False})
        try:
            first = await run_bootstrap(
                session_factory=session_factory,
                config=config,
                prompts_dir=tmp_path,
            )
            second = await run_bootstrap(
                session_factory=session_factory,
                config=config,
                prompts_dir=tmp_path,
            )

            assert first.completed_versions == tuple(step.version for step in BOOTSTRAP_STEPS)
            assert second.skipped_versions == tuple(step.version for step in BOOTSTRAP_STEPS)
            assert (await check_database_readiness(engine)).ready is True
        finally:
            await engine.dispose()


@pytest.mark.asyncio(loop_scope="session")
async def test_concurrent_postgres_migrations_are_serialized_by_advisory_lock(
    _pg_engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_acquire_lock = migration_module._acquire_migration_lock
    first_locked = asyncio.Event()
    second_waiting = asyncio.Event()
    release_first = asyncio.Event()
    invocation_count = 0
    backend_pids: dict[str, int] = {}

    async def observe_lock(connection: AsyncConnection) -> None:
        nonlocal invocation_count
        invocation_count += 1
        if invocation_count == 1:
            await original_acquire_lock(connection)
            backend_pids["first"] = int(await connection.scalar(sa.text("SELECT pg_backend_pid()")))
            first_locked.set()
            await release_first.wait()
            return

        backend_pids["second"] = int(await connection.scalar(sa.text("SELECT pg_backend_pid()")))
        second_waiting.set()
        await original_acquire_lock(connection)

    monkeypatch.setattr(migration_module, "_acquire_migration_lock", observe_lock)

    async with _temporary_postgres_database(_pg_engine) as database_url:
        observer_engine = create_async_engine(database_url)
        tasks: list[asyncio.Task[None]] = []
        blocked_by_first = False
        try:
            tasks.append(asyncio.create_task(run_migrations(database_url)))
            await asyncio.wait_for(first_locked.wait(), timeout=10)
            tasks.append(asyncio.create_task(run_migrations(database_url)))
            await asyncio.wait_for(second_waiting.wait(), timeout=10)

            async with observer_engine.connect() as connection:
                for _ in range(100):
                    blocking_pids = await connection.scalar(
                        sa.text("SELECT pg_blocking_pids(:pid)"),
                        {"pid": backend_pids["second"]},
                    )
                    if backend_pids["first"] in (blocking_pids or []):
                        blocked_by_first = True
                        break
                    await asyncio.sleep(0.01)

            release_first.set()
            await asyncio.wait_for(asyncio.gather(*tasks), timeout=30)

            async with observer_engine.connect() as connection:
                revisions = (
                    (await connection.execute(sa.text("SELECT version_num FROM alembic_version")))
                    .scalars()
                    .all()
                )
                table_names = await connection.run_sync(
                    lambda sync_connection: set(sa.inspect(sync_connection).get_table_names())
                )
        finally:
            release_first.set()
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await observer_engine.dispose()

        assert backend_pids["first"] != backend_pids["second"]
        assert blocked_by_first is True
        assert revisions == ["c8e5f2a1d4b6"]
        assert {
            "chapter_revisions",
            "chapter_outbox_events",
            "chapter_projection_runs",
        } <= table_names


@pytest.mark.asyncio(loop_scope="session")
async def test_head_schema_accepts_pre_projection_chapter_insert(_pg_engine) -> None:
    async with _temporary_postgres_database(_pg_engine) as database_url:
        await run_migrations(database_url)
        engine = create_async_engine(database_url)
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    sa.text(
                        "INSERT INTO users "
                        "(id, username, hashed_password, is_admin, is_active) "
                        "VALUES (7003, 'old-chapter-writer', 'secret', false, true)"
                    )
                )
                await connection.execute(
                    sa.text(
                        "INSERT INTO novel_projects (id, user_id, title, status) "
                        "VALUES ('old-chapter-project', 7003, '旧写入兼容项目', 'draft')"
                    )
                )
                await connection.execute(
                    sa.text(
                        "INSERT INTO chapters "
                        "(id, project_id, chapter_number, status, generation_progress, "
                        "generation_step_index, generation_step_total, word_count) "
                        "VALUES (8102, 'old-chapter-project', 1, 'pending', 0, 0, 0, 0)"
                    )
                )

            async with engine.connect() as connection:
                chapter = (
                    (
                        await connection.execute(
                            sa.text(
                                "SELECT current_revision, source_hash, "
                                "required_projection_snapshot, projection_generation, "
                                "tombstone_revision FROM chapters WHERE id = 8102"
                            )
                        )
                    )
                    .mappings()
                    .one()
                )
        finally:
            await engine.dispose()

        assert chapter == {
            "current_revision": 0,
            "source_hash": None,
            "required_projection_snapshot": [],
            "projection_generation": None,
            "tombstone_revision": 0,
        }


@pytest.mark.asyncio(loop_scope="session")
async def test_projection_migration_rejects_destructive_downgrade(_pg_engine) -> None:
    async with _temporary_postgres_database(_pg_engine) as database_url:
        await run_migrations(database_url)
        engine = create_async_engine(database_url)
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    sa.text(
                        "INSERT INTO users "
                        "(id, username, hashed_password, is_admin, is_active) "
                        "VALUES (7999, 'rollback-floor-user', 'secret', true, true)"
                    )
                )
                await connection.execute(
                    sa.text(
                        "INSERT INTO background_tasks "
                        "(id, user_id, task_type, title, status, progress, payload, "
                        "result, error, log_entries, stream_id) VALUES "
                        "('rollback-floor-job', 7999, 'chapter_projection_rag', "
                        "'rollback floor', 'queued', 0, '{}'::json, NULL, NULL, "
                        "'[]'::json, 'rollback-floor-job')"
                    )
                )
                await connection.execute(
                    sa.text(
                        "INSERT INTO job_activities "
                        "(id, job_id, activity_key, side_effect_class, status, "
                        "provider_request_key, attempt, fencing_token, request_payload, "
                        "started_at) VALUES "
                        "('rollback-floor-activity', 'rollback-floor-job', 'embedding', "
                        "'idempotent_external', 'succeeded', 'rollback-floor-provider', "
                        "1, 1, '{}'::json, now())"
                    )
                )
                await connection.execute(
                    sa.text(
                        "INSERT INTO ai_usage_records "
                        "(job_activity_id, job_id, user_id, provider_type, model_name, "
                        "stage, usage_complete, cost_known, cost_unknown_reason) VALUES "
                        "('rollback-floor-activity', 'rollback-floor-job', 7999, "
                        "'openai_compatible', 'rollback-model', 'embedding', false, "
                        "false, 'usage_unavailable')"
                    )
                )
                await connection.execute(
                    sa.text(
                        "INSERT INTO chapter_projection_retention_audits "
                        "(id, operator_user_id, project_id, chapter_number, revision, "
                        "artifact_generation, artifact_kind, mode, status, idempotency_key, "
                        "reason, request_scope, result) VALUES "
                        "('rollback-floor-retention', 7999, 'deleted-project', 1, 1, "
                        "'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'rag', 'purge', "
                        "'completed', 'rollback-floor-retention', '保留审计', "
                        "'{}'::json, '{}'::json)"
                    )
                )

            with pytest.raises(RuntimeError, match="binary rollback floor"):
                async with engine.begin() as connection:
                    await connection.run_sync(
                        _downgrade_to_revision,
                        database_url,
                        "d4b8f1a2c3e7",
                    )

            async with engine.connect() as connection:
                revision = await connection.scalar(
                    sa.text("SELECT version_num FROM alembic_version")
                )
                table_names = await connection.run_sync(
                    lambda sync_connection: set(sa.inspect(sync_connection).get_table_names())
                )
                usage_count = await connection.scalar(
                    sa.text(
                        "SELECT count(*) FROM ai_usage_records "
                        "WHERE job_activity_id = 'rollback-floor-activity'"
                    )
                )
                retention_count = await connection.scalar(
                    sa.text(
                        "SELECT count(*) FROM chapter_projection_retention_audits "
                        "WHERE id = 'rollback-floor-retention'"
                    )
                )
        finally:
            await engine.dispose()

        assert revision == "c8e5f2a1d4b6"
        assert {
            "chapter_revisions",
            "chapter_outbox_events",
            "chapter_projection_runs",
            "ai_usage_records",
            "chapter_projection_retention_audits",
        } <= table_names
        assert usage_count == 1
        assert retention_count == 1


@pytest.mark.asyncio(loop_scope="session")
async def test_postgres_legacy_adoption_is_explicit_and_audited(
    _pg_engine,
    tmp_path: Path,
) -> None:
    async with _temporary_postgres_database(_pg_engine) as database_url:
        engine = create_async_engine(database_url)
        try:
            async with engine.begin() as connection:
                await connection.run_sync(
                    _upgrade_to_revision,
                    database_url,
                    "17a89f18291c",
                )
                await connection.execute(sa.text("DROP TABLE alembic_version"))

            with pytest.raises(LegacyDatabaseRequiresAdoption) as adoption_required:
                await run_migrations(database_url)
            fingerprint = adoption_required.value.fingerprint
            assert fingerprint in KNOWN_LEGACY_BASELINES

            with pytest.raises(LegacyDatabaseRequiresAdoption, match="mismatch"):
                await adopt_legacy_database(
                    operator="release-operator",
                    expected_fingerprint="0" * 64,
                    backup_confirmed=True,
                    database_url=database_url,
                )

            revision = await adopt_legacy_database(
                operator="release-operator",
                expected_fingerprint=fingerprint,
                backup_confirmed=True,
                database_url=database_url,
            )
            assert revision == KNOWN_LEGACY_BASELINES[fingerprint]

            async with engine.connect() as connection:
                audit_count = await connection.scalar(
                    sa.text(
                        "SELECT count(*) FROM legacy_database_adoptions "
                        "WHERE operator = 'release-operator' AND result = 'completed' "
                        "AND backup_confirmed IS TRUE"
                    )
                )
            assert audit_count == 1

            config = settings.model_copy(update={"bootstrap_create_default_admin": False})
            await run_bootstrap(
                session_factory=async_sessionmaker(engine, expire_on_commit=False),
                config=config,
                prompts_dir=tmp_path,
            )
            assert (await check_database_readiness(engine)).ready is True
        finally:
            await engine.dispose()


@pytest.mark.asyncio(loop_scope="session")
async def test_postgres_migration_failure_rolls_back_and_stays_not_ready(
    _pg_engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_after_schema_write(connection, _database_url: str) -> None:
        connection.execute(sa.text("CREATE TABLE migration_probe (id integer)"))
        raise RuntimeError("injected migration failure")

    monkeypatch.setattr(
        migration_module,
        "_upgrade_on_connection",
        fail_after_schema_write,
    )

    async with _temporary_postgres_database(_pg_engine) as database_url:
        with pytest.raises(RuntimeError, match="injected migration failure"):
            await run_migrations(database_url)

        engine = create_async_engine(database_url)
        try:
            async with engine.connect() as connection:
                table_names = await connection.run_sync(
                    lambda sync_connection: set(sa.inspect(sync_connection).get_table_names())
                )
            assert "migration_probe" not in table_names
            assert (await check_database_readiness(engine)).ready is False
        finally:
            await engine.dispose()
