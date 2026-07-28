# AIMETA P=章节投影管理API_重放与发布控制|R=管理员鉴权_请求校验_领域错误映射|NR=不执行投影计算或直接提交制品|E=route:/api/admin/chapter-projections/*|X=http|A=router|D=fastapi|S=db|RD=./README.ai
"""Privileged operational endpoints for chapter projection recovery."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import get_current_admin
from ...db.session import get_session
from ...schemas.chapter_projection import (
    ChapterProjectionEnterShadowRequest,
    ChapterProjectionOperationRequest,
    ChapterProjectionOperationResponse,
    ChapterProjectionRolloutMutationRequest,
    ChapterProjectionRolloutResponse,
)
from ...schemas.user import UserInDB
from ...services.chapter_projection_ops import (
    ChapterProjectionConflictError,
    ChapterProjectionNotFoundError,
    ChapterProjectionOpsService,
    ChapterProjectionRateLimitError,
)
from ...services.chapter_projection_rollout import (
    ChapterProjectionRolloutConflictError,
    ChapterProjectionRolloutNotFoundError,
    ChapterProjectionRolloutService,
)


router = APIRouter(prefix="/api/admin/chapter-projections", tags=["Admin"])


async def _execute(
    *,
    payload: ChapterProjectionOperationRequest,
    mode: str,
    session: AsyncSession,
    admin: UserInDB,
) -> ChapterProjectionOperationResponse:
    try:
        return await ChapterProjectionOpsService(session).execute(
            request=payload,
            operator_user_id=admin.id,
            mode=mode,
        )
    except ChapterProjectionNotFoundError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=exc.code,
        ) from exc
    except ChapterProjectionRateLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=exc.code,
        ) from exc
    except ChapterProjectionConflictError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=exc.code,
        ) from exc


@router.post("/dry-run", response_model=ChapterProjectionOperationResponse)
async def dry_run_chapter_projection(
    payload: ChapterProjectionOperationRequest,
    session: AsyncSession = Depends(get_session),
    admin: UserInDB = Depends(get_current_admin),
) -> ChapterProjectionOperationResponse:
    return await _execute(payload=payload, mode="dry_run", session=session, admin=admin)


@router.post("/replay", response_model=ChapterProjectionOperationResponse)
async def replay_chapter_projection(
    payload: ChapterProjectionOperationRequest,
    session: AsyncSession = Depends(get_session),
    admin: UserInDB = Depends(get_current_admin),
) -> ChapterProjectionOperationResponse:
    return await _execute(payload=payload, mode="replay", session=session, admin=admin)


@router.get(
    "/rollouts/{chapter_id}",
    response_model=ChapterProjectionRolloutResponse,
)
async def get_chapter_projection_rollout(
    chapter_id: int,
    project_id: str,
    session: AsyncSession = Depends(get_session),
    _admin: UserInDB = Depends(get_current_admin),
) -> ChapterProjectionRolloutResponse:
    try:
        payload = await ChapterProjectionRolloutService(session).get_status(
            project_id=project_id,
            chapter_id=chapter_id,
        )
        return ChapterProjectionRolloutResponse.model_validate(payload)
    except ChapterProjectionRolloutNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.code) from exc


async def _mutate_rollout(
    *,
    action: str,
    payload: ChapterProjectionRolloutMutationRequest,
    session: AsyncSession,
    admin: UserInDB,
) -> ChapterProjectionRolloutResponse:
    service = ChapterProjectionRolloutService(session)
    kwargs = {
        "project_id": payload.project_id,
        "chapter_id": payload.chapter_id,
        "expected_generation": payload.expected_generation,
        "expected_fencing_token": payload.expected_fencing_token,
        "operator_user_id": admin.id,
        "reason": payload.reason,
    }
    try:
        if action == "enter_shadow":
            if not isinstance(payload, ChapterProjectionEnterShadowRequest):
                raise TypeError("enter_shadow payload 类型无效")
            result = await service.enter_shadow(
                **kwargs,
                observation_seconds=payload.observation_seconds,
                required_observations=payload.required_observations,
            )
        elif action == "prepare_cutover":
            result = await service.prepare_cutover(**kwargs)
        elif action == "complete_cutover":
            result = await service.complete_cutover(**kwargs)
        elif action == "rollback":
            result = await service.rollback(**kwargs)
        else:
            raise TypeError("未知 rollout 操作")
        await session.commit()
        return ChapterProjectionRolloutResponse.model_validate(result)
    except ChapterProjectionRolloutNotFoundError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.code) from exc
    except ChapterProjectionRolloutConflictError as exc:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.code) from exc


@router.post(
    "/rollouts/enter-shadow",
    response_model=ChapterProjectionRolloutResponse,
)
async def enter_chapter_projection_shadow(
    payload: ChapterProjectionEnterShadowRequest,
    session: AsyncSession = Depends(get_session),
    admin: UserInDB = Depends(get_current_admin),
) -> ChapterProjectionRolloutResponse:
    return await _mutate_rollout(
        action="enter_shadow",
        payload=payload,
        session=session,
        admin=admin,
    )


@router.post(
    "/rollouts/prepare-cutover",
    response_model=ChapterProjectionRolloutResponse,
)
async def prepare_chapter_projection_cutover(
    payload: ChapterProjectionRolloutMutationRequest,
    session: AsyncSession = Depends(get_session),
    admin: UserInDB = Depends(get_current_admin),
) -> ChapterProjectionRolloutResponse:
    return await _mutate_rollout(
        action="prepare_cutover",
        payload=payload,
        session=session,
        admin=admin,
    )


@router.post(
    "/rollouts/complete-cutover",
    response_model=ChapterProjectionRolloutResponse,
)
async def complete_chapter_projection_cutover(
    payload: ChapterProjectionRolloutMutationRequest,
    session: AsyncSession = Depends(get_session),
    admin: UserInDB = Depends(get_current_admin),
) -> ChapterProjectionRolloutResponse:
    return await _mutate_rollout(
        action="complete_cutover",
        payload=payload,
        session=session,
        admin=admin,
    )


@router.post(
    "/rollouts/rollback",
    response_model=ChapterProjectionRolloutResponse,
)
async def rollback_chapter_projection(
    payload: ChapterProjectionRolloutMutationRequest,
    session: AsyncSession = Depends(get_session),
    admin: UserInDB = Depends(get_current_admin),
) -> ChapterProjectionRolloutResponse:
    return await _mutate_rollout(
        action="rollback",
        payload=payload,
        session=session,
        admin=admin,
    )


__all__ = ["router"]
