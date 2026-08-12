from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute

BASELINE_PATH_COUNT = 87
BASELINE_OPERATION_COUNT = 111
BASELINE_SCHEMA_COUNT = 92
BASELINE_OPERATION_ID_SHA256 = "9f3ce62d0ebf49d91bb99c89d7dfaf35d7bbb035ca5dd2cfdd3669a612e0fdd2"
HTTP_METHODS = {"delete", "get", "head", "options", "patch", "post", "put", "trace"}
BACKEND_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_RESPONSE_SCHEMAS = {
    ("post", "/api/writer/chapter-workflows", "202"): "ChapterWorkflowStartResponse",
    ("get", "/api/writer/chapter-workflows/{run_id}", "200"): "ChapterWorkflowSnapshot",
    (
        "post",
        "/api/writer/chapter-workflows/{run_id}/commands",
        "202",
    ): "ChapterWorkflowCommandResponse",
    (
        "post",
        "/api/writer/novels/{project_id}/chapters/edit-fast",
        "200",
    ): "Chapter",
    ("get", "/api/tasks/snapshot", "200"): "BackgroundTaskSnapshotResponse",
    ("get", "/api/tasks/{task_id}", "200"): "BackgroundTaskResponse",
    (
        "get",
        "/api/novels/{project_id}/chapters/{chapter_number}",
        "200",
    ): "Chapter",
    (
        "get",
        "/api/admin/novel-projects/{project_id}",
        "200",
    ): "NovelProject",
    (
        "get",
        "/api/admin/novel-projects/{project_id}/chapters/{chapter_number}",
        "200",
    ): "Chapter",
    ("get", "/api/admin/stats", "200"): "Statistics",
    (
        "post",
        "/api/admin/chapter-projections/dry-run",
        "200",
    ): "ChapterProjectionOperationResponse",
    (
        "get",
        "/api/admin/chapter-projections/rollouts/{chapter_id}",
        "200",
    ): "ChapterProjectionRolloutResponse",
}


def _operation_items(schema: dict[str, Any]) -> Iterator[tuple[str, str, dict[str, Any]]]:
    for path, path_item in schema["paths"].items():
        for method, operation in path_item.items():
            if method in HTTP_METHODS:
                yield path, method, operation


def _operation_ids(schema: dict[str, Any]) -> list[str]:
    return [operation["operationId"] for _, _, operation in _operation_items(schema)]


def _fresh_application_schema() -> dict[str, Any]:
    from app.main import app

    app.openapi_schema = None
    return app.openapi()


