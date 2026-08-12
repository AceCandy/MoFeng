# AIMETA P=OpenAPI契约构建_稳定operationId与额外组件注册|R=构建校验缓存schema|NR=不负责文件导出|E=build_openapi_schema|X=internal|A=contract_builder|D=fastapi,pydantic|S=none|RD=./README.ai
from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any, cast

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.openapi.constants import REF_TEMPLATE
from fastapi.openapi.models import Schema
from fastapi.openapi.utils import get_openapi
from fastapi.routing import APIRoute
from pydantic import BaseModel
from pydantic.json_schema import models_json_schema

from .schemas.task import (
    BackgroundTaskCursorResetResponse,
    BackgroundTaskEventResponse,
    BackgroundTaskSnapshotResponse,
)

HTTP_METHODS = {"delete", "get", "head", "options", "patch", "post", "put", "trace"}
EXTRA_OPENAPI_MODELS: tuple[type[BaseModel], ...] = (
    BackgroundTaskSnapshotResponse,
    BackgroundTaskEventResponse,
    BackgroundTaskCursorResetResponse,
)


def stable_operation_id(route: APIRoute) -> str:
    """保留 FastAPI 0.110.0 单 method 命名，同时拒绝非确定性 route。"""

    if route.operation_id is not None:
        if not isinstance(route.operation_id, str) or not route.operation_id:
            raise ValueError("operationId must not be empty")
        return route.operation_id
    methods = route.methods or set()
    if len(methods) != 1:
        raise ValueError("OpenAPI routes must declare exactly one HTTP method")
    method = next(iter(methods)).lower()
    prefix = re.sub(r"\W", "_", f"{route.name}{route.path_format}")
    return f"{prefix}_{method}"


def _validate_routes(routes: Iterable[object]) -> None:
    operation_ids: dict[str, str] = {}
    for route in routes:
        if not isinstance(route, APIRoute) or not route.include_in_schema:
            continue
        if len(route.methods or set()) != 1:
            raise ValueError("OpenAPI routes must declare exactly one HTTP method")
        operation_id = route.operation_id or route.unique_id
        if not operation_id:
            raise ValueError(f"missing operationId for route {route.path_format}")
        previous = operation_ids.get(operation_id)
        if previous is not None:
            raise ValueError(
                f"duplicate operationId {operation_id!r} for {previous} and {route.path_format}"
            )
        operation_ids[operation_id] = route.path_format


def _extra_model_definitions() -> dict[str, dict[str, Any]]:
    _, schema = models_json_schema(
        [(model, "validation") for model in EXTRA_OPENAPI_MODELS],
        ref_template=REF_TEMPLATE,
    )
    raw_definitions = schema.get("$defs")
    if not isinstance(raw_definitions, dict):
        raise ValueError("extra OpenAPI models did not produce schema definitions")
    return {
        name: jsonable_encoder(
            Schema.model_validate(definition),
            by_alias=True,
            exclude_none=True,
        )
        for name, definition in raw_definitions.items()
    }


def _register_extra_models(document: dict[str, Any]) -> None:
    components = document.setdefault("components", {})
    schemas = components.setdefault("schemas", {})
    if not isinstance(schemas, dict):
        raise ValueError("OpenAPI components.schemas must be an object")
    for name, definition in _extra_model_definitions().items():
        existing = schemas.get(name)
        if existing is not None and existing != definition:
            raise ValueError(f"OpenAPI schema collision for {name}")
        schemas[name] = definition
    components["schemas"] = {name: schemas[name] for name in sorted(schemas)}


def _request_body_schema(
    document: dict[str, Any],
    *,
    path: str,
    media_type: str,
) -> dict[str, Any] | None:
    schema = (
        document.get("paths", {})
        .get(path, {})
        .get("post", {})
        .get("requestBody", {})
        .get("content", {})
        .get(media_type, {})
        .get("schema", {})
    )
    reference = schema.get("$ref") if isinstance(schema, dict) else None
    prefix = "#/components/schemas/"
    if not isinstance(reference, str) or not reference.startswith(prefix):
        return None
    schemas = document.get("components", {}).get("schemas", {})
    component = schemas.get(reference.removeprefix(prefix))
    return component if isinstance(component, dict) else None


def _preserve_request_schema_compatibility(document: dict[str, Any]) -> None:
    """稳定框架升级前已经发布的登录与文件上传 schema。"""

    login = _request_body_schema(
        document,
        path="/api/auth/token",
        media_type="application/x-www-form-urlencoded",
    )
    login_properties = login.get("properties", {}) if login else {}
    for field_name in ("client_secret", "password"):
        field = login_properties.get(field_name)
        if isinstance(field, dict) and field.get("format") == "password":
            field.pop("format")

    novel_import = _request_body_schema(
        document,
        path="/api/novels/import",
        media_type="multipart/form-data",
    )
    import_properties = novel_import.get("properties", {}) if novel_import else {}
    file_schema = import_properties.get("file")
    if (
        isinstance(file_schema, dict)
        and file_schema.get("contentMediaType") == "application/octet-stream"
    ):
        file_schema.pop("contentMediaType")
        file_schema["format"] = "binary"


def validate_openapi_document(document: dict[str, Any]) -> None:
    """拒绝不完整 operationId 与 pinned oasdiff 无法可靠解析的结构。"""

    components = document.get("components")
    if isinstance(components, dict) and "pathItems" in components:
        raise ValueError("unsupported OpenAPI construct: components.pathItems")

    def reject_dynamic_keywords(value: object) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                if key in {"$dynamicRef", "$dynamicAnchor"}:
                    raise ValueError(f"unsupported OpenAPI construct: {key}")
                reject_dynamic_keywords(nested)
        elif isinstance(value, list):
            for nested in value:
                reject_dynamic_keywords(nested)

    reject_dynamic_keywords(document)

    paths = document.get("paths")
    if not isinstance(paths, dict):
        raise ValueError("OpenAPI paths must be an object")
    operation_ids: dict[str, str] = {}
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method not in HTTP_METHODS or not isinstance(operation, dict):
                continue
            operation_id = operation.get("operationId")
            if not isinstance(operation_id, str) or not operation_id:
                raise ValueError(f"missing operationId for {method.upper()} {path}")
            previous = operation_ids.get(operation_id)
            if previous is not None:
                raise ValueError(
                    f"duplicate operationId {operation_id!r} for {previous} and {method.upper()} {path}"
                )
            operation_ids[operation_id] = f"{method.upper()} {path}"


def build_openapi_schema(application: FastAPI) -> dict[str, Any]:
    _validate_routes(application.routes)
    document: dict[str, Any] = get_openapi(
        title=application.title,
        version=application.version,
        openapi_version=application.openapi_version,
        summary=application.summary,
        description=application.description,
        routes=application.routes,
        webhooks=application.webhooks.routes,
        tags=application.openapi_tags,
        servers=application.servers,
        terms_of_service=application.terms_of_service,
        contact=application.contact,
        license_info=application.license_info,
        separate_input_output_schemas=application.separate_input_output_schemas,
    )
    _register_extra_models(document)
    _preserve_request_schema_compatibility(document)
    validate_openapi_document(document)
    return document


def install_openapi_schema(application: FastAPI) -> None:
    def openapi() -> dict[str, Any]:
        if application.openapi_schema is None:
            application.openapi_schema = build_openapi_schema(application)
        return cast(dict[str, Any], application.openapi_schema)

    application.openapi_schema = None
    setattr(application, "openapi", openapi)
