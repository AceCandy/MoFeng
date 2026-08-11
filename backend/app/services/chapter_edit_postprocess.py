# AIMETA P=章节编辑持久后处理_摘要索引伏笔收敛|R=版本CAS_外部activity_原子投影提交|NR=不处理HTTP正文编辑|E=handle_chapter_edit_postprocess_job|X=job|A=durable_handler|D=sqlalchemy,llm,pgvector|S=db,net|RD=./README.ai
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional

from pydantic import ValidationError
from sqlalchemy import select

from ..models.novel import ChapterOutline
from ..repositories.novel_repository import NovelRepository
from ..schemas.chapter_context import stable_digest
from ..schemas.job import ChapterEditPostprocessJobPayload, ChapterFinalizeJobPayload
from ..utils.json_utils import remove_think_tags
from .chapter_ingest_service import ChapterIngestionService, PreparedChapterIngestion
from .foreshadowing_sync_service import (
    ForeshadowingComputeContext,
    ForeshadowingLLMRequest,
    ForeshadowingPlan,
    ForeshadowingSyncService,
)
from .job_worker import JobOutcome, PermanentJobError
from .llm_service import LLMService
from .prompt_service import PromptService


class _PostprocessSuperseded(RuntimeError):
    pass


@dataclass(frozen=True)
class ChapterPostprocessSnapshot:
    """一次后处理计算绑定的正文与提示词快照。"""

    content: str
    title: str
    summary_prompt: str
    foreshadowing: ForeshadowingComputeContext


ActivityCall = Callable[[], Awaitable[dict[str, Any]]]


def _artifact_lineage(
    payload: ChapterEditPostprocessJobPayload,
) -> tuple[int, str, Optional[str], Optional[str]]:
    """把 canonical legacy payload 映射为派生产物 lineage。"""

    if not isinstance(payload, ChapterFinalizeJobPayload) or payload.chapter_revision_id is None:
        return 0, "legacy", None, None
    if payload.revision is None or payload.source_hash is None or payload.source_generation is None:
        raise PermanentJobError("invalid_legacy_lineage", "章节定稿任务缺少 canonical lineage")
    return payload.revision, "legacy", payload.source_hash, payload.source_generation


async def _is_current(
    context,
    payload: ChapterEditPostprocessJobPayload,
) -> bool:
    async with context.session_factory() as session:
        pair = await NovelRepository(session).get_owned_selected_version(
            project_id=payload.project_id,
            chapter_number=payload.chapter_number,
            user_id=context.lease.user_id,
        )
    if pair is None:
        return False
    chapter, version = pair
    return (
        chapter.selected_version_id == payload.selected_version_id
        and version.id == payload.selected_version_id
        and stable_digest(version.content) == payload.content_hash
    )


async def _run_ambiguous_activity(
    context,
    payload: ChapterEditPostprocessJobPayload,
    *,
    activity_key: str,
    request_payload: dict[str, Any],
    call: ActivityCall,
) -> dict[str, Any]:
    if not await _is_current(context, payload):
        raise _PostprocessSuperseded
    activity = await context.begin_activity(activity_key, request_payload=request_payload)
    if activity.should_execute:
        try:
            result = await call()
        except Exception:
            await context.mark_activity_ambiguous(
                activity_key,
                provider_request_key=activity.provider_request_key,
                public_message="章节后处理外部调用结果不确定，需要人工确认",
            )
            raise AssertionError("mark_activity_ambiguous 必须终止当前执行")
        await context.complete_activity(
            activity_key,
            provider_request_key=activity.provider_request_key,
            result=result,
        )
    else:
        result = dict(activity.result or {})
    if not await _is_current(context, payload):
        raise _PostprocessSuperseded
    return result


