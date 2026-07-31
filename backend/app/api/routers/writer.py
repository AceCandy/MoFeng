# AIMETA P=写作API_章节生成和大纲创建|R=章节生成_大纲生成_评审_L2导演脚本_护栏检查|NR=不含数据存储|E=route:POST_/api/writer/*|X=http|A=生成_评审_过滤|D=fastapi,openai|S=net,db|RD=./README.ai
"""
Writer API Router - 人类化起点长篇写作系统

核心架构：
- L1 Planner：全知规划层（蓝图/大纲）
- L2 Director：章节导演脚本（ChapterMission）
- L3 Writer：有限视角正文生成

关键改进：
1. 信息可见性过滤：L3 Writer 只能看到已登场角色
2. 跨章 1234 逻辑：通过 ChapterMission 控制每章只写一个节拍
3. 后置护栏检查：自动检测并修复违规内容
"""
import json
import logging
import re
from datetime import datetime
from typing import NoReturn, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ...core.config import settings
from ...core.dependencies import get_current_user
from ...db.session import get_session
from ...models.novel import Chapter, ChapterOutline, ChapterVersion
from ...schemas.chapter_workflow import (
    ChapterWorkflowCommandConflictDetail,
    ChapterWorkflowCommandConflictResponse,
    ChapterWorkflowCommandEnvelope,
    ChapterWorkflowCommandResponse,
    ChapterWorkflowConnection,
    ChapterWorkflowSnapshot,
    ChapterWorkflowStartRequest,
    ChapterWorkflowStartResponse,
)
from ...schemas.novel import (
    AdvancedGenerateRequest,
    ChapterGenerationStatus,
    ConfirmFinalizeChapterRequest,
    DeleteChapterRequest,
    EditChapterRequest,
    EvaluateChapterRequest,
    FinalizeChapterRequest,
    GenerateChapterRequest,
    GenerateOutlineRequest,
    SelectVersionRequest,
    UpdateChapterOutlineRequest,
)
from ...schemas.novel import (
    Chapter as ChapterSchema,
)
from ...schemas.novel import (
    NovelProject as NovelProjectSchema,
)
from ...schemas.task import BackgroundTaskResponse
from ...schemas.user import UserInDB
from ...services.ai_review_service import AIReviewService
from ...services.chapter_context_adapters import (
    WRITER_VISIBILITY_SHADOW_PREFIXES,
    ChapterContextShadowComparator,
    ReviewContextAdapter,
)
from ...services.chapter_context_resolver import ChapterContextResolver
from ...services.chapter_edit_service import ChapterEditService
from ...services.chapter_finalize_service import ChapterFinalizeSubmissionService
from ...services.chapter_generation_trace_service import CN_TIMEZONE, ChapterGenerationTraceService
from ...services.chapter_projection_rollout import ChapterProjectionRolloutConflictError
from ...services.chapter_projection_service import ChapterFinalizeConflictError
from ...services.chapter_workflow_compatibility import (
    ChapterWorkflowCompatibilityConflictError,
    ChapterWorkflowCompatibilityService,
)
from ...services.chapter_workflow_start import ChapterWorkflowStartService
from ...services.job_service import ChapterWorkflowCommandRejectedError, JobService
from ...services.llm_service import LLMService
from ...services.novel_service import NovelService
from ...services.prompt_service import PromptService

router = APIRouter(prefix="/api/writer", tags=["Writer"])
logger = logging.getLogger(__name__)


def get_chapter_workflow_start_service(
    session: AsyncSession = Depends(get_session),
) -> ChapterWorkflowStartService:
    return ChapterWorkflowStartService(session)


def get_job_service(session: AsyncSession = Depends(get_session)) -> JobService:
    return JobService(session)


async def _load_project_schema(service: NovelService, project_id: str, user_id: int) -> NovelProjectSchema:
    return await service.get_project_schema(project_id, user_id)


def _build_evaluation_failure_detail(exc: Exception, max_length: int = 300) -> str:
    """保留 AI 评审失败根因，同时避免把敏感配置原样回传给前端。"""
    raw_detail = str(exc).strip() or exc.__class__.__name__
    normalized = re.sub(r"\s+", " ", raw_detail).strip()
    if not normalized:
        return "AI评审失败：未收到具体错误信息，请查看后端日志。"

    redacted = re.sub(
        r"(?i)\b(api[_-]?key|authorization|bearer|token|secret|password)\b(\s*[=:]\s*)([^,\s;]+)",
        r"\1\2[已隐藏]",
        normalized,
    )
    if len(redacted) > max_length:
        redacted = redacted[:max_length].rstrip() + "..."

    if redacted.startswith("AI评审失败"):
        return redacted
    if redacted.startswith("评审失败"):
        return f"AI{redacted}"
    return f"AI评审失败：{redacted}"


