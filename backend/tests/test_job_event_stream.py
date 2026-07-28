import asyncio
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, select, update

from app.models.background_task import BackgroundTask
from app.models.job import JobEvent
from app.models.novel import NovelProject
from app.models.user import User
from app.schemas.task import BackgroundTaskResponse
from app.services.job_service import (
    EventCursorExpiredError,
    JobService,
    JobStreamNotFoundError,
    _utc_now,
)


@pytest.mark.asyncio(loop_scope="session")
async def test_snapshot_cursor_resumes_without_cross_user_events(db_session_factory):
    async with db_session_factory() as session:
        session.add_all(
            [
                User(id=21, username="stream-writer", hashed_password="secret"),
                User(id=22, username="other-writer", hashed_password="secret"),
            ]
        )
        await session.commit()
        service = JobService(session)
        first = await service.enqueue_job(
            user_id=21,
            job_type="stream-test",
            title="快照内任务",
            payload={"prompt": "不应进入事件流"},
            idempotency_key="stream-first",
        )

        snapshot = await service.get_snapshot(user_id=21, limit=20)

        await service.enqueue_job(
            user_id=22,
            job_type="stream-test",
            title="其他用户任务",
            idempotency_key="stream-other",
        )
        second = await service.enqueue_job(
            user_id=21,
            job_type="stream-test",
            title="快照后任务",
            idempotency_key="stream-second",
        )
        resumed = await service.list_events(
            user_id=21,
            after_cursor=snapshot.resume_cursor,
        )

        assert [job.id for job in snapshot.jobs] == [first.id]
        assert snapshot.snapshot_revision == f"cursor:{snapshot.resume_cursor}"
        assert [(event.job_id, event.event_type) for event in resumed] == [
            (second.id, "job.queued"),
        ]
        assert resumed[0].cursor > snapshot.resume_cursor
        task_projection = resumed[0].payload["task"]
        assert "payload" not in task_projection
        assert "result" not in task_projection


@pytest.mark.asyncio(loop_scope="session")
async def test_empty_snapshot_returns_current_user_cursor(db_session_factory):
    async with db_session_factory() as session:
        session.add_all(
            [
                User(id=23, username="empty-stream", hashed_password="secret"),
                User(id=24, username="active-stream", hashed_password="secret"),
            ]
        )
        await session.commit()
        service = JobService(session)
        await service.enqueue_job(
            user_id=24,
            job_type="stream-test",
            title="其他用户任务",
            idempotency_key="other-user-only",
        )

        snapshot = await service.get_snapshot(user_id=23, limit=20)

        assert snapshot.jobs == []
        assert snapshot.resume_cursor == 0
        assert snapshot.snapshot_revision == "cursor:0"


@pytest.mark.asyncio(loop_scope="session")
async def test_retention_cleanup_requires_snapshot_reset_and_preserves_resume_cursor(
    db_session_factory,
):
    async with db_session_factory() as session:
        session.add(User(id=25, username="retention-stream", hashed_password="secret"))
        await session.commit()
        service = JobService(session)
        first = await service.enqueue_job(
            user_id=25,
            job_type="stream-test",
            title="即将清理的任务事件",
            idempotency_key="retention-first",
        )
        before_cleanup = await service.get_snapshot(user_id=25, limit=20)

        cleanup = await service.cleanup_events(before=_utc_now() + timedelta(days=1))

        assert cleanup.deleted_events == 1
        assert cleanup.affected_user_ids == (25,)
        with pytest.raises(EventCursorExpiredError) as exc_info:
            await service.list_events(user_id=25, after_cursor=0)
        assert exc_info.value.retained_through_cursor == before_cleanup.resume_cursor

        reset_snapshot = await service.get_snapshot(user_id=25, limit=20)
        assert [job.id for job in reset_snapshot.jobs] == [first.id]
        assert reset_snapshot.resume_cursor == before_cleanup.resume_cursor
        assert reset_snapshot.snapshot_revision == f"cursor:{before_cleanup.resume_cursor}"

        second = await service.enqueue_job(
            user_id=25,
            job_type="stream-test",
            title="清理后的任务事件",
            idempotency_key="retention-second",
        )
        resumed = await service.list_events(
            user_id=25,
            after_cursor=reset_snapshot.resume_cursor,
        )
        assert [(event.job_id, event.event_type) for event in resumed] == [
            (second.id, "job.queued"),
        ]


