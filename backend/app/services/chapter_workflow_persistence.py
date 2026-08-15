# AIMETA P=章节工作流候选事务持久化|R=私有activity引用校验_fenced原子写入_引用型checkpoint|NR=不读取trace_不推进等待lease|E=ChapterWorkflowCandidatePersistenceService|X=internal|A=domain_service|D=pydantic,sqlalchemy|S=db|RD=./README.ai
"""Transactional candidate persistence for the durable Chapter workflow."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.chapter_projection import ChapterRevision
from ..models.novel import Chapter, ChapterEvaluation, ChapterVersion
from ..repositories.chapter_workflow_repository import ChapterWorkflowRepository
from ..repositories.job_repository import JobRepository
from ..schemas.chapter_context import stable_digest
from ..schemas.job import (
    ChapterWorkflowJobPayload,
    validate_chapter_workflow_job_payload,
)
from ..schemas.novel import ChapterGenerationStatus
from .chapter_workflow_activities import (
    ChapterWorkflowActivityRef,
    ChapterWorkflowCandidateOutput,
    ChapterWorkflowModelActivityResult,
    ChapterWorkflowPostReviewOutput,
    ChapterWorkflowReviewOutput,
)
from .job_registry import SideEffectClass
from .job_worker import JobExecutionContext

PERSIST_DRAFTS_REF = "persist_drafts"


class ChapterWorkflowPersistCandidatesInput(BaseModel):
    """只引用已入账模型结果；候选正文不进入事务 activity request。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    candidate_refs: list[ChapterWorkflowActivityRef] = Field(
        min_length=1,
        max_length=100,
    )
    review_ref: ChapterWorkflowActivityRef | None = None
    post_review_refs: dict[int, list[ChapterWorkflowActivityRef]] = Field(
        default_factory=dict,
        max_length=100,
    )

    @model_validator(mode="after")
    def validate_refs(self):
        refs = [*self.candidate_refs]
        if self.review_ref is not None:
            refs.append(self.review_ref)
        for ordinal, stage_refs in self.post_review_refs.items():
            if ordinal < 1 or ordinal > 100:
                raise ValueError("post-review ordinal 必须在 1 到 100 之间")
            if not stage_refs:
                raise ValueError("post-review 引用列表不可为空")
            refs.extend(stage_refs)
        activity_keys = [ref.activity_key for ref in refs]
        if len(activity_keys) != len(set(activity_keys)):
            raise ValueError("候选持久化 activity 引用不可重复")
        return self


