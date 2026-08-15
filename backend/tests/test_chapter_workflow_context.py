# AIMETA P=章节工作流context_activity测试|R=冻结retrieval输入_activity重放_引用型state|NR=不执行完整graph|E=test_*|X=internal|A=integration_test|D=pytest|S=test|RD=./README.ai
from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from test_chapter_workflow_start import _seed_project

from app.models import JobActivity
from app.schemas.chapter_context import ChapterContext, ContextFallback, stable_digest
from app.services.chapter_context_resolver import ChapterContextResolver
from app.services.chapter_workflow_context import ChapterWorkflowContextService
from app.services.chapter_workflow_start import ChapterWorkflowStartService
from app.services.job_registry import SideEffectClass
from app.services.job_service import JobService
from app.services.job_worker import JobExecutionContext, RetryableJobError


async def _start_and_claim(isolated_pg, *, user_id: int, project_id: str):
    session_factory = isolated_pg.session_factory
    async with session_factory() as session:
        await _seed_project(session, user_id=user_id, project_id=project_id)
        started = await ChapterWorkflowStartService(session).start(
            user_id=user_id,
            project_id=project_id,
            chapter_number=1,
            writing_notes="保持克制",
            flow_config={"preset": "enhanced", "enable_rag": True},
        )
        lease = await JobService(session).claim_next(
            worker_id=f"context-{user_id}",
            lease_seconds=60,
        )
    assert lease is not None
    execution = JobExecutionContext(
        lease=lease,
        side_effect_class=SideEffectClass.TRANSACTIONAL,
        session_factory=session_factory,
    )
    return started, execution


@pytest.mark.asyncio(loop_scope="session")
async def test_retrieval_activity_persists_enriched_snapshot_and_returns_only_refs(
    isolated_pg,
):
    started, execution = await _start_and_claim(
        isolated_pg,
        user_id=4201,
        project_id="workflow-context-project",
    )
    calls = 0

    def resolver_factory(session):
        resolver = ChapterContextResolver(session, vector_store=None)
        original = resolver.with_retrieval

        async def counted(*args, **kwargs):
            nonlocal calls
            calls += 1
            return await original(*args, **kwargs)

        resolver.with_retrieval = counted
        return resolver

    service = ChapterWorkflowContextService(
        execution,
        resolver_factory=resolver_factory,
    )
    first = await service.execute_retrieval_activity()
    replay = await service.execute_retrieval_activity()

    async with isolated_pg.session_factory() as session:
        activity = (
            await session.execute(
                select(JobActivity).where(JobActivity.job_id == started.root_job.id)
            )
        ).scalar_one()

    persisted = activity.result_payload
    assert persisted is not None
    restored = ChapterContext.model_validate(persisted["context_snapshot"])
    assert calls == 1
    assert activity.status == "succeeded"
    assert activity.side_effect_class == SideEffectClass.IDEMPOTENT_EXTERNAL.value
    assert persisted["base_context_hash"] == started.run.context_hash
    assert persisted["context_hash"] == restored.input_hash
    assert persisted["result_hash"] == stable_digest(
        {key: value for key, value in persisted.items() if key != "result_hash"}
    )
    assert restored.rag.fallback == ContextFallback.UNAVAILABLE
    assert replay == first
    assert first.state_update() == {
        "node_key": "plan_chapter",
        "context_hash": restored.input_hash,
        "activity_refs": {"retrieval_context": activity.activity_key},
        "result_refs": {"retrieval_context": persisted["result_hash"]},
    }
    assert "context_snapshot" not in first.state_update()


@pytest.mark.asyncio(loop_scope="session")
async def test_retrieval_activity_rejects_frozen_identity_drift_before_intent(
    isolated_pg,
):
    started, execution = await _start_and_claim(
        isolated_pg,
        user_id=4202,
        project_id="workflow-context-drift",
    )
    execution.lease.payload["context_hash"] = "f" * 64

    with pytest.raises(ValueError, match="冻结身份"):
        await ChapterWorkflowContextService(execution).execute_retrieval_activity()

    async with isolated_pg.session_factory() as session:
        activity_count = len(
            list(
                (
                    await session.execute(
                        select(JobActivity).where(JobActivity.job_id == started.root_job.id)
                    )
                ).scalars()
            )
        )
    assert activity_count == 0


@pytest.mark.asyncio(loop_scope="session")
async def test_retrieval_activity_marks_unclassified_failure_retryable(
    isolated_pg,
):
    started, execution = await _start_and_claim(
        isolated_pg,
        user_id=4203,
        project_id="workflow-context-failure",
    )

    class FailingResolver:
        async def with_retrieval(self, *_args, **_kwargs):
            raise RuntimeError("provider transport broke")

    service = ChapterWorkflowContextService(
        execution,
        resolver_factory=lambda _session: FailingResolver(),
    )
    with pytest.raises(RetryableJobError, match="章节检索上下文构建失败"):
        await service.execute_retrieval_activity()

    async with isolated_pg.session_factory() as session:
        activity = (
            await session.execute(
                select(JobActivity).where(JobActivity.job_id == started.root_job.id)
            )
        ).scalar_one()
    assert activity.status == "retryable_failed"
    assert activity.error_category == "chapter_context_retrieval_failed"
    assert activity.result_payload is None


@pytest.mark.asyncio(loop_scope="session")
async def test_retrieval_activity_rejects_canonical_request_drift(isolated_pg):
    _started, execution = await _start_and_claim(
        isolated_pg,
        user_id=4204,
        project_id="workflow-context-request-drift",
    )
    service = ChapterWorkflowContextService(
        execution,
        resolver_factory=lambda session: ChapterContextResolver(
            session,
            vector_store=None,
        ),
    )
    completed = await service.execute_retrieval_activity()

    drifted_payload = deepcopy(execution.lease.payload)
    drifted_payload["runtime_inputs"]["retrieval_inputs"]["query_text"] = "漂移"
    drifted_payload["runtime_input_hash"] = stable_digest(drifted_payload["runtime_inputs"])
    execution.lease.payload.clear()
    execution.lease.payload.update(drifted_payload)

    with pytest.raises(ValueError, match="冻结身份"):
        await service.execute_retrieval_activity()
    assert completed.result.context_hash


@pytest.mark.asyncio(loop_scope="session")
async def test_retrieval_activity_replay_rejects_tampered_private_result(isolated_pg):
    _started, execution = await _start_and_claim(
        isolated_pg,
        user_id=4205,
        project_id="workflow-context-result-drift",
    )
    calls = 0

    def resolver_factory(session):
        resolver = ChapterContextResolver(session, vector_store=None)
        original = resolver.with_retrieval

        async def counted(*args, **kwargs):
            nonlocal calls
            calls += 1
            return await original(*args, **kwargs)

        resolver.with_retrieval = counted
        return resolver

    service = ChapterWorkflowContextService(
        execution,
        resolver_factory=resolver_factory,
    )
    await service.execute_retrieval_activity()
    async with isolated_pg.session_factory() as session:
        activity = (
            await session.execute(
                select(JobActivity).where(JobActivity.job_id == execution.lease.job_id)
            )
        ).scalar_one()
        activity.result_payload = {
            **activity.result_payload,
            "result_hash": "f" * 64,
        }
        await session.commit()

    with pytest.raises(ValidationError, match="result hash"):
        await service.execute_retrieval_activity()
    assert calls == 1
