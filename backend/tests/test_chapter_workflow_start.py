# AIMETA P=章节工作流start事务测试|R=冻结身份_并发复用_无孤儿|NR=不执行graph或HTTP适配|E=test_*|X=internal|A=integration_test|D=pytest|S=test|RD=./README.ai
import asyncio

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from app.models import (
    BackgroundTask,
    Chapter,
    ChapterOutline,
    ChapterWorkflowRun,
    JobEvent,
    NovelProject,
    SystemConfig,
)
from app.models.user import User
from app.schemas.chapter_context import ChapterContext, ContextFallback, stable_digest
from app.schemas.job import ChapterWorkflowJobPayload
from app.services.chapter_workflow_start import ChapterWorkflowStartService


async def _seed_project(session, *, user_id: int, project_id: str) -> None:
    session.add(User(id=user_id, username=f"start-{user_id}", hashed_password="secret"))
    session.add(
        NovelProject(
            id=project_id,
            user_id=user_id,
            title="Workflow start",
            initial_prompt="test",
        )
    )
    session.add(
        ChapterOutline(
            project_id=project_id,
            chapter_number=1,
            title="第一章",
            summary="开端",
            goals="建立冲突",
            highlights=[],
            character_states={},
        )
    )
    await session.commit()


@pytest.mark.asyncio(loop_scope="session")
async def test_start_freezes_identity_and_reuses_active_run(isolated_pg):
    session_factory = isolated_pg.session_factory
    async with session_factory() as session:
        await _seed_project(session, user_id=4101, project_id="workflow-start-project")
        service = ChapterWorkflowStartService(session)
        created = await service.start(
            user_id=4101,
            project_id="workflow-start-project",
            chapter_number=1,
            writing_notes="保持克制",
            flow_config={"preset": "basic", "enable_rag": True},
        )
        duplicate = await service.start(
            user_id=4101,
            project_id="workflow-start-project",
            chapter_number=1,
            writing_notes="不同请求仍返回当前活动 run",
            flow_config={"preset": "enhanced"},
        )

        events = list(
            (
                await session.execute(
                    select(JobEvent)
                    .where(JobEvent.stream_id == created.run.id)
                    .order_by(JobEvent.sequence)
                )
            ).scalars()
        )
        jobs = await session.scalar(
            select(func.count())
            .select_from(BackgroundTask)
            .where(BackgroundTask.task_type == "chapter_workflow")
        )

    assert created.created is True
    assert duplicate.created is False
    assert duplicate.run.id == created.run.id
    assert duplicate.root_job.id == created.root_job.id
    assert created.run.id == created.root_job.stream_id
    assert created.root_job.payload["run_id"] == created.run.id
    assert created.root_job.payload_version == 1
    assert created.run.workflow_version == 1
    assert created.run.state_schema_version == 1
    assert created.run.node_key == "freeze_base_context"
    assert created.root_job.payload["runtime_input_hash"] == created.run.runtime_input_hash
    assert created.run.runtime_input_hash == stable_digest(
        created.root_job.payload["runtime_inputs"]
    )
    restored_context = ChapterContext.model_validate(created.run.context_snapshot)
    assert restored_context.input_hash == created.run.context_hash
    assert restored_context.rag.fallback == ContextFallback.DISABLED
    assert created.root_job.payload["runtime_inputs"]["flow_config"]["enable_rag"] is True
    assert created.root_job.payload["runtime_inputs"]["retrieval_inputs"] == {
        "schema_version": 1,
        "enabled": True,
        "mode": "simple",
        "query_text": "第一章 开端 保持克制",
        "pov_character": None,
    }
    assert [event.event_type for event in events] == ["job.queued", "workflow.started"]
    assert events[1].payload["workflow"]["run_id"] == created.run.id
    assert jobs == 1

    drifted_payload = dict(created.root_job.payload)
    drifted_payload["context_hash"] = "f" * 64
    created.root_job.payload = drifted_payload
    with pytest.raises(ValueError, match="冻结身份不一致"):
        service.job_service.assert_workflow_root_identity(
            job=created.root_job,
            run=created.run,
        )

    nested_drift = dict(created.root_job.payload)
    nested_drift["context_hash"] = created.run.context_hash
    nested_drift["runtime_inputs"] = {
        **nested_drift["runtime_inputs"],
        "chapter_number": 2,
    }
    nested_drift["runtime_input_hash"] = stable_digest(nested_drift["runtime_inputs"])
    with pytest.raises(ValueError, match="runtime input 身份"):
        ChapterWorkflowJobPayload.model_validate(nested_drift)


