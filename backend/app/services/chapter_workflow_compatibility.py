# AIMETA P=章节工作流兼容适配_generate_finalize_select统一到run|R=legacy入口路由_command映射_候选校验|NR=不执行legacy handler或graph|E=ChapterWorkflowCompatibilityService|X=internal|A=domain_service|D=sqlalchemy,pydantic|S=db|RD=./README.ai
"""Route legacy writer operations to an existing durable Chapter workflow."""

from __future__ import annotations

from typing import Any, Optional, cast
from uuid import NAMESPACE_URL, uuid4, uuid5

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.background_task import BackgroundTask
from ..models.chapter_workflow import ChapterWorkflowRun
from ..models.novel import Chapter
from ..repositories.chapter_workflow_repository import ChapterWorkflowRepository
from ..repositories.novel_repository import NovelRepository
from ..schemas.chapter_workflow import (
    ChapterWorkflowCommandEnvelope,
    ChapterWorkflowCommandType,
    ChapterWorkflowSnapshot,
)
from ..schemas.novel import FlowConfig
from ..schemas.task import BackgroundTaskResponse
from .chapter_workflow_start import ChapterWorkflowStartService
from .job_public_projection import public_job_snapshot
from .job_service import ChapterWorkflowCommandRejectedError, JobService

RETRY_NODE_MAP = {
    "context_prep": "freeze_base_context",
    "rag_retrieval": "retrieve_context",
    "director_mission": "plan_chapter",
    "draft_generation": "generate_candidate_1",
    "quality_review": "review_candidates",
    "review_refinement": "refine_candidate",
}


class ChapterWorkflowCompatibilityConflictError(ValueError):
    """Legacy request cannot be represented by the current workflow contract."""

    def __init__(self, reason_code: str):
        super().__init__(reason_code)
        self.reason_code = reason_code