async def _enqueue_chapter_generation(
    *,
    session: AsyncSession,
    project_id: str,
    chapter_number: int,
    writing_notes: Optional[str],
    flow_config: dict,
    from_node_key: Optional[str],
    user_id: int,
    idempotency_key: Optional[str],
) -> BackgroundTaskResponse:
    try:
        workflow_response = await ChapterWorkflowCompatibilityService(
            session
        ).adapt_generation(
            user_id=user_id,
            project_id=project_id,
            chapter_number=chapter_number,
            writing_notes=writing_notes,
            flow_config=flow_config,
            from_node_key=from_node_key,
            idempotency_key=idempotency_key,
            start_enabled=settings.chapter_workflow_start_enabled,
        )
        if workflow_response is not None:
            return workflow_response
        await NovelService(session).ensure_project_owner(project_id, user_id)
        return await JobService(session).enqueue_job(
            user_id=user_id,
            project_id=project_id,
            job_type="chapter_generation",
            title=f"生成第 {chapter_number} 章正文",
            payload={
                "project_id": project_id,
                "chapter_number": chapter_number,
                "writing_notes": writing_notes,
                "flow_config": flow_config,
                "from_node_key": from_node_key,
            },
            payload_version=1,
            idempotency_key=idempotency_key,
        )
    except ChapterWorkflowCompatibilityConflictError as exc:
        raise HTTPException(status_code=409, detail=exc.reason_code) from exc
    except ValueError as exc:
        status_code = 409 if "idempotency_key" in str(exc) else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


async def _enqueue_chapter_finalize(
    *,
    session: AsyncSession,
    project_id: str,
    chapter_number: int,
    user_id: int,
    selected_version_index: Optional[int] = None,
    selected_version_id: Optional[int] = None,
    edited_content: Optional[str] = None,
    skip_vector_update: bool = False,
    idempotency_key: Optional[str] = None,
) -> BackgroundTaskResponse:
    try:
        workflow_response = await ChapterWorkflowCompatibilityService(
            session
        ).adapt_finalize(
            project_id=project_id,
            chapter_number=chapter_number,
            user_id=user_id,
            selected_version_index=selected_version_index,
            selected_version_id=selected_version_id,
            edited_content=edited_content,
            skip_vector_update=skip_vector_update,
            idempotency_key=idempotency_key,
        )
        if workflow_response is not None:
            return workflow_response
        return await ChapterFinalizeSubmissionService(session).submit(
            project_id=project_id,
            chapter_number=chapter_number,
            user_id=user_id,
            selected_version_index=selected_version_index,
            selected_version_id=selected_version_id,
            edited_content=edited_content,
            skip_vector_update=skip_vector_update,
            idempotency_key=idempotency_key,
        )
    except ChapterWorkflowCompatibilityConflictError as exc:
        raise HTTPException(status_code=409, detail=exc.reason_code) from exc
    except ChapterFinalizeConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ChapterProjectionRolloutConflictError as exc:
        raise HTTPException(status_code=409, detail=exc.code) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _raise_workflow_lookup_error(exc: ValueError) -> NoReturn:
    if str(exc) == "workflow run 不存在":
        raise HTTPException(status_code=404, detail="章节工作流不存在") from exc
    raise HTTPException(status_code=409, detail="章节工作流当前不可用") from exc


def _chapter_workflow_events_url(run_id: str) -> str:
    return f"/api/tasks/events?stream_type=workflow&stream_id={run_id}"