@pytest.mark.asyncio(loop_scope="session")
async def test_start_freezes_configured_version_count_and_preserves_explicit_override(isolated_pg):
    async with isolated_pg.session_factory() as session:
        await _seed_project(session, user_id=4106, project_id="workflow-version-default")
        await _seed_project(session, user_id=4107, project_id="workflow-version-explicit")
        config = SystemConfig(
            key="writer.chapter_versions",
            value="2",
            description="章节候选版本数量",
        )
        session.add(config)
        await session.commit()

        service = ChapterWorkflowStartService(session)
        configured = await service.start(
            user_id=4106,
            project_id="workflow-version-default",
            chapter_number=1,
            idempotency_key="workflow-version-default",
        )
        config.value = "1"
        await session.commit()
        replay = await service.start(
            user_id=4106,
            project_id="workflow-version-default",
            chapter_number=1,
            idempotency_key="workflow-version-default",
        )
        explicit = await service.start(
            user_id=4107,
            project_id="workflow-version-explicit",
            chapter_number=1,
            flow_config={"versions": 1},
        )

    assert configured.root_job.payload["runtime_inputs"]["flow_config"]["versions"] == 2
    assert replay.created is False
    assert replay.root_job.payload["runtime_inputs"]["flow_config"]["versions"] == 2
    assert explicit.root_job.payload["runtime_inputs"]["flow_config"]["versions"] == 1


@pytest.mark.asyncio(loop_scope="session")
async def test_start_freezes_word_count_and_expands_ultimate_preset(isolated_pg):
    async with isolated_pg.session_factory() as session:
        await _seed_project(session, user_id=4108, project_id="workflow-ultimate")
        session.add(
            SystemConfig(
                key="writer.chapter_word_limit",
                value="4000",
                description="章节目标字数",
            )
        )
        await session.commit()

        started = await ChapterWorkflowStartService(session).start(
            user_id=4108,
            project_id="workflow-ultimate",
            chapter_number=1,
            flow_config={"preset": "ultimate"},
        )

    runtime_inputs = started.root_job.payload["runtime_inputs"]
    assert runtime_inputs["target_word_count"] == 4000
    assert runtime_inputs["minimum_word_count"] == 3200
    assert runtime_inputs["maximum_word_count"] == 4400
    assert started.root_job.payload["optional_stages"] == {
        "enhance_content": True,
        "repair_consistency": True,
        "optimize_style": True,
        "enrich_content": True,
    }


@pytest.mark.asyncio(loop_scope="session")
async def test_start_rejects_blank_idempotency_key(isolated_pg):
    async with isolated_pg.session_factory() as session:
        await _seed_project(session, user_id=4105, project_id="workflow-blank-key")
        with pytest.raises(ValueError, match="idempotency_key 不能为空"):
            await ChapterWorkflowStartService(session).start(
                user_id=4105,
                project_id="workflow-blank-key",
                chapter_number=1,
                idempotency_key="",
            )

    async with isolated_pg.session_factory() as session:
        runs = await session.scalar(select(func.count()).select_from(ChapterWorkflowRun))
        jobs = await session.scalar(
            select(func.count())
            .select_from(BackgroundTask)
            .where(BackgroundTask.task_type == "chapter_workflow")
        )
    assert (runs, jobs) == (0, 0)