class ChapterWorkflowCompatibilityService:
    """Map existing writer request shapes to durable Chapter workflow operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.novel_repo = NovelRepository(session)
        self.workflow_repo = ChapterWorkflowRepository(session)
        self.job_service = JobService(session)

    async def adapt_generation(
        self,
        *,
        user_id: int,
        project_id: str,
        chapter_number: int,
        writing_notes: Optional[str],
        flow_config: FlowConfig | dict[str, Any],
        from_node_key: Optional[str],
        idempotency_key: Optional[str],
    ) -> BackgroundTaskResponse:
        """Start a workflow or map a legacy node retry to its durable run."""

        if from_node_key is not None:
            return await self._adapt_generation_retry(
                user_id=user_id,
                project_id=project_id,
                chapter_number=chapter_number,
                from_node_key=from_node_key,
                idempotency_key=idempotency_key,
            )

        result = await ChapterWorkflowStartService(self.session).start(
            user_id=user_id,
            project_id=project_id,
            chapter_number=chapter_number,
            writing_notes=writing_notes,
            flow_config=flow_config,
            idempotency_key=idempotency_key,
        )
        return self._public_root_response(result.root_job)

    async def adapt_finalize(
        self,
        *,
        user_id: int,
        project_id: str,
        chapter_number: int,
        selected_version_index: Optional[int],
        selected_version_id: Optional[int],
        edited_content: Optional[str],
        skip_vector_update: bool,
        idempotency_key: Optional[str],
    ) -> Optional[BackgroundTaskResponse]:
        """Map an active workflow finalize/select request to one select command."""

        located = await self._current_chapter_and_active_run(
            user_id=user_id,
            project_id=project_id,
            chapter_number=chapter_number,
        )
        if located is None:
            return None
        chapter, run = located
        if edited_content is not None or skip_vector_update:
            raise ChapterWorkflowCompatibilityConflictError("workflow_finalize_options_unsupported")

        selected_id = await self._resolve_candidate_version_id(
            chapter_id=chapter.id,
            run_id=run.id,
            selected_version_index=selected_version_index,
            selected_version_id=selected_version_id,
        )
        replayed = await self._replay_existing_command(
            run=run,
            user_id=user_id,
            command_type="select",
            payload={"selected_version_id": selected_id},
            command_kind="finalize-select",
            idempotency_key=idempotency_key,
        )
        if replayed is not None:
            return replayed
        snapshot = await self.job_service.get_chapter_workflow_snapshot(
            run.id,
            user_id=user_id,
        )
        if "select" not in snapshot.allowed_commands:
            raise ChapterWorkflowCompatibilityConflictError("command_not_allowed_in_current_state")
        return await self._submit_command_and_return_root(
            snapshot=snapshot,
            user_id=user_id,
            command_type="select",
            payload={"selected_version_id": selected_id},
            command_kind="finalize-select",
            idempotency_key=idempotency_key,
        )

    async def _adapt_generation_retry(
        self,
        *,
        user_id: int,
        project_id: str,
        chapter_number: int,
        from_node_key: str,
        idempotency_key: Optional[str],
    ) -> BackgroundTaskResponse:
        chapter = await self.novel_repo.get_owned_chapter(
            project_id=project_id,
            chapter_number=chapter_number,
            user_id=user_id,
        )
        if chapter is None:
            raise ChapterWorkflowCompatibilityConflictError("workflow_retry_run_not_found")
        run = await self.workflow_repo.get_active_run(
            project_id=project_id,
            chapter_number=chapter_number,
            base_revision=chapter.current_revision,
        )
        if run is None:
            run = await self.workflow_repo.get_latest_retryable_run(
                project_id=project_id,
                chapter_number=chapter_number,
                base_revision=chapter.current_revision,
            )
        if run is None:
            raise ChapterWorkflowCompatibilityConflictError("workflow_retry_run_not_found")

        mapped_node = RETRY_NODE_MAP.get(from_node_key)
        if mapped_node is None:
            raise ChapterWorkflowCompatibilityConflictError("workflow_retry_node_unsupported")
        if mapped_node != run.node_key:
            raise ChapterWorkflowCompatibilityConflictError("workflow_retry_node_mismatch")
        replayed = await self._replay_existing_command(
            run=run,
            user_id=user_id,
            command_type="retry",
            payload={},
            command_kind="generation-retry",
            idempotency_key=idempotency_key,
        )
        if replayed is not None:
            return replayed
        snapshot = await self.job_service.get_chapter_workflow_snapshot(
            run.id,
            user_id=user_id,
        )
        if "retry" not in snapshot.allowed_commands:
            raise ChapterWorkflowCompatibilityConflictError("command_not_allowed_in_current_state")
        return await self._submit_command_and_return_root(
            snapshot=snapshot,
            user_id=user_id,
            command_type="retry",
            payload={},
            command_kind="generation-retry",
            idempotency_key=idempotency_key,
        )

    async def _current_chapter_and_active_run(
        self,
        *,
        user_id: int,
        project_id: str,
        chapter_number: int,
    ) -> Optional[tuple[Chapter, ChapterWorkflowRun]]:
        chapter = await self.novel_repo.get_owned_chapter(
            project_id=project_id,
            chapter_number=chapter_number,
            user_id=user_id,
        )
        if chapter is None:
            return None
        run = await self.workflow_repo.get_active_run(
            project_id=project_id,
            chapter_number=chapter_number,
            base_revision=chapter.current_revision,
        )
        if run is None:
            return None
        if run.user_id != user_id or run.chapter_id != chapter.id:
            raise ChapterWorkflowCompatibilityConflictError("workflow_identity_mismatch")
        return chapter, run

    async def _resolve_candidate_version_id(
        self,
        *,
        chapter_id: int,
        run_id: str,
        selected_version_index: Optional[int],
        selected_version_id: Optional[int],
    ) -> int:
        if (selected_version_index is None) == (selected_version_id is None):
            raise ValueError("必须且只能指定候选草稿索引或版本 ID")
        versions = await self.novel_repo.list_chapter_versions(chapter_id=chapter_id)
        if selected_version_index is not None:
            if selected_version_index < 0 or selected_version_index >= len(versions):
                raise ChapterWorkflowCompatibilityConflictError(
                    "workflow_candidate_version_invalid"
                )
            selected = versions[selected_version_index]
        else:
            selected = next(
                (version for version in versions if version.id == selected_version_id),
                None,
            )
            if selected is None:
                raise ChapterWorkflowCompatibilityConflictError(
                    "workflow_candidate_version_invalid"
                )
        metadata = selected.metadata if isinstance(selected.metadata, dict) else {}
        workflow_metadata = metadata.get("_chapter_workflow")
        if not isinstance(workflow_metadata, dict) or workflow_metadata.get("run_id") != run_id:
            raise ChapterWorkflowCompatibilityConflictError("workflow_candidate_version_invalid")
        return cast(int, selected.id)

    async def _submit_command_and_return_root(
        self,
        *,
        snapshot: ChapterWorkflowSnapshot,
        user_id: int,
        command_type: ChapterWorkflowCommandType,
        payload: dict[str, Any],
        command_kind: str,
        idempotency_key: Optional[str],
    ) -> BackgroundTaskResponse:
        if snapshot.checkpoint_id is None:
            raise ChapterWorkflowCompatibilityConflictError("workflow_checkpoint_missing")
        command_id = self._command_id(
            kind=command_kind,
            user_id=user_id,
            run_id=snapshot.run_id,
            idempotency_key=idempotency_key,
        )
        envelope = ChapterWorkflowCommandEnvelope(
            command_id=command_id,
            type=command_type,
            payload=payload,
            expected_run_revision=snapshot.row_revision,
            expected_chapter_revision=snapshot.current_chapter_revision,
            expected_checkpoint_id=snapshot.checkpoint_id,
        )
        return await self._submit_envelope_and_return_root(
            envelope=envelope,
            run_id=snapshot.run_id,
            root_job_id=snapshot.root_job_id,
            user_id=user_id,
        )

    async def _replay_existing_command(
        self,
        *,
        run: ChapterWorkflowRun,
        user_id: int,
        command_type: ChapterWorkflowCommandType,
        payload: dict[str, Any],
        command_kind: str,
        idempotency_key: Optional[str],
    ) -> Optional[BackgroundTaskResponse]:
        if idempotency_key is None:
            return None
        command_id = self._command_id(
            kind=command_kind,
            user_id=user_id,
            run_id=run.id,
            idempotency_key=idempotency_key,
        )
        existing = await self.workflow_repo.get_command(command_id)
        if existing is None:
            return None
        if existing.expected_checkpoint_id is None:
            raise ChapterWorkflowCompatibilityConflictError("workflow_checkpoint_missing")
        envelope = ChapterWorkflowCommandEnvelope(
            command_id=command_id,
            type=command_type,
            payload=payload,
            expected_run_revision=existing.expected_run_revision,
            expected_chapter_revision=existing.expected_chapter_revision,
            expected_checkpoint_id=existing.expected_checkpoint_id,
        )
        return await self._submit_envelope_and_return_root(
            envelope=envelope,
            run_id=run.id,
            root_job_id=run.root_job_id,
            user_id=user_id,
        )

    async def _submit_envelope_and_return_root(
        self,
        *,
        envelope: ChapterWorkflowCommandEnvelope,
        run_id: str,
        root_job_id: str,
        user_id: int,
    ) -> BackgroundTaskResponse:
        try:
            await self.job_service.submit_chapter_workflow_command(
                run_id,
                actor_user_id=user_id,
                envelope=envelope,
            )
        except ChapterWorkflowCommandRejectedError as exc:
            raise ChapterWorkflowCompatibilityConflictError(exc.reason_code) from exc
        except ValueError as exc:
            if "command id 已绑定不同请求" in str(exc):
                raise ChapterWorkflowCompatibilityConflictError(
                    "workflow_command_identity_conflict"
                ) from exc
            raise
        job = await self.job_service.get_job(root_job_id)
        if job is None:
            raise RuntimeError("workflow run 缺少 root JobRun")
        return self._public_root_response(job)

    @staticmethod
    def _command_id(
        *,
        kind: str,
        user_id: int,
        run_id: str,
        idempotency_key: Optional[str],
    ) -> str:
        if idempotency_key is None:
            return str(uuid4())
        return str(
            uuid5(
                NAMESPACE_URL,
                f"chapter-workflow-compat:{kind}:{user_id}:{run_id}:{idempotency_key}",
            )
        )

    @staticmethod
    def _public_root_response(job: BackgroundTask) -> BackgroundTaskResponse:
        return BackgroundTaskResponse.model_validate(public_job_snapshot(job))
