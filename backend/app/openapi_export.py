# AIMETA P=OpenAPI契约导出_确定性文件生成与漂移检查|R=固定环境_原子写入_只读check|NR=不启动ASGI或数据库生命周期|E=python_-m_app.openapi_export|X=internal|A=cli|D=app.openapi_schema|S=fs|RD=./README.ai
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Sequence

OPENAPI_TITLE = "AI Novel Generator API"
OPENAPI_VERSION = "1.0.0"
EXPORT_ENVIRONMENT = {
    "APP_NAME": OPENAPI_TITLE,
    "BOOTSTRAP_CREATE_DEFAULT_ADMIN": "false",
    "DATABASE_URL": "postgresql+asyncpg://openapi:openapi@127.0.0.1:1/openapi_contract",
    "DEBUG": "false",
    "ENVIRONMENT": "development",
    "SECRET_KEY": "mofeng-openapi-contract-sentinel-000000000000000000000000",
}


def _configure_export_environment() -> None:
    for name, value in EXPORT_ENVIRONMENT.items():
        os.environ[name] = value


def build_export_document() -> dict[str, Any]:
    _configure_export_environment()
    from .main import app
    from .openapi_schema import validate_openapi_document

    app.title = OPENAPI_TITLE
    app.version = OPENAPI_VERSION
    app.openapi_schema = None
    document: dict[str, Any] = app.openapi()
    document["info"]["title"] = OPENAPI_TITLE
    document["info"]["version"] = OPENAPI_VERSION
    validate_openapi_document(document)
    return document


def canonical_openapi_bytes() -> bytes:
    serialized = json.dumps(
        build_export_document(),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    return f"{serialized}\n".encode("utf-8")


def _atomic_write(output: Path, content: bytes) -> None:
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=output.parent,
            prefix=f".{output.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.chmod(temporary_path, 0o644)
        os.replace(temporary_path, output)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _check_output(output: Path, expected: bytes) -> bool:
    try:
        actual = output.read_bytes()
    except FileNotFoundError:
        return False
    return actual == expected


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export the canonical FastAPI OpenAPI contract")
    parser.add_argument("--output", type=Path, default=Path("openapi.json"))
    parser.add_argument("--check", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    try:
        expected = canonical_openapi_bytes()
        if arguments.check:
            if _check_output(arguments.output, expected):
                return 0
            print(f"OpenAPI artifact is out of date: {arguments.output.name}", file=sys.stderr)
            return 1
        _atomic_write(arguments.output, expected)
        return 0
    except (OSError, ValueError) as exc:
        print(f"OpenAPI export failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