@pytest.mark.asyncio(loop_scope="session")
async def test_concurrent_start_returns_one_durable_identity(isolated_pg):
    session_factory = isolated_pg.session_factory
    async with session_factory() as session:
        await _seed_project(session, user_id=4102, project_id="workflow-race-project")

    release = asyncio.Event()
    ready = 0
    backend_pids: set[int] = set()

    async def start_one(note: str):
        nonlocal ready
        async with session_factory() as session:
            backend_pid = await session.scalar(select(func.pg_backend_pid()))
            assert backend_pid is not None
            backend_pids.add(backend_pid)
            ready += 1
            if ready == 2:
                release.set()
            await release.wait()
            return await ChapterWorkflowStartService(session).start(
                user_id=4102,
                project_id="workflow-race-project",
                chapter_number=1,
                writing_notes=note,
            )

    first, second = await asyncio.wait_for(
        asyncio.gather(start_one("A"), start_one("B")),
        timeout=10,
    )

    async with session_factory() as session:
        counts = {
            "chapters": await session.scalar(select(func.count()).select_from(Chapter)),
            "runs": await session.scalar(select(func.count()).select_from(ChapterWorkflowRun)),
            "jobs": await session.scalar(
                select(func.count())
                .select_from(BackgroundTask)
                .where(BackgroundTask.task_type == "chapter_workflow")
            ),
            "events": await session.scalar(select(func.count()).select_from(JobEvent)),
        }

    assert first.run.id == second.run.id
    assert first.root_job.id == second.root_job.id
    assert sorted([first.created, second.created]) == [False, True]
    assert len(backend_pids) == 2
    assert counts == {"chapters": 1, "runs": 1, "jobs": 1, "events": 2}


@pytest.mark.asyncio(loop_scope="session")
async def test_start_failure_rolls_back_root_job_run_and_events(isolated_pg, monkeypatch):
    session_factory = isolated_pg.session_factory
    async with session_factory() as session:
        await _seed_project(session, user_id=4103, project_id="workflow-rollback-project")
        service = ChapterWorkflowStartService(session)

        async def fail_started_event(**_kwargs):
            raise RuntimeError("injected start event failure")

        monkeypatch.setattr(
            service.job_service,
            "append_workflow_started_in_transaction",
            fail_started_event,
        )
        with pytest.raises(RuntimeError, match="injected start event failure"):
            await service.start(
                user_id=4103,
                project_id="workflow-rollback-project",
                chapter_number=1,
            )

    async with session_factory() as session:
        runs = await session.scalar(select(func.count()).select_from(ChapterWorkflowRun))
        jobs = await session.scalar(
            select(func.count())
            .select_from(BackgroundTask)
            .where(BackgroundTask.task_type == "chapter_workflow")
        )
        events = await session.scalar(select(func.count()).select_from(JobEvent))

    assert (runs, jobs, events) == (0, 0, 0)


@pytest.mark.asyncio(loop_scope="session")
async def test_start_rejects_unsupported_retrieval_mode_at_typed_freeze(isolated_pg):
    async with isolated_pg.session_factory() as session:
        await _seed_project(session, user_id=4104, project_id="workflow-rag-mode")
        with pytest.raises(ValidationError, match="mode"):
            await ChapterWorkflowStartService(session).start(
                user_id=4104,
                project_id="workflow-rag-mode",
                chapter_number=1,
                flow_config={"rag_mode": "unsupported"},
            )

    async with isolated_pg.session_factory() as session:
        runs = await session.scalar(select(func.count()).select_from(ChapterWorkflowRun))
        jobs = await session.scalar(
            select(func.count())
            .select_from(BackgroundTask)
            .where(BackgroundTask.task_type == "chapter_workflow")
        )
    assert (runs, jobs) == (0, 0)
