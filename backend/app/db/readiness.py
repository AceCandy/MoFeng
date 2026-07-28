# AIMETA P=数据库就绪检查_Schema和Bootstrap契约|R=连接_AlembicHead_引导账本检查|NR=不含修复和写入|E=check_database_readiness|X=internal|A=只读检查器|D=sqlalchemy,alembic|S=db|RD=./README.ai
from __future__ import annotations

from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine

from ..models.database_bootstrap import DatabaseBootstrapVersion
from .bootstrap import BOOTSTRAP_STEPS, CURRENT_BOOTSTRAP_BINARY_VERSION
from .migration import get_code_heads
from .session import engine as application_engine


@dataclass(frozen=True)
class BootstrapLedgerState:
    """readiness 所需的单条 bootstrap ledger 投影。"""

    version: int
    name: str
    status: str
    checksum: str
    minimum_binary_version: int


@dataclass(frozen=True)
class DatabaseState:
    """一次数据库只读探测结果。"""

    reachable: bool
    database_revisions: tuple[str, ...] = ()
    code_heads: tuple[str, ...] = ()
    bootstrap_rows: tuple[BootstrapLedgerState, ...] = ()
    probe_error_code: str | None = None


@dataclass(frozen=True)
class DatabaseReadiness:
    """供 HTTP/CLI 返回的稳定 readiness 结果。"""

    ready: bool
    codes: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "status": "ready" if self.ready else "not_ready",
            "codes": list(self.codes),
        }


def evaluate_database_readiness(state: DatabaseState) -> DatabaseReadiness:
    """只比较已采集状态，不连接数据库也不触发任何修复。"""

    if not state.reachable:
        return DatabaseReadiness(
            False,
            (state.probe_error_code or "database_unreachable",),
        )

    codes: list[str] = []
    if set(state.database_revisions) != set(state.code_heads) or not state.code_heads:
        codes.append("schema_not_at_head")

    rows_by_version = {row.version: row for row in state.bootstrap_rows}
    incomplete = False
    contract_mismatch = False
    for step in BOOTSTRAP_STEPS:
        row = rows_by_version.get(step.version)
        if row is None or row.status != "completed":
            incomplete = True
            continue
        if (
            row.name != step.name
            or row.checksum != step.checksum
            or row.minimum_binary_version != step.minimum_binary_version
        ):
            contract_mismatch = True
    if incomplete:
        codes.append("bootstrap_incomplete")
    if contract_mismatch:
        codes.append("bootstrap_contract_mismatch")
    if any(
        row.minimum_binary_version > CURRENT_BOOTSTRAP_BINARY_VERSION
        for row in state.bootstrap_rows
    ):
        codes.append("binary_below_rollback_floor")

    return DatabaseReadiness(not codes, tuple(codes))


async def inspect_database_state(
    engine: AsyncEngine = application_engine,
) -> DatabaseState:
    """读取连接、Alembic revision 与 bootstrap ledger，不写数据库。"""

    try:
        code_heads = get_code_heads()
    except Exception:
        return DatabaseState(
            reachable=False,
            probe_error_code="readiness_check_failed",
        )
    try:
        async with engine.connect() as connection:
            await connection.execute(sa.text("SELECT 1"))
            table_names = set(
                await connection.run_sync(lambda sync: sa.inspect(sync).get_table_names())
            )
            database_revisions: tuple[str, ...] = ()
            if "alembic_version" in table_names:
                revisions = await connection.scalars(
                    sa.text("SELECT version_num FROM alembic_version")
                )
                database_revisions = tuple(sorted(str(value) for value in revisions))

            bootstrap_rows: tuple[BootstrapLedgerState, ...] = ()
            if DatabaseBootstrapVersion.__tablename__ in table_names:
                rows = await connection.execute(
                    sa.select(
                        DatabaseBootstrapVersion.version,
                        DatabaseBootstrapVersion.name,
                        DatabaseBootstrapVersion.status,
                        DatabaseBootstrapVersion.checksum,
                        DatabaseBootstrapVersion.minimum_binary_version,
                    ).order_by(DatabaseBootstrapVersion.version)
                )
                bootstrap_rows = tuple(
                    BootstrapLedgerState(
                        version=row.version,
                        name=row.name,
                        status=row.status,
                        checksum=row.checksum,
                        minimum_binary_version=row.minimum_binary_version,
                    )
                    for row in rows
                )
        return DatabaseState(
            reachable=True,
            database_revisions=database_revisions,
            code_heads=code_heads,
            bootstrap_rows=bootstrap_rows,
        )
    except (OSError, sa.exc.SQLAlchemyError):
        return DatabaseState(reachable=False, code_heads=code_heads)
    except Exception:
        return DatabaseState(
            reachable=False,
            code_heads=code_heads,
            probe_error_code="readiness_check_failed",
        )


async def check_database_readiness(
    engine: AsyncEngine = application_engine,
) -> DatabaseReadiness:
    """动态执行一次只读数据库 readiness 检查。"""

    return evaluate_database_readiness(await inspect_database_state(engine))
