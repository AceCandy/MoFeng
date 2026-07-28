# AIMETA P=章节投影共享事件合同|R=outbox版本_事件类型_稳定指纹与finalize_envelope校验|NR=不访问数据库或执行业务流程|E=payload_fingerprint_validate_finalize_outbox_event|X=internal|A=contract|D=pydantic,schema|S=none|RD=./README.ai
"""章节投影生产者、派发器与消费者共享的 immutable outbox 合同。"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal, Protocol

from pydantic import ValidationError

from ..schemas.job import ChapterFinalizeOutboxPayload


FINALIZE_EVENT_TYPE = "ChapterFinalizationRequested"
OUTBOX_EVENT_VERSION = 2
SUPPORTED_EVENT_TYPES = (
    FINALIZE_EVENT_TYPE,
    "ChapterRevisionSuperseded",
    "ChapterTombstoned",
)

FinalizeOutboxValidationError = Literal[
    "event_contract_mismatch",
    "payload_mismatch",
    "invalid_payload",
    "identity_mismatch",
]


class FinalizeOutboxEvent(Protocol):
    """finalize event 校验所需的最小持久化 envelope。"""

    id: str
    aggregate_type: str
    aggregate_id: str
    chapter_id: int | None
    project_id: str | None
    revision: int
    event_type: str
    event_version: int
    payload: Any
    payload_fingerprint: str
    workflow_stream_type: str | None
    workflow_stream_id: str | None


def payload_fingerprint(payload: dict[str, Any]) -> str:
    """按稳定 JSON 表示计算 outbox payload 指纹。"""

    serialized = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def validate_finalize_outbox_event(
    event: FinalizeOutboxEvent,
) -> tuple[
    ChapterFinalizeOutboxPayload | None,
    FinalizeOutboxValidationError | None,
]:
    """统一校验 finalize outbox 的版本、指纹和 envelope/payload identity。"""

    if (
        event.event_type != FINALIZE_EVENT_TYPE
        or event.event_version != OUTBOX_EVENT_VERSION
    ):
        return None, "event_contract_mismatch"
    if not isinstance(event.payload, dict):
        return None, "invalid_payload"
    if payload_fingerprint(event.payload) != event.payload_fingerprint:
        return None, "payload_mismatch"
    try:
        payload = ChapterFinalizeOutboxPayload.model_validate(event.payload)
    except ValidationError:
        return None, "invalid_payload"
    if (
        payload.outbox_event_id != event.id
        or payload.project_id != event.project_id
        or event.aggregate_type != "chapter"
        or event.aggregate_id != str(payload.chapter_id)
        or event.chapter_id not in (None, payload.chapter_id)
        or event.revision != payload.revision
        or event.workflow_stream_type != payload.workflow_stream_type
        or event.workflow_stream_id != payload.workflow_stream_id
    ):
        return None, "identity_mismatch"
    return payload, None


__all__ = [
    "FINALIZE_EVENT_TYPE",
    "OUTBOX_EVENT_VERSION",
    "SUPPORTED_EVENT_TYPES",
    "payload_fingerprint",
    "validate_finalize_outbox_event",
]
