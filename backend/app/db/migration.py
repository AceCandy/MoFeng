# AIMETA P=数据库Schema迁移_旧库指纹与显式认领|R=建库_Alembic迁移_旧库审计|NR=不含业务种子|E=create_database_run_migrations_adopt_legacy_database|X=internal|A=迁移编排|D=sqlalchemy,alembic|S=db|RD=./README.ai
from __future__ import annotations

import asyncio
import hashlib
import json
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from alembic import command
from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory
from sqlalchemy.engine import Connection, URL, make_url
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from ..core.config import settings
from ..models.database_bootstrap import LegacyDatabaseAdoption

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"
_MIGRATION_LOCK_KEY = 0x4D4F464D4947
_OPERATIONAL_TABLES = {
    "alembic_version",
    "database_bootstrap_versions",
    "legacy_database_adoptions",
}

# 由 2026-07-28 的 pre-bootstrap ORM schema 生成；该结构对应旧 runtime 认为的 17a89f head。
_LEGACY_HEAD_FINGERPRINT = "0a9efa15dd30c365ec2ea13ade9ed013d4bf574c50166f0f8ae3453daf7dffc4"
KNOWN_LEGACY_BASELINES: Mapping[str, str] = {
    _LEGACY_HEAD_FINGERPRINT: "17a89f18291c",
}


class DatabaseMigrationError(RuntimeError):
    """显式数据库迁移命令无法安全继续。"""


class LegacyDatabaseRequiresAdoption(DatabaseMigrationError):
    """无 Alembic 版本的业务库必须先由 operator 显式认领。"""

    def __init__(self, reason: str, fingerprint: str | None = None) -> None:
        self.reason = reason
        self.fingerprint = fingerprint
        detail = f"{reason}; fingerprint={fingerprint}" if fingerprint else reason
        super().__init__(detail)


_UNORDERED_SEQUENCE_FIELDS = {
    "check_constraints",
    "foreign_keys",
    "indexes",
    "tables",
    "unique_constraints",
}


