# AIMETA P=章节投影任务处理器_summary_memory_RAG_伏笔_reconcile|R=typed_job执行_DAG推进_结果提交|NR=不拥有claim_lease_retry状态机|E=CHAPTER_PROJECTION_HANDLERS|X=worker|A=handler|D=job_service,sqlalchemy|S=db,net|RD=./README.ai
"""Typed durable handlers for the chapter projection DAG."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Awaitable, Callable
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import func, select, update

from ..models.chapter_projection import ChapterOutboxEvent, ChapterProjectionRun
from ..models.foreshadowing import Foreshadowing
from ..models.job import JobEvent
from ..models.memory_layer import CharacterState
from ..models.novel import ChapterOutline
from ..models.project_memory import ChapterSnapshot
from ..models.rag import RagChunk, RagSummary
from ..schemas.job import ChapterProjectionJobPayload, ChapterTombstoneJobPayload
from ..schemas.novel import ChapterGenerationStatus
from ..utils.ai_telemetry import AICallResult, combine_ai_call_results
from ..utils.json_utils import remove_think_tags
from .chapter_ingest_service import ChapterIngestionService, PreparedChapterIngestion
from .chapter_memory_projection import (
    apply_memory_projection,
    load_memory_input,
    memory_prompts,
    parse_memory_results,
)
from .chapter_projection_runtime import (
    complete_projection,
    enqueue_downstream_projections,
    load_current_projection,
    load_current_tombstone,
    mark_projection_running,
    mark_projection_stale,
    mark_tombstone_running,
    maybe_enqueue_reconciler,
)
from .chapter_projection_rollout import (
    ChapterProjectionObservationPendingError,
    ChapterProjectionRolloutService,
)
from .foreshadowing_sync_service import (
    ForeshadowingLLMRequest,
    ForeshadowingSyncService,
    deserialize_foreshadowing_context,
    serialize_foreshadowing_plan,
)
from .job_worker import JobOutcome, PermanentJobError, RetryableJobError
from .llm_service import LLMService
from .prompt_service import PromptService


ActivityCall = Callable[
    [],
    Awaitable[dict[str, Any] | AICallResult[dict[str, Any]]],
]


def _parse_payload(context) -> ChapterProjectionJobPayload:
    try:
        payload = ChapterProjectionJobPayload.model_validate(context.lease.payload)
    except ValidationError as exc:
        raise PermanentJobError(
            "invalid_chapter_projection_payload",
            "章节投影任务参数无效",
        ) from exc
    if context.lease.project_id != payload.project_id:
        raise PermanentJobError(
            "chapter_projection_project_mismatch",
            "章节投影任务项目不匹配",
        )
    return payload


async def _start_projection(context, payload: ChapterProjectionJobPayload, name: str) -> bool:
    async with context.session_factory() as session:
        current = await mark_projection_running(
            session,
            payload=payload,
            user_id=context.lease.user_id,
            job_id=context.lease.job_id,
            expected_projection=name,
            attempt=context.lease.attempt,
            fencing_token=context.lease.fencing_token,
            executor_generation=context.lease.executor_generation,
        )
        await session.commit()
        return current


async def _start_tombstone(context, payload: ChapterTombstoneJobPayload) -> bool:
    async with context.session_factory() as session:
        current = await mark_tombstone_running(
            session,
            payload=payload,
            user_id=context.lease.user_id,
            job_id=context.lease.job_id,
            attempt=context.lease.attempt,
            fencing_token=context.lease.fencing_token,
            executor_generation=context.lease.executor_generation,
        )
        await session.commit()
        return current


async def _run_activity(
    context,
    _payload: ChapterProjectionJobPayload,
    *,
    activity_key: str,
    request_payload: dict[str, Any],
    call: ActivityCall,
) -> dict[str, Any]:
    activity = await context.begin_activity(activity_key, request_payload=request_payload)
    if not activity.should_execute:
        return dict(activity.result or {})
    try:
        call_result = await call()
        ai_call = call_result if isinstance(call_result, AICallResult) else None
        result = call_result.value if ai_call is not None else call_result
        if not isinstance(result, dict):
            raise TypeError("projection activity 必须返回 dict")
    except Exception as exc:
        status_code = getattr(exc, "status_code", None)
        if status_code is None:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
        if status_code == 429 or (
            isinstance(status_code, int) and status_code >= 500
        ):
            await context.mark_activity_failed(
                activity_key,
                provider_request_key=activity.provider_request_key,
                error_category="provider_retryable_error",
                retryable=True,
            )
            raise RetryableJobError(
                "provider_retryable_error",
                "章节投影外部服务暂时不可用",
            ) from exc
        if isinstance(status_code, int) and 400 <= status_code < 500:
            await context.mark_activity_failed(
                activity_key,
                provider_request_key=activity.provider_request_key,
                error_category="provider_request_rejected",
                retryable=False,
            )
            raise PermanentJobError(
                "provider_request_rejected",
                "章节投影外部请求被拒绝",
            ) from exc
        if isinstance(exc, (ValueError, TypeError)):
            await context.mark_activity_failed(
                activity_key,
                provider_request_key=activity.provider_request_key,
                error_category="projection_activity_invalid",
                retryable=False,
            )
            raise PermanentJobError(
                "projection_activity_invalid",
                "章节投影活动输入或结果无效",
            ) from exc
        await context.mark_activity_ambiguous(
            activity_key,
            provider_request_key=activity.provider_request_key,
            public_message="章节投影外部调用结果不确定，需要人工确认",
        )
        raise AssertionError("mark_activity_ambiguous 必须终止当前执行")
    await context.complete_activity(
        activity_key,
        provider_request_key=activity.provider_request_key,
        result=result,
        ai_call=ai_call,
    )
    return result


def _stale_outcome(payload: ChapterProjectionJobPayload, name: str) -> JobOutcome:
    return JobOutcome(
        result={
            "status": "stale",
            "projection": name,
            "project_id": payload.project_id,
            "chapter_number": payload.chapter_number,
            "revision": payload.revision,
        }
    )


async def handle_chapter_summary_projection(context) -> JobOutcome:
    """Compute and commit the summary before creating dependent child jobs."""

    payload = _parse_payload(context)
    if not await _start_projection(context, payload, "summary"):
        return _stale_outcome(payload, "summary")

    async with context.session_factory() as session:
        current = await load_current_projection(
            session,
            payload=payload,
            user_id=context.lease.user_id,
            job_id=context.lease.job_id,
            expected_projection="summary",
            for_update=False,
        )
        if current is None:
            return _stale_outcome(payload, "summary")
        projection_context = current.revision.projection_context or {}
        summary_prompt = projection_context.get("summary_prompt")
        if not summary_prompt:
            summary_prompt = await PromptService(session).get_prompt("extraction")
        source_content = current.revision.source_content
    if not summary_prompt:
        raise PermanentJobError("summary_prompt_missing", "未配置章节摘要提示词")

    await context.progress("正在生成章节摘要", progress=25)

    async def generate_summary() -> AICallResult[dict[str, Any]]:
        response = await LLMService.get_summary_result_detached(
            source_content,
            session_factory=context.session_factory,
            temperature=0.15,
            user_id=context.lease.user_id,
            system_prompt=summary_prompt,
            stage="summary_memory",
        )
        return response.with_value({"response": response.value})

    activity_result = await _run_activity(
        context,
        payload,
        activity_key="summary_generation",
        request_payload={
            "project_id": payload.project_id,
            "chapter_id": payload.chapter_id,
            "revision": payload.revision,
            "source_hash": payload.source_hash,
        },
        call=generate_summary,
    )
    summary_text = remove_think_tags(str(activity_result.get("response") or "")).strip()
    if not summary_text:
        raise PermanentJobError("invalid_summary_response", "章节摘要模型未返回有效内容")

    result: dict[str, Any] = {
        "status": "projected",
        "projection": "summary",
        "project_id": payload.project_id,
        "chapter_number": payload.chapter_number,
        "revision": payload.revision,
        "execution_mode": payload.execution_mode,
    }

    async def write_outcome(session) -> None:
        current = await load_current_projection(
            session,
            payload=payload,
            user_id=context.lease.user_id,
            job_id=context.lease.job_id,
            expected_projection="summary",
            for_update=True,
        )
        if current is None:
            result["status"] = "stale"
            await mark_projection_stale(
                session,
                run_id=payload.projection_run_id,
                job_id=context.lease.job_id,
                reason="canonical_revision_changed",
            )
            return
        activate = payload.execution_mode == "active"
        if activate:
            current.chapter.real_summary = summary_text
        await complete_projection(
            session,
            current=current,
            result={"summary": summary_text},
            activate=activate,
        )
        children = await enqueue_downstream_projections(
            session,
            payload=payload,
            current=current,
            user_id=context.lease.user_id,
        )
        result["queued_projections"] = sorted(
            run.projection_name for run in children if run.status == "queued"
        )

    await context.progress("摘要结果已就绪，等待原子提交", progress=95)
    return JobOutcome(result=result, outcome_writer=write_outcome)


async def handle_chapter_memory_projection(context) -> JobOutcome:
    """Compute memory fields outside transactions and apply one fenced generation."""

    payload = _parse_payload(context)
    if not await _start_projection(context, payload, "memory"):
        return _stale_outcome(payload, "memory")

    async with context.session_factory() as session:
        current = await load_current_projection(
            session,
            payload=payload,
            user_id=context.lease.user_id,
            job_id=context.lease.job_id,
            expected_projection="memory",
            for_update=False,
        )
        if current is None:
            return _stale_outcome(payload, "memory")
        source_content = current.revision.source_content
        projection_context = current.revision.projection_context or {}
        raw_memory_input = projection_context.get("memory")
        memory_input = (
            dict(raw_memory_input)
            if isinstance(raw_memory_input, dict)
            else await load_memory_input(session, project_id=payload.project_id)
        )

    requests = memory_prompts(
        chapter_text=source_content,
        chapter_number=payload.chapter_number,
        memory_input=memory_input,
    )
    activity_results: dict[str, dict[str, Any]] = {}
    for index, (field, request) in enumerate(requests.items(), start=1):
        await context.progress(f"正在计算章节记忆 {index}/4", progress=15 + index * 15)

        async def invoke(request=request) -> AICallResult[dict[str, Any]]:
            response = await LLMService.generate_result_detached(
                request["prompt"],
                session_factory=context.session_factory,
                temperature=0.3,
                user_id=context.lease.user_id,
                max_tokens=request["max_tokens"],
                response_format=request["response_format"],
                stage="summary_memory",
            )
            return response.with_value({"response": response.value})

        activity_results[field] = await _run_activity(
            context,
            payload,
            activity_key=f"memory_{field}",
            request_payload={
                "project_id": payload.project_id,
                "chapter_id": payload.chapter_id,
                "revision": payload.revision,
                "source_hash": payload.source_hash,
                "field": field,
            },
            call=invoke,
        )

    prepared = parse_memory_results(
        activity_results=activity_results,
        memory_input=memory_input,
    )
    if not prepared.get("success"):
        raise PermanentJobError("empty_memory_projection", "章节记忆投影未产生有效结果")

    result: dict[str, Any] = {
        "status": "projected",
        "projection": "memory",
        "project_id": payload.project_id,
        "chapter_number": payload.chapter_number,
        "revision": payload.revision,
        "partial_success": bool(prepared.get("partial_success")),
    }

    async def write_outcome(session) -> None:
        current = await load_current_projection(
            session,
            payload=payload,
            user_id=context.lease.user_id,
            job_id=context.lease.job_id,
            expected_projection="memory",
            for_update=True,
        )
        if current is None:
            result["status"] = "stale"
            await mark_projection_stale(
                session,
                run_id=payload.projection_run_id,
                job_id=context.lease.job_id,
                reason="canonical_revision_changed",
            )
            return
        stats = await apply_memory_projection(
            session,
            project_id=payload.project_id,
            chapter_number=payload.chapter_number,
            chapter_text=current.revision.source_content,
            revision=payload.revision,
            artifact_generation=payload.artifact_generation,
            projection_run_id=payload.projection_run_id,
            expected_source_hash=payload.source_hash,
            expected_source_generation=payload.source_generation,
            prepared=prepared,
            activate=payload.execution_mode == "active",
        )
        result.update(stats)
        await complete_projection(
            session,
            current=current,
            result=stats,
            activate=payload.execution_mode == "active",
        )
        await maybe_enqueue_reconciler(
            session,
            payload=payload,
            current=current,
            user_id=context.lease.user_id,
        )

    return JobOutcome(result=result, outcome_writer=write_outcome)


async def handle_chapter_rag_projection(context) -> JobOutcome:
    """Build a deterministic vector generation and atomically switch it active."""

    payload = _parse_payload(context)
    if not await _start_projection(context, payload, "rag"):
        return _stale_outcome(payload, "rag")

    async with context.session_factory() as session:
        current = await load_current_projection(
            session,
            payload=payload,
            user_id=context.lease.user_id,
            job_id=context.lease.job_id,
            expected_projection="rag",
            for_update=False,
        )
        if current is None or current.dependency is None:
            return _stale_outcome(payload, "rag")
        source_content = current.revision.source_content
        summary_text = str((current.dependency.result or {}).get("summary") or "").strip()
        projection_context = current.revision.projection_context or {}
        title = projection_context.get("rag_title")
        if not isinstance(title, str) or not title:
            outline = (
                await session.execute(
                    select(ChapterOutline).where(
                        ChapterOutline.project_id == payload.project_id,
                        ChapterOutline.chapter_number == payload.chapter_number,
                    )
                )
            ).scalars().first()
            title = outline.title if outline and outline.title else f"第{payload.chapter_number}章"
    if not summary_text:
        raise PermanentJobError("summary_dependency_missing", "RAG 投影缺少已提交摘要")

    async def prepare_ingestion() -> AICallResult[dict[str, Any]]:
        embedding_results: list[AICallResult[list[float]]] = []

        async def embed(text: str) -> list[float]:
            embedding_result = await LLMService.get_embedding_result_detached(
                text,
                session_factory=context.session_factory,
                user_id=context.lease.user_id,
                stage="rag_embedding",
            )
            embedding_results.append(embedding_result)
            return embedding_result.value

        prepared = await ChapterIngestionService().prepare_chapter(
            project_id=payload.project_id,
            chapter_number=payload.chapter_number,
            title=title,
            content=source_content,
            content_hash=payload.source_hash,
            summary=summary_text,
            user_id=context.lease.user_id,
            revision=payload.revision,
            artifact_generation=payload.artifact_generation,
            projection_run_id=payload.projection_run_id,
            embedding_provider=embed,
        )
        if not prepared.enabled or not prepared.complete:
            raise RuntimeError("章节 RAG embedding 未完整生成")
        return combine_ai_call_results(
            {"projection": prepared.to_payload()},
            embedding_results,
        )

    activity_result = await _run_activity(
        context,
        payload,
        activity_key="rag_embedding",
        request_payload={
            "project_id": payload.project_id,
            "chapter_id": payload.chapter_id,
            "revision": payload.revision,
            "source_hash": payload.source_hash,
            "artifact_generation": payload.artifact_generation,
        },
        call=prepare_ingestion,
    )
    raw_projection = activity_result.get("projection")
    if not isinstance(raw_projection, dict):
        raise PermanentJobError("invalid_rag_projection", "RAG 活动结果无效")
    prepared = PreparedChapterIngestion.from_payload(raw_projection)

    result: dict[str, Any] = {
        "status": "projected",
        "projection": "rag",
        "project_id": payload.project_id,
        "chapter_number": payload.chapter_number,
        "revision": payload.revision,
        "chunk_count": len(prepared.chunk_records),
        "summary_count": len(prepared.summary_records),
    }

    async def write_outcome(session) -> None:
        current = await load_current_projection(
            session,
            payload=payload,
            user_id=context.lease.user_id,
            job_id=context.lease.job_id,
            expected_projection="rag",
            for_update=True,
        )
        if current is None:
            result["status"] = "stale"
            await mark_projection_stale(
                session,
                run_id=payload.projection_run_id,
                job_id=context.lease.job_id,
                reason="canonical_revision_changed",
            )
            return
        await ChapterIngestionService().apply_prepared(
            session,
            project_id=payload.project_id,
            chapter_number=payload.chapter_number,
            revision=payload.revision,
            artifact_generation=payload.artifact_generation,
            projection_run_id=payload.projection_run_id,
            prepared=prepared,
            activate=payload.execution_mode == "active",
        )
        await complete_projection(
            session,
            current=current,
            result={
                "chunk_count": len(prepared.chunk_records),
                "summary_count": len(prepared.summary_records),
            },
            activate=payload.execution_mode == "active",
        )
        await maybe_enqueue_reconciler(
            session,
            payload=payload,
            current=current,
            user_id=context.lease.user_id,
        )

    return JobOutcome(result=result, outcome_writer=write_outcome)


async def handle_chapter_foreshadowing_projection(context) -> JobOutcome:
    """Compute and apply a versioned foreshadowing plan."""

    payload = _parse_payload(context)
    if not await _start_projection(context, payload, "foreshadowing"):
        return _stale_outcome(payload, "foreshadowing")

    async with context.session_factory() as session:
        current = await load_current_projection(
            session,
            payload=payload,
            user_id=context.lease.user_id,
            job_id=context.lease.job_id,
            expected_projection="foreshadowing",
            for_update=False,
        )
        if current is None:
            return _stale_outcome(payload, "foreshadowing")
        projection_context = current.revision.projection_context or {}
        raw_foreshadowing_context = projection_context.get("foreshadowing")
        compute_context = (
            deserialize_foreshadowing_context(raw_foreshadowing_context)
            if isinstance(raw_foreshadowing_context, dict)
            else await ForeshadowingSyncService(session).load_compute_context(
                project_id=payload.project_id,
                chapter_number=payload.chapter_number,
                content=current.revision.source_content,
            )
        )

    async def llm_call(request: ForeshadowingLLMRequest) -> str:
        async def invoke() -> AICallResult[dict[str, Any]]:
            response = await LLMService.get_llm_response_result_detached(
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
            return response.with_value({"response": response.value})

        activity_result = await _run_activity(
            context,
            payload,
            activity_key=request.activity_key,
            request_payload={
                "project_id": payload.project_id,
                "chapter_id": payload.chapter_id,
                "revision": payload.revision,
                "source_hash": payload.source_hash,
                "stage": request.activity_key,
            },
            call=invoke,
        )
        return str(activity_result.get("response") or "")

    plan = await ForeshadowingSyncService.compute_plan(
        compute_context,
        llm_call=llm_call,
        tolerate_llm_errors=False,
    )
    result: dict[str, Any] = {
        "status": "projected",
        "projection": "foreshadowing",
        "project_id": payload.project_id,
        "chapter_number": payload.chapter_number,
        "revision": payload.revision,
    }

    async def write_outcome(session) -> None:
        current = await load_current_projection(
            session,
            payload=payload,
            user_id=context.lease.user_id,
            job_id=context.lease.job_id,
            expected_projection="foreshadowing",
            for_update=True,
        )
        if current is None:
            result["status"] = "stale"
            await mark_projection_stale(
                session,
                run_id=payload.projection_run_id,
                job_id=context.lease.job_id,
                reason="canonical_revision_changed",
            )
            return
        plan_payload = serialize_foreshadowing_plan(plan)
        stats = await ForeshadowingSyncService(session).apply_plan(
            project_id=payload.project_id,
            chapter=current.chapter,
            plan=plan,
            chapter_revision=payload.revision,
            artifact_generation=payload.artifact_generation,
            projection_run_id=payload.projection_run_id,
            activate=payload.execution_mode == "active",
        )
        result.update(stats)
        await complete_projection(
            session,
            current=current,
            result={**stats, "plan": plan_payload},
            activate=payload.execution_mode == "active",
        )
        await maybe_enqueue_reconciler(
            session,
            payload=payload,
            current=current,
            user_id=context.lease.user_id,
        )

    return JobOutcome(result=result, outcome_writer=write_outcome)


async def handle_chapter_trace_projection(context) -> JobOutcome:
    """Project an allowlisted trace summary from workflow JobEvents."""

    payload = _parse_payload(context)
    if not await _start_projection(context, payload, "trace"):
        return _stale_outcome(payload, "trace")

    async with context.session_factory() as session:
        rows = (
            await session.execute(
                select(JobEvent.event_type, func.count(JobEvent.cursor))
                .where(
                    JobEvent.stream_type == "workflow",
                    JobEvent.stream_id == payload.workflow_stream_id,
                    JobEvent.project_id == payload.project_id,
                )
                .group_by(JobEvent.event_type)
            )
        ).all()
    trace = {str(event_type): int(count) for event_type, count in rows}
    result: dict[str, Any] = {
        "status": "projected",
        "projection": "trace",
        "project_id": payload.project_id,
        "chapter_number": payload.chapter_number,
        "revision": payload.revision,
        "event_counts": trace,
    }

    async def write_outcome(session) -> None:
        current = await load_current_projection(
            session,
            payload=payload,
            user_id=context.lease.user_id,
            job_id=context.lease.job_id,
            expected_projection="trace",
            for_update=True,
        )
        if current is None:
            result["status"] = "stale"
            await mark_projection_stale(
                session,
                run_id=payload.projection_run_id,
                job_id=context.lease.job_id,
                reason="canonical_revision_changed",
            )
            return
        await complete_projection(
            session,
            current=current,
            result={"event_counts": trace},
            activate=payload.execution_mode == "active",
        )
        await maybe_enqueue_reconciler(
            session,
            payload=payload,
            current=current,
            user_id=context.lease.user_id,
        )

    return JobOutcome(result=result, outcome_writer=write_outcome)


async def handle_chapter_projection_reconcile(context) -> JobOutcome:
    """Sole owner of finalizing -> successful for a canonical revision."""

    payload = _parse_payload(context)
    if not await _start_projection(context, payload, "reconcile"):
        return _stale_outcome(payload, "reconcile")

    result: dict[str, Any] = {
        "status": "finalized",
        "projection": "reconcile",
        "project_id": payload.project_id,
        "chapter_number": payload.chapter_number,
        "revision": payload.revision,
    }

    async def write_outcome(session) -> None:
        current = await load_current_projection(
            session,
            payload=payload,
            user_id=context.lease.user_id,
            job_id=context.lease.job_id,
            expected_projection="reconcile",
            for_update=True,
        )
        if current is None:
            result["status"] = "stale"
            await mark_projection_stale(
                session,
                run_id=payload.projection_run_id,
                job_id=context.lease.job_id,
                reason="canonical_revision_changed",
            )
            return

        required = set(current.revision.required_projections or [])
        expected_active = payload.execution_mode == "active"
        satisfied = set(
            (
                await session.scalars(
                    select(ChapterProjectionRun.projection_name).where(
                        ChapterProjectionRun.chapter_revision_id == current.revision.id,
                        ChapterProjectionRun.projection_name.in_(required),
                        ChapterProjectionRun.status == "succeeded",
                        ChapterProjectionRun.is_active == expected_active,
                    )
                )
            ).all()
        )
        active_status_invalid = (
            expected_active
            and current.chapter.status != ChapterGenerationStatus.FINALIZING.value
        )
        if satisfied != required or active_status_invalid:
            result["status"] = "not_ready"
            await mark_projection_stale(
                session,
                run_id=payload.projection_run_id,
                job_id=context.lease.job_id,
                reason="required_projection_gate_not_satisfied",
            )
            return

        if payload.execution_mode == "shadow":
            try:
                observation = await ChapterProjectionRolloutService(
                    session
                ).record_shadow_observation(
                    payload=payload,
                    reconcile_run=current.run,
                    chapter=current.chapter,
                    revision=current.revision,
                    rollout=current.rollout,
                )
            except ChapterProjectionObservationPendingError as exc:
                raise RetryableJobError(exc.code, "等待 legacy owner 完成后再记录 shadow 观察") from exc
            result["status"] = (
                "shadow_observed" if observation.outcome == "match" else "shadow_mismatch"
            )
            result["shadow_digest"] = observation.digest
            await complete_projection(
                session,
                current=current,
                result={
                    "observation_id": observation.id,
                    "outcome": observation.outcome,
                    "digest": observation.digest,
                },
                activate=False,
            )
            return

        current.chapter.status = ChapterGenerationStatus.SUCCESSFUL.value
        current.chapter.generation_progress = 100
        current.chapter.generation_step = "finalized"
        current.chapter.generation_step_index = 4
        current.chapter.generation_step_total = 4
        current.revision.lifecycle = "successful"
        await complete_projection(
            session,
            current=current,
            result={"required_projections": sorted(required)},
            activate=True,
        )

        finalized_payload = {
            "project_id": payload.project_id,
            "chapter_id": payload.chapter_id,
            "chapter_number": payload.chapter_number,
            "revision": payload.revision,
            "source_hash": payload.source_hash,
            "required_projections": sorted(required),
        }
        fingerprint = hashlib.sha256(
            json.dumps(
                finalized_payload,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        session.add(
            ChapterOutboxEvent(
                id=str(uuid4()),
                aggregate_type="chapter",
                aggregate_id=str(payload.chapter_id),
                chapter_id=payload.chapter_id,
                project_id=payload.project_id,
                revision=payload.revision,
                event_type="ChapterFinalized",
                event_version=1,
                payload=finalized_payload,
                payload_fingerprint=fingerprint,
                idempotency_key=(
                    f"chapter:{payload.chapter_id}:revision:{payload.revision}:finalized"
                ),
                workflow_stream_type="workflow",
                workflow_stream_id=payload.workflow_stream_id,
                created_at=datetime.now(timezone.utc),
            )
        )

    return JobOutcome(result=result, outcome_writer=write_outcome)


async def handle_chapter_projection_tombstone(context) -> JobOutcome:
    """Deactivate only the revision/generation named by a tombstone fact."""

    try:
        payload = ChapterTombstoneJobPayload.model_validate(context.lease.payload)
    except ValidationError as exc:
        raise PermanentJobError(
            "invalid_chapter_tombstone_payload",
            "章节投影清理任务参数无效",
        ) from exc
    if context.lease.project_id != payload.project_id:
        raise PermanentJobError(
            "chapter_tombstone_project_mismatch",
            "章节投影清理任务项目不匹配",
        )
    if not await _start_tombstone(context, payload):
        return JobOutcome(
            result={
                "status": "stale",
                "projection": "tombstone",
                "project_id": payload.project_id,
                "chapter_number": payload.chapter_number,
                "target_revision": payload.target_revision,
            }
        )

    result: dict[str, Any] = {
        "status": "cleaned",
        "projection": "tombstone",
        "project_id": payload.project_id,
        "chapter_number": payload.chapter_number,
        "target_revision": payload.target_revision,
        "target_generation": payload.target_generation,
    }

    async def write_outcome(session) -> None:
        current = await load_current_tombstone(
            session,
            payload=payload,
            user_id=context.lease.user_id,
            job_id=context.lease.job_id,
            for_update=True,
        )
        if current is None:
            await mark_projection_stale(
                session,
                run_id=payload.projection_run_id,
                job_id=context.lease.job_id,
                reason="tombstone_fact_stale",
            )
            result["status"] = "stale"
            return

        rag_generation = payload.target_artifact_generations.get("rag", payload.target_generation)
        memory_generation = payload.target_artifact_generations.get(
            "memory", payload.target_generation
        )
        foreshadowing_generation = payload.target_artifact_generations.get(
            "foreshadowing", payload.target_generation
        )
        def rag_predicates(model):
            return (
                model.project_id == payload.project_id,
                model.chapter_number == payload.chapter_number,
                model.source_revision == payload.target_revision,
                model.artifact_generation == rag_generation,
                model.is_active.is_(True),
            )

        chunk_result = await session.execute(
            update(RagChunk).where(*rag_predicates(RagChunk)).values(is_active=False)
        )
        summary_result = await session.execute(
            update(RagSummary).where(*rag_predicates(RagSummary)).values(is_active=False)
        )
        snapshot_result = await session.execute(
            update(ChapterSnapshot)
            .where(
                ChapterSnapshot.project_id == payload.project_id,
                ChapterSnapshot.chapter_number == payload.chapter_number,
                ChapterSnapshot.chapter_revision == payload.target_revision,
                ChapterSnapshot.artifact_generation == memory_generation,
                ChapterSnapshot.is_active.is_(True),
            )
            .values(is_active=False)
        )
        state_result = await session.execute(
            update(CharacterState)
            .where(
                CharacterState.project_id == payload.project_id,
                CharacterState.chapter_number == payload.chapter_number,
                CharacterState.chapter_revision == payload.target_revision,
                CharacterState.artifact_generation == memory_generation,
                CharacterState.is_active.is_(True),
            )
            .values(is_active=False)
        )
        foreshadowing_result = await session.execute(
            update(Foreshadowing)
            .where(
                Foreshadowing.project_id == payload.project_id,
                Foreshadowing.chapter_number == payload.chapter_number,
                Foreshadowing.chapter_revision == payload.target_revision,
                Foreshadowing.artifact_generation == foreshadowing_generation,
                Foreshadowing.is_manual.is_(False),
                Foreshadowing.is_active.is_(True),
            )
            .values(is_active=False)
        )
        projection_run_count = 0
        if current.target_revision is not None:
            for projection_name, artifact_generation in sorted(
                payload.target_artifact_generations.items()
            ):
                projection_result = await session.execute(
                    update(ChapterProjectionRun)
                    .where(
                        ChapterProjectionRun.chapter_revision_id
                        == current.target_revision.id,
                        ChapterProjectionRun.projection_name == projection_name,
                        ChapterProjectionRun.artifact_generation == artifact_generation,
                        ChapterProjectionRun.id != current.run.id,
                        ChapterProjectionRun.is_active.is_(True),
                    )
                    .values(
                        status="stale",
                        is_active=False,
                        error_category=payload.reason,
                    )
                )
                projection_run_count += int(projection_result.rowcount or 0)
        result["affected"] = {
            "rag_chunks": int(chunk_result.rowcount or 0),
            "rag_summaries": int(summary_result.rowcount or 0),
            "snapshots": int(snapshot_result.rowcount or 0),
            "character_states": int(state_result.rowcount or 0),
            "foreshadowings": int(foreshadowing_result.rowcount or 0),
            "projection_runs": projection_run_count,
        }
        current.run.status = "succeeded"
        current.run.result = result
        current.run.error_category = None
        current.run.is_active = False
        current.run.checkpoint = {
            **(current.run.checkpoint or {}),
            "affected": result["affected"],
        }

    return JobOutcome(result=result, outcome_writer=write_outcome)


__all__ = [
    "handle_chapter_foreshadowing_projection",
    "handle_chapter_memory_projection",
    "handle_chapter_projection_reconcile",
    "handle_chapter_rag_projection",
    "handle_chapter_summary_projection",
    "handle_chapter_projection_tombstone",
    "handle_chapter_trace_projection",
]