@router.post(
    "/chapter-workflows",
    response_model=ChapterWorkflowStartResponse,
    status_code=202,
)
async def start_chapter_workflow(
    request: ChapterWorkflowStartRequest,
    start_service: ChapterWorkflowStartService = Depends(get_chapter_workflow_start_service),
    job_service: JobService = Depends(get_job_service),
    current_user: UserInDB = Depends(get_current_user),
) -> ChapterWorkflowStartResponse:
    """创建或复用 durable Chapter workflow；切流前由配置显式关闭。"""

    if not settings.chapter_workflow_start_enabled:
        raise HTTPException(status_code=404, detail="章节工作流入口未启用")
    try:
        result = await start_service.start(
            user_id=current_user.id,
            project_id=request.project_id,
            chapter_number=request.chapter_number,
            writing_notes=request.writing_notes,
            flow_config=request.flow_config,
        )
        snapshot = await job_service.get_chapter_workflow_snapshot(
            result.run.id,
            user_id=current_user.id,
        )
    except ValueError as exc:
        if str(exc) == "项目不存在":
            raise HTTPException(status_code=404, detail="项目不存在") from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ChapterWorkflowStartResponse(
        created=result.created,
        snapshot=snapshot,
        events_url=_chapter_workflow_events_url(snapshot.run_id),
    )


@router.get(
    "/chapter-workflows/current",
    response_model=Optional[ChapterWorkflowConnection],
)
async def get_current_chapter_workflow(
    project_id: str = Query(min_length=1, max_length=36),
    chapter_number: int = Query(ge=1),
    job_service: JobService = Depends(get_job_service),
    current_user: UserInDB = Depends(get_current_user),
) -> Optional[ChapterWorkflowConnection]:
    """恢复 owner scope 内可连接的当前 workflow；无可见 run 时返回 null。"""

    try:
        snapshot = await job_service.get_current_chapter_workflow_snapshot(
            user_id=current_user.id,
            project_id=project_id,
            chapter_number=chapter_number,
        )
    except ValueError as exc:
        _raise_workflow_lookup_error(exc)
    if snapshot is None:
        return None
    return ChapterWorkflowConnection(
        snapshot=snapshot,
        events_url=_chapter_workflow_events_url(snapshot.run_id),
    )


@router.get(
    "/chapter-workflows/{run_id}",
    response_model=ChapterWorkflowSnapshot,
)
async def get_chapter_workflow(
    run_id: str,
    job_service: JobService = Depends(get_job_service),
    current_user: UserInDB = Depends(get_current_user),
) -> ChapterWorkflowSnapshot:
    try:
        snapshot: ChapterWorkflowSnapshot = await job_service.get_chapter_workflow_snapshot(
            run_id,
            user_id=current_user.id,
        )
        return snapshot
    except ValueError as exc:
        _raise_workflow_lookup_error(exc)


@router.post(
    "/chapter-workflows/{run_id}/commands",
    response_model=ChapterWorkflowCommandResponse,
    status_code=202,
    responses={409: {"model": ChapterWorkflowCommandConflictResponse}},
)
async def submit_chapter_workflow_command(
    run_id: str,
    request: ChapterWorkflowCommandEnvelope,
    job_service: JobService = Depends(get_job_service),
    current_user: UserInDB = Depends(get_current_user),
) -> ChapterWorkflowCommandResponse:
    try:
        command = await job_service.submit_chapter_workflow_command(
            run_id,
            actor_user_id=current_user.id,
            envelope=request,
        )
    except ChapterWorkflowCommandRejectedError as exc:
        snapshot = await job_service.get_chapter_workflow_snapshot(
            run_id,
            user_id=current_user.id,
        )
        detail = ChapterWorkflowCommandConflictDetail(
            reason_code=exc.reason_code,
            current_snapshot=snapshot,
        )
        raise HTTPException(
            status_code=409,
            detail=detail.model_dump(mode="json"),
        ) from exc
    except ValueError as exc:
        if str(exc) == "workflow run 不存在":
            _raise_workflow_lookup_error(exc)
        status_code = 409 if "command id 已绑定不同请求" in str(exc) else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    snapshot = await job_service.get_chapter_workflow_snapshot(
        run_id,
        user_id=current_user.id,
    )
    return ChapterWorkflowCommandResponse(
        command_id=command.id,
        type=command.type,
        status=command.status,
        snapshot=snapshot,
    )


