# AIMETA P=章节定稿持久任务_记忆索引伏笔闭环|R=版本CAS_外部activity_最终状态原子提交|NR=不处理HTTP版本选择|E=handle_chapter_finalize_job|X=job|A=durable_handler|D=chapter_edit_postprocess,chapter_memory_projection,job_service,llm_service|S=db,net|RD=./README.ai
from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select

from ..models.chapter_projection import ChapterProjectionRollout, ChapterRevision
from ..models.novel import Chapter, NovelProject
from ..repositories.novel_repository import NovelRepository
from ..schemas.chapter_context import stable_digest
from ..schemas.job import ChapterFinalizeJobPayload
from ..schemas.novel import ChapterGenerationStatus
from .chapter_edit_postprocess import (
    ChapterPostprocessSnapshot,
    _load_snapshot,
    _run_ambiguous_activity,
    handle_chapter_edit_postprocess_job,
)
from .chapter_memory_projection import (
    apply_memory_projection,
    load_memory_input,
    memory_prompts,
    parse_memory_results,
)
from .foreshadowing_sync_service import deserialize_foreshadowing_context
from .job_service import AmbiguousActivityError, JobService, LeaseLostError
from .job_worker import JobOutcome, PermanentJobError
from .llm_service import LLMService

logger = logging.getLogger(__name__)


async def _load_current_canonical_legacy(
    session,
    *,
    payload,
    user_id: int,
    job_id: str,
    for_update: bool,
):
    """Lock an optional v2-era legacy command before committing active artifacts."""

    if payload.chapter_revision_id is None:
        return None
    if (
        payload.chapter_id is None
        or payload.revision is None
        or payload.source_hash is None
        or payload.source_generation is None
        or payload.rollout_generation is None
        or payload.rollout_fencing_token is None
    ):
        return False
    expected_state = payload.execution_mode
    stmt = (
        select(Chapter, ChapterRevision, ChapterProjectionRollout)
        .join(NovelProject, NovelProject.id == Chapter.project_id)
        .join(ChapterRevision, ChapterRevision.id == payload.chapter_revision_id)
        .join(
            ChapterProjectionRollout,
            ChapterProjectionRollout.chapter_id == Chapter.id,
        )
        .where(
            NovelProject.user_id == user_id,
            Chapter.id == payload.chapter_id,
            Chapter.project_id == payload.project_id,
            Chapter.chapter_number == payload.chapter_number,
            Chapter.current_revision == payload.revision,
            Chapter.source_hash == payload.source_hash,
            Chapter.projection_generation == payload.source_generation,
            ChapterRevision.chapter_id == Chapter.id,
            ChapterRevision.revision == payload.revision,
            ChapterRevision.source_hash == payload.source_hash,
            ChapterRevision.source_generation == payload.source_generation,
            ChapterRevision.legacy_job_id == job_id,
            ChapterRevision.lifecycle == "finalizing",
            ChapterProjectionRollout.owner == "legacy",
            ChapterProjectionRollout.state == expected_state,
            ChapterProjectionRollout.generation == payload.rollout_generation,
            ChapterProjectionRollout.fencing_token == payload.rollout_fencing_token,
        )
    )
    if for_update:
        stmt = stmt.with_for_update()
    row = (await session.execute(stmt)).first()
    if row is None or stable_digest(row[1].source_content) != payload.source_hash:
        return False
    return row


def _canonical_projection_inputs(
    revision: ChapterRevision,
) -> tuple[ChapterPostprocessSnapshot, dict[str, Any]]:
    """从 immutable revision 恢复 legacy owner 的全部计算输入。"""

    projection_context = revision.projection_context
    if not isinstance(projection_context, dict):
        raise PermanentJobError("invalid_legacy_projection_context", "章节定稿快照上下文无效")
    summary_prompt = projection_context.get("summary_prompt")
    memory_input = projection_context.get("memory")
    raw_foreshadowing = projection_context.get("foreshadowing")
    if (
        not isinstance(summary_prompt, str)
        or not summary_prompt.strip()
        or not isinstance(memory_input, dict)
        or not isinstance(raw_foreshadowing, dict)
    ):
        raise PermanentJobError("invalid_legacy_projection_context", "章节定稿快照上下文不完整")
    try:
        foreshadowing = deserialize_foreshadowing_context(raw_foreshadowing)
    except (KeyError, TypeError, ValueError) as exc:
        raise PermanentJobError(
            "invalid_legacy_projection_context",
            "章节定稿伏笔快照无效",
        ) from exc
    title = projection_context.get("rag_title")
    return (
        ChapterPostprocessSnapshot(
            content=revision.source_content,
            title=str(title).strip() if title else f"第{revision.chapter_number}章",
            summary_prompt=summary_prompt,
            foreshadowing=foreshadowing,
        ),
        dict(memory_input),
    )


