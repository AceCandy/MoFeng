import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, func, select

from app.models import (
    Chapter,
    ChapterGenerationTrace,
    ChapterGenerationTraceProjectionCheckpoint,
    ChapterOutline,
    ChapterWorkflowRun,
    JobEvent,
    NovelProject,
)
from app.models.user import User
from app.repositories.chapter_generation_trace_projection_repository import (
    CHAPTER_GENERATION_TRACE_PROJECTOR_NAME,
)
from app.services.chapter_generation_trace_projector import (
    project_chapter_generation_traces,
    rebuild_chapter_generation_traces,
)
from app.services.chapter_generation_trace_service import ChapterGenerationTraceService
from app.services.chapter_workflow_start import ChapterWorkflowStartService
from app.services.job_service import JobService


async def _start_workflow(session, *, user_id: int, project_id: str):
    session.add(User(id=user_id, username=f"trace-projector-{user_id}", hashed_password="secret"))
    session.add(
        NovelProject(
            id=project_id,
            user_id=user_id,
            title="Trace projector",
            initial_prompt="private initial prompt",
        )
    )
    session.add(
        ChapterOutline(
            project_id=project_id,
            chapter_number=1,
            title="第一章",
            summary="开端",
        )
    )
    await session.commit()
    started = await ChapterWorkflowStartService(session).start(
        user_id=user_id,
        project_id=project_id,
        chapter_number=1,
        writing_notes="private writing notes",
    )
    await _seed_projector_checkpoint(session)
    return started


async def _seed_projector_checkpoint(session) -> None:
    session.add(
        ChapterGenerationTraceProjectionCheckpoint(
            projector_name=CHAPTER_GENERATION_TRACE_PROJECTOR_NAME,
            last_event_cursor=0,
        )
    )
    await session.commit()


