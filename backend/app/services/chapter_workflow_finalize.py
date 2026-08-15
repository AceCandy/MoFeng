# AIMETA P=章节工作流事务定稿|R=冻结身份复核_fenced定稿写入_引用型结果|NR=不提交事务_不观察projection|E=ChapterWorkflowFinalizeService|X=internal|A=domain_service|D=pydantic,sqlalchemy|S=db|RD=./README.ai
"""Transactional canonical finalize activity for the durable Chapter workflow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.background_task import BackgroundTask
from ..models.novel import Chapter, ChapterVersion
from ..repositories.chapter_workflow_repository import ChapterWorkflowRepository
from ..schemas.chapter_context import stable_digest
from ..schemas.job import (
    ChapterWorkflowJobPayload,
    validate_chapter_workflow_job_payload,
)
from ..schemas.novel import ChapterGenerationStatus
from .chapter_finalize_service import ChapterFinalizeSubmissionService
from .job_registry import SideEffectClass
from .job_worker import JobExecutionContext

FINALIZE_REVISION_REF = "finalize_revision"


class ChapterWorkflowFinalizeInput(BaseModel):
    """只携带 checkpoint 中的候选与选版身份。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    run_id: str = Field(min_length=36, max_length=36)
    candidate_version_ids: list[int] = Field(min_length=1, max_length=100)
    selected_version_id: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_selection(self):
        if len(self.candidate_version_ids) != len(set(self.candidate_version_ids)):
            raise ValueError("workflow finalize 候选版本不可重复")
        if self.selected_version_id not in self.candidate_version_ids:
            raise ValueError("workflow finalize 选中版本不在候选集合中")
        return self


