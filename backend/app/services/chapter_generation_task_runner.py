# AIMETA P=章节生成持久任务_LangGraph桥接执行|R=payload校验_外部activity_安全结果|NR=不细分LangGraph节点恢复|E=handle_chapter_generation_job|X=job|A=durable_handler|D=pipeline_orchestrator,job_runtime|S=db,net|RD=./README.ai
from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from pydantic import ValidationError

from ..schemas.chapter_context import stable_digest
from ..schemas.job import ChapterGenerationJobPayload
from .job_worker import JobOutcome, PermanentJobError
from .novel_service import NovelService
from .pipeline_orchestrator import PipelineOrchestrator

_GENERATION_ACTIVITY_KEY = "chapter_generation_pipeline"


def _public_generation_result(
    payload: ChapterGenerationJobPayload,
    raw_result: dict[str, Any],
) -> dict[str, Any]:
    """任务公开结果只保留定位和计数，不持久化正文、prompt 或 debug 数据。"""

    variants = raw_result.get("variants")
    review_summaries = raw_result.get("review_summaries")
    return {
        "project_id": payload.project_id,
        "chapter_number": payload.chapter_number,
        "preset": str(raw_result.get("preset") or payload.flow_config.preset),
        "best_version_index": int(raw_result.get("best_version_index") or 0),
        "variant_count": len(variants) if isinstance(variants, list) else 0,
        "review_count": len(review_summaries) if isinstance(review_summaries, dict) else 0,
    }


async def handle_chapter_generation_job(context) -> JobOutcome:
    """以保守 ambiguous activity 执行现有 LangGraph，未知结果禁止自动重放。"""

    try:
        payload = ChapterGenerationJobPayload.model_validate(context.lease.payload)
    except ValidationError as exc:
        raise PermanentJobError(
            "invalid_chapter_generation_payload", "章节生成任务参数无效"
        ) from exc
    if context.lease.project_id != payload.project_id:
        raise PermanentJobError("chapter_generation_project_mismatch", "章节生成任务项目不匹配")

    try:
        async with context.session_factory() as session:
            await NovelService(session).ensure_project_owner(
                payload.project_id,
                context.lease.user_id,
            )
    except HTTPException as exc:
        raise PermanentJobError(
            "chapter_generation_project_unavailable",
            "项目不存在或无权访问",
        ) from exc

    await context.progress("章节生成任务已进入 LangGraph 编排", progress=10)
    activity = await context.begin_activity(
        _GENERATION_ACTIVITY_KEY,
        request_payload={
            "project_id": payload.project_id,
            "chapter_number": payload.chapter_number,
            "flow_config": payload.flow_config.model_dump(exclude_none=True),
            "from_node_key": payload.from_node_key,
            "writing_notes_hash": stable_digest(payload.writing_notes or ""),
        },
    )
    if activity.should_execute:
        try:
            async with context.session_factory() as session:
                raw_result = await PipelineOrchestrator(session).generate_chapter(
                    project_id=payload.project_id,
                    chapter_number=payload.chapter_number,
                    writing_notes=payload.writing_notes,
                    user_id=context.lease.user_id,
                    flow_config=payload.flow_config.model_dump(exclude_none=True),
                    from_node_key=payload.from_node_key,
                )
            public_result = _public_generation_result(payload, raw_result)
        except Exception:
            await context.mark_activity_ambiguous(
                _GENERATION_ACTIVITY_KEY,
                provider_request_key=activity.provider_request_key,
                public_message="章节生成外部调用结果不确定，需要人工确认",
            )
            raise AssertionError("mark_activity_ambiguous 必须终止当前执行")
        await context.complete_activity(
            _GENERATION_ACTIVITY_KEY,
            provider_request_key=activity.provider_request_key,
            result=public_result,
        )
    else:
        public_result = dict(activity.result or {})

    await context.progress("章节生成结果已持久化", progress=95)
    return JobOutcome(result=public_result)


__all__ = ["handle_chapter_generation_job"]
