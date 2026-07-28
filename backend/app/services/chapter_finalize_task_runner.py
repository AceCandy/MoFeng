# AIMETA P=章节定稿持久任务_记忆索引伏笔闭环|R=版本CAS_外部activity_最终状态原子提交|NR=不处理HTTP版本选择|E=handle_chapter_finalize_job|X=job|A=durable_handler|D=chapter_edit_postprocess,finalize_service|S=db,net|RD=./README.ai
from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError

from ..core.config import settings
from ..repositories.novel_repository import NovelRepository
from ..schemas.chapter_context import stable_digest
from ..schemas.job import ChapterFinalizeJobPayload
from ..schemas.novel import ChapterGenerationStatus
from .chapter_edit_postprocess import (
    _load_snapshot,
    _run_ambiguous_activity,
    handle_chapter_edit_postprocess_job,
)
from .finalize_service import FinalizeService
from .job_service import AmbiguousActivityError, LeaseLostError
from .job_worker import JobOutcome, PermanentJobError
from .llm_service import LLMService
from .vector_store_service import VectorStoreService


logger = logging.getLogger(__name__)


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
        base_outcome = await handle_chapter_edit_postprocess_job(context)
        if base_outcome.result.get("status") == "superseded":
            return base_outcome

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

        await context.progress("正在更新章节记忆快照", progress=96)

        async def finalize_memory() -> dict[str, Any]:
            async with context.session_factory() as session:
                vector_store = None
                if settings.vector_store_enabled and not payload.skip_vector_update:
                    vector_store = VectorStoreService()
                memory_result = await FinalizeService(
                    session,
                    LLMService(session),
                    vector_store,
                ).finalize_chapter(
                    project_id=payload.project_id,
                    chapter_number=payload.chapter_number,
                    chapter_text=snapshot.content,
                    user_id=context.lease.user_id,
                    skip_vector_update=payload.skip_vector_update,
                )
            if not memory_result.get("success"):
                raise RuntimeError("章节记忆更新未产生有效结果")
            updates = memory_result.get("updates")
            return {
                "success": True,
                "partial_success": bool(memory_result.get("partial_success")),
                "conflict": bool(memory_result.get("conflict")),
                "updated_fields": sorted(updates) if isinstance(updates, dict) else [],
            }

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

    await context.progress("定稿结果已就绪，等待原子提交", progress=99)
    return JobOutcome(result=result, outcome_writer=write_outcome)


__all__ = ["handle_chapter_finalize_job"]