@router.post("/advanced/generate", response_model=BackgroundTaskResponse, status_code=202)
async def advanced_generate_chapter(
    request: AdvancedGenerateRequest,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> BackgroundTaskResponse:
    """提交高级章节生成任务，具体 LangGraph 流程由独立 worker 执行。"""

    return await _enqueue_chapter_generation(
        session=session,
        project_id=request.project_id,
        chapter_number=request.chapter_number,
        writing_notes=request.writing_notes,
        user_id=current_user.id,
        flow_config=request.flow_config.model_dump(),
        from_node_key=request.from_node_key,
        idempotency_key=idempotency_key,
    )


@router.post(
    "/chapters/{chapter_number}/finalize",
    response_model=BackgroundTaskResponse,
    status_code=202,
)
async def finalize_chapter(
    chapter_number: int,
    request: FinalizeChapterRequest,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> BackgroundTaskResponse:
    """兼容旧定稿入口：按版本 ID 提交同一 durable 定稿任务。"""

    return await _enqueue_chapter_finalize(
        session=session,
        project_id=request.project_id,
        chapter_number=chapter_number,
        user_id=current_user.id,
        selected_version_id=request.selected_version_id,
        skip_vector_update=request.skip_vector_update or False,
        idempotency_key=idempotency_key,
    )


@router.post(
    "/novels/{project_id}/chapters/generate",
    response_model=BackgroundTaskResponse,
    status_code=202,
)
async def generate_chapter(
    project_id: str,
    request: GenerateChapterRequest,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> BackgroundTaskResponse:
    """提交普通章节生成任务，返回可持久查询的任务 ID。"""

    return await _enqueue_chapter_generation(
        session=session,
        project_id=project_id,
        chapter_number=request.chapter_number,
        writing_notes=request.writing_notes,
        user_id=current_user.id,
        flow_config={"preset": "basic", "enable_rag": True},
        from_node_key=request.from_node_key,
        idempotency_key=idempotency_key,
    )


@router.post(
    "/novels/{project_id}/chapters/{chapter_number}/confirm-finalize",
    response_model=BackgroundTaskResponse,
    status_code=202,
)
async def confirm_finalize_chapter(
    project_id: str,
    chapter_number: int,
    request: ConfirmFinalizeChapterRequest,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> BackgroundTaskResponse:
    return await _enqueue_chapter_finalize(
        session=session,
        project_id=project_id,
        chapter_number=chapter_number,
        user_id=current_user.id,
        selected_version_index=request.selected_version_index,
        edited_content=request.edited_content,
        skip_vector_update=request.skip_vector_update,
        idempotency_key=idempotency_key,
    )


@router.post(
    "/novels/{project_id}/chapters/select",
    response_model=BackgroundTaskResponse,
    status_code=202,
)
async def select_chapter_version(
    project_id: str,
    request: SelectVersionRequest,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> BackgroundTaskResponse:
    return await _enqueue_chapter_finalize(
        session=session,
        project_id=project_id,
        chapter_number=request.chapter_number,
        user_id=current_user.id,
        selected_version_index=request.version_index,
        idempotency_key=idempotency_key,
    )


@router.post("/novels/{project_id}/chapters/evaluate", response_model=NovelProjectSchema)
async def evaluate_chapter(
    project_id: str,
    request: EvaluateChapterRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)

    await novel_service.ensure_project_owner(project_id, current_user.id)
    # 确保预加载 selected_version 与 versions 关系
    from sqlalchemy.orm import selectinload
    stmt = (
        select(Chapter)
        .options(
            selectinload(Chapter.selected_version),
            selectinload(Chapter.versions),
        )
        .where(
            Chapter.project_id == project_id,
            Chapter.chapter_number == request.chapter_number,
        )
    )
    result = await session.execute(stmt)
    chapter = result.scalars().first()

    if not chapter:
        chapter = await novel_service.get_or_create_chapter(project_id, request.chapter_number)

    ordered_versions = sorted(
        [version for version in (chapter.versions or []) if version.content and version.content.strip()],
        key=lambda item: item.created_at,
    )

    version_to_evaluate = chapter.selected_version
    if version_to_evaluate and (not version_to_evaluate.content or not version_to_evaluate.content.strip()):
        version_to_evaluate = None

    if not ordered_versions and not version_to_evaluate:
        raise HTTPException(status_code=400, detail="该章节还没有生成任何版本，无法进行评审")

    chapter.status = "evaluating"
    chapter.generation_progress = 84
    chapter.generation_step = "evaluating"
    chapter.generation_step_index = 2
    chapter.generation_step_total = 3
    await session.commit()

    evaluation_feedback: Optional[str] = None
    evaluation_version: Optional[ChapterVersion] = None

    try:
        # 获取章节内容用于上下文增强
        chapter_content = None
        if ordered_versions:
            # 使用最新版本的内容
            chapter_content = ordered_versions[-1].content
        elif version_to_evaluate and version_to_evaluate.content:
            chapter_content = version_to_evaluate.content

        chapter_context = await ChapterContextResolver(
            session,
            llm_service=llm_service,
        ).resolve(
            project_id=project_id,
            chapter_number=request.chapter_number,
            user_id=current_user.id,
            rag_enabled=settings.vector_store_enabled,
            rag_query=chapter_content,
            rag_mode="review",
        )
        review_context = ReviewContextAdapter.to_prompt_context(chapter_context)
        if settings.chapter_context_shadow_compare:
            shadow_report = ChapterContextShadowComparator.compare(
                ReviewContextAdapter.to_legacy_writer_context(chapter_context),
                review_context,
                allowed_prefixes=WRITER_VISIBILITY_SHADOW_PREFIXES,
            )
            logger.log(
                logging.WARNING if shadow_report["unexplained_count"] else logging.INFO,
                "canonical context shadow compare: entry=writer total=%s unexplained=%s diffs=%s",
                shadow_report["difference_count"],
                shadow_report["unexplained_count"],
                shadow_report["differences"],
            )

        if len(ordered_versions) > 1:
            ai_review_service = AIReviewService(llm_service, prompt_service)
            ai_review_result = await ai_review_service.review_versions(
                versions=[version.content for version in ordered_versions],
                chapter_mission=review_context.get("chapter_mission") if isinstance(review_context.get("chapter_mission"), dict) else None,
                user_id=current_user.id,
                review_context=review_context,
            )
            if not ai_review_result:
                raise ValueError("多版本评审失败")

            evaluation_feedback = json.dumps(
                ai_review_result.to_evaluation_payload(),
                ensure_ascii=False,
            )
        else:
            if not version_to_evaluate:
                version_to_evaluate = ordered_versions[-1]
            if not version_to_evaluate or not version_to_evaluate.content:
                raise HTTPException(status_code=400, detail="版本内容为空，无法进行评审")

            ai_review_service = AIReviewService(llm_service, prompt_service)
            evaluation_text = await ai_review_service.review_single_version(
                version_content=version_to_evaluate.content,
                user_id=current_user.id,
                review_context=review_context,
            )
            if not evaluation_text or len(evaluation_text.strip()) == 0:
                raise ValueError("评审结果为空")

            # 单版本同样包装成与多版本结构一致的 JSON 格式
            evaluation_feedback = json.dumps({
                "best_choice": 1,
                "reason_for_choice": evaluation_text,
                "evaluation": {
                    "version1": {
                        "pros": [],
                        "cons": [],
                        "overall_review": evaluation_text,
                        "scores": {}
                    }
                }
            }, ensure_ascii=False)
            evaluation_version = version_to_evaluate

        await novel_service.add_chapter_evaluation(
            chapter=chapter,
            version=evaluation_version,
            feedback=evaluation_feedback,
            decision="reviewed"
        )
        logger.info("项目 %s 第 %s 章评审成功", project_id, request.chapter_number)

        # 自动优化流程
        try:
            # 1. 解析评审结果获取最佳版本和修改建议
            eval_data = json.loads(evaluation_feedback)
            best_choice = eval_data.get("best_choice", 1)

            # 寻找源版本
            source_version = None
            if len(ordered_versions) > 1:
                if isinstance(best_choice, int) and 1 <= best_choice <= len(ordered_versions):
                    source_version = ordered_versions[best_choice - 1]

            if not source_version:
                # 只有单版本或者没找到多版本对应索引，使用 evaluation_version 或者是 ordered_versions[-1]
                source_version = evaluation_version or (ordered_versions[-1] if ordered_versions else None)

            if source_version and source_version.content:
                source_content = source_version.content
                version_num = best_choice if isinstance(best_choice, int) else 1
                review_summary = eval_data.get("reason_for_choice", "")
                version_review = eval_data.get("evaluation", {}).get(f"version{version_num}", {})

                # 2. 更新状态为 auto_optimizing (复用 evaluating 状态，前端显示"评审中")
                chapter.status = "evaluating"
                chapter.generation_step = "auto_optimizing"
                await session.commit()

                # 3. 调用优化函数 do_optimize_recommended_version
                from .optimizer import do_optimize_recommended_version
                optimized_content, _ = await do_optimize_recommended_version(
                    llm_service=llm_service,
                    prompt_service=prompt_service,
                    source_content=source_content,
                    review_summary=review_summary,
                    version_number=version_num,
                    version_review=version_review,
                    user_id=current_user.id,
                )

                if optimized_content and optimized_content.strip():
                    # 4. 创建优化版本
                    optimized_version = ChapterVersion(
                        chapter_id=chapter.id,
                        content=optimized_content,
                        version_label="ai_optimized",
                    )
                    session.add(optimized_version)
                    await session.flush()

                    # 5. 设为选中版本，并将状态改为 waiting_for_confirm
                    chapter.selected_version_id = optimized_version.id
                    chapter.selected_version = optimized_version
                    chapter.status = "waiting_for_confirm"
                    chapter.generation_step = "optimization_done"
                    await session.commit()
                else:
                    raise ValueError("自动优化结果为空")
            else:
                logger.warning("未找到可供优化的源版本，跳过自动优化")
                chapter.status = "waiting_for_confirm"
                chapter.generation_step = "evaluation_done"
                await session.commit()

        except Exception as opt_exc:
            logger.warning("项目 %s 第 %s 章自动优化失败，降级为仅评审: %s", project_id, request.chapter_number, opt_exc)
            # 确保即使优化失败，章节也处于 waiting_for_confirm 状态
            chapter.status = "waiting_for_confirm"
            chapter.generation_step = "evaluation_done"
            await session.commit()
    except Exception as exc:
        logger.exception("项目 %s 第 %s 章评审失败: %s", project_id, request.chapter_number, exc)
        failure_detail = _build_evaluation_failure_detail(exc)
        failure_summary = failure_detail[:120]
        # 回滚事务，恢复状态
        await session.rollback()

        # 重新加载 chapter 对象（因为 rollback 后对象已脱离 session）
        stmt = (
            select(Chapter)
            .where(
                Chapter.project_id == project_id,
                Chapter.chapter_number == request.chapter_number,
            )
        )
        result = await session.execute(stmt)
        chapter = result.scalars().first()

        if chapter:
            # 使用 add_chapter_evaluation 创建失败记录
            # 注意：这里不能再用 add_chapter_evaluation，因为它会设置状态为 waiting_for_confirm
            # 失败时应该设置为 evaluation_failed
            from app.models.novel import ChapterEvaluation
            evaluation_record = ChapterEvaluation(
                chapter_id=chapter.id,
                version_id=version_to_evaluate.id if version_to_evaluate else None,
                decision="failed",
                feedback=failure_detail,
                score=None
            )
            session.add(evaluation_record)
            chapter.status = "evaluation_failed"
            chapter.generation_progress = 0
            chapter.generation_step = f"evaluation_failed|error={failure_summary}"
            chapter.generation_step_index = 0
            chapter.generation_step_total = 3
            await session.commit()
            trace_service = ChapterGenerationTraceService(session)
            try:
                await trace_service.record_failure(
                    project_id=project_id,
                    chapter_number=request.chapter_number,
                    node_key="quality_review",
                    node_label="AI评审",
                    stage="version_review",
                    error=failure_detail,
                    input_payload={
                        "version_count": len(ordered_versions),
                        "selected_version_id": version_to_evaluate.id if version_to_evaluate else None,
                    },
                    metadata={
                        "trace_kind": "llm",
                        "call_type": "chat_llm",
                        "summary": "手动 AI 评审失败，章节保留候选版本等待重试。",
                        "actions": [
                            "读取章节候选版本",
                            "构建评审上下文",
                            "调用 AI 评审服务",
                        ],
                        "model_calls": [
                            {
                                "stage": "version_review",
                                "call_type": "chat_llm",
                                "purpose": "AI评审候选版本并产出修改建议",
                            }
                        ],
                    },
                    started_at=datetime.now(CN_TIMEZONE),
                    ended_at=datetime.now(CN_TIMEZONE),
                )
            except Exception:
                logger.exception("项目 %s 第 %s 章记录评审失败 trace 失败", project_id, request.chapter_number)

        # 抛出异常，让前端知道评审失败
        raise HTTPException(status_code=500, detail=failure_detail) from exc

    return await _load_project_schema(novel_service, project_id, current_user.id)



@router.post("/novels/{project_id}/chapters/update-outline", response_model=NovelProjectSchema)
async def update_chapter_outline(
    project_id: str,
    request: UpdateChapterOutlineRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    await novel_service.ensure_project_owner(project_id, current_user.id)

    outline = await novel_service.get_outline(project_id, request.chapter_number)
    if not outline:
        raise HTTPException(status_code=404, detail="未找到对应章节大纲")

    outline.title = request.title
    outline.summary = request.summary
    outline.goals = request.goals
    outline.highlights = request.highlights
    outline.character_states = request.character_states
    await session.commit()

    return await _load_project_schema(novel_service, project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/delete", response_model=NovelProjectSchema)
async def delete_chapters(
    project_id: str,
    request: DeleteChapterRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    await novel_service.ensure_project_owner(project_id, current_user.id)

    await novel_service.delete_chapters(
        project_id,
        request.chapter_numbers,
        delete_artifacts_confirmed=request.delete_artifacts_confirmed,
        confirmation_text=request.confirmation_text,
    )
    return await _load_project_schema(novel_service, project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/outline", response_model=BackgroundTaskResponse, status_code=202)
async def generate_chapters_outline(
    project_id: str,
    request: GenerateOutlineRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> BackgroundTaskResponse:
    novel_service = NovelService(session)
    await novel_service.ensure_project_owner(project_id, current_user.id)

    task = await JobService(session).enqueue_job(
        user_id=current_user.id,
        project_id=project_id,
        job_type="chapter_outline",
        title=f"生成第 {request.start_chapter} 章起的后续大纲",
        payload={
            "project_id": project_id,
            "start_chapter": request.start_chapter,
            "num_chapters": request.num_chapters,
        },
        payload_version=1,
    )

    return task


@router.post("/novels/{project_id}/chapters/edit", response_model=NovelProjectSchema)
async def edit_chapter_content(
    project_id: str,
    request: EditChapterRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    await ChapterEditService(session).apply_content(
        project_id=project_id,
        chapter_number=request.chapter_number,
        content=request.content,
        user_id=current_user.id,
        version_label="manual_edit",
    )
    novel_service = NovelService(session)
    return await _load_project_schema(novel_service, project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/edit-fast", response_model=ChapterSchema)
async def edit_chapter_content_fast(
    project_id: str,
    request: EditChapterRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> ChapterSchema:
    await ChapterEditService(session).apply_content(
        project_id=project_id,
        chapter_number=request.chapter_number,
        content=request.content,
        user_id=current_user.id,
        version_label="manual_edit",
    )

    stmt = (
        select(Chapter)
        .options(
            selectinload(Chapter.versions),
            selectinload(Chapter.evaluations),
            selectinload(Chapter.selected_version),
        )
        .where(
            Chapter.project_id == project_id,
            Chapter.chapter_number == request.chapter_number,
        )
    )
    result = await session.execute(stmt)
    chapter = result.scalars().first()
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")

    outline_stmt = select(ChapterOutline).where(
        ChapterOutline.project_id == project_id,
        ChapterOutline.chapter_number == request.chapter_number,
    )
    outline_result = await session.execute(outline_stmt)
    outline = outline_result.scalars().first()

    title = outline.title if outline else f"第{request.chapter_number}章"
    summary = outline.summary if outline else ""
    real_summary = chapter.real_summary
    selected_version = None
    if chapter.selected_version_id and chapter.versions:
        selected_version = next((v for v in chapter.versions if v.id == chapter.selected_version_id), None)
    if (
        selected_version is None
        and chapter.selected_version
        and (
            chapter.selected_version_id is None
            or chapter.selected_version.id == chapter.selected_version_id
        )
    ):
        selected_version = chapter.selected_version
    content = selected_version.content if selected_version else None
    versions = (
        [v.content for v in sorted(chapter.versions, key=lambda item: item.created_at)]
        if chapter.versions
        else None
    )
    evaluation_text = None
    if chapter.evaluations:
        latest = sorted(chapter.evaluations, key=lambda item: item.created_at)[-1]
        evaluation_text = latest.feedback or latest.decision
    status_value = chapter.status or ChapterGenerationStatus.NOT_GENERATED.value

    return ChapterSchema(
        chapter_number=request.chapter_number,
        title=title,
        summary=summary,
        real_summary=real_summary,
        content=content,
        versions=versions,
        evaluation=evaluation_text,
        generation_status=ChapterGenerationStatus(status_value),
        generation_progress=chapter.generation_progress,
        generation_step=chapter.generation_step,
        generation_step_index=chapter.generation_step_index,
        generation_step_total=chapter.generation_step_total,
        generation_started_at=chapter.__dict__.get("generation_started_at"),
        status_updated_at=chapter.__dict__.get("updated_at"),
        word_count=chapter.word_count or 0,
    )
