# AIMETA P=后台任务API_查询用户任务和日志|R=任务列表_任务详情_SSE推送|NR=不含任务创建|E=route:/api/tasks|X=http|A=query|D=fastapi|S=db|RD=./README.ai
import asyncio
import json
import logging
from typing import AsyncGenerator, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import get_current_user
from ...db.session import AsyncSessionLocal, get_session
from ...models.job import JobEvent
from ...schemas.task import (
    BackgroundTaskCursorResetResponse,
    BackgroundTaskEventResponse,
    BackgroundTaskResponse,
    BackgroundTaskSnapshotResponse,
)
from ...schemas.user import UserInDB
from ...services.background_task_service import BackgroundTaskService
from ...services.event_bus import subscribe_background_task
from ...services.job_service import (
    EventCursorExpiredError,
    JobService,
    JobSnapshot,
    JobStreamNotFoundError,
)

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/tasks", tags=["Tasks"])


def _sse_event(event: str, payload: object, *, event_id: Optional[int] = None) -> str:
    lines = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.extend(
        [
            f"event: {event}",
            f"data: {json.dumps(payload, ensure_ascii=False)}",
        ]
    )
    return "\n".join(lines) + "\n\n"


def _resolve_event_cursor(request: Request, cursor: Optional[int]) -> Optional[int]:
    header_value = request.headers.get("last-event-id")
    if not header_value:
        return cursor
    try:
        header_cursor = int(header_value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Last-Event-ID 必须是非负整数") from exc
    if header_cursor < 0:
        raise HTTPException(status_code=400, detail="Last-Event-ID 必须是非负整数")
    if cursor is not None and cursor != header_cursor:
        raise HTTPException(status_code=400, detail="cursor 与 Last-Event-ID 不一致")
    return header_cursor


def _resolve_stream_scope(
    stream_type: Optional[str],
    stream_id: Optional[str],
) -> Optional[tuple[str, str]]:
    if stream_type is None and stream_id is None:
        return None
    if stream_type is None or stream_id is None:
        raise HTTPException(
            status_code=400,
            detail="stream_type 与 stream_id 必须同时提供",
        )
    return stream_type, stream_id


async def _get_snapshot(
    session: AsyncSession,
    *,
    user_id: int,
    limit: int,
    stream_scope: Optional[tuple[str, str]],
) -> JobSnapshot:
    service = JobService(session)
    try:
        if stream_scope is None:
            return await service.get_snapshot(user_id=user_id, limit=limit)
        return await service.get_stream_snapshot(
            user_id=user_id,
            stream_type=stream_scope[0],
            stream_id=stream_scope[1],
            limit=limit,
        )
    except JobStreamNotFoundError as exc:
        raise HTTPException(status_code=404, detail="未找到任务事件流") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _public_task_response(
    task: object,
    *,
    include_result: bool = False,
) -> BackgroundTaskResponse:
    response = BackgroundTaskResponse.model_validate(task)
    return response.model_copy(
        update={
            "payload": None,
            "result": response.result if include_result else None,
        }
    )


def _serialize_snapshot(snapshot: JobSnapshot) -> dict:
    return BackgroundTaskSnapshotResponse(
        schema_version=1,
        tasks=[_public_task_response(job) for job in snapshot.jobs],
        snapshot_revision=snapshot.snapshot_revision,
        resume_cursor=snapshot.resume_cursor,
        stream_type=snapshot.stream_type,
        stream_id=snapshot.stream_id,
    ).model_dump(mode="json", exclude_none=True)


def _serialize_event(event: JobEvent) -> dict:
    task_payload = event.payload.get("task") if isinstance(event.payload, dict) else None
    if not isinstance(task_payload, dict):
        raise ValueError("任务事件缺少 public task snapshot")
    return BackgroundTaskEventResponse(
        schema_version=1,
        cursor=event.cursor,
        event_type=event.event_type,
        task=_public_task_response(task_payload),
    ).model_dump(mode="json", exclude_none=True)


def _sse_response(stream: AsyncGenerator[str, None]) -> StreamingResponse:
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("", response_model=list[BackgroundTaskResponse])
async def list_background_tasks(
    limit: int = Query(default=20, ge=1, le=50),
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> list[BackgroundTaskResponse]:
    service = BackgroundTaskService(session)
    tasks = await service.list_user_tasks(user_id=current_user.id, limit=limit)
    return [_public_task_response(task) for task in tasks]


@router.get(
    "/snapshot",
    response_model=BackgroundTaskSnapshotResponse,
    response_model_exclude_none=True,
)
async def get_background_task_snapshot(
    limit: int = Query(default=20, ge=1, le=50),
    stream_type: Optional[str] = Query(default=None, max_length=32),
    stream_id: Optional[str] = Query(default=None, max_length=64),
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> BackgroundTaskSnapshotResponse:
    snapshot = await _get_snapshot(
        session,
        user_id=current_user.id,
        limit=limit,
        stream_scope=_resolve_stream_scope(stream_type, stream_id),
    )
    return BackgroundTaskSnapshotResponse.model_validate(_serialize_snapshot(snapshot))


@router.get(
    "/events",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "Durable task events",
            "content": {"text/event-stream": {"schema": {"type": "string"}}},
        }
    },
)
async def stream_background_tasks(
    request: Request,
    limit: int = Query(default=20, ge=1, le=50),
    cursor: Optional[int] = Query(default=None, ge=0),
    stream_type: Optional[str] = Query(default=None, max_length=32),
    stream_id: Optional[str] = Query(default=None, max_length=64),
    current_user: UserInDB = Depends(get_current_user),
) -> StreamingResponse:
    """从 PostgreSQL event log 按 cursor 推送任务变化；Redis 只负责唤醒。"""

    requested_cursor = _resolve_event_cursor(request, cursor)
    stream_scope = _resolve_stream_scope(stream_type, stream_id)

    authorized_snapshot = None
    if stream_scope is not None:
        async with AsyncSessionLocal() as session:
            authorized_snapshot = await _get_snapshot(
                session,
                user_id=current_user.id,
                limit=limit,
                stream_scope=stream_scope,
            )

    async def fetch_snapshot() -> JobSnapshot:
        async with AsyncSessionLocal() as session:
            return await _get_snapshot(
                session,
                user_id=current_user.id,
                limit=limit,
                stream_scope=stream_scope,
            )

    async def fetch_events(after_cursor: int) -> list[JobEvent]:
        async with AsyncSessionLocal() as session:
            service = JobService(session)
            if stream_scope is None:
                return await service.list_events(
                    user_id=current_user.id,
                    after_cursor=after_cursor,
                    limit=200,
                )
            return await service.list_stream_events(
                user_id=current_user.id,
                stream_type=stream_scope[0],
                stream_id=stream_scope[1],
                after_cursor=after_cursor,
                limit=200,
            )

    async def event_stream() -> AsyncGenerator[str, None]:
        current_cursor = requested_cursor
        pubsub = None
        try:
            if current_cursor is None:
                snapshot = authorized_snapshot or await fetch_snapshot()
                current_cursor = snapshot.resume_cursor
                yield _sse_event(
                    "snapshot",
                    _serialize_snapshot(snapshot),
                    event_id=current_cursor,
                )

            pubsub = await subscribe_background_task(current_user.id)
            while True:
                if await request.is_disconnected():
                    return
                try:
                    events = await fetch_events(current_cursor)
                except EventCursorExpiredError as exc:
                    reset = BackgroundTaskCursorResetResponse(
                        schema_version=1, retained_through_cursor=exc.retained_through_cursor
                    )
                    yield _sse_event(
                        "reset",
                        reset.model_dump(mode="json"),
                        event_id=exc.retained_through_cursor,
                    )
                    return

                if events:
                    for event in events:
                        current_cursor = event.cursor
                        yield _sse_event(
                            "task",
                            _serialize_event(event),
                            event_id=event.cursor,
                        )
                    continue

                if pubsub is None:
                    await asyncio.sleep(5.0)
                    yield ": keepalive\n\n"
                    continue

                try:
                    await pubsub.get_message(
                        ignore_subscribe_messages=True,
                        timeout=5.0,
                    )
                except Exception:
                    logger.warning(
                        "后台任务 SSE pubsub 读取异常，回退轮询: user_id=%s",
                        current_user.id,
                    )
                    try:
                        await pubsub.aclose()
                    except Exception:
                        pass
                    pubsub = None
                yield ": keepalive\n\n"
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("后台任务 SSE 读取失败: user_id=%s", current_user.id)
            yield _sse_event("error", {"detail": "任务日志同步失败，请稍后重试"})
        finally:
            if pubsub is not None:
                try:
                    await pubsub.aclose()
                except Exception:
                    pass

    return _sse_response(event_stream())


@router.get("/{task_id}", response_model=BackgroundTaskResponse)
async def get_background_task(
    task_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> BackgroundTaskResponse:
    service = BackgroundTaskService(session)
    task = await service.get_user_task(task_id, user_id=current_user.id)
    if not task:
        raise HTTPException(status_code=404, detail="未找到后台任务")
    return _public_task_response(task, include_result=True)