@pytest.mark.asyncio(loop_scope="session")
async def test_projector_is_atomic_idempotent_private_and_rebuildable(isolated_pg):
    session_factory = isolated_pg.session_factory
    async with session_factory() as session:
        started = await _start_workflow(
            session,
            user_id=4701,
            project_id="workflow-trace-projector",
        )
        snapshot_before_projection = await JobService(session).get_chapter_workflow_snapshot(
            started.run.id,
            user_id=4701,
        )
        chapter_status_before = await session.scalar(
            select(Chapter.status).where(Chapter.project_id == started.run.project_id)
        )
        session.add(
            JobEvent(
                job_id=started.root_job.id,
                user_id=4701,
                project_id=started.run.project_id,
                stream_type="workflow",
                stream_id=started.run.id,
                sequence=3,
                event_type="workflow.phase_changed",
                payload={
                    "task": {
                        "payload": {"prompt": "must-not-project"},
                        "result": {"content": "must-not-project"},
                    },
                    "workflow": {
                        "run_id": started.run.id,
                        "row_revision": 1,
                        "node_key": "generate_candidates",
                        "status": "running",
                        "checkpoint_id": "checkpoint-public-id",
                        "progress": 35,
                        "private_prompt": "must-not-project",
                        "content": "must-not-project",
                        "token": "must-not-project",
                    },
                },
                created_at=datetime.now(timezone.utc),
            )
        )
        session.add(
            JobEvent(
                job_id=started.root_job.id,
                user_id=4701,
                project_id=started.run.project_id,
                stream_type="workflow",
                stream_id=started.run.id,
                sequence=4,
                event_type="workflow.phase_changed",
                payload={
                    "task": {},
                    "workflow": {
                        "run_id": started.run.id,
                        "node_key": ["invalid", "node"],
                        "status": "running",
                    },
                },
                created_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()

    assert snapshot_before_projection.run_id == started.run.id
    assert snapshot_before_projection.status == "queued"

    async with session_factory() as session:
        rolled_back = await project_chapter_generation_traces(session)
        assert rolled_back.projected_traces == 3
        await session.rollback()

    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(ChapterGenerationTrace)) == 0
        checkpoint_cursor = await session.scalar(
            select(ChapterGenerationTraceProjectionCheckpoint.last_event_cursor)
        )
        assert checkpoint_cursor == 0

        committed = await project_chapter_generation_traces(session)
        await session.commit()
        replay = await project_chapter_generation_traces(session)
        await session.commit()
        traces = list(
            (
                await session.execute(
                    select(ChapterGenerationTrace)
                    .where(ChapterGenerationTrace.source_run_id == started.run.id)
                    .order_by(ChapterGenerationTrace.source_event_cursor)
                )
            ).scalars()
        )

    assert committed.projected_traces == 3
    assert replay.projected_traces == 0
    assert [trace.node_key for trace in traces] == [
        "freeze_context",
        "generate_candidates",
        "workflow",
    ]
    assert all(
        trace.system_prompt is None
        and trace.user_prompt is None
        and trace.raw_response is None
        and trace.cleaned_output is None
        for trace in traces
    )
    serialized_metadata = json.dumps(
        [trace.metadata for trace in traces],
        ensure_ascii=False,
    )
    assert "must-not-project" not in serialized_metadata
    assert set(traces[1].metadata) == {
        "projection_schema_version",
        "source",
        "event_cursor",
        "event_sequence",
        "event_type",
        "run_id",
        "uses_llm",
        "row_revision",
        "progress",
        "checkpoint_id",
    }
    assert set(traces[-1].metadata) == {
        "projection_schema_version",
        "source",
        "event_cursor",
        "event_sequence",
        "event_type",
        "run_id",
        "uses_llm",
    }

    async with session_factory() as session:
        await session.execute(
            delete(ChapterGenerationTrace).where(
                ChapterGenerationTrace.source_run_id == started.run.id
            )
        )
        await session.commit()
        snapshot_after_delete = await JobService(session).get_chapter_workflow_snapshot(
            started.run.id,
            user_id=4701,
        )
        rebuilt = await rebuild_chapter_generation_traces(
            session,
            run_id=started.run.id,
        )
        await session.commit()
        duplicate_rebuild = await rebuild_chapter_generation_traces(
            session,
            run_id=started.run.id,
        )
        await session.commit()
        rebuilt_count = await session.scalar(
            select(func.count())
            .select_from(ChapterGenerationTrace)
            .where(ChapterGenerationTrace.source_run_id == started.run.id)
        )

    assert snapshot_after_delete.status == snapshot_before_projection.status
    assert rebuilt == 3
    assert duplicate_rebuild == 0
    assert rebuilt_count == 3

    async with session_factory() as session:
        legacy = await ChapterGenerationTraceService(session).record_success(
            project_id=started.run.project_id,
            chapter_number=1,
            node_key="draft_generation",
            node_label="生成正文",
            user_prompt="legacy prompt",
            raw_response="legacy response",
        )
        persisted_run = await session.get(ChapterWorkflowRun, started.run.id)
        chapter = await session.scalar(
            select(Chapter).where(Chapter.project_id == started.run.project_id)
        )

    assert legacy.source_run_id is None
    assert legacy.source_event_cursor is None
    assert persisted_run is not None and persisted_run.status == "queued"
    assert chapter is not None and chapter.status == chapter_status_before


@pytest.mark.asyncio(loop_scope="session")
async def test_retention_cannot_pass_a_paused_projector(isolated_pg):
    session_factory = isolated_pg.session_factory
    async with session_factory() as session:
        session.add(User(id=4702, username="trace-retention", hashed_password="secret"))
        await session.commit()
        await _seed_projector_checkpoint(session)
        job_service = JobService(session)
        await job_service.enqueue_job(
            user_id=4702,
            job_type="trace-retention",
            title="retention guard",
        )

        paused_cleanup = await job_service.cleanup_events(
            before=datetime.now(timezone.utc) + timedelta(days=1)
        )
        remaining_while_paused = await session.scalar(select(func.count()).select_from(JobEvent))

        batch = await project_chapter_generation_traces(session)
        await session.commit()
        resumed_cleanup = await job_service.cleanup_events(
            before=datetime.now(timezone.utc) + timedelta(days=1)
        )

    assert paused_cleanup.deleted_events == 0
    assert remaining_while_paused == 1
    assert batch.scanned_events == 1
    assert batch.projected_traces == 0
    assert resumed_cleanup.deleted_events == 1


@pytest.mark.asyncio(loop_scope="session")
async def test_concurrent_projector_skips_the_locked_checkpoint(isolated_pg):
    session_factory = isolated_pg.session_factory
    async with session_factory() as session:
        started = await _start_workflow(
            session,
            user_id=4703,
            project_id="workflow-trace-concurrency",
        )
        await project_chapter_generation_traces(session)
        await session.commit()
        session.add(
            JobEvent(
                job_id=started.root_job.id,
                user_id=4703,
                project_id=started.run.project_id,
                stream_type="workflow",
                stream_id=started.run.id,
                sequence=3,
                event_type="workflow.phase_changed",
                payload={
                    "task": {},
                    "workflow": {
                        "run_id": started.run.id,
                        "row_revision": 1,
                        "node_key": "plan_and_direct",
                        "status": "running",
                        "checkpoint_id": "concurrent-checkpoint",
                        "progress": 15,
                    },
                },
                created_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()

    async with session_factory() as lock_holder, session_factory() as contender:
        first = await project_chapter_generation_traces(lock_holder)
        second = await project_chapter_generation_traces(contender)
        await lock_holder.commit()
        await contender.commit()

    async with session_factory() as session:
        projected = await session.scalar(
            select(func.count())
            .select_from(ChapterGenerationTrace)
            .where(
                ChapterGenerationTrace.source_run_id == started.run.id,
                ChapterGenerationTrace.node_key == "plan_and_direct",
            )
        )

    assert first.projected_traces == 1
    assert second.scanned_events == 0
    assert second.projected_traces == 0
    assert projected == 1