@pytest.mark.asyncio(loop_scope="session")
async def test_concurrent_workflow_jobs_share_sequence_and_resume_without_gap(
    isolated_pg,
):
    session_factory = isolated_pg.session_factory
    async with session_factory() as session:
        user = User(
            username=f"workflow-stream-{uuid4().hex}",
            hashed_password="secret",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user_id = user.id

    async def enqueue(job_type: str, key: str):
        async with session_factory() as session:
            return await JobService(session).enqueue_job(
                user_id=user_id,
                job_type=job_type,
                title=job_type,
                idempotency_key=key,
                stream_type="workflow",
                stream_id="workflow-concurrent-run",
            )

    try:
        root, child = await asyncio.gather(
            enqueue("workflow-root", "workflow-root-key"),
            enqueue("workflow-child", "workflow-child-key"),
        )

        async with session_factory() as session:
            service = JobService(session)
            snapshot = await service.get_stream_snapshot(
                user_id=user_id,
                stream_type="workflow",
                stream_id="workflow-concurrent-run",
            )
            events = await service.list_stream_events(
                user_id=user_id,
                stream_type="workflow",
                stream_id="workflow-concurrent-run",
                after_cursor=0,
            )

        assert {job.id for job in snapshot.jobs} == {root.id, child.id}
        assert [event.sequence for event in events] == [1, 2]
        assert len({event.cursor for event in events}) == 2
        assert snapshot.resume_cursor == events[-1].cursor
        assert snapshot.stream_type == "workflow"
        assert snapshot.stream_id == "workflow-concurrent-run"
        assert snapshot.snapshot_revision == (
            "stream:workflow:workflow-concurrent-run:"
            f"sequence:2:cursor:{snapshot.resume_cursor}"
        )

        projection = await enqueue("workflow-projection", "workflow-projection-key")
        async with session_factory() as session:
            resumed = await JobService(session).list_stream_events(
                user_id=user_id,
                stream_type="workflow",
                stream_id="workflow-concurrent-run",
                after_cursor=snapshot.resume_cursor,
            )
        assert [(event.job_id, event.sequence) for event in resumed] == [
            (projection.id, 3),
        ]
    finally:
        async with session_factory() as session:
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()


@pytest.mark.asyncio(loop_scope="session")
async def test_workflow_stream_authorization_and_idempotency_identity(
    db_session_factory,
):
    async with db_session_factory() as session:
        session.add_all(
            [
                User(id=26, username="workflow-owner", hashed_password="secret"),
                User(id=27, username="workflow-stranger", hashed_password="secret"),
                NovelProject(
                    id="workflow-owned-project",
                    user_id=26,
                    title="授权项目",
                    initial_prompt="",
                ),
            ]
        )
        await session.commit()
        service = JobService(session)

        first = await service.enqueue_job(
            user_id=26,
            project_id="workflow-owned-project",
            job_type="workflow-root",
            title="根任务",
            payload={"run": 1},
            idempotency_key="workflow-idempotency",
            stream_type="workflow",
            stream_id="workflow-authorized-run",
        )
        duplicate = await service.enqueue_job(
            user_id=26,
            project_id="workflow-owned-project",
            job_type="workflow-root",
            title="根任务",
            payload={"run": 1},
            idempotency_key="workflow-idempotency",
            stream_type="workflow",
            stream_id="workflow-authorized-run",
        )

        assert duplicate.id == first.id
        with pytest.raises(ValueError, match="idempotency_key"):
            await service.enqueue_job(
                user_id=26,
                project_id="workflow-owned-project",
                job_type="workflow-root",
                title="根任务",
                payload={"run": 1},
                idempotency_key="workflow-idempotency",
                stream_type="workflow",
                stream_id="workflow-other-run",
            )
        with pytest.raises(ValueError, match="idempotency_key"):
            await service.enqueue_job(
                user_id=26,
                project_id="workflow-owned-project",
                job_type="workflow-root",
                title="根任务",
                payload={"run": 1},
                idempotency_key="workflow-idempotency",
            )
        with pytest.raises(ValueError, match="项目不存在"):
            await service.enqueue_job(
                user_id=27,
                project_id="workflow-owned-project",
                job_type="workflow-root",
                title="越权任务",
                stream_type="workflow",
                stream_id="workflow-stranger-run",
            )

        for operation in (
            service.get_stream_snapshot(
                user_id=27,
                stream_type="workflow",
                stream_id="workflow-authorized-run",
            ),
            service.list_stream_events(
                user_id=27,
                stream_type="workflow",
                stream_id="workflow-authorized-run",
                after_cursor=0,
            ),
        ):
            with pytest.raises(JobStreamNotFoundError):
                await operation

        events = await service.list_stream_events(
            user_id=26,
            stream_type="workflow",
            stream_id="workflow-authorized-run",
            after_cursor=0,
        )
        assert [(event.job_id, event.sequence) for event in events] == [(first.id, 1)]


@pytest.mark.asyncio(loop_scope="session")
async def test_stream_retention_watermarks_are_isolated(db_session_factory):
    async with db_session_factory() as session:
        session.add(User(id=28, username="stream-retention-owner", hashed_password="secret"))
        await session.commit()
        service = JobService(session)
        await service.enqueue_job(
            user_id=28,
            job_type="workflow-a",
            title="将被清理",
            stream_type="workflow",
            stream_id="retention-stream-a",
        )
        await service.enqueue_job(
            user_id=28,
            job_type="workflow-b",
            title="继续保留",
            stream_type="workflow",
            stream_id="retention-stream-b",
        )
        stream_a_event = await session.scalar(
            select(JobEvent).where(JobEvent.stream_id == "retention-stream-a")
        )
        stream_b_event = await session.scalar(
            select(JobEvent).where(JobEvent.stream_id == "retention-stream-b")
        )
        assert stream_a_event is not None
        assert stream_b_event is not None
        now = _utc_now()
        await session.execute(
            update(JobEvent)
            .where(JobEvent.stream_id == "retention-stream-a")
            .values(created_at=now - timedelta(days=2))
        )
        await session.commit()
        cleanup = await service.cleanup_events(before=now - timedelta(days=1))

        assert cleanup.deleted_events == 1

    async with db_session_factory() as session:
        service = JobService(session)
        with pytest.raises(EventCursorExpiredError) as exc_info:
            await service.list_stream_events(
                user_id=28,
                stream_type="workflow",
                stream_id="retention-stream-a",
                after_cursor=0,
            )
        assert exc_info.value.retained_through_cursor == stream_a_event.cursor

        stream_b_events = await service.list_stream_events(
            user_id=28,
            stream_type="workflow",
            stream_id="retention-stream-b",
            after_cursor=0,
        )
        stream_b_snapshot = await service.get_stream_snapshot(
            user_id=28,
            stream_type="workflow",
            stream_id="retention-stream-b",
        )
        assert [event.cursor for event in stream_b_events] == [stream_b_event.cursor]
        assert stream_b_snapshot.resume_cursor == stream_b_event.cursor


@pytest.mark.asyncio(loop_scope="session")
async def test_deleting_job_keeps_append_only_event(db_session_factory):
    async with db_session_factory() as session:
        session.add(User(id=29, username="deleted-job-event-owner", hashed_password="secret"))
        await session.commit()
        service = JobService(session)
        job = await service.enqueue_job(
            user_id=29,
            job_type="delete-job",
            title="删除 current row",
        )
        await session.execute(delete(BackgroundTask).where(BackgroundTask.id == job.id))
        await session.commit()

    async with db_session_factory() as session:
        service = JobService(session)
        events = await service.list_stream_events(
            user_id=29,
            stream_type="job",
            stream_id=job.id,
            after_cursor=0,
        )
        snapshot = await service.get_stream_snapshot(
            user_id=29,
            stream_type="job",
            stream_id=job.id,
        )
        assert len(events) == 1
        assert events[0].job_id is None
        assert events[0].payload["task"]["id"] == job.id
        assert snapshot.jobs == []
        assert snapshot.resume_cursor == events[0].cursor


def test_internal_job_statuses_preserve_four_state_background_task_contract():
    assert BackgroundTaskResponse.public_status("queued") == "queued"
    assert BackgroundTaskResponse.public_status("retry_wait") == "queued"
    assert BackgroundTaskResponse.public_status("running") == "running"
    assert BackgroundTaskResponse.public_status("succeeded") == "succeeded"
    assert BackgroundTaskResponse.public_status("dead_letter") == "failed"
    assert BackgroundTaskResponse.public_status("needs_attention") == "failed"
    assert BackgroundTaskResponse.public_status("cancelled") == "failed"