async def _load_snapshot(
    context,
    payload: ChapterEditPostprocessJobPayload,
) -> Optional[ChapterPostprocessSnapshot]:
    async with context.session_factory() as session:
        pair = await NovelRepository(session).get_owned_selected_version(
            project_id=payload.project_id,
            chapter_number=payload.chapter_number,
            user_id=context.lease.user_id,
        )
        if pair is None:
            return None
        chapter, version = pair
        if (
            chapter.selected_version_id != payload.selected_version_id
            or version.id != payload.selected_version_id
            or stable_digest(version.content) != payload.content_hash
        ):
            return None

        summary_prompt = await PromptService(session).get_prompt("extraction")
        if not summary_prompt:
            raise PermanentJobError("summary_prompt_missing", "未配置章节摘要提示词")
        outline = (
            (
                await session.execute(
                    select(ChapterOutline).where(
                        ChapterOutline.project_id == payload.project_id,
                        ChapterOutline.chapter_number == payload.chapter_number,
                    )
                )
            )
            .scalars()
            .first()
        )
        foreshadowing = await ForeshadowingSyncService(session).load_compute_context(
            project_id=payload.project_id,
            chapter_number=payload.chapter_number,
            content=version.content,
        )
        return ChapterPostprocessSnapshot(
            content=version.content,
            title=outline.title if outline and outline.title else f"第{payload.chapter_number}章",
            summary_prompt=summary_prompt,
            foreshadowing=foreshadowing,
        )


def _superseded_outcome(payload: ChapterEditPostprocessJobPayload) -> JobOutcome:
    return JobOutcome(
        result={
            "status": "superseded",
            "project_id": payload.project_id,
            "chapter_number": payload.chapter_number,
            "content_hash": payload.content_hash,
        }
    )


