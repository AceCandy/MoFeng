# AIMETA P=优化器API_内容优化建议|R=内容优化_建议生成|NR=不含内容修改|E=route:POST_/api/optimizer/*|X=http|A=优化建议|D=fastapi|S=net|RD=./README.ai
"""
章节内容分层优化API
支持对话、环境描写、心理活动、节奏韵律四个维度的深度优化
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import get_current_user
from ...db.session import get_session
from ...schemas.user import UserInDB
from ...services.chapter_edit_service import ChapterEditService
from ...services.llm_service import LLMService
from ...services.model_response_parser import (
    parse_optimizer_response as _parse_optimizer_response,
)
from ...services.novel_service import NovelService
from ...services.prompt_service import PromptService

router = APIRouter(prefix="/api/optimizer", tags=["Optimizer"])
logger = logging.getLogger(__name__)


class OptimizeRequest(BaseModel):
    """优化请求"""

    project_id: str = Field(..., description="项目ID")
    chapter_number: int = Field(..., description="章节编号")
    dimension: str = Field(..., description="优化维度: dialogue/environment/psychology/rhythm")
    additional_notes: Optional[str] = Field(default=None, description="额外优化指令")


class OptimizeResponse(BaseModel):
    """优化响应"""

    optimized_content: str = Field(..., description="优化后的内容")
    optimization_notes: str = Field(..., description="优化说明")
    dimension: str = Field(..., description="优化维度")


class OptimizeRecommendedVersionRequest(BaseModel):
    """基于评审结果优化推荐版本请求"""

    project_id: str = Field(..., description="项目ID")
    chapter_number: int = Field(..., description="章节编号")
    source_content: str = Field(..., description="推荐版本正文")
    review_summary: str = Field(..., description="评审建议摘要")
    version_number: Optional[int] = Field(default=None, description="推荐版本编号")
    version_review: Optional[dict] = Field(default=None, description="推荐版本详细评审")


class ApplyOptimizationRequest(BaseModel):
    """应用优化内容请求"""

    project_id: str = Field(..., description="项目ID")
    chapter_number: int = Field(..., description="章节编号")
    optimized_content: str = Field(..., description="优化后的完整内容")


DIMENSION_PROMPT_MAP = {
    "dialogue": "optimize_dialogue",
    "environment": "optimize_environment",
    "psychology": "optimize_psychology",
    "rhythm": "optimize_rhythm",
}


@router.post("/optimize", response_model=OptimizeResponse)
async def optimize_chapter(
    request: OptimizeRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> OptimizeResponse:
    """
    对章节内容进行分层优化
    """
    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(request.project_id, current_user.id)

    chapter = next(
        (ch for ch in project.chapters if ch.chapter_number == request.chapter_number), None
    )
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")

    if not chapter.selected_version or not chapter.selected_version.content:
        raise HTTPException(status_code=400, detail="章节尚未生成内容")

    original_content = chapter.selected_version.content

    if request.dimension not in DIMENSION_PROMPT_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的优化维度: {request.dimension}，支持的维度: {list(DIMENSION_PROMPT_MAP.keys())}",
        )

    prompt_name = DIMENSION_PROMPT_MAP[request.dimension]
    optimizer_prompt = await prompt_service.get_prompt(prompt_name)

    if not optimizer_prompt:
        raise HTTPException(
            status_code=500,
            detail=f"缺少{request.dimension}优化提示词，请联系管理员配置 '{prompt_name}' 提示词",
        )

    character_dna = {}
    if request.dimension == "psychology":
        project_schema = await novel_service._serialize_project(project)
        for char in project_schema.blueprint.characters:
            if "extra" in char and "dna_profile" in char.get("extra", {}):
                character_dna[char.get("name", "")] = char["extra"]["dna_profile"]

    optimize_input = {
        "original_content": original_content,
        "additional_notes": request.additional_notes or "无额外指令",
    }

    if character_dna:
        optimize_input["character_dna"] = character_dna

    logger.info(
        "用户 %s 开始优化项目 %s 第 %s 章，维度: %s",
        current_user.id,
        request.project_id,
        request.chapter_number,
        request.dimension,
    )

    try:
        response = await llm_service.get_llm_response(
            system_prompt=optimizer_prompt,
            conversation_history=[
                {"role": "user", "content": json.dumps(optimize_input, ensure_ascii=False)}
            ],
            temperature=0.7,
            user_id=current_user.id,
            timeout=600.0,
            stage="chapter_optimization",
        )

        optimized_content, optimization_notes = _parse_optimizer_response(response)

        logger.info(
            "项目 %s 第 %s 章 %s 优化完成",
            request.project_id,
            request.chapter_number,
            request.dimension,
        )

        return OptimizeResponse(
            optimized_content=optimized_content,
            optimization_notes=optimization_notes,
            dimension=request.dimension,
        )

    except Exception as exc:
        logger.error(
            "项目 %s 第 %s 章优化失败 [error_type=%s]",
            request.project_id,
            request.chapter_number,
            type(exc).__name__,
        )
        raise HTTPException(status_code=500, detail="优化过程中发生错误") from None


async def do_optimize_recommended_version(
    llm_service: LLMService,
    prompt_service: PromptService,
    source_content: str,
    review_summary: str,
    version_number: Optional[int],
    version_review: Optional[dict],
    user_id: int,
) -> tuple[str, str]:
    """根据评审建议优化推荐版本的核心逻辑（供内部和 API 复用）。"""
    source_content = (source_content or "").strip()
    review_summary = (review_summary or "").strip()
    if not source_content:
        raise ValueError("缺少推荐版本正文")
    if not review_summary:
        raise ValueError("缺少评审建议")

    optimizer_prompt = await prompt_service.get_prompt("optimize_recommended_version")
    if not optimizer_prompt:
        raise ValueError("缺少推荐版本优化提示词，请配置 'optimize_recommended_version' 提示词")

    optimize_input = {
        "source_content": source_content,
        "review_summary": review_summary,
        "version_number": version_number,
        "version_review": version_review or {},
    }

    response = await llm_service.get_llm_response(
        system_prompt=optimizer_prompt,
        conversation_history=[
            {"role": "user", "content": json.dumps(optimize_input, ensure_ascii=False)}
        ],
        temperature=0.7,
        user_id=user_id,
        timeout=600.0,
        stage="chapter_optimization",
    )

    optimized_content, optimization_notes = _parse_optimizer_response(response)
    if not optimized_content.strip():
        raise ValueError("优化结果为空，请重试")

    return optimized_content, optimization_notes


@router.post("/optimize-recommended-version", response_model=OptimizeResponse)
async def optimize_recommended_version(
    request: OptimizeRecommendedVersionRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> OptimizeResponse:
    """根据评审建议优化推荐版本。"""
    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(request.project_id, current_user.id)
    chapter = next(
        (ch for ch in project.chapters if ch.chapter_number == request.chapter_number),
        None,
    )
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")

    logger.info(
        "用户 %s 开始根据评审优化项目 %s 第 %s 章推荐版本 version=%s",
        current_user.id,
        request.project_id,
        request.chapter_number,
        request.version_number,
    )

    try:
        optimized_content, optimization_notes = await do_optimize_recommended_version(
            llm_service=llm_service,
            prompt_service=prompt_service,
            source_content=request.source_content,
            review_summary=request.review_summary,
            version_number=request.version_number,
            version_review=request.version_review,
            user_id=current_user.id,
        )

        return OptimizeResponse(
            optimized_content=optimized_content,
            optimization_notes=optimization_notes,
            dimension="recommended_version_review",
        )
    except ValueError as exc:
        logger.error(
            "项目 %s 第 %s 章推荐版本优化请求无效 [error_type=%s]",
            request.project_id,
            request.chapter_number,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=400,
            detail="推荐版本优化请求无效",
        ) from None
    except Exception as exc:
        logger.error(
            "项目 %s 第 %s 章推荐版本优化失败 [error_type=%s]",
            request.project_id,
            request.chapter_number,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail="评审优化过程中发生错误",
        ) from None


@router.post("/apply-optimization", status_code=202)
async def apply_optimization(
    request: Optional[ApplyOptimizationRequest] = None,
    project_id: Optional[str] = None,
    chapter_number: Optional[int] = None,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
):
    """提交优化正文，并原子创建统一的 durable 后处理任务。"""

    resolved_project_id = request.project_id if request else project_id
    resolved_chapter_number = request.chapter_number if request else chapter_number
    resolved_optimized_content = request.optimized_content if request else None

    if (
        not resolved_project_id
        or resolved_chapter_number is None
        or resolved_optimized_content is None
    ):
        raise HTTPException(
            status_code=422, detail="缺少必填参数: project_id/chapter_number/optimized_content"
        )

    edit_result = await ChapterEditService(session).apply_content(
        project_id=resolved_project_id,
        chapter_number=resolved_chapter_number,
        content=resolved_optimized_content,
        user_id=current_user.id,
        version_label="optimized",
    )

    logger.info(
        "用户 %s 应用了项目 %s 第 %s 章的优化内容，后处理任务=%s",
        current_user.id,
        resolved_project_id,
        resolved_chapter_number,
        edit_result.job.id,
    )

    return {
        "status": "accepted",
        "message": "优化内容已应用，章节后处理已进入队列",
        "task_id": edit_result.job.id,
    }
