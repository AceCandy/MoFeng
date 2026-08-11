# AIMETA P=LLM配置API_模型配置管理|R=LLM配置CRUD|NR=不含模型调用|E=route:GET_POST_/api/llm-config/*|X=http|A=配置CRUD|D=fastapi,sqlalchemy|S=db|RD=./README.ai
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from ...core.dependencies import get_current_user
from ...db.session import get_session
from ...schemas.llm_config import (
    LLMConfigBundle,
    LLMConfigCreate,
    LLMConfigRead,
    ModelListRequest,
    ProviderCreate,
    ProviderRead,
    ProviderUpdate,
    StageRouteRead,
    StageRoutesPayload,
    UserAIModelCreate,
    UserAIModelRead,
    UserAIModelUpdate,
)
from ...schemas.user import UserInDB
from ...services.llm_config_service import LLMConfigService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/llm-config", tags=["LLM Configuration"])


def get_llm_config_service(session: AsyncSession = Depends(get_session)) -> LLMConfigService:
    return LLMConfigService(session)


@router.get("", response_model=LLMConfigBundle)
async def read_llm_config(
    service: LLMConfigService = Depends(get_llm_config_service),
    current_user: UserInDB = Depends(get_current_user),
) -> LLMConfigBundle:
    logger.info("用户 %s 获取 LLM 配置包", current_user.id)
    return await service.list_bundle(current_user.id)


@router.put("", response_model=LLMConfigRead)
async def upsert_llm_config(
    payload: LLMConfigCreate,
    service: LLMConfigService = Depends(get_llm_config_service),
    current_user: UserInDB = Depends(get_current_user),
) -> LLMConfigRead:
    logger.info("用户 %s 更新 LLM 配置", current_user.id)
    return await service.upsert_config(current_user.id, payload)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_llm_config(
    service: LLMConfigService = Depends(get_llm_config_service),
    current_user: UserInDB = Depends(get_current_user),
) -> None:
    deleted = await service.delete_config(current_user.id)
    if not deleted:
        logger.warning("用户 %s 删除 LLM 配置失败，未找到记录", current_user.id)
        raise HTTPException(status_code=404, detail="未找到配置")
    logger.info("用户 %s 删除 LLM 配置", current_user.id)


@router.post("/models", response_model=List[str])
async def list_models(
    payload: ModelListRequest,
    service: LLMConfigService = Depends(get_llm_config_service),
    current_user: UserInDB = Depends(get_current_user),
) -> List[str]:
    """获取可用的模型列表"""
    try:
        models = await service.get_available_models(
            api_key=payload.llm_provider_api_key, base_url=payload.llm_provider_url
        )
        logger.info("用户 %s 获取模型列表，返回 %d 个模型", current_user.id, len(models))
        return models
    except Exception as e:
        logger.error("用户 %s 获取模型列表失败: %s", current_user.id, str(e))
        # 返回空列表而不是抛出异常，因为这只是提示功能
        return []


@router.get("/providers", response_model=List[ProviderRead])
async def list_providers(
    service: LLMConfigService = Depends(get_llm_config_service),
    current_user: UserInDB = Depends(get_current_user),
) -> List[ProviderRead]:
    return await service.list_providers(current_user.id)


@router.post("/providers", response_model=ProviderRead, status_code=status.HTTP_201_CREATED)
async def create_provider(
    payload: ProviderCreate,
    service: LLMConfigService = Depends(get_llm_config_service),
    current_user: UserInDB = Depends(get_current_user),
) -> ProviderRead:
    return await service.create_provider(current_user.id, payload)


@router.patch("/providers/{provider_id}", response_model=ProviderRead)
async def patch_provider(
    provider_id: int,
    payload: ProviderUpdate,
    service: LLMConfigService = Depends(get_llm_config_service),
    current_user: UserInDB = Depends(get_current_user),
) -> ProviderRead:
    try:
        return await service.update_provider(current_user.id, provider_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/providers/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider(
    provider_id: int,
    service: LLMConfigService = Depends(get_llm_config_service),
    current_user: UserInDB = Depends(get_current_user),
) -> None:
    try:
        await service.delete_provider(current_user.id, provider_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/providers/{provider_id}/models", response_model=List[str])
async def list_provider_models(
    provider_id: int,
    service: LLMConfigService = Depends(get_llm_config_service),
    current_user: UserInDB = Depends(get_current_user),
) -> List[str]:
    try:
        models = await service.get_provider_models(current_user.id, provider_id)
        logger.info(
            "用户 %s 通过供应商 %s 拉取模型，返回 %d 个模型",
            current_user.id,
            provider_id,
            len(models),
        )
        return models
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/user-models", response_model=List[UserAIModelRead])
async def list_user_models(
    service: LLMConfigService = Depends(get_llm_config_service),
    current_user: UserInDB = Depends(get_current_user),
) -> List[UserAIModelRead]:
    return await service.list_models(current_user.id)


@router.post("/user-models", response_model=UserAIModelRead, status_code=status.HTTP_201_CREATED)
async def create_user_model(
    payload: UserAIModelCreate,
    service: LLMConfigService = Depends(get_llm_config_service),
    current_user: UserInDB = Depends(get_current_user),
) -> UserAIModelRead:
    try:
        return await service.create_model(current_user.id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/user-models/{model_id}", response_model=UserAIModelRead)
async def patch_user_model(
    model_id: int,
    payload: UserAIModelUpdate,
    service: LLMConfigService = Depends(get_llm_config_service),
    current_user: UserInDB = Depends(get_current_user),
) -> UserAIModelRead:
    try:
        return await service.update_model(current_user.id, model_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/user-models/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_model(
    model_id: int,
    service: LLMConfigService = Depends(get_llm_config_service),
    current_user: UserInDB = Depends(get_current_user),
) -> None:
    try:
        await service.delete_model(current_user.id, model_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/stage-routes", response_model=List[StageRouteRead])
async def list_stage_routes(
    service: LLMConfigService = Depends(get_llm_config_service),
    current_user: UserInDB = Depends(get_current_user),
) -> List[StageRouteRead]:
    bundle = await service.list_bundle(current_user.id)
    return bundle.stage_routes


@router.put("/stage-routes", response_model=List[StageRouteRead])
async def put_stage_routes(
    payload: StageRoutesPayload,
    service: LLMConfigService = Depends(get_llm_config_service),
    current_user: UserInDB = Depends(get_current_user),
) -> List[StageRouteRead]:
    try:
        return await service.upsert_stage_routes(current_user.id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
