# AIMETA P=后台任务API_查询用户任务和日志|R=任务列表_任务详情_SSE推送|NR=不含任务创建|E=route:/api/tasks|X=http|A=query|D=fastapi|S=db|RD=./README.ai
import asyncio
import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import get_current_user
from ...db.session import AsyncSessionLocal
from ...db.session import get_session
from ...schemas.task import BackgroundTaskResponse
from ...schemas.user import UserInDB
from ...services.background_task_service import BackgroundTaskService
from ...services.event_bus import subscribe_background_task

logger = logging.getLogger(__name__)


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
    """推送后台任务列表变化，事件驱动（Redis pub-sub），替代固定轮询。"""

    async def fetch_payload() -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
        """查 DB 取任务列表快照，返回 (payload, error_event)；成功时 error_event 为 None。"""
        try:
            async with AsyncSessionLocal() as session:
                service = BackgroundTaskService(session)
                tasks = await service.list_user_tasks(user_id=current_user.id, limit=limit)
            payload = [
                BackgroundTaskResponse.model_validate(task).model_dump(mode="json")
                for task in tasks
            ]
            return payload, None
        except Exception as exc:
            logger.exception("后台任务 SSE 读取失败: user_id=%s", current_user.id)
            return None, _sse_event("error", {"detail": f"任务日志同步失败: {str(exc)}"})

    async def event_stream() -> AsyncGenerator[str, None]:
        last_payload: str | None = None

        def build_event(payload: List[Dict[str, Any]]) -> Optional[str]:
            """JSON 快照去重后构造 SSE 事件，无变化返回 None。"""
            nonlocal last_payload
            payload_text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
            if payload_text == last_payload:
                return None
            last_payload = payload_text
            return _sse_event("tasks", payload)

        async def poll_loop() -> AsyncGenerator[str, None]:
            """降级轮询：Redis 不可用时每 1.5s 查 DB 推送。"""
            while True:
                if await request.is_disconnected():
                    return
                await asyncio.sleep(1.5)
                payload, error_event = await fetch_payload()
                if error_event is not None:
                    yield error_event
                    return
                event = build_event(payload)
                if event is not None:
                    yield event

        # 1. 初始态：subscribe 前先查 DB 发一次快照，覆盖订阅前已发生的变更。
        payload, error_event = await fetch_payload()
        if error_event is not None:
            yield error_event
            return
        event = build_event(payload)
        if event is not None:
            yield event

        # 2. 订阅 Redis pub-sub channel；不可用回退轮询。
        pubsub = await subscribe_background_task(current_user.id)
        if pubsub is None:
            async for evt in poll_loop():
                yield evt
            return

        # 3. 事件驱动：收到变更通知即查 DB 推送。
        #    运行中 Redis 断连时 get_message 抛异常，回退轮询避免连接抖动。
        redis_disconnected = False
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                except Exception:
                    logger.warning(
                        "后台任务 SSE pubsub 读取异常，回退轮询: user_id=%s",
                        current_user.id,
                    )
                    redis_disconnected = True
                    break
                if message is None:
                    continue
                payload, error_event = await fetch_payload()
                if error_event is not None:
                    yield error_event
                    break
                event = build_event(payload)
                if event is not None:
                    yield event
        finally:
            try:
                await pubsub.aclose()
            except Exception:
                pass

        # 4. 事件驱动因 Redis 断连退出：回退轮询。
        if redis_disconnected:
            async for evt in poll_loop():
                yield evt

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
