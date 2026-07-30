# AIMETA P=章节工作流投影桥|R=确定失败事务重放_canonical完成观察_stream校验|NR=不写Chapter成功或执行projection算法|E=ChapterWorkflowProjectionService|X=internal|A=domain_service|D=pydantic,sqlalchemy|S=db|RD=./README.ai
"""Retry and observe canonical projections without holding a workflow lease while waiting."""

from __future__ import annotations

from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.background_task import BackgroundTask
from ..models.chapter_projection import (
    ChapterOutboxEvent,
    ChapterProjectionRun,
    ChapterRevision,
)
from ..models.novel import Chapter
from ..repositories.chapter_workflow_repository import ChapterWorkflowRepository
from ..schemas.chapter_context import stable_digest
from ..schemas.chapter_workflow import ChapterWorkflowStateV1
from ..schemas.job import ChapterWorkflowJobPayload
from ..schemas.novel import ChapterGenerationStatus
from .chapter_projection_contract import FINALIZE_EVENT_TYPE
from .chapter_projection_ops import (
    ChapterProjectionOpsService,
    ChapterProjectionReplayRequest,
)
from .job_registry import SideEffectClass
from .job_worker import JobExecutionContext


class ChapterWorkflowProjectionRetryResult(BaseModel):
    """Projection retry activity 只保存 command 与新 durable identity。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    command_id: str = Field(min_length=36, max_length=36)
    target_chapter_revision: int = Field(ge=1)
    projection_run_ids: dict[str, str] = Field(default_factory=dict, max_length=8)
    job_ids: dict[str, str] = Field(default_factory=dict, max_length=8)
    result_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_result_hash(self):
        if set(self.projection_run_ids) != set(self.job_ids):
            raise ValueError("projection retry result identity 集合不一致")
        expected = stable_digest(self.model_dump(mode="json", exclude={"result_hash"}))
        if self.result_hash != expected:
            raise ValueError("projection retry result hash 与结果不一致")
        return self


class ChapterWorkflowProjectionService:
    """在 root fence 下重放失败 projection，并只读观察 canonical 完成事实。"""

    def __init__(self, execution: JobExecutionContext) -> None:
        self.execution = execution

    async def retry_failed(
        self,
        state: ChapterWorkflowStateV1,
        *,
        command_id: str,
    ) -> ChapterWorkflowProjectionRetryResult:
        payload = self._payload(state)
        target_revision = self._target_revision(state)
        canonical_request = {
            "schema_version": 1,
            "workflow_version": payload.workflow_version,
            "state_schema_version": payload.state_schema_version,
            "run_id": payload.run_id,
            "node_key": "projection_pending",
            "command_id": command_id,
            "target_chapter_revision": target_revision,
        }
        input_hash = stable_digest(canonical_request)
        activity_key = f"wf:retry_projection:{command_id}"
        activity = await self.execution.begin_activity(
            activity_key,
            side_effect_class=SideEffectClass.TRANSACTIONAL,
            request_payload={**canonical_request, "input_hash": input_hash},
        )
        if not activity.should_execute:
            return cast(
                ChapterWorkflowProjectionRetryResult,
                ChapterWorkflowProjectionRetryResult.model_validate(activity.result),
            )

        result_payload: dict[str, object] = {
            "schema_version": 1,
            "input_hash": input_hash,
            "command_id": command_id,
            "target_chapter_revision": target_revision,
            "projection_run_ids": {},
            "job_ids": {},
        }

        async def write_replays(session: AsyncSession) -> None:
            await self._write_replays(
                session,
                payload=payload,
                command_id=command_id,
                target_revision=target_revision,
                result_payload=result_payload,
            )

        completed = await self.execution.complete_activity(
            activity_key,
            provider_request_key=activity.provider_request_key,
            result=result_payload,
            outcome_writer=write_replays,
        )
        return cast(
            ChapterWorkflowProjectionRetryResult,
            ChapterWorkflowProjectionRetryResult.model_validate(completed.result_payload),
        )

    async def observe_completed(self, state: ChapterWorkflowStateV1) -> None:
        """验证 projection reconciler 已完成当前 canonical revision。"""

        payload = self._payload(state)
        target_revision = self._target_revision(state)
        async with self.execution.session_factory() as session:
            run = await ChapterWorkflowRepository(session).get_user_run(
                payload.run_id,
                user_id=self.execution.lease.user_id,
            )
            chapter = await session.get(Chapter, payload.chapter_id)
            revision = (
                (
                    await session.execute(
                        select(ChapterRevision).where(
                            ChapterRevision.chapter_id == payload.chapter_id,
                            ChapterRevision.revision == target_revision,
                        )
                    )
                )
                .scalars()
                .first()
            )
            projection_runs = (
                list(
                    (
                        await session.execute(
                            select(ChapterProjectionRun).where(
                                ChapterProjectionRun.chapter_revision_id
                                == (revision.id if revision is not None else "")
                            )
                        )
                    ).scalars()
                )
                if revision is not None
                else []
            )
            job_ids = [item.job_id for item in projection_runs if item.job_id is not None]
            jobs = (
                list(
                    (
                        await session.execute(
                            select(BackgroundTask).where(BackgroundTask.id.in_(job_ids))
                        )
                    ).scalars()
                )
                if job_ids
                else []
            )
            outbox = (
                (
                    await session.execute(
                        select(ChapterOutboxEvent).where(
                            ChapterOutboxEvent.chapter_id == payload.chapter_id,
                            ChapterOutboxEvent.revision == target_revision,
                            ChapterOutboxEvent.event_type == FINALIZE_EVENT_TYPE,
                        )
                    )
                )
                .scalars()
                .first()
            )

        if (
            run is None
            or chapter is None
            or revision is None
            or outbox is None
            or run.root_job_id != self.execution.lease.job_id
            or run.chapter_id != chapter.id
            or run.project_id != chapter.project_id
            or chapter.project_id != payload.project_id
            or run.chapter_number != chapter.chapter_number
            or chapter.chapter_number != payload.chapter_number
            or not run.is_active
            or run.status != "running"
            or run.node_key != "projection_pending"
            or state.node_key != "observe_projection"
        ):
            raise ValueError("workflow projection observation identity 不一致")
        if (
            chapter.current_revision != target_revision
            or chapter.status != ChapterGenerationStatus.SUCCESSFUL.value
            or chapter.source_hash != revision.source_hash
            or revision.lifecycle != "successful"
            or revision.revision != target_revision
        ):
            raise ValueError("workflow projection 尚未完成或 canonical revision 已漂移")
        if outbox.workflow_stream_id != payload.run_id:
            raise ValueError("workflow projection outbox stream 已漂移")

        required = set(revision.required_projections or []) | {"reconcile"}
        completed_runs = [
            item
            for item in projection_runs
            if item.projection_name in required
            and item.status == "succeeded"
            and item.is_active
            and item.source_hash == revision.source_hash
        ]
        completed = {item.projection_name: item for item in completed_runs}
        if len(completed_runs) != len(completed) or set(completed) != required:
            raise ValueError("workflow required projections 尚未全部完成")
        jobs_by_id = {job.id: job for job in jobs}
        for projection_name, projection_run in completed.items():
            job = jobs_by_id.get(projection_run.job_id or "")
            if (
                job is None
                or job.stream_type != "workflow"
                or job.stream_id != payload.run_id
                or not isinstance(job.payload, dict)
                or job.payload.get("workflow_stream_id") != payload.run_id
            ):
                raise ValueError(f"workflow projection stream 已漂移: {projection_name}")

    async def _write_replays(
        self,
        session: AsyncSession,
        *,
        payload: ChapterWorkflowJobPayload,
        command_id: str,
        target_revision: int,
        result_payload: dict[str, object],
    ) -> None:
        workflow_repo = ChapterWorkflowRepository(session)
        run = await workflow_repo.get_by_root_job_for_update(self.execution.lease.job_id)
        command = await workflow_repo.get_command_for_update(command_id)
        chapter = (
            (
                await session.execute(
                    select(Chapter)
                    .where(Chapter.id == payload.chapter_id)
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            )
            .scalars()
            .first()
        )
        outbox = (
            (
                await session.execute(
                    select(ChapterOutboxEvent)
                    .where(
                        ChapterOutboxEvent.chapter_id == payload.chapter_id,
                        ChapterOutboxEvent.revision == target_revision,
                        ChapterOutboxEvent.event_type == FINALIZE_EVENT_TYPE,
                    )
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            )
            .scalars()
            .first()
        )
        if (
            run is None
            or command is None
            or chapter is None
            or outbox is None
            or run.id != payload.run_id
            or run.root_job_id != self.execution.lease.job_id
            or run.chapter_id != chapter.id
            or run.project_id != chapter.project_id
            or command.run_id != run.id
            or command.type != "retry_projection"
            or command.status != "pending"
            or command.actor_user_id != run.user_id
            or command.expected_chapter_revision != target_revision
            or chapter.current_revision != target_revision
            or chapter.status != ChapterGenerationStatus.FINALIZING.value
            or outbox.workflow_stream_id != run.id
        ):
            raise ValueError("workflow projection retry identity 已漂移")

        responses = await ChapterProjectionOpsService(
            session
        ).enqueue_failed_replays_in_transaction(
            request=ChapterProjectionReplayRequest(
                project_id=payload.project_id,
                chapter_id=payload.chapter_id,
                revision=target_revision,
                projection_name="summary",
                idempotency_key=f"chapter-workflow:{run.id}:projection-retry:{command_id}",
                reason="workflow projection retry",
                outbox_event_id=outbox.id,
            ),
            job_idempotency_key_prefix=(f"chapter-workflow:{run.id}:projection-retry:{command_id}"),
            checkpoint={"workflow_command_id": command_id},
        )
        projection_run_ids = {
            response.projection_name: response.projection_run_id
            for response in responses
            if response.projection_run_id is not None
        }
        job_ids = {
            response.projection_name: response.job_id
            for response in responses
            if response.job_id is not None
        }
        result_payload["projection_run_ids"] = projection_run_ids
        result_payload["job_ids"] = job_ids
        result_payload["result_hash"] = stable_digest(result_payload)

    def _payload(self, state: ChapterWorkflowStateV1) -> ChapterWorkflowJobPayload:
        lease = self.execution.lease
        if lease.job_type != "chapter_workflow" or lease.payload_version != 1:
            raise ValueError("JobLease 不是 Chapter workflow v1 root")
        payload = ChapterWorkflowJobPayload.model_validate(lease.payload)
        if state.run_id != payload.run_id:
            raise ValueError("workflow projection state 与 root payload 不一致")
        return payload

    @staticmethod
    def _target_revision(state: ChapterWorkflowStateV1) -> int:
        if state.target_chapter_revision is None:
            raise ValueError("workflow projection checkpoint 缺少目标 revision")
        return state.target_chapter_revision


__all__ = [
    "ChapterWorkflowProjectionRetryResult",
    "ChapterWorkflowProjectionService",
]