def _run_export(
    output: Path, *, hash_seed: int, check: bool = False
) -> subprocess.CompletedProcess[str]:
    private_secret = "private-openapi-test-secret-that-must-not-leak"
    private_database = "postgresql+asyncpg://private:private@127.0.0.1:9/private"
    environment = os.environ.copy()
    environment.update(
        {
            "APP_NAME": "private-openapi-test-title",
            "DATABASE_URL": private_database,
            "PYTHONHASHSEED": str(hash_seed),
            "SECRET_KEY": private_secret,
        }
    )
    command = [sys.executable, "-m", "app.openapi_export", "--output", str(output)]
    if check:
        command.append("--check")
    return subprocess.run(
        command,
        cwd=BACKEND_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


def test_openapi_inventory_and_operation_ids_preserve_the_baseline() -> None:
    schema = _fresh_application_schema()
    operations = list(_operation_items(schema))
    operation_ids = _operation_ids(schema)

    assert schema["openapi"] == "3.1.0"
    assert len(schema["paths"]) == BASELINE_PATH_COUNT
    assert len(operations) == BASELINE_OPERATION_COUNT
    assert len(schema["components"]["schemas"]) >= BASELINE_SCHEMA_COUNT
    assert len(operation_ids) == len(set(operation_ids))
    assert hashlib.sha256("\n".join(sorted(operation_ids)).encode()).hexdigest() == (
        BASELINE_OPERATION_ID_SHA256
    )


def test_task_sse_components_are_explicit_and_versioned() -> None:
    schema = _fresh_application_schema()
    schemas = schema["components"]["schemas"]

    for name in (
        "BackgroundTaskSnapshotResponse",
        "BackgroundTaskEventResponse",
        "BackgroundTaskCursorResetResponse",
    ):
        component = schemas[name]
        assert "schema_version" in component["required"]
        assert component["properties"]["schema_version"]["const"] == 1

    success_content = schema["paths"]["/api/tasks/events"]["get"]["responses"]["200"]["content"]
    assert set(success_content) == {"text/event-stream"}


def test_in_scope_json_operations_reference_explicit_models() -> None:
    schema = _fresh_application_schema()

    for (method, path, status), component_name in EXPECTED_RESPONSE_SCHEMAS.items():
        response_schema = schema["paths"][path][method]["responses"][status]["content"][
            "application/json"
        ]["schema"]
        assert response_schema["$ref"] == f"#/components/schemas/{component_name}"

    task_list_schema = schema["paths"]["/api/tasks"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]
    assert task_list_schema["items"]["$ref"] == ("#/components/schemas/BackgroundTaskResponse")


def test_framework_request_schemas_preserve_published_metadata() -> None:
    schema = _fresh_application_schema()
    schemas = schema["components"]["schemas"]

    def request_properties(path: str, media_type: str) -> dict[str, Any]:
        reference = schema["paths"][path]["post"]["requestBody"]["content"][media_type]["schema"][
            "$ref"
        ]
        return schemas[reference.rsplit("/", maxsplit=1)[-1]]["properties"]

    login = request_properties("/api/auth/token", "application/x-www-form-urlencoded")
    assert "format" not in login["client_secret"]
    assert "format" not in login["password"]

    novel_import = request_properties("/api/novels/import", "multipart/form-data")
    assert novel_import["file"]["format"] == "binary"
    assert "contentMediaType" not in novel_import["file"]


def test_stable_operation_id_is_legacy_compatible_and_fail_closed() -> None:
    from app.openapi_schema import stable_operation_id

    async def read_widget() -> None:
        return None

    route = APIRoute("/widgets/{widget_id}", read_widget, methods=["GET"])
    assert stable_operation_id(route) == "read_widget_widgets__widget_id__get"

    explicit = APIRoute(
        "/renamed",
        read_widget,
        methods=["GET"],
        operation_id="legacy_operation_id",
    )
    assert stable_operation_id(explicit) == "legacy_operation_id"

    multiple = APIRoute("/multiple", read_widget, methods=["POST", "GET"])
    with pytest.raises(ValueError, match="exactly one HTTP method"):
        stable_operation_id(multiple)

    route.methods = set()
    with pytest.raises(ValueError, match="exactly one HTTP method"):
        stable_operation_id(route)


def test_openapi_builder_rejects_duplicate_ids_and_multi_method_routes() -> None:
    from app.openapi_schema import build_openapi_schema, stable_operation_id

    duplicate_app = FastAPI(generate_unique_id_function=stable_operation_id)

    @duplicate_app.get("/first", operation_id="duplicate_operation")
    async def first() -> None:
        return None

    @duplicate_app.get("/second", operation_id="duplicate_operation")
    async def second() -> None:
        return None

    with pytest.raises(ValueError, match="duplicate operationId"):
        build_openapi_schema(duplicate_app)

    multi_method_app = FastAPI(generate_unique_id_function=stable_operation_id)

    @multi_method_app.api_route(
        "/multiple",
        methods=["GET", "POST"],
        operation_id="explicit_multi_method",
    )
    async def multiple() -> None:
        return None

    with pytest.raises(ValueError, match="exactly one HTTP method"):
        build_openapi_schema(multi_method_app)


def test_openapi_builder_is_registration_order_independent() -> None:
    from app.openapi_schema import build_openapi_schema, stable_operation_id

    def build(paths: tuple[str, ...]) -> dict[str, str]:
        local_app = FastAPI(generate_unique_id_function=stable_operation_id)

        async def read_item() -> None:
            return None

        for path in paths:
            local_app.add_api_route(path, read_item, methods=["GET"])
        schema = build_openapi_schema(local_app)
        return {path: operation["operationId"] for path, _, operation in _operation_items(schema)}

    assert build(("/alpha", "/beta")) == build(("/beta", "/alpha"))


def test_openapi_generation_does_not_enter_lifespan(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.main as main_module

    async def fail_readiness() -> None:
        raise AssertionError("OpenAPI generation entered application lifespan")

    monkeypatch.setattr(main_module, "check_database_readiness", fail_readiness)
    main_module.app.openapi_schema = None
    schema = main_module.app.openapi()

    assert schema["paths"]


def test_exporter_is_hermetic_deterministic_and_check_is_read_only(tmp_path: Path) -> None:
    first_output = tmp_path / "first.json"
    second_output = tmp_path / "second.json"

    first = _run_export(first_output, hash_seed=1)
    second = _run_export(second_output, hash_seed=2)
    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr

    first_bytes = first_output.read_bytes()
    assert first_bytes == second_output.read_bytes()
    assert first_bytes.endswith(b"\n") and not first_bytes.endswith(b"\n\n")
    assert json.loads(first_bytes)["openapi"] == "3.1.0"
    for forbidden in (
        b"private-openapi-test-secret",
        b"postgresql+asyncpg://private",
        b"private-openapi-test-title",
        str(BACKEND_ROOT).encode(),
        str(tmp_path).encode(),
    ):
        assert forbidden not in first_bytes

    before = first_output.stat().st_mtime_ns
    check = _run_export(first_output, hash_seed=3, check=True)
    assert check.returncode == 0, check.stderr
    assert first_output.stat().st_mtime_ns == before


def test_semantic_diff_unsupported_constructs_fail_closed() -> None:
    from app.openapi_schema import validate_openapi_document

    base = {
        "openapi": "3.1.0",
        "info": {"title": "test", "version": "1"},
        "paths": {},
    }
    for unsupported in (
        {"components": {"schemas": {"Example": {"$dynamicRef": "#example"}}}},
        {"components": {"schemas": {"Example": {"$dynamicAnchor": "example"}}}},
        {"components": {"pathItems": {"Example": {}}}},
    ):
        document = {**base, **unsupported}
        with pytest.raises(ValueError, match="unsupported OpenAPI construct"):
            validate_openapi_document(document)