class ChapterWorkflowFinalizeResult(BaseModel):
    """定稿 activity 只保存 canonical identity 与内容 hash。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    selected_version_id: int = Field(ge=1)
    source_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    target_chapter_revision: int = Field(ge=1)
    chapter_revision_id: str = Field(min_length=36, max_length=36)
    outbox_event_id: str = Field(min_length=36, max_length=36)
    dispatcher_job_id: str = Field(min_length=36, max_length=36)
    result_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_result_hash(self):
        expected = stable_digest(self.model_dump(mode="json", exclude={"result_hash"}))
        if self.result_hash != expected:
            raise ValueError("workflow finalize result hash 与结果不一致")
        return self


@dataclass(frozen=True)
class ChapterWorkflowFinalizeExecution:
    activity_key: str
    result: ChapterWorkflowFinalizeResult

    def state_update(self) -> dict[str, object]:
        return {
            "target_chapter_revision": self.result.target_chapter_revision,
            "activity_refs": {FINALIZE_REVISION_REF: self.activity_key},
            "result_refs": {FINALIZE_REVISION_REF: self.result.result_hash},
        }


@dataclass(frozen=True)
class _FinalizeIdentity:
    payload: ChapterWorkflowJobPayload
    source_hash: str


class ChapterWorkflowFinalizeService:
    """在 root lease fence 内原子完成 canonical finalize 与 activity。"""

    def __init__(self, execution: JobExecutionContext) -> None:
        self.execution = execution

    async def execute(
        self,
        request: ChapterWorkflowFinalizeInput,
    ) -> ChapterWorkflowFinalizeExecution:
        identity = await self._load_identity(request)
        input_payload = request.model_dump(mode="json")
        input_hash = stable_digest(
            {
                **input_payload,
                "base_revision": identity.payload.base_revision,
                "source_hash": identity.source_hash,
            }
        )
        canonical_request = {
            "schema_version": 1,
            "workflow_version": identity.payload.workflow_version,
            "state_schema_version": identity.payload.state_schema_version,
            "run_id": identity.payload.run_id,
            "node_key": "finalize_revision",
            "base_revision": identity.payload.base_revision,
            "selected_version_id": request.selected_version_id,
            "source_hash": identity.source_hash,
            "input_hash": input_hash,
        }
        activity_key = f"wf:finalize_revision:{stable_digest(canonical_request)}"
        activity = await self.execution.begin_activity(
            activity_key,
            side_effect_class=SideEffectClass.TRANSACTIONAL,
            request_payload=canonical_request,
        )
        if not activity.should_execute:
            result = ChapterWorkflowFinalizeResult.model_validate(activity.result)
            if result.input_hash != input_hash:
                raise ValueError("workflow finalize replay input hash 不一致")
            return ChapterWorkflowFinalizeExecution(activity_key, result)

        result_payload: dict[str, object] = {
            "schema_version": 1,
            "input_hash": input_hash,
            "selected_version_id": request.selected_version_id,
            "source_hash": identity.source_hash,
        }

        async def write_finalize(session: AsyncSession) -> None:
            await self._write_finalize(
                session=session,
                request=request,
                identity=identity,
                result_payload=result_payload,
            )

        completed = await self.execution.complete_activity(
            activity_key,
            provider_request_key=activity.provider_request_key,
            result=result_payload,
            outcome_writer=write_finalize,
        )
        result = ChapterWorkflowFinalizeResult.model_validate(completed.result_payload)
        return ChapterWorkflowFinalizeExecution(activity_key, result)

    async def _load_identity(
        self,
        request: ChapterWorkflowFinalizeInput,
    ) -> _FinalizeIdentity:
        lease = self.execution.lease
        if lease.job_type != "chapter_workflow":
            raise ValueError("workflow root job 类型或版本不匹配")
        payload = validate_chapter_workflow_job_payload(
            lease.payload_version,
            lease.payload,
        )
        if request.run_id != payload.run_id:
            raise ValueError("workflow finalize run identity 不一致")

        async with self.execution.session_factory() as session:
            run = await ChapterWorkflowRepository(session).get_user_run(
                payload.run_id,
                user_id=lease.user_id,
            )
            chapter = await session.get(Chapter, payload.chapter_id)
            selected_version = await session.get(ChapterVersion, request.selected_version_id)
            if not self._matches_frozen_identity(
                payload=payload,
                run=run,
                chapter=chapter,
                selected_version=selected_version,
            ):
                raise ValueError("workflow finalize 与冻结身份不一致")
            if selected_version is None:
                raise ValueError("workflow finalize 选中版本不存在")
            self._validate_selected_version(
                selected_version,
                run_id=payload.run_id,
            )
            source_content = (selected_version.content or "").strip()
            if not source_content:
                raise ValueError("workflow finalize 选中版本正文为空")
            source_hash = stable_digest(source_content)
            current_revision = int(chapter.current_revision or 0)
            is_pre_finalize = (
                current_revision == payload.base_revision
                and chapter.status == ChapterGenerationStatus.WAITING_FOR_CONFIRM.value
            )
            is_matching_finalized_result = (
                current_revision == payload.base_revision + 1
                and chapter.selected_version_id == request.selected_version_id
                and chapter.source_hash == source_hash
            )
            if not is_pre_finalize and not is_matching_finalized_result:
                raise ValueError("Chapter revision 已漂移，拒绝 workflow finalize")
            return _FinalizeIdentity(
                payload=payload,
                source_hash=source_hash,
            )

    async def _write_finalize(
        self,
        *,
        session: AsyncSession,
        request: ChapterWorkflowFinalizeInput,
        identity: _FinalizeIdentity,
        result_payload: dict[str, object],
    ) -> None:
        payload = identity.payload
        run = await ChapterWorkflowRepository(session).get_by_root_job_for_update(
            self.execution.lease.job_id
        )
        chapter = (
            await session.execute(
                select(Chapter)
                .where(Chapter.id == payload.chapter_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        versions = list(
            (
                await session.execute(
                    select(ChapterVersion)
                    .where(ChapterVersion.chapter_id == payload.chapter_id)
                    .order_by(ChapterVersion.id.asc())
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            ).scalars()
        )
        selected_version = next(
            (version for version in versions if version.id == request.selected_version_id),
            None,
        )
        if not self._matches_frozen_identity(
            payload=payload,
            run=run,
            chapter=chapter,
            selected_version=selected_version,
        ):
            raise ValueError("workflow finalize 事务 identity 已漂移")
        if selected_version is None:
            raise ValueError("workflow finalize 选中版本不存在")
        if int(chapter.current_revision or 0) != payload.base_revision:
            raise ValueError("Chapter revision 已漂移，拒绝 workflow finalize")
        if chapter.status != ChapterGenerationStatus.WAITING_FOR_CONFIRM.value:
            raise ValueError("Chapter 当前状态不允许 workflow finalize")
        self._validate_selected_version(selected_version, run_id=payload.run_id)
        source_content = (selected_version.content or "").strip()
        if stable_digest(source_content) != identity.source_hash:
            raise ValueError("workflow finalize 选中版本正文已漂移")

        finalize_service = ChapterFinalizeSubmissionService(session)
        prepared = await finalize_service.prepare(
            project_id=payload.project_id,
            chapter_number=payload.chapter_number,
            user_id=self.execution.lease.user_id,
            selected_version_id=request.selected_version_id,
            skip_vector_update=False,
            idempotency_key=f"chapter-workflow:{payload.run_id}:finalize",
        )
        if isinstance(prepared, BackgroundTask):
            raise ValueError("workflow finalize activity 与既有 canonical finalize 不一致")
        if prepared.source_hash != identity.source_hash:
            raise ValueError("workflow finalize prepare source hash 已漂移")
        finalized = await finalize_service.apply(
            prepared,
            workflow_stream_id=payload.run_id,
        )
        result_payload.update(
            {
                "target_chapter_revision": finalized.revision.revision,
                "chapter_revision_id": finalized.revision.id,
                "outbox_event_id": finalized.outbox_event.id,
                "dispatcher_job_id": finalized.job.id,
            }
        )
        result_payload["result_hash"] = stable_digest(result_payload)

    def _matches_frozen_identity(
        self,
        *,
        payload: ChapterWorkflowJobPayload,
        run,
        chapter: Chapter | None,
        selected_version: ChapterVersion | None,
    ) -> bool:
        return bool(
            run is not None
            and chapter is not None
            and selected_version is not None
            and run.id == payload.run_id
            and run.root_job_id == self.execution.lease.job_id
            and run.user_id == self.execution.lease.user_id
            and run.chapter_id == chapter.id == payload.chapter_id
            and selected_version.chapter_id == chapter.id
            and run.project_id == chapter.project_id == payload.project_id
            and payload.project_id == self.execution.lease.project_id
            and run.chapter_number == chapter.chapter_number == payload.chapter_number
            and run.base_revision == payload.base_revision
            and run.workflow_version == payload.workflow_version
            and run.state_schema_version == payload.state_schema_version
            and run.is_active
        )

    @staticmethod
    def _validate_selected_version(
        selected_version: ChapterVersion,
        *,
        run_id: str,
    ) -> None:
        workflow_metadata = (selected_version.metadata or {}).get("_chapter_workflow")
        if not isinstance(workflow_metadata, dict) or workflow_metadata.get("run_id") != run_id:
            raise ValueError("workflow finalize 选中版本不属于当前 run")


__all__ = [
    "ChapterWorkflowFinalizeExecution",
    "ChapterWorkflowFinalizeInput",
    "ChapterWorkflowFinalizeResult",
    "ChapterWorkflowFinalizeService",
]