class ChapterWorkflowPersistCandidatesResult(BaseModel):
    """事务结果仅保存数据库 identity 和内容 hash。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_version_ids: list[int] = Field(min_length=1, max_length=100)
    candidate_content_hashes: list[str] = Field(min_length=1, max_length=100)
    result_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_content_addresses(self):
        if len(self.candidate_version_ids) != len(self.candidate_content_hashes):
            raise ValueError("候选版本 ID 与正文 hash 数量不一致")
        if any(version_id < 1 for version_id in self.candidate_version_ids):
            raise ValueError("候选版本 ID 必须大于 0")
        if any(
            len(content_hash) != 64 or any(char not in "0123456789abcdef" for char in content_hash)
            for content_hash in self.candidate_content_hashes
        ):
            raise ValueError("候选正文 hash 格式无效")
        expected_hash = stable_digest(self.model_dump(mode="json", exclude={"result_hash"}))
        if self.result_hash != expected_hash:
            raise ValueError("候选持久化 result hash 与结果不一致")
        return self


@dataclass(frozen=True)
class ChapterWorkflowPersistCandidatesExecution:
    activity_key: str
    result: ChapterWorkflowPersistCandidatesResult

    def state_update(self) -> dict[str, object]:
        return {
            "node_key": "wait_for_selection",
            "candidate_version_ids": self.result.candidate_version_ids,
            "activity_refs": {PERSIST_DRAFTS_REF: self.activity_key},
            "result_refs": {PERSIST_DRAFTS_REF: self.result.result_hash},
        }


@dataclass(frozen=True)
class _CandidateDraft:
    ordinal: int
    content: str
    metadata: dict[str, object]
    source_ref: ChapterWorkflowActivityRef


class ChapterWorkflowCandidatePersistenceService:
    """Persist candidate rows atomically with the transactional activity result."""

    def __init__(self, execution: JobExecutionContext) -> None:
        self.execution = execution

    async def execute(
        self,
        request: ChapterWorkflowPersistCandidatesInput,
    ) -> ChapterWorkflowPersistCandidatesExecution:
        payload, drafts, review = await self._load_inputs(request)
        input_hash = stable_digest(request.model_dump(mode="json"))
        canonical_request = {
            "schema_version": 1,
            "workflow_version": payload.workflow_version,
            "state_schema_version": payload.state_schema_version,
            "run_id": payload.run_id,
            "node_key": "persist_drafts",
            "base_revision": payload.base_revision,
            "input_hash": input_hash,
        }
        activity_key = f"wf:{canonical_request['node_key']}:{stable_digest(canonical_request)}"
        activity = await self.execution.begin_activity(
            activity_key,
            side_effect_class=SideEffectClass.TRANSACTIONAL,
            request_payload=canonical_request,
        )
        if not activity.should_execute:
            result = ChapterWorkflowPersistCandidatesResult.model_validate(activity.result)
            if result.input_hash != input_hash:
                raise ValueError("候选持久化 replay input hash 不一致")
            return ChapterWorkflowPersistCandidatesExecution(activity_key, result)

        result_payload: dict[str, object] = {
            "schema_version": 1,
            "input_hash": input_hash,
            "candidate_version_ids": [],
            "candidate_content_hashes": [stable_digest(draft.content) for draft in drafts],
        }

        async def write_candidates(session: AsyncSession) -> None:
            version_ids = await self._write_candidates(
                session=session,
                payload=payload,
                drafts=drafts,
                review=review,
            )
            result_payload["candidate_version_ids"] = version_ids
            result_payload["result_hash"] = stable_digest(result_payload)

        completed_activity = await self.execution.complete_activity(
            activity_key,
            provider_request_key=activity.provider_request_key,
            result=result_payload,
            outcome_writer=write_candidates,
        )
        result = ChapterWorkflowPersistCandidatesResult.model_validate(
            completed_activity.result_payload
        )
        return ChapterWorkflowPersistCandidatesExecution(activity_key, result)

    async def _load_inputs(
        self,
        request: ChapterWorkflowPersistCandidatesInput,
    ) -> tuple[
        ChapterWorkflowJobPayload,
        list[_CandidateDraft],
        ChapterWorkflowReviewOutput | None,
    ]:
        lease = self.execution.lease
        if lease.job_type != "chapter_workflow":
            raise ValueError("workflow root job 类型或版本不匹配")
        payload = validate_chapter_workflow_job_payload(
            lease.payload_version,
            lease.payload,
        )
        async with self.execution.session_factory() as session:
            run = await ChapterWorkflowRepository(session).get_user_run(
                payload.run_id,
                user_id=lease.user_id,
            )
            chapter = await session.get(Chapter, payload.chapter_id)
            if (
                run is None
                or chapter is None
                or run.root_job_id != lease.job_id
                or run.chapter_id != chapter.id
                or run.project_id != payload.project_id
                or payload.project_id != lease.project_id
                or run.chapter_number != payload.chapter_number
                or run.base_revision != payload.base_revision
                or run.workflow_version != payload.workflow_version
                or run.state_schema_version != payload.state_schema_version
                or not run.is_active
            ):
                raise ValueError("候选持久化与 workflow 冻结身份不一致")
            if int(chapter.current_revision or 0) != payload.base_revision:
                raise ValueError("Chapter revision 已漂移，拒绝持久化候选")

            repository = JobRepository(session)
            candidate_results = [
                await self._load_model_result(repository, ref) for ref in request.candidate_refs
            ]
            candidates: list[ChapterWorkflowCandidateOutput] = []
            for result in candidate_results:
                if result.stage != "generate_candidate" or not isinstance(
                    result.output, ChapterWorkflowCandidateOutput
                ):
                    raise ValueError("候选持久化引用不是 candidate result")
                candidates.append(result.output)
            ordinals = [candidate.ordinal for candidate in candidates]
            if ordinals != list(range(1, len(candidates) + 1)):
                raise ValueError("候选持久化 ordinal 必须从 1 连续递增")

            review: ChapterWorkflowReviewOutput | None = None
            if request.review_ref is not None:
                review_result = await self._load_model_result(
                    repository,
                    request.review_ref,
                )
                if review_result.stage != "version_review" or not isinstance(
                    review_result.output, ChapterWorkflowReviewOutput
                ):
                    raise ValueError("候选持久化 review 引用无效")
                review = review_result.output
                if review.best_ordinal not in ordinals:
                    raise ValueError("review 推荐 ordinal 不在候选集合中")
                expected_candidate_hashes = {
                    f"candidate:{candidate.ordinal}": ref.result_hash
                    for candidate, ref in zip(
                        candidates,
                        request.candidate_refs,
                        strict=True,
                    )
                }
                if any(
                    review_result.upstream_result_hashes.get(name) != result_hash
                    for name, result_hash in expected_candidate_hashes.items()
                ):
                    raise ValueError("review result 未绑定当前候选集合")

            drafts = [
                _CandidateDraft(
                    ordinal=candidate.ordinal,
                    content=candidate.content,
                    metadata=deepcopy(candidate.metadata),
                    source_ref=ref,
                )
                for candidate, ref in zip(candidates, request.candidate_refs, strict=True)
            ]
            draft_by_ordinal = {draft.ordinal: draft for draft in drafts}
            for ordinal, refs in request.post_review_refs.items():
                draft = draft_by_ordinal.get(ordinal)
                if draft is None:
                    raise ValueError("post-review ordinal 不在候选集合中")
                stages: set[str] = set()
                content = draft.content
                reports: dict[str, object] = {}
                for ref in refs:
                    result = await self._load_model_result(repository, ref)
                    if result.subject_ordinal != ordinal or not isinstance(
                        result.output, ChapterWorkflowPostReviewOutput
                    ):
                        raise ValueError("post-review result 与候选 ordinal 不一致")
                    candidate_ref = request.candidate_refs[ordinal - 1]
                    if (
                        result.upstream_result_hashes.get(f"candidate:{ordinal}")
                        != candidate_ref.result_hash
                    ):
                        raise ValueError("post-review result 未绑定当前候选")
                    if (
                        request.review_ref is not None
                        and result.upstream_result_hashes.get("review:version_review")
                        != request.review_ref.result_hash
                    ):
                        raise ValueError("post-review result 未绑定当前 review")
                    if result.output.stage in stages:
                        raise ValueError("同一候选 post-review stage 不可重复")
                    stages.add(result.output.stage)
                    if result.output.content is not None:
                        content = result.output.content
                    if result.output.report:
                        reports[result.output.stage] = result.output.report
                metadata = deepcopy(draft.metadata)
                if reports:
                    metadata["review_summaries"] = reports
                draft_by_ordinal[ordinal] = _CandidateDraft(
                    ordinal=draft.ordinal,
                    content=content,
                    metadata=metadata,
                    source_ref=refs[-1],
                )
            return payload, [draft_by_ordinal[value] for value in ordinals], review

    async def _load_model_result(
        self,
        repository: JobRepository,
        ref: ChapterWorkflowActivityRef,
    ) -> ChapterWorkflowModelActivityResult:
        activity = await repository.get_activity(
            job_id=self.execution.lease.job_id,
            activity_key=ref.activity_key,
        )
        if (
            activity is None
            or activity.status != "succeeded"
            or activity.side_effect_class != SideEffectClass.AMBIGUOUS_EXTERNAL.value
        ):
            raise ValueError("候选持久化上游 activity 不存在或未完成")
        result: ChapterWorkflowModelActivityResult = (
            ChapterWorkflowModelActivityResult.model_validate(activity.result_payload)
        )
        if result.result_hash != ref.result_hash:
            raise ValueError("候选持久化上游 result hash 不一致")
        return result

    async def _write_candidates(
        self,
        *,
        session: AsyncSession,
        payload: ChapterWorkflowJobPayload,
        drafts: list[_CandidateDraft],
        review: ChapterWorkflowReviewOutput | None,
    ) -> list[int]:
        run = await ChapterWorkflowRepository(session).get_by_root_job_for_update(
            self.execution.lease.job_id
        )
        chapter = await session.get(Chapter, payload.chapter_id)
        if (
            run is None
            or chapter is None
            or run.id != payload.run_id
            or run.chapter_id != chapter.id
            or run.project_id != payload.project_id
            or run.chapter_number != payload.chapter_number
            or run.base_revision != payload.base_revision
            or int(chapter.current_revision or 0) != payload.base_revision
            or not run.is_active
        ):
            raise ValueError("候选持久化事务 identity/revision 已漂移")

        existing_versions = list(
            (
                await session.execute(
                    select(ChapterVersion)
                    .where(ChapterVersion.chapter_id == chapter.id)
                    .order_by(ChapterVersion.id.asc())
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            ).scalars()
        )
        existing_version_ids = {version.id for version in existing_versions}
        if (
            chapter.selected_version_id is not None
            and chapter.selected_version_id not in existing_version_ids
        ):
            raise ValueError("Chapter selected version 不属于当前章节")
        revision_version_ids = set(
            (
                await session.execute(
                    select(ChapterRevision.selected_version_id).where(
                        ChapterRevision.chapter_id == chapter.id,
                        ChapterRevision.selected_version_id.is_not(None),
                    )
                )
            ).scalars()
        )
        protected_version_ids = {
            version_id
            for version_id in {
                chapter.selected_version_id,
                *revision_version_ids,
            }
            if version_id is not None
        }
        stale_ids = [
            version.id for version in existing_versions if version.id not in protected_version_ids
        ]
        if stale_ids:
            await session.execute(
                delete(ChapterEvaluation).where(ChapterEvaluation.version_id.in_(stale_ids))
            )
            await session.execute(delete(ChapterVersion).where(ChapterVersion.id.in_(stale_ids)))

        versions: list[ChapterVersion] = []
        for draft in drafts:
            metadata = deepcopy(draft.metadata)
            if review is not None:
                metadata["ai_review"] = {
                    "is_best": draft.ordinal == review.best_ordinal,
                }
            metadata["_chapter_workflow"] = {
                "run_id": payload.run_id,
                "ordinal": draft.ordinal,
                "source_activity_key": draft.source_ref.activity_key,
                "source_result_hash": draft.source_ref.result_hash,
                "content_hash": stable_digest(draft.content),
            }
            version = ChapterVersion(
                chapter_id=chapter.id,
                version_label=f"v{draft.ordinal}",
                content=draft.content,
                metadata=metadata,
            )
            session.add(version)
            versions.append(version)
        await session.flush()

        if review is not None:
            review_version = versions[review.best_ordinal - 1]
            session.add(
                ChapterEvaluation(
                    chapter_id=chapter.id,
                    version_id=review_version.id,
                    decision="ai_review",
                    feedback=json.dumps(
                        {
                            "best_ordinal": review.best_ordinal,
                            "report": review.report,
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                )
            )

        chapter.status = ChapterGenerationStatus.WAITING_FOR_CONFIRM.value
        chapter.generation_step = f"waiting_for_confirm|v={len(versions)}"
        chapter.generation_progress = 100
        chapter.generation_step_index = 7
        chapter.generation_step_total = 7
        await session.flush()
        return [cast(int, version.id) for version in versions]


__all__ = [
    "ChapterWorkflowCandidatePersistenceService",
    "ChapterWorkflowPersistCandidatesExecution",
    "ChapterWorkflowPersistCandidatesInput",
    "ChapterWorkflowPersistCandidatesResult",
]