def _canonical_sort_key(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


def _canonicalize(value: Any, *, field: str | None = None) -> Any:
    if isinstance(value, Mapping):
        return {
            key: _canonicalize(value[key], field=str(key))
            for key in sorted(value)
        }
    if isinstance(value, (set, frozenset)):
        return sorted((_canonicalize(item) for item in value), key=_canonical_sort_key)
    if isinstance(value, (list, tuple)):
        normalized = [_canonicalize(item) for item in value]
        # Table/constraint collections are unordered, while composite key/index
        # column order is part of the schema contract.
        if field in _UNORDERED_SEQUENCE_FIELDS or (
            field == "columns" and all(isinstance(item, Mapping) for item in normalized)
        ):
            return sorted(normalized, key=_canonical_sort_key)
        return normalized
    return value


def canonical_schema_fingerprint(manifest: Mapping[str, Any]) -> str:
    """对结构 manifest 排序并生成稳定 SHA-256 指纹。"""

    payload = json.dumps(
        _canonicalize(manifest),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def classify_database_tables(table_names: set[str]) -> str:
    """将数据库分为空库、Alembic 管理库或必须显式认领的旧库。"""

    if not table_names:
        return "empty"
    if "alembic_version" in table_names:
        return "versioned"
    return "legacy"


def resolve_legacy_baseline(fingerprint: str) -> str:
    """仅解析代码冻结登记过的旧库指纹。"""

    revision = KNOWN_LEGACY_BASELINES.get(fingerprint)
    if revision is None:
        raise LegacyDatabaseRequiresAdoption("unknown_legacy_schema", fingerprint)
    return revision


def _normalize_type(column_type: sa.types.TypeEngine[Any]) -> str:
    if isinstance(column_type, sa.BigInteger):
        return "big_integer"
    if isinstance(column_type, sa.Integer):
        return "integer"
    if isinstance(column_type, sa.Boolean):
        return "boolean"
    if isinstance(column_type, sa.DateTime):
        return "datetime:tz" if column_type.timezone else "datetime"
    if isinstance(column_type, sa.Text):
        return "text"
    if isinstance(column_type, sa.String):
        return f"string:{column_type.length}" if column_type.length else "string"
    if isinstance(column_type, sa.JSON):
        return "json"
    if isinstance(column_type, sa.Float):
        return "float"
    if isinstance(column_type, sa.Numeric):
        return f"numeric:{column_type.precision}:{column_type.scale}"
    return str(column_type).strip().lower().replace(" ", "_")


def _columns_manifest(columns: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "name": str(column["name"]),
            "type": _normalize_type(column["type"]),
            "nullable": bool(column.get("nullable", True)),
        }
        for column in columns
    ]


def _normalize_check_constraint(sqltext: Any) -> str:
    return " ".join(str(sqltext).split())


def inspect_schema_manifest(connection: Connection) -> dict[str, Any]:
    """反射数据库的稳定语义结构，排除 migration/bootstrap 自身的表。"""

    inspector = sa.inspect(connection)
    tables: list[dict[str, Any]] = []
    for table_name in sorted(set(inspector.get_table_names()) - _OPERATIONAL_TABLES):
        primary_key = inspector.get_pk_constraint(table_name)
        unique_constraints = inspector.get_unique_constraints(table_name)
        foreign_keys = inspector.get_foreign_keys(table_name)
        indexes = inspector.get_indexes(table_name)
        check_constraints = inspector.get_check_constraints(table_name)
        tables.append(
            {
                "name": table_name,
                "columns": _columns_manifest(inspector.get_columns(table_name)),
                "primary_key": list(primary_key.get("constrained_columns") or ()),
                "unique_constraints": [
                    list(constraint.get("column_names") or ())
                    for constraint in unique_constraints
                ],
                "foreign_keys": [
                    {
                        "columns": list(foreign_key.get("constrained_columns") or ()),
                        "referred_table": foreign_key.get("referred_table"),
                        "referred_columns": list(
                            foreign_key.get("referred_columns") or ()
                        ),
                        "ondelete": (foreign_key.get("options") or {}).get("ondelete"),
                    }
                    for foreign_key in foreign_keys
                ],
                "indexes": [
                    {
                        "columns": list(index.get("column_names") or ()),
                        "unique": bool(index.get("unique", False)),
                    }
                    for index in indexes
                    if all(index.get("column_names") or ())
                    and not index.get("duplicates_constraint")
                ],
                "check_constraints": [
                    _normalize_check_constraint(constraint["sqltext"])
                    for constraint in check_constraints
                    if constraint.get("sqltext")
                ],
            }
        )
    return {"tables": tables}


def metadata_schema_manifest(metadata: sa.MetaData) -> dict[str, Any]:
    """生成与数据库反射同构的 manifest，用于维护冻结 baseline。"""

    tables: list[dict[str, Any]] = []
    for table_name in sorted(set(metadata.tables) - _OPERATIONAL_TABLES):
        table = metadata.tables[table_name]
        unique_constraints = [
            list(constraint.columns.keys())
            for constraint in table.constraints
            if isinstance(constraint, sa.UniqueConstraint)
        ]
        foreign_keys = [
            {
                "columns": list(constraint.columns.keys()),
                "referred_table": next(iter(constraint.elements)).column.table.name,
                "referred_columns": [element.column.name for element in constraint.elements],
                "ondelete": constraint.ondelete,
            }
            for constraint in table.constraints
            if isinstance(constraint, sa.ForeignKeyConstraint)
        ]
        check_constraints = [
            _normalize_check_constraint(constraint.sqltext)
            for constraint in table.constraints
            if isinstance(constraint, sa.CheckConstraint)
        ]
        tables.append(
            {
                "name": table_name,
                "columns": [
                    {
                        "name": column.name,
                        "type": _normalize_type(column.type),
                        "nullable": column.nullable,
                    }
                    for column in table.columns
                ],
                "primary_key": list(table.primary_key.columns.keys()),
                "unique_constraints": unique_constraints,
                "foreign_keys": foreign_keys,
                "indexes": [
                    {
                        "columns": [column.name for column in index.columns],
                        "unique": index.unique,
                    }
                    for index in table.indexes
                ],
                "check_constraints": check_constraints,
            }
        )
    return {"tables": tables}


def build_alembic_config(database_url: str | None = None) -> AlembicConfig:
    """构建不依赖当前工作目录的 Alembic 配置。"""

    configured_url = database_url or settings.sqlalchemy_database_uri
    config = AlembicConfig(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(ALEMBIC_INI.parent / "alembic"))
    config.set_main_option("sqlalchemy.url", configured_url.replace("%", "%%"))
    config.attributes["database_url"] = configured_url
    return config


def get_code_heads(database_url: str | None = None) -> tuple[str, ...]:
    """读取代码中登记的所有 Alembic heads，不连接数据库。"""

    script = ScriptDirectory.from_config(build_alembic_config(database_url))
    return tuple(sorted(script.get_heads()))


async def wait_for_database(
    engine: AsyncEngine,
    *,
    timeout_seconds: float = 180.0,
    retry_interval_seconds: float = 1.0,
) -> None:
    """在部署 one-shot 进程内等待目标数据库可连接。"""

    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            async with engine.connect() as connection:
                await connection.execute(sa.text("SELECT 1"))
            return
        except (OSError, sa.exc.SQLAlchemyError) as exc:
            if time.monotonic() >= deadline:
                raise DatabaseMigrationError("database_unreachable") from exc
            await asyncio.sleep(retry_interval_seconds)


async def create_database(database_url: str | None = None) -> bool:
    """显式创建 PostgreSQL 目标 database；已存在时返回 False。"""

    target_url = make_url(database_url or settings.sqlalchemy_database_uri)
    if not target_url.drivername.startswith("postgresql"):
        raise DatabaseMigrationError("db-create only supports PostgreSQL")
    database = (target_url.database or "").strip("/")
    if not database:
        raise DatabaseMigrationError("target database name is empty")

    admin_url = URL.create(
        drivername=target_url.drivername,
        username=target_url.username,
        password=target_url.password,
        host=target_url.host,
        port=target_url.port,
        database="postgres",
        query=target_url.query,
    )
    admin_engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        async with admin_engine.connect() as connection:
            exists = await connection.scalar(
                sa.text("SELECT 1 FROM pg_database WHERE datname = :database"),
                {"database": database},
            )
            if exists is not None:
                return False
            quoted_database = connection.dialect.identifier_preparer.quote(database)
            await connection.execute(sa.text(f"CREATE DATABASE {quoted_database}"))
            return True
    finally:
        await admin_engine.dispose()


async def _inspect_connection(
    connection: AsyncConnection,
) -> tuple[set[str], dict[str, Any] | None]:
    table_names = set(await connection.run_sync(lambda sync: sa.inspect(sync).get_table_names()))
    if classify_database_tables(table_names) != "legacy":
        return table_names, None
    manifest = await connection.run_sync(inspect_schema_manifest)
    return table_names, manifest


async def _acquire_migration_lock(connection: AsyncConnection) -> None:
    if connection.dialect.name == "postgresql":
        await connection.execute(
            sa.text("SELECT pg_advisory_xact_lock(:lock_key)"),
            {"lock_key": _MIGRATION_LOCK_KEY},
        )


def _upgrade_on_connection(connection: Connection, database_url: str) -> None:
    config = build_alembic_config(database_url)
    config.attributes["connection"] = connection
    command.upgrade(config, "head")


async def run_migrations(database_url: str | None = None) -> None:
    """仅执行 Alembic upgrade；遇到无版本业务库时携带 fingerprint 拒绝。"""

    configured_url = database_url or settings.sqlalchemy_database_uri
    engine = create_async_engine(configured_url, pool_pre_ping=True)
    try:
        await wait_for_database(engine)
        async with engine.begin() as connection:
            await _acquire_migration_lock(connection)
            table_names, legacy_manifest = await _inspect_connection(connection)
            if classify_database_tables(table_names) == "legacy":
                assert legacy_manifest is not None
                fingerprint = canonical_schema_fingerprint(legacy_manifest)
                raise LegacyDatabaseRequiresAdoption(
                    "legacy_database_requires_adoption",
                    fingerprint,
                )
            await connection.run_sync(_upgrade_on_connection, configured_url)
    finally:
        await engine.dispose()


def _adopt_and_upgrade_on_connection(
    connection: Connection,
    database_url: str,
    revision: str,
) -> None:
    config = build_alembic_config(database_url)
    config.attributes["connection"] = connection
    command.stamp(config, revision)
    command.upgrade(config, "head")


async def adopt_legacy_database(
    *,
    operator: str,
    expected_fingerprint: str,
    backup_confirmed: bool,
    database_url: str | None = None,
) -> str:
    """校验冻结指纹后显式 stamp 已知 revision、升级 head 并写 adoption 审计。"""

    normalized_operator = operator.strip()
    if not normalized_operator:
        raise DatabaseMigrationError("operator is required")
    if not backup_confirmed:
        raise DatabaseMigrationError("backup confirmation is required")

    configured_url = database_url or settings.sqlalchemy_database_uri
    engine = create_async_engine(configured_url, pool_pre_ping=True)
    try:
        await wait_for_database(engine)
        if engine.dialect.name != "postgresql":
            raise DatabaseMigrationError("legacy adoption requires PostgreSQL")
        async with engine.begin() as connection:
            await _acquire_migration_lock(connection)
            table_names, manifest = await _inspect_connection(connection)
            if classify_database_tables(table_names) != "legacy" or manifest is None:
                raise DatabaseMigrationError("database_is_not_legacy")
            actual_fingerprint = canonical_schema_fingerprint(manifest)
            if actual_fingerprint != expected_fingerprint:
                raise LegacyDatabaseRequiresAdoption(
                    "legacy_fingerprint_mismatch",
                    actual_fingerprint,
                )
            revision = resolve_legacy_baseline(actual_fingerprint)
            await connection.run_sync(
                _adopt_and_upgrade_on_connection,
                configured_url,
                revision,
            )
            await connection.execute(
                sa.insert(LegacyDatabaseAdoption).values(
                    schema_fingerprint=actual_fingerprint,
                    adopted_revision=revision,
                    operator=normalized_operator,
                    backup_confirmed=True,
                    result="completed",
                )
            )
        return revision
    finally:
        await engine.dispose()
