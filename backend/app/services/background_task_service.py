# AIMETA P=后台任务服务_状态流转与日志记录|R=创建任务_更新进度_查询用户任务|NR=不含具体业务任务|E=BackgroundTaskService|X=internal|A=task_crud|D=sqlalchemy|S=db|RD=./README.ai
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.background_task import BackgroundTask


ACTIVE_TASK_STATUSES = {"queued", "running"}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _log_entry(message: str, *, level: str = "info") -> dict[str, str]:
    return {
        "timestamp": _utc_now().isoformat(),
        "level": level,
        "message": message,
    }


def _clamp_progress(progress: int) -> int:
    return max(0, min(100, int(progress)))


class BackgroundTaskService:
    """集中维护任务状态，避免业务代码直接拼接日志结构。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_task(
        self,
        *,
        user_id: int,
        task_type: str,
        title: str,
        project_id: Optional[str] = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> BackgroundTask:
        task = BackgroundTask(
            id=str(uuid4()),
            user_id=user_id,
            project_id=project_id,
            task_type=task_type,
            title=title,
            status="queued",
            progress=0,
            payload=payload or {},
            result=None,
            error=None,
            log_entries=[_log_entry("任务已创建，等待后台执行")],
        )
        self.session.add(task)
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def get_user_task(self, task_id: str, *, user_id: int) -> Optional[BackgroundTask]:
        result = await self.session.execute(
            select(BackgroundTask).where(
                BackgroundTask.id == task_id,
                BackgroundTask.user_id == user_id,
            )
        )
        return result.scalars().first()

    async def list_user_tasks(self, *, user_id: int, limit: int = 20) -> list[BackgroundTask]:
        result = await self.session.execute(
            select(BackgroundTask)
            .where(BackgroundTask.user_id == user_id)
            .order_by(BackgroundTask.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def append_log(
        self,
        task_id: str,
        message: str,
        *,
        level: str = "info",
        progress: Optional[int] = None,
    ) -> Optional[BackgroundTask]:
        task = await self.session.get(BackgroundTask, task_id)
        if not task:
            return None

        entries = list(task.log_entries or [])
        entries.append(_log_entry(message, level=level))
        task.log_entries = entries
        if progress is not None:
            task.progress = _clamp_progress(progress)

        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def mark_running(self, task_id: str, message: str = "任务开始执行") -> Optional[BackgroundTask]:
        task = await self.session.get(BackgroundTask, task_id)
        if not task:
            return None

        task.status = "running"
        task.started_at = task.started_at or _utc_now()
        task.progress = max(task.progress or 0, 5)
        task.log_entries = [*(task.log_entries or []), _log_entry(message)]
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def mark_succeeded(
        self,
        task_id: str,
        *,
        result: Optional[dict[str, Any]] = None,
    ) -> Optional[BackgroundTask]:
        task = await self.session.get(BackgroundTask, task_id)
        if not task:
            return None

        task.status = "succeeded"
        task.progress = 100
        task.result = result or {}
        task.completed_at = _utc_now()
        task.log_entries = [*(task.log_entries or []), _log_entry("任务执行完成")]
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def mark_failed(self, task_id: str, error: str) -> Optional[BackgroundTask]:
        task = await self.session.get(BackgroundTask, task_id)
        if not task:
            return None

        task.status = "failed"
        task.error = error
        task.completed_at = _utc_now()
        task.log_entries = [*(task.log_entries or []), _log_entry(f"任务失败：{error}", level="error")]
        await self.session.commit()
        await self.session.refresh(task)
        return task
