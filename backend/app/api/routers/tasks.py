# AIMETA P=后台任务API_查询用户任务和日志|R=任务列表_任务详情_SSE推送|NR=不含任务创建|E=route:/api/tasks|X=http|A=query|D=fastapi|S=db|RD=./README.ai
import asyncio
import json
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import get_current_user
from ...db.session import AsyncSessionLocal
from ...db.session import get_session
from ...schemas.task import BackgroundTaskResponse
from ...schemas.user import UserInDB
from ...services.background_task_service import BackgroundTaskService


router = APIRouter(prefix="/api/tasks", tags=["Tasks"])


def _sse_event(event: str, payload: object) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


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
    return await service.list_user_tasks(user_id=current_user.id, limit=limit)


@router.get("/events")
async def stream_background_tasks(
    request: Request,
    limit: int = Query(default=20, ge=1, le=50),
    current_user: UserInDB = Depends(get_current_user),
) -> StreamingResponse:
    """推送后台任务列表变化，避免全局任务日志固定轮询。"""

    async def event_stream() -> AsyncGenerator[str, None]:
        last_payload: str | None = None

        while True:
            if await request.is_disconnected():
                break

            async with AsyncSessionLocal() as session:
                service = BackgroundTaskService(session)
                tasks = await service.list_user_tasks(user_id=current_user.id, limit=limit)
                payload = [
                    BackgroundTaskResponse.model_validate(task).model_dump(mode="json")
                    for task in tasks
                ]

            # 任务日志是全局角标和弹窗的唯一实时来源；仅在快照变化时发送。
            payload_text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
            if payload_text != last_payload:
                yield _sse_event("tasks", payload)
                last_payload = payload_text

            await asyncio.sleep(1.5)

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
    return task
