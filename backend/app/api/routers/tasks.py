# AIMETA P=后台任务API_查询用户任务和日志|R=任务列表_任务详情|NR=不含任务创建|E=route:/api/tasks|X=http|A=query|D=fastapi|S=db|RD=./README.ai
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import get_current_user
from ...db.session import get_session
from ...schemas.task import BackgroundTaskResponse
from ...schemas.user import UserInDB
from ...services.background_task_service import BackgroundTaskService


router = APIRouter(prefix="/api/tasks", tags=["Tasks"])


@router.get("", response_model=list[BackgroundTaskResponse])
async def list_background_tasks(
    limit: int = Query(default=20, ge=1, le=50),
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> list[BackgroundTaskResponse]:
    service = BackgroundTaskService(session)
    return await service.list_user_tasks(user_id=current_user.id, limit=limit)


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
