# AIMETA P=章节工作流启动事务_复用活动run或创建durable身份|R=Chapter锁_冻结输入_root_job_run_event原子提交|NR=不执行graph或接收HTTP命令|E=ChapterWorkflowStartService|X=internal|A=domain_service|D=sqlalchemy,pydantic|S=db|RD=./README.ai
"""Create or reuse one durable Chapter workflow identity."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.background_task import BackgroundTask
from ..models.chapter_workflow import ChapterWorkflowRun
from ..repositories.chapter_workflow_repository import ChapterWorkflowRepository
from ..repositories.novel_repository import NovelRepository
from ..schemas.chapter_context import stable_digest
from ..schemas.chapter_workflow import (
    CHAPTER_WORKFLOW_CONTEXT_SCHEMA_VERSION_V1,
    CHAPTER_WORKFLOW_STATE_SCHEMA_VERSION_V1,
    CHAPTER_WORKFLOW_VERSION_V1,
)
from ..schemas.job import ChapterWorkflowJobPayload, ChapterWorkflowRuntimeInputs
from ..schemas.novel import FlowConfig
from .chapter_context_resolver import ChapterContextResolver
from .chapter_workflow_context import build_chapter_workflow_retrieval_inputs
from .event_bus import publish_background_task
from .job_service import JobService


def _integrity_constraint_name(error: IntegrityError) -> Optional[str]:
    candidates = (
        error.orig,
        getattr(error.orig, "orig", None),
        getattr(error.orig, "__cause__", None),
    )
    for candidate in candidates:
        if candidate is None:
            continue
        name = getattr(candidate, "constraint_name", None)
        if isinstance(name, str) and name:
            return name
        diag = getattr(candidate, "diag", None)
        name = getattr(diag, "constraint_name", None)
        if isinstance(name, str) and name:
            return name
    return None


@dataclass(frozen=True)
class ChapterWorkflowStartResult:
    run: ChapterWorkflowRun
    root_job: BackgroundTask
    created: bool


class ChapterWorkflowStartService:
    """Own the transaction that establishes a Chapter workflow root."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.novel_repo = NovelRepository(session)
        self.workflow_repo = ChapterWorkflowRepository(session)
        self.job_service = JobService(session)

    async def start(
        self,
        *,
        user_id: int,
        project_id: str,
        chapter_number: int,
        writing_notes: Optional[str] = None,
        flow_config: Optional[FlowConfig | dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
    ) -> ChapterWorkflowStartResult:
        if user_id < 1:
            raise ValueError("user_id 必须大于等于 1")
        if not project_id.strip():
            raise ValueError("project_id 不能为空")
        if chapter_number < 1:
            raise ValueError("chapter_number 必须大于等于 1")

        project = await self.novel_repo.get_by_id(project_id)
        if project is None or project.user_id != user_id:
            await self.session.rollback()
            raise ValueError("项目不存在")

        base_revision: Optional[int] = None
        try:
            chapter = await self.novel_repo.ensure_chapter_for_update(
                project_id=project_id,
                chapter_number=chapter_number,
            )
            base_revision = chapter.current_revision
            replay = await self._idempotent_result(
                user_id=user_id,
                project_id=project_id,
                chapter_number=chapter_number,
                writing_notes=writing_notes,
                flow_config=flow_config,
                idempotency_key=idempotency_key,
            )
            if replay is not None:
                await self.session.commit()
                return replay
            existing = await self.workflow_repo.get_active_run(
                project_id=project_id,
                chapter_number=chapter_number,
                base_revision=base_revision,
            )
            if existing is not None:
                result = await self._existing_result(existing, user_id=user_id)
                await self.session.commit()
                return result

            normalized_flow = FlowConfig.model_validate(flow_config or {})
            # Base freeze 只读取 PostgreSQL canonical facts；RAG 由后续 typed
            # retrieval activity 按冻结配置执行并持久化，start 不做外部 I/O。
            resolver = ChapterContextResolver(
                self.session,
                vector_store=None,
            )
            context = await resolver.resolve(
                project_id=project_id,
                chapter_number=chapter_number,
                user_id=user_id,
                writing_notes=writing_notes,
                rag_enabled=False,
            )
            runtime_inputs = ChapterWorkflowRuntimeInputs(
                project_id=project_id,
                chapter_number=chapter_number,
                writing_notes=writing_notes,
                flow_config=normalized_flow,
                retrieval_inputs=build_chapter_workflow_retrieval_inputs(
                    context=context,
                    flow_config=normalized_flow,
                    resolver=resolver,
                ),
            )
            runtime_input_payload = runtime_inputs.model_dump(mode="json")
            runtime_input_hash = stable_digest(runtime_input_payload)
            run_id = str(uuid4())
            payload = ChapterWorkflowJobPayload(
                run_id=run_id,
                project_id=project_id,
                chapter_id=chapter.id,
                chapter_number=chapter_number,
                base_revision=base_revision,
                context_hash=context.input_hash,
                runtime_input_hash=runtime_input_hash,
                runtime_inputs=runtime_inputs,
            )
            root_job = await self.job_service.enqueue_job_in_transaction(
                user_id=user_id,
                project_id=project_id,
                job_type="chapter_workflow",
                title=f"生成第 {chapter_number} 章正文",
                payload=payload.model_dump(mode="json"),
                payload_version=1,
                idempotency_key=(
                    idempotency_key if idempotency_key is not None else f"chapter-workflow:{run_id}"
                ),
                stream_type="workflow",
                stream_id=run_id,
            )
            run = ChapterWorkflowRun(
                id=run_id,
                user_id=user_id,
                project_id=project_id,
                chapter_id=chapter.id,
                chapter_number=chapter_number,
                base_revision=base_revision,
                root_job_id=root_job.id,
                workflow_version=CHAPTER_WORKFLOW_VERSION_V1,
                state_schema_version=CHAPTER_WORKFLOW_STATE_SCHEMA_VERSION_V1,
                context_schema_version=CHAPTER_WORKFLOW_CONTEXT_SCHEMA_VERSION_V1,
                context_snapshot=context.snapshot_payload(),
                context_hash=context.input_hash,
                runtime_input_hash=runtime_input_hash,
                status="queued",
                node_key="freeze_context",
            )
            await self.workflow_repo.add(run)
            await self.job_service.append_workflow_started_in_transaction(
                job=root_job,
                run=run,
            )
            await self.session.commit()
        except IntegrityError as error:
            await self.session.rollback()
            if _integrity_constraint_name(error) == "uq_background_tasks_idempotency":
                replay = await self._idempotent_result(
                    user_id=user_id,
                    project_id=project_id,
                    chapter_number=chapter_number,
                    writing_notes=writing_notes,
                    flow_config=flow_config,
                    idempotency_key=idempotency_key,
                )
                if replay is not None:
                    await self.session.commit()
                    return replay
            if (
                base_revision is None
                or _integrity_constraint_name(error) != "uq_chapter_workflow_active"
            ):
                raise
            winner = await self.workflow_repo.get_active_run(
                project_id=project_id,
                chapter_number=chapter_number,
                base_revision=base_revision,
            )
            if winner is None:
                raise
            result = await self._existing_result(winner, user_id=user_id)
            await self.session.commit()
            return result
        except Exception:
            await self.session.rollback()
            raise

        await self.session.refresh(root_job)
        await self.session.refresh(run)
        await publish_background_task(user_id)
        return ChapterWorkflowStartResult(run=run, root_job=root_job, created=True)

    async def _idempotent_result(
        self,
        *,
        user_id: int,
        project_id: str,
        chapter_number: int,
        writing_notes: Optional[str],
        flow_config: Optional[FlowConfig | dict[str, Any]],
        idempotency_key: Optional[str],
    ) -> Optional[ChapterWorkflowStartResult]:
        if idempotency_key is None:
            return None
        existing_job = await self.job_service.repo.get_by_idempotency_key(
            user_id=user_id,
            job_type="chapter_workflow",
            idempotency_key=idempotency_key.strip(),
        )
        if existing_job is None:
            return None
        payload = ChapterWorkflowJobPayload.model_validate(existing_job.payload)
        requested_flow = FlowConfig.model_validate(flow_config or {})
        if (
            existing_job.project_id != project_id
            or payload.project_id != project_id
            or payload.chapter_number != chapter_number
            or payload.runtime_inputs.writing_notes != writing_notes
            or payload.runtime_inputs.flow_config != requested_flow
        ):
            raise ValueError("同一 idempotency_key 不能用于不同的任务参数")
        run = await self.workflow_repo.get_user_run(payload.run_id, user_id=user_id)
        if run is None or run.root_job_id != existing_job.id:
            raise RuntimeError("workflow idempotency root 缺少对应 run")
        self.job_service.assert_workflow_root_identity(job=existing_job, run=run)
        return ChapterWorkflowStartResult(run=run, root_job=existing_job, created=False)

    async def _existing_result(
        self,
        run: ChapterWorkflowRun,
        *,
        user_id: int,
    ) -> ChapterWorkflowStartResult:
        if run.user_id != user_id:
            raise ValueError("项目不存在")
        root_job = await self.job_service.get_job(run.root_job_id)
        if root_job is None:
            raise RuntimeError("活动 workflow run 缺少 root JobRun")
        self.job_service.assert_workflow_root_identity(job=root_job, run=run)
        return ChapterWorkflowStartResult(run=run, root_job=root_job, created=False)
