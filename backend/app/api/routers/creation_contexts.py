# AIMETA P=创作上下文API_跨设备恢复入口|R=用户上下文列表_项目字段PATCH|NR=不含项目内容或实时协同|E=route:/api/creation-contexts|X=http|A=query_command|D=fastapi,sqlalchemy|S=db|RD=./README.ai
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import get_current_user
from ...db.session import get_session
from ...schemas.creation_context import CreationContextPatch, CreationContextRead
from ...schemas.user import UserInDB
from ...services.creation_context_service import CreationContextService

router = APIRouter(prefix="/api/creation-contexts", tags=["Creation Contexts"])


def get_creation_context_service(
    session: AsyncSession = Depends(get_session),
) -> CreationContextService:
    return CreationContextService(session)


@router.get("", response_model=list[CreationContextRead])
async def list_creation_contexts(
    service: CreationContextService = Depends(get_creation_context_service),
    current_user: UserInDB = Depends(get_current_user),
) -> list[CreationContextRead]:
    contexts = await service.list_contexts(user_id=current_user.id)
    return [CreationContextRead.model_validate(context) for context in contexts]


@router.patch("/{project_id}", response_model=CreationContextRead)
async def patch_creation_context(
    project_id: str,
    patch: CreationContextPatch,
    service: CreationContextService = Depends(get_creation_context_service),
    current_user: UserInDB = Depends(get_current_user),
) -> CreationContextRead:
    try:
        context = await service.patch_context(
            user_id=current_user.id,
            project_id=project_id,
            patch=patch,
        )
    except ValueError as exc:
        code = (
            status.HTTP_404_NOT_FOUND if str(exc) == "项目不存在" else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    return CreationContextRead.model_validate(context)
