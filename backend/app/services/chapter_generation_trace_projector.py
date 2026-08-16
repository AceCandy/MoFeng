"""Project public workflow JobEvents into the deletable legacy trace view."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.chapter_workflow import ChapterWorkflowRun
from ..models.job import JobEvent
from ..repositories.chapter_generation_trace_projection_repository import (
    ChapterGenerationTraceProjectionRepository,
)
from .chapter_workflow_transition import CHAPTER_WORKFLOW_NODE_LABELS

_PROJECTABLE_EVENT_TYPES = frozenset(
    {
        "job.started",
        "job.reclaimed",
        "job.retry_scheduled",
        "job.needs_attention",
        "job.succeeded",
        "job.failed",
        "job.dead_lettered",
        "workflow.started",
        "workflow.phase_changed",
        "workflow.waiting",
        "workflow.command.accepted",
        "workflow.command.rejected",
        "workflow.command.applied",
        "workflow.needs_attention",
        "workflow.reconciled",
        "workflow.completed",
    }
)
_FAILED_WORKFLOW_STATUSES = frozenset({"failed", "needs_attention"})
_PROJECTION_JOB_NODES = {
    "chapter_finalize": ("commit_summary_projection", "保存章节梳理"),
    "chapter_projection_memory": ("commit_memory_projection", "写入章节记忆"),
    "chapter_projection_rag": ("commit_rag_projection", "写入章节索引"),
    "chapter_projection_foreshadowing": (
        "commit_foreshadowing_projection",
        "写入伏笔同步结果",
    ),
    "chapter_projection_reconcile": ("reconcile_projections", "汇合章节投影"),
}


@dataclass(frozen=True)
class ChapterGenerationTraceProjectionBatch:
    scanned_events: int
    projected_traces: int
    last_event_cursor: int


def _bounded_string(value: object, *, max_length: int) -> str | None:
    if not isinstance(value, str):
        return None
    return value[:max_length]


def _nonnegative_int(value: object, *, maximum: int | None = None) -> int | None:
    if type(value) is not int or value < 0:
        return None
    if maximum is not None and value > maximum:
        return None
    return value


def _public_metadata(event: JobEvent, workflow: dict[str, Any]) -> dict[str, object]:
    metadata: dict[str, object] = {
        "projection_schema_version": 1,
        "source": "job_event",
        "event_cursor": event.cursor,
        "event_sequence": event.sequence,
        "event_type": event.event_type,
        "run_id": event.stream_id,
        "uses_llm": False,
    }
    for key, maximum in (("row_revision", None), ("progress", 100)):
        integer_value = _nonnegative_int(workflow.get(key), maximum=maximum)
        if integer_value is not None:
            metadata[key] = integer_value
    for key, maximum in (
        ("checkpoint_id", 512),
        ("reason_code", 64),
        ("error_category", 64),
    ):
        string_value = _bounded_string(workflow.get(key), max_length=maximum)
        if string_value is not None:
            metadata[key] = string_value

    command = workflow.get("command")
    if isinstance(command, dict):
        public_command: dict[str, str] = {}
        for key, maximum in (
            ("id", 36),
            ("type", 32),
            ("status", 16),
            ("rejection_code", 64),
        ):
            command_value = _bounded_string(command.get(key), max_length=maximum)
            if command_value is not None:
                public_command[key] = command_value
        if public_command:
            metadata["command"] = public_command
    return metadata


def _trace_row(
    event: JobEvent,
    run: ChapterWorkflowRun,
) -> dict[str, object] | None:
    if (
        event.stream_type != "workflow"
        or event.event_type not in _PROJECTABLE_EVENT_TYPES
        or run.chapter_id is None
        or not isinstance(event.payload, dict)
    ):
        return None
    workflow = event.payload.get("workflow")
    if not isinstance(workflow, dict):
        return _projection_trace_row(event, run)
    if workflow.get("run_id") != run.id:
        return None

    raw_node_key = workflow.get("node_key")
    node_key = (
        raw_node_key
        if isinstance(raw_node_key, str) and raw_node_key in CHAPTER_WORKFLOW_NODE_LABELS
        else "workflow"
    )
    workflow_status = _bounded_string(workflow.get("status"), max_length=32)
    failed = (
        workflow_status in _FAILED_WORKFLOW_STATUSES
        or event.event_type == "workflow.command.rejected"
    )
    public_error = _bounded_string(workflow.get("public_error"), max_length=512)
    return {
        "chapter_id": run.chapter_id,
        "project_id": run.project_id,
        "chapter_number": run.chapter_number,
        "node_key": node_key,
        "node_label": CHAPTER_WORKFLOW_NODE_LABELS[node_key],
        "stage": "workflow_event",
        "status": "failed" if failed else "success",
        "system_prompt": None,
        "user_prompt": None,
        "raw_response": None,
        "cleaned_output": None,
        "error": public_error,
        "metadata": _public_metadata(event, workflow),
        "source_run_id": run.id,
        "source_event_cursor": event.cursor,
        "started_at": event.created_at,
        "ended_at": event.created_at,
        "created_at": event.created_at,
    }


def _projection_trace_row(
    event: JobEvent,
    run: ChapterWorkflowRun,
) -> dict[str, object] | None:
    task = event.payload.get("task") if isinstance(event.payload, dict) else None
    if not isinstance(task, dict):
        return None
    task_type = task.get("task_type")
    node = _PROJECTION_JOB_NODES.get(task_type) if isinstance(task_type, str) else None
    if node is None:
        return None
    node_key, node_label = node
    task_status = task.get("status")
    failed = task_status == "failed" or event.event_type in {
        "job.needs_attention",
        "job.failed",
        "job.dead_lettered",
    }
    completed = task_status == "successful" or event.event_type == "job.succeeded"
    error = _bounded_string(task.get("error"), max_length=512)
    metadata: dict[str, object] = {
        "projection_schema_version": 1,
        "source": "projection_job_event",
        "event_cursor": event.cursor,
        "event_sequence": event.sequence,
        "event_type": event.event_type,
        "run_id": run.id,
        "uses_llm": False,
        "remote_call": False,
        "call_type": "database_write",
        "node_kind": "system",
    }
    return {
        "chapter_id": run.chapter_id,
        "project_id": run.project_id,
        "chapter_number": run.chapter_number,
        "node_key": node_key,
        "node_label": node_label,
        "stage": "projection_job",
        "status": "failed" if failed else "success" if completed else "running",
        "system_prompt": None,
        "user_prompt": None,
        "raw_response": None,
        "cleaned_output": None,
        "error": error,
        "metadata": metadata,
        "source_run_id": run.id,
        "source_event_cursor": event.cursor,
        "started_at": event.created_at,
        "ended_at": event.created_at if failed or completed else None,
        "created_at": event.created_at,
    }


async def project_chapter_generation_traces(
    session: AsyncSession,
    *,
    limit: int = 200,
) -> ChapterGenerationTraceProjectionBatch:
    """锁定全局 cursor，并在同一事务写 trace 与推进 checkpoint。"""

    if limit < 1 or limit > 500:
        raise ValueError("limit 必须在 1 到 500 之间")
    repository = ChapterGenerationTraceProjectionRepository(session)
    checkpoint = await repository.lock_checkpoint()
    if checkpoint is None:
        if await repository.checkpoint_exists():
            return ChapterGenerationTraceProjectionBatch(0, 0, 0)
        raise RuntimeError("generation trace projector checkpoint 不存在")

    events = await repository.list_events_after(
        after_cursor=checkpoint.last_event_cursor,
        limit=limit,
    )
    if not events:
        return ChapterGenerationTraceProjectionBatch(0, 0, checkpoint.last_event_cursor)

    run_ids = {
        event.stream_id
        for event in events
        if event.stream_type == "workflow" and event.event_type in _PROJECTABLE_EVENT_TYPES
    }
    runs = await repository.get_runs(run_ids)
    rows = [
        row
        for event in events
        if (run := runs.get(event.stream_id)) is not None
        if (row := _trace_row(event, run)) is not None
    ]
    projected = await repository.upsert_traces(rows)
    checkpoint.last_event_cursor = events[-1].cursor
    await session.flush()
    return ChapterGenerationTraceProjectionBatch(
        scanned_events=len(events),
        projected_traces=projected,
        last_event_cursor=checkpoint.last_event_cursor,
    )


async def rebuild_chapter_generation_traces(
    session: AsyncSession,
    *,
    run_id: str,
    batch_size: int = 500,
) -> int:
    """从仍保留的 JobEvent 重建单个 run 的兼容 trace，不改变全局 cursor。"""

    if batch_size < 1 or batch_size > 500:
        raise ValueError("batch_size 必须在 1 到 500 之间")
    repository = ChapterGenerationTraceProjectionRepository(session)
    run = await repository.get_run(run_id)
    if run is None:
        raise ValueError("workflow run 不存在")

    projected = 0
    after_cursor = 0
    while True:
        events = await repository.list_run_events_after(
            run_id=run_id,
            after_cursor=after_cursor,
            limit=batch_size,
        )
        if not events:
            break
        rows = [row for event in events if (row := _trace_row(event, run)) is not None]
        projected += await repository.upsert_traces(rows)
        after_cursor = events[-1].cursor
        if len(events) < batch_size:
            break
    await session.flush()
    return projected


__all__ = [
    "ChapterGenerationTraceProjectionBatch",
    "project_chapter_generation_traces",
    "rebuild_chapter_generation_traces",
]
