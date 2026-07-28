# AIMETA P=数据库运维CLI_显式建库迁移引导检查|R=命令解析_数据库操作编排|NR=不含HTTP接口|E=build_parser_main|X=cli|A=argparse命令|D=sqlalchemy,alembic|S=db|RD=./README.ai
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence

from .bootstrap import BootstrapContractError, run_bootstrap
from .migration import (
    DatabaseMigrationError,
    adopt_legacy_database,
    create_database,
    run_migrations,
)
from .readiness import check_database_readiness, inspect_database_state


def build_parser() -> argparse.ArgumentParser:
    """构建显式数据库运维命令解析器。"""

    parser = argparse.ArgumentParser(prog="python -m app.db.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("db-create", help="创建目标 PostgreSQL database")
    subparsers.add_parser("db-migrate", help="执行 Alembic upgrade head")

    adopt = subparsers.add_parser(
        "db-adopt-legacy",
        help="显式认领与冻结 baseline 完全匹配的旧库",
    )
    adopt.add_argument("--operator", required=True)
    adopt.add_argument("--expected-fingerprint", required=True)
    adopt.add_argument("--backup-confirmed", action="store_true", required=True)

    subparsers.add_parser("db-bootstrap", help="执行缺失的版本化数据引导步骤")
    subparsers.add_parser("db-check", help="只读检查 schema/bootstrap readiness")
    return parser


def _emit(payload: dict[str, object], *, stream=None) -> None:
    print(
        json.dumps(payload, ensure_ascii=False, sort_keys=True),
        file=stream or sys.stdout,
    )


async def _run_command(args: argparse.Namespace) -> int:
    if args.command == "db-create":
        created = await create_database()
        _emit({"command": args.command, "status": "created" if created else "exists"})
        return 0
    if args.command == "db-migrate":
        await run_migrations()
        _emit({"command": args.command, "status": "completed"})
        return 0
    if args.command == "db-adopt-legacy":
        revision = await adopt_legacy_database(
            operator=args.operator,
            expected_fingerprint=args.expected_fingerprint,
            backup_confirmed=args.backup_confirmed,
        )
        _emit({"command": args.command, "revision": revision, "status": "completed"})
        return 0
    if args.command == "db-bootstrap":
        state = await inspect_database_state()
        if not state.reachable:
            raise DatabaseMigrationError("database_unreachable")
        if set(state.database_revisions) != set(state.code_heads) or not state.code_heads:
            raise DatabaseMigrationError("schema_not_at_head")
        result = await run_bootstrap()
        _emit(
            {
                "command": args.command,
                "completed_versions": list(result.completed_versions),
                "skipped_versions": list(result.skipped_versions),
                "status": "completed",
            }
        )
        return 0
    if args.command == "db-check":
        readiness = await check_database_readiness()
        _emit({"command": args.command, **readiness.as_dict()})
        return 0 if readiness.ready else 1
    raise DatabaseMigrationError("unknown_command")


def main(argv: Sequence[str] | None = None) -> int:
    """执行命令并将预期失败转换为无敏感信息的结构化输出。"""

    args = build_parser().parse_args(argv)
    try:
        return asyncio.run(_run_command(args))
    except (BootstrapContractError, DatabaseMigrationError) as exc:
        _emit(
            {
                "command": args.command,
                "status": "failed",
                "error": str(exc),
            },
            stream=sys.stderr,
        )
        return 1
    except Exception:
        _emit(
            {
                "command": args.command,
                "status": "failed",
                "error": "database_operation_failed",
            },
            stream=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
