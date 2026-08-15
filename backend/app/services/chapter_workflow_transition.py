# AIMETA P=章节工作流转换适配器_原子同步run与事件|R=锁序_状态映射_active_slot|NR=不提交事务或执行graph|E=ChapterWorkflowTransitionAdapter|X=internal|A=domain_service|D=sqlalchemy|S=db|RD=./README.ai
"""Keep a Chapter workflow run aligned with its root durable job transition."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.background_task import BackgroundTask
from ..models.chapter_workflow import ChapterWorkflowCommand, ChapterWorkflowRun
from ..models.novel import Chapter
from ..repositories.chapter_workflow_repository import ChapterWorkflowRepository
from ..repositories.novel_repository import NovelRepository
from .job_public_projection import sanitize_public_text

_ACTIVE_RUN_STATUSES = {
    "queued",
    "running",
    "retry_wait",
    "waiting_for_selection",
    "finalizing",
    "projection_pending",
    "needs_attention",
}
_TERMINAL_RUN_STATUSES = {"successful", "failed", "cancelled", "superseded"}
_WAITING_RUN_STATUSES = {"waiting_for_selection", "projection_pending"}
_WORKFLOW_EVENT_TYPES = {
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
_TRANSITION_SOURCE_EVENT_TYPES = {
    "job.started",
    "job.reclaimed",
    "job.retry_scheduled",
    "job.needs_attention",
    "job.succeeded",
    "job.failed",
    "job.dead_lettered",
    "job.cancelled",
    "workflow.phase_changed",
    "workflow.waiting",
}
CHAPTER_WORKFLOW_NODE_LABELS = {
    "freeze_base_context": "冻结基础上下文",
    "retrieve_context": "检索章节上下文",
    "plan_chapter": "规划章节任务",
    "generate_candidate_1": "生成候选版本 1",
    "generate_candidate_2": "生成候选版本 2",
    "review_candidates": "评审候选版本",
    "refine_candidate": "润色推荐版本",
    "enhance_content": "增强正文",
    "repair_consistency": "修复一致性",
    "optimize_style": "优化文风",
    "enrich_content": "扩写正文",
    "compress_candidate": "压缩超长正文",
    "persist_drafts": "保存候选草稿",
    "wait_for_selection": "等待选择版本",
    "finalize_revision": "定稿章节版本",
    "wait_for_projections": "等待章节投影",
    "reconcile_projections": "汇合章节投影",
    "successful": "章节工作流完成",
    "failed": "章节工作流失败",
    "cancelled": "章节工作流取消",
    "superseded": "章节工作流已被替代",
    "needs_attention": "章节工作流需要处理",
    "workflow": "章节工作流状态",
}
_ACTIVITY_PROGRESS = {
    "freeze_base_context": (3, 5),
    "retrieve_context": (6, 12),
    "plan_chapter": (15, 22),
    "generate_candidate_1": (25, 44),
    "generate_candidate_2": (25, 44),
    "review_candidates": (47, 52),
    "refine_candidate": (53, 56),
    "enhance_content": (56, 57),
    "repair_consistency": (57, 58),
    "optimize_style": (58, 59),
    "enrich_content": (59, 60),
    "compress_candidate": (60, 62),
    "persist_drafts": (63, 65),
    "finalize_revision": (70, 85),
    "wait_for_projections": (90, 90),
    "reconcile_projections": (95, 98),
}
_ACTIVITY_EVENT_TYPES = {
    "activity.started",
    "activity.retried",
    "activity.succeeded",
    "activity.retryable_failed",
    "activity.failed",
}


@dataclass(frozen=True)
class ChapterWorkflowTransition:
    """由 graph/command 提供的显式 workflow 目标快照。"""

    status: str
    node_key: str
    checkpoint_id: Optional[str]
    progress: Optional[int] = None
    reason_code: Optional[str] = None


@dataclass(frozen=True)
class LockedChapterWorkflowTransition:
    """按 root JobRun -> workflow run -> Chapter 顺序取得的锁定上下文。"""

    run: ChapterWorkflowRun
    chapter: Chapter


@dataclass(frozen=True)
class ChapterWorkflowEvent:
    """写入共享 JobEvent stream 的 allowlisted workflow 事件。"""

    event_type: str
    payload: dict[str, object]


class ChapterWorkflowTransitionAdapter:
    """在 JobService 事务内同步 root job 对应的 workflow current row。"""

    def __init__(self, session: AsyncSession):
        self.workflow_repo = ChapterWorkflowRepository(session)
        self.novel_repo = NovelRepository(session)

    @staticmethod
    def is_transition_event(source_event_type: str) -> bool:
        """区分 run transition 与仅更新 activity/progress 的普通事件。"""

        return source_event_type in _TRANSITION_SOURCE_EVENT_TYPES

    @staticmethod
    def command_event(
        *,
        context: LockedChapterWorkflowTransition,
        command: ChapterWorkflowCommand,
        event_type: str,
    ) -> ChapterWorkflowEvent:
        """生成不改变 run revision、且不暴露 command payload 的审计事件。"""

        if event_type not in {
            "workflow.command.accepted",
            "workflow.command.rejected",
            "workflow.command.applied",
        }:
            raise ValueError("workflow command event type 不受支持")
        run = context.run
        command_payload: dict[str, object] = {
            "id": command.id,
            "type": command.type,
            "status": command.status,
        }
        if command.rejection_code is not None:
            command_payload["rejection_code"] = command.rejection_code
        return ChapterWorkflowEvent(
            event_type=event_type,
            payload={
                "run_id": run.id,
                "row_revision": run.row_revision,
                "node_key": run.node_key,
                "status": run.status,
                "checkpoint_id": run.checkpoint_id,
                "progress": run.progress,
                "command": command_payload,
            },
        )

    async def lock_for_job(
        self,
        job: BackgroundTask,
    ) -> Optional[LockedChapterWorkflowTransition]:
        """root job 必须已锁定；无绑定 workflow run 时保持普通 job 行为。"""

        if job.stream_type != "workflow":
            return None
        run = await self.workflow_repo.get_by_root_job_for_update(job.id)
        if run is None:
            return None
        if (
            job.stream_id != run.id
            or job.user_id != run.user_id
            or job.project_id != run.project_id
        ):
            raise ValueError("workflow run 与 root JobRun 身份不一致")

        chapter = await self.novel_repo.get_chapter_for_update(
            project_id=run.project_id,
            chapter_number=run.chapter_number,
        )
        if chapter is None or run.chapter_id is None or chapter.id != run.chapter_id:
            raise ValueError("workflow run 绑定的 Chapter 不存在或身份不一致")
        return LockedChapterWorkflowTransition(run=run, chapter=chapter)

    def apply_event(
        self,
        *,
        job: BackgroundTask,
        context: LockedChapterWorkflowTransition,
        source_event_type: str,
        now: datetime,
        transition: Optional[ChapterWorkflowTransition] = None,
    ) -> ChapterWorkflowEvent:
        """更新 run/active slot，并生成不含私有 payload 的 workflow 事件。"""

        return self._apply_run_event(
            job=job,
            run=context.run,
            source_event_type=source_event_type,
            now=now,
            transition=transition,
        )

    def apply_activity_event(
        self,
        *,
        job: BackgroundTask,
        context: LockedChapterWorkflowTransition,
        source_event_type: str,
        request_payload: dict[str, object],
        now: datetime,
    ) -> Optional[ChapterWorkflowEvent]:
        """用 activity 的公开节点身份推进 run，同时保留原 activity 事件类型。"""

        if source_event_type not in _ACTIVITY_EVENT_TYPES:
            raise ValueError("workflow activity event type 不受支持")
        node_key = request_payload.get("node_key")
        if not isinstance(node_key, str) or node_key not in _ACTIVITY_PROGRESS:
            return None
        start_progress, completed_progress = _ACTIVITY_PROGRESS[node_key]
        target_progress = (
            completed_progress if source_event_type == "activity.succeeded" else start_progress
        )
        workflow_event = self._apply_run_event(
            job=job,
            run=context.run,
            source_event_type="workflow.phase_changed",
            now=now,
            transition=ChapterWorkflowTransition(
                status=context.run.status,
                node_key=node_key,
                checkpoint_id=context.run.checkpoint_id,
                progress=max(context.run.progress, target_progress),
            ),
        )
        return ChapterWorkflowEvent(
            event_type=source_event_type,
            payload=workflow_event.payload,
        )

    def apply_reconciliation(
        self,
        *,
        job: BackgroundTask,
        run: ChapterWorkflowRun,
        now: datetime,
        transition: ChapterWorkflowTransition,
    ) -> ChapterWorkflowEvent:
        """在身份或 Chapter 已损坏时也能原子记录 fail-closed 修复。"""

        if transition.reason_code is None:
            raise ValueError("workflow reconciliation 缺少 reason_code")
        return self._apply_run_event(
            job=job,
            run=run,
            source_event_type="workflow.reconciled",
            now=now,
            transition=transition,
        )

    def reconciliation_snapshot(
        self,
        *,
        run: ChapterWorkflowRun,
        reason_code: str,
    ) -> ChapterWorkflowEvent:
        """记录无法安全改变 terminal run 时的 fail-closed 当前快照。"""

        return ChapterWorkflowEvent(
            event_type="workflow.reconciled",
            payload={
                "run_id": run.id,
                "row_revision": run.row_revision,
                "node_key": run.node_key,
                "status": run.status,
                "checkpoint_id": run.checkpoint_id,
                "progress": run.progress,
                "reason_code": reason_code,
            },
        )

    def _apply_run_event(
        self,
        *,
        job: BackgroundTask,
        run: ChapterWorkflowRun,
        source_event_type: str,
        now: datetime,
        transition: Optional[ChapterWorkflowTransition],
    ) -> ChapterWorkflowEvent:
        target_status = (
            transition.status
            if transition is not None
            else self._infer_status(run=run, job=job, source_event_type=source_event_type)
        )
        self._validate_target(job=job, target_status=target_status)

        node_key = (
            transition.node_key
            if transition is not None
            else self._infer_node_key(
                run=run,
                target_status=target_status,
            )
        )
        if not node_key.strip() or len(node_key) > 64:
            raise ValueError("workflow node_key 必须为 1 到 64 个字符")

        progress = (
            job.progress
            if transition is None or transition.progress is None
            else transition.progress
        )
        if not 0 <= progress <= 100:
            raise ValueError("workflow progress 必须在 0 到 100 之间")

        run.status = target_status
        run.node_key = node_key
        if transition is not None:
            run.checkpoint_id = transition.checkpoint_id
        run.progress = progress
        run.row_revision += 1
        run.is_active = target_status in _ACTIVE_RUN_STATUSES
        if target_status != "queued":
            run.started_at = run.started_at or now
        run.completed_at = now if target_status in _TERMINAL_RUN_STATUSES else None

        if target_status in {"failed", "needs_attention"}:
            run.error_category = job.error_category
            run.public_error = sanitize_public_text(job.error) if job.error is not None else None
        elif target_status == "cancelled":
            run.error_category = job.error_category or "job_cancelled"
            run.public_error = sanitize_public_text(job.error) if job.error is not None else None
        else:
            run.error_category = None
            run.public_error = None

        workflow_payload: dict[str, object] = {
            "run_id": run.id,
            "row_revision": run.row_revision,
            "node_key": run.node_key,
            "status": run.status,
            "checkpoint_id": run.checkpoint_id,
            "progress": run.progress,
        }
        if run.error_category is not None:
            workflow_payload["error_category"] = run.error_category
        if run.public_error is not None:
            workflow_payload["public_error"] = run.public_error
        if transition is not None and transition.reason_code is not None:
            workflow_payload["reason_code"] = transition.reason_code
        return ChapterWorkflowEvent(
            event_type=self._workflow_event_type(source_event_type),
            payload=workflow_payload,
        )

    @staticmethod
    def _infer_status(
        *,
        run: ChapterWorkflowRun,
        job: BackgroundTask,
        source_event_type: str,
    ) -> str:
        if source_event_type == "workflow.waiting":
            if run.status not in _WAITING_RUN_STATUSES:
                raise ValueError("workflow waiting transition 必须显式指定等待阶段")
            return str(run.status)
        if source_event_type in {"job.started", "job.reclaimed"}:
            return "running"
        if source_event_type == "job.retry_scheduled":
            return "retry_wait"
        if source_event_type == "workflow.phase_changed" and job.status == "queued":
            return "queued"
        if job.status == "needs_attention":
            return "needs_attention"
        if job.status == "succeeded":
            return "successful"
        if job.status in {"failed", "dead_letter"}:
            return "failed"
        if job.status == "cancelled":
            return "cancelled"
        return str(run.status)

    @staticmethod
    def _infer_node_key(*, run: ChapterWorkflowRun, target_status: str) -> str:
        if target_status in _WAITING_RUN_STATUSES | _TERMINAL_RUN_STATUSES:
            return target_status
        return str(run.node_key)

    @staticmethod
    def _validate_target(*, job: BackgroundTask, target_status: str) -> None:
        if target_status not in _ACTIVE_RUN_STATUSES | _TERMINAL_RUN_STATUSES:
            raise ValueError("workflow transition status 不受支持")
        allowed_by_job_status = {
            "queued": {"queued"},
            "running": {"running", "finalizing"},
            "retry_wait": {"retry_wait"},
            "waiting": _WAITING_RUN_STATUSES,
            "needs_attention": {"needs_attention"},
            "succeeded": {"successful"},
            "failed": {"failed"},
            "dead_letter": {"failed"},
            "cancelled": {"cancelled", "superseded"},
        }
        if target_status not in allowed_by_job_status.get(job.status, set()):
            raise ValueError("workflow run 目标状态与 root JobRun 状态不一致")

    @staticmethod
    def _workflow_event_type(source_event_type: str) -> str:
        if source_event_type in _WORKFLOW_EVENT_TYPES:
            return source_event_type
        if source_event_type == "job.needs_attention":
            return "workflow.needs_attention"
        if source_event_type in {
            "job.succeeded",
            "job.failed",
            "job.dead_lettered",
            "job.cancelled",
        }:
            return "workflow.completed"
        return "workflow.phase_changed"