async def handle_chapter_edit_postprocess_job(
    context,
    *,
    payload_override: Optional[ChapterEditPostprocessJobPayload] = None,
    snapshot_override: Optional[ChapterPostprocessSnapshot] = None,
) -> JobOutcome:
    """计算外部结果，并在 job success 事务内 CAS 应用全部 PostgreSQL 投影。"""

    if payload_override is None:
        try:
            payload = ChapterEditPostprocessJobPayload.model_validate(context.lease.payload)
        except ValidationError as exc:
            raise PermanentJobError(
                "invalid_chapter_edit_payload", "章节后处理任务参数无效"
            ) from exc
    else:
        payload = payload_override
    if context.lease.project_id != payload.project_id:
        raise PermanentJobError("chapter_edit_project_mismatch", "章节后处理任务项目不匹配")

    revision, artifact_generation, expected_source_hash, expected_source_generation = (
        _artifact_lineage(payload)
    )
    snapshot = snapshot_override or await _load_snapshot(context, payload)
    if snapshot is None:
        return _superseded_outcome(payload)

    try:
        await context.progress("正在生成章节摘要", progress=20)

        async def generate_summary() -> dict[str, Any]:
            response = await LLMService.get_summary_detached(
                snapshot.content,
                session_factory=context.session_factory,
                temperature=0.15,
                user_id=context.lease.user_id,
                system_prompt=snapshot.summary_prompt,
                stage="summary_memory",
            )
            return {"response": response}

        summary_result = await _run_ambiguous_activity(
            context,
            payload,
            activity_key="summary_generation",
            request_payload={
                "project_id": payload.project_id,
                "chapter_number": payload.chapter_number,
                "content_hash": payload.content_hash,
            },
            call=generate_summary,
        )
        summary_text = remove_think_tags(str(summary_result.get("response") or "")).strip()
        if not summary_text:
            raise PermanentJobError("invalid_summary_response", "章节摘要模型未返回有效内容")

        async def call_foreshadowing_model(request: ForeshadowingLLMRequest) -> str:
            async def invoke() -> dict[str, Any]:
                response = await LLMService.get_llm_response_detached(
                    system_prompt=request.system_prompt,
                    conversation_history=[{"role": "user", "content": request.user_prompt}],
                    session_factory=context.session_factory,
                    temperature=0.1,
                    user_id=context.lease.user_id,
                    timeout=90.0,
                    response_format="json_object",
                    max_tokens=request.max_tokens,
                    stage="foreshadowing",
                )
                return {"response": response}

            result = await _run_ambiguous_activity(
                context,
                payload,
                activity_key=request.activity_key,
                request_payload={
                    "project_id": payload.project_id,
                    "chapter_number": payload.chapter_number,
                    "content_hash": payload.content_hash,
                    "stage": request.activity_key,
                },
                call=invoke,
            )
            return str(result.get("response") or "")

        await context.progress("正在计算章节伏笔变更", progress=45)
        foreshadowing_plan = await ForeshadowingSyncService.compute_plan(
            snapshot.foreshadowing,
            llm_call=call_foreshadowing_model,
            tolerate_llm_errors=False,
        )

        prepared: Optional[PreparedChapterIngestion] = None
        if not payload.skip_vector_update:
            await context.progress("正在生成章节检索向量", progress=70)

            async def prepare_ingestion() -> dict[str, Any]:
                async def embed(text: str) -> list[float]:
                    return await LLMService.get_embedding_detached(
                        text,
                        session_factory=context.session_factory,
                        user_id=context.lease.user_id,
                        stage="rag_embedding",
                    )

                candidate = await ChapterIngestionService().prepare_chapter(
                    project_id=payload.project_id,
                    chapter_number=payload.chapter_number,
                    title=snapshot.title,
                    content=snapshot.content,
                    content_hash=payload.content_hash,
                    summary=summary_text,
                    user_id=context.lease.user_id,
                    revision=revision,
                    artifact_generation=artifact_generation,
                    projection_run_id=None,
                    embedding_provider=embed,
                )
                if not candidate.complete:
                    raise RuntimeError("章节 embedding 未完整生成")
                return {"projection": candidate.to_payload()}

            ingestion_result = await _run_ambiguous_activity(
                context,
                payload,
                activity_key="chapter_embedding",
                request_payload={
                    "project_id": payload.project_id,
                    "chapter_number": payload.chapter_number,
                    "content_hash": payload.content_hash,
                },
                call=prepare_ingestion,
            )
            projection_payload = ingestion_result.get("projection")
            if not isinstance(projection_payload, dict):
                raise PermanentJobError("invalid_embedding_result", "章节向量活动结果无效")
            prepared = PreparedChapterIngestion.from_payload(projection_payload)
            if not prepared.complete:
                raise PermanentJobError("incomplete_embedding_result", "章节向量活动结果不完整")
    except _PostprocessSuperseded:
        return _superseded_outcome(payload)

    result: dict[str, Any] = {
        "status": "applied",
        "project_id": payload.project_id,
        "chapter_number": payload.chapter_number,
        "content_hash": payload.content_hash,
        "vector_ingested": prepared is not None,
    }

    async def write_outcome(session) -> None:
        pair = await NovelRepository(session).get_owned_selected_version(
            project_id=payload.project_id,
            chapter_number=payload.chapter_number,
            user_id=context.lease.user_id,
            for_update=True,
        )
        if pair is None:
            result["status"] = "superseded"
            return
        chapter, version = pair
        if (
            chapter.selected_version_id != payload.selected_version_id
            or version.id != payload.selected_version_id
            or stable_digest(version.content) != payload.content_hash
        ):
            result["status"] = "superseded"
            return

        chapter.real_summary = summary_text
        if prepared is not None:
            await ChapterIngestionService().apply_prepared(
                session,
                project_id=payload.project_id,
                chapter_number=payload.chapter_number,
                revision=revision,
                artifact_generation=artifact_generation,
                projection_run_id=None,
                expected_source_hash=expected_source_hash,
                expected_source_generation=expected_source_generation,
                prepared=prepared,
            )
        stats = await ForeshadowingSyncService(session).apply_plan(
            project_id=payload.project_id,
            chapter=chapter,
            plan=foreshadowing_plan,
            chapter_revision=revision,
            artifact_generation=artifact_generation,
            projection_run_id=None,
        )
        result["foreshadowing_sync"] = stats

    await context.progress("后处理结果已就绪，等待原子提交", progress=95)
    return JobOutcome(result=result, outcome_writer=write_outcome)


__all__ = ["handle_chapter_edit_postprocess_job"]