async def _restore_waiting_draft(context, payload: ChapterFinalizeJobPayload) -> None:
    """失败时仅在正文引用仍匹配时恢复待确认状态，避免覆盖后续编辑。"""

    async with context.session_factory() as session:
        pair = await NovelRepository(session).get_owned_selected_version(
            project_id=payload.project_id,
            chapter_number=payload.chapter_number,
            user_id=context.lease.user_id,
            for_update=True,
        )
        if pair is None:
            await session.rollback()
            return
        chapter, version = pair
        if (
            chapter.selected_version_id != payload.selected_version_id
            or version.id != payload.selected_version_id
            or stable_digest(version.content) != payload.content_hash
        ):
            await session.rollback()
            return
        chapter.status = ChapterGenerationStatus.WAITING_FOR_CONFIRM.value
        chapter.selected_version_id = None
        chapter.selected_version = None
        chapter.real_summary = None
        chapter.word_count = 0
        chapter.generation_progress = 100
        chapter.generation_step = "finalization_failed"
        chapter.generation_step_index = 4
        chapter.generation_step_total = 4
        await session.commit()


async def handle_chapter_finalize_job(context) -> JobOutcome:
    """复用章节后处理 activity，并补齐记忆闭环与最终章节状态。"""

    try:
        payload = ChapterFinalizeJobPayload.model_validate(context.lease.payload)
    except ValidationError as exc:
        raise PermanentJobError("invalid_chapter_finalize_payload", "章节定稿任务参数无效") from exc
    if context.lease.project_id != payload.project_id:
        raise PermanentJobError("chapter_finalize_project_mismatch", "章节定稿任务项目不匹配")

    try:
        async with context.session_factory() as session:
            canonical = await _load_current_canonical_legacy(
                session,
                payload=payload,
                user_id=context.lease.user_id,
                job_id=context.lease.job_id,
                for_update=False,
            )
        if canonical is False:
            return JobOutcome(
                result={
                    "status": "superseded",
                    "project_id": payload.project_id,
                    "chapter_number": payload.chapter_number,
                    "content_hash": payload.content_hash,
                }
            )
        if canonical is None:
            snapshot = await _load_snapshot(context, payload)
            if snapshot is None:
                return JobOutcome(
                    result={
                        "status": "superseded",
                        "project_id": payload.project_id,
                        "chapter_number": payload.chapter_number,
                        "content_hash": payload.content_hash,
                    }
                )
            async with context.session_factory() as session:
                memory_input = await load_memory_input(
                    session,
                    project_id=payload.project_id,
                )
        else:
            snapshot, memory_input = _canonical_projection_inputs(canonical[1])

        base_outcome = await handle_chapter_edit_postprocess_job(
            context,
            payload_override=payload,
            snapshot_override=snapshot,
        )
        if base_outcome.result.get("status") == "superseded":
            return base_outcome

        await context.progress("正在更新章节记忆快照", progress=96)

        requests = memory_prompts(
            chapter_text=snapshot.content,
            chapter_number=payload.chapter_number,
            memory_input=memory_input,
        )

        async def finalize_memory() -> dict[str, Any]:
            activity_results: dict[str, dict[str, Any]] = {}
            for field, request in requests.items():
                response = await LLMService.generate_detached(
                    request["prompt"],
                    session_factory=context.session_factory,
                    temperature=0.3,
                    user_id=context.lease.user_id,
                    max_tokens=request["max_tokens"],
                    response_format=request["response_format"],
                    stage="summary_memory",
                )
                activity_results[field] = {"response": response}
            prepared = parse_memory_results(
                activity_results=activity_results,
                memory_input=memory_input,
            )
            if not prepared.get("success"):
                raise RuntimeError("章节记忆更新未产生有效结果")
            return {"prepared": prepared}

        memory_result = await _run_ambiguous_activity(
            context,
            payload,
            activity_key="finalize_memory",
            request_payload={
                "project_id": payload.project_id,
                "chapter_number": payload.chapter_number,
                "content_hash": payload.content_hash,
                "skip_vector_update": payload.skip_vector_update,
            },
            call=finalize_memory,
        )
        raw_prepared = memory_result.get("prepared")
        if not isinstance(raw_prepared, dict) or not raw_prepared.get("success"):
            async with context.session_factory() as session:
                await JobService(session).mark_dead_letter(
                    context.lease,
                    error_category="legacy_memory_result_incompatible",
                    public_message="历史章节记忆活动缺少可验证结果，需要人工处置",
                )
            raise AmbiguousActivityError("历史章节记忆活动缺少可验证结果")
        memory_prepared = dict(raw_prepared)
    except (AmbiguousActivityError, LeaseLostError):
        raise
    except Exception:
        try:
            await _restore_waiting_draft(context, payload)
        except Exception:
            logger.exception(
                "恢复定稿草稿状态失败: project_id=%s chapter_number=%s",
                payload.project_id,
                payload.chapter_number,
            )
        raise

    finalize_stats: dict[str, Any] = {
        "summary_generated": True,
        "memory_updated": bool(memory_result.get("success")),
        "vector_ingested": bool(base_outcome.result.get("vector_ingested")),
        "foreshadowing_sync": {"created": 0, "developing": 0, "revealed": 0},
    }
    result: dict[str, Any] = {
        "status": "applied",
        "project_id": payload.project_id,
        "chapter_number": payload.chapter_number,
        "content_hash": payload.content_hash,
        "finalize": finalize_stats,
    }

    async def write_outcome(session) -> None:
        canonical = await _load_current_canonical_legacy(
            session,
            payload=payload,
            user_id=context.lease.user_id,
            job_id=context.lease.job_id,
            for_update=True,
        )
        if canonical is False:
            result["status"] = "superseded"
            return
        if base_outcome.outcome_writer is not None:
            await base_outcome.outcome_writer(session)
        if base_outcome.result.get("status") != "applied":
            result["status"] = "superseded"
            return

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

        memory_revision = canonical[1].revision if canonical is not None else 0
        memory_source_hash = canonical[1].source_hash if canonical is not None else None
        memory_source_generation = canonical[1].source_generation if canonical is not None else None
        memory_stats = await apply_memory_projection(
            session,
            project_id=payload.project_id,
            chapter_number=payload.chapter_number,
            chapter_text=snapshot.content,
            revision=memory_revision,
            artifact_generation="legacy",
            projection_run_id=None,
            expected_source_hash=memory_source_hash,
            expected_source_generation=memory_source_generation,
            prepared=memory_prepared,
        )
        finalize_stats["memory_updated"] = bool(memory_stats.get("snapshot_created"))
        finalize_stats["memory_conflict"] = bool(memory_stats.get("conflict"))

        raw_foreshadowing = base_outcome.result.get("foreshadowing_sync")
        if isinstance(raw_foreshadowing, dict):
            finalize_stats["foreshadowing_sync"] = {
                "created": int(raw_foreshadowing.get("created", 0)),
                "developing": int(raw_foreshadowing.get("developing", 0)),
                "revealed": int(raw_foreshadowing.get("revealed", 0)),
            }
        chapter.status = ChapterGenerationStatus.SUCCESSFUL.value
        chapter.generation_progress = 100
        chapter.generation_step = "finalized"
        chapter.generation_step_index = 4
        chapter.generation_step_total = 4
        if canonical is not None and payload.execution_mode == "legacy":
            canonical[1].lifecycle = "successful"

    await context.progress("定稿结果已就绪，等待原子提交", progress=99)
    return JobOutcome(result=result, outcome_writer=write_outcome)


__all__ = ["handle_chapter_finalize_job"]
