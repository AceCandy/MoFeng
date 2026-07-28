from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.api.routers.tasks import (
    _get_snapshot,
    _resolve_event_cursor,
    _resolve_stream_scope,
    _serialize_event,
    _sse_event,
    list_background_tasks,
)
from app.services.job_service import JobStreamNotFoundError


def _request(last_event_id: str | None = None) -> Request:
    headers = [] if last_event_id is None else [(b"last-event-id", last_event_id.encode())]
    return Request({"type": "http", "method": "GET", "path": "/", "headers": headers})


def test_sse_event_emits_cursor_as_event_id():
    event = _sse_event("task", {"cursor": 42}, event_id=42)

    assert event == 'id: 42\nevent: task\ndata: {"cursor": 42}\n\n'


def test_last_event_id_and_query_cursor_must_match():
    assert _resolve_event_cursor(_request("12"), None) == 12
    assert _resolve_event_cursor(_request("12"), 12) == 12

    with pytest.raises(HTTPException) as exc_info:
        _resolve_event_cursor(_request("12"), 13)
    assert exc_info.value.status_code == 400


def test_stream_scope_must_be_provided_as_a_pair():
    assert _resolve_stream_scope(None, None) is None
    assert _resolve_stream_scope("workflow", "run-1") == ("workflow", "run-1")

    with pytest.raises(HTTPException) as exc_info:
        _resolve_stream_scope("workflow", None)
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio(loop_scope="session")
async def test_stream_snapshot_hides_missing_and_foreign_stream_as_404(monkeypatch):
    async def missing_stream(self, **kwargs):
        raise JobStreamNotFoundError("未找到任务事件流")

    monkeypatch.setattr(
        "app.api.routers.tasks.JobService.get_stream_snapshot",
        missing_stream,
    )

    with pytest.raises(HTTPException) as exc_info:
        await _get_snapshot(
            object(),
            user_id=1,
            limit=20,
            stream_scope=("workflow", "foreign-run"),
        )
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "未找到任务事件流"


def test_event_serialization_keeps_only_public_task_fields():
    event = SimpleNamespace(
        cursor=7,
        event_type="job.succeeded",
        payload={
            "task": {
                "id": "job-1",
                "user_id": 1,
                "stream_type": "workflow",
                "stream_id": "run-1",
                "task_type": "test",
                "title": "测试任务",
                "status": "succeeded",
                "progress": 100,
                "payload": {"prompt": "private"},
                "result": {"content": "private"},
                "log_entries": [],
                "created_at": "2026-07-28T00:00:00Z",
                "updated_at": "2026-07-28T00:00:01Z",
            }
        },
    )

    serialized = _serialize_event(event)

    assert serialized["cursor"] == 7
    assert serialized["task"]["id"] == "job-1"
    assert serialized["task"]["stream_type"] == "workflow"
    assert serialized["task"]["stream_id"] == "run-1"
    assert "payload" not in serialized["task"]
    assert "result" not in serialized["task"]


@pytest.mark.asyncio(loop_scope="session")
async def test_task_list_hides_private_payload_and_result(monkeypatch):
    now = datetime.now(timezone.utc)
    private_task = SimpleNamespace(
        id="job-private",
        user_id=1,
        project_id=None,
        stream_type="job",
        stream_id="job-private",
        task_type="test",
        title="私有任务",
        status="succeeded",
        progress=100,
        payload={"prompt": "private prompt"},
        result={"content": "private result"},
        error=None,
        log_entries=[],
        created_at=now,
        updated_at=now,
        started_at=now,
        completed_at=now,
    )

    async def list_user_tasks(self, **kwargs):
        return [private_task]

    monkeypatch.setattr(
        "app.api.routers.tasks.BackgroundTaskService.list_user_tasks",
        list_user_tasks,
    )

    tasks = await list_background_tasks(
        limit=20,
        session=object(),
        current_user=SimpleNamespace(id=1),
    )

    assert tasks[0].payload is None
    assert tasks[0].result is None
