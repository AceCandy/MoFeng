# AIMETA P=章节工作流HTTP契约测试|R=start_snapshot_command_授权与冲突响应|NR=不执行worker或legacy适配|E=test_*|X=internal|A=integration_test|D=pytest,httpx,postgresql|S=test|RD=./README.ai
import json
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import httpx
import pytest
from pydantic import ValidationError
from sqlalchemy import update

from app.core.dependencies import get_current_user
from app.db.session import get_session
from app.main import app
from app.models import ChapterOutline, ChapterWorkflowRun, NovelProject
from app.models.background_task import BackgroundTask
from app.models.user import User
from app.schemas.chapter_workflow import ChapterWorkflowSnapshot
from app.schemas.user import UserInDB


async def _seed_users_and_project(session) -> None:
    session.add_all(
        [
            User(id=6101, username="workflow-http-owner", hashed_password="secret"),
            User(id=6102, username="workflow-http-foreign", hashed_password="secret"),
            NovelProject(
                id="workflow-http-project",
                user_id=6101,
                title="Workflow HTTP",
                initial_prompt="test",
            ),
            ChapterOutline(
                project_id="workflow-http-project",
                chapter_number=1,
                title="第一章",
                summary="开端",
                goals="建立冲突",
                highlights=[],
                character_states={},
            ),
        ]
    )
    await session.commit()


@asynccontextmanager
async def _client(isolated_pg, *, user_id: int):
    async def override_session():
        async with isolated_pg.session_factory() as session:
            yield session

    async def override_user() -> UserInDB:
        username = "workflow-http-owner" if user_id == 6101 else "workflow-http-foreign"
        return UserInDB(
            id=user_id,
            username=username,
            hashed_password="secret",
            is_admin=False,
            is_active=True,
        )

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_user] = override_user
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def _start_payload() -> dict[str, object]:
    return {
        "project_id": "workflow-http-project",
        "chapter_number": 1,
        "writing_notes": "保持克制",
        "flow_config": {"preset": "basic", "enable_rag": False},
    }


def _assert_private_workflow_data_absent(payload: object) -> None:
    serialized = json.dumps(payload, ensure_ascii=False)
    for forbidden in (
        "context_snapshot",
        "runtime_inputs",
        "writing_notes",
        "private provider input",
        '"payload"',
        '"result_payload"',
    ):
        assert forbidden not in serialized


def _snapshot_payload() -> dict[str, object]:
    return {
        "run_id": str(uuid4()),
        "root_job_id": str(uuid4()),
        "project_id": "workflow-http-project",
        "chapter_id": 1,
        "chapter_number": 1,
        "base_revision": 0,
        "current_chapter_revision": 0,
        "workflow_version": 1,
        "state_schema_version": 1,
        "context_schema_version": 1,
        "status": "queued",
        "root_job_status": "queued",
        "node_key": "freeze_context",
        "checkpoint_id": None,
        "progress": 0,
        "row_revision": 0,
        "is_active": True,
        "successor_run_id": None,
        "error_category": None,
        "public_error": None,
        "allowed_commands": ["cancel"],
        "retry_activity_key": None,
        "resume_cursor": 0,
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("workflow_version", 2),
        ("state_schema_version", 2),
        ("context_schema_version", 2),
        ("status", "unknown"),
        ("root_job_status", "unknown"),
        ("node_key", "unknown"),
    ],
)
def test_workflow_snapshot_rejects_unknown_contract_values(field: str, value: object):
    payload = _snapshot_payload()
    payload[field] = value

    with pytest.raises(ValidationError):
        ChapterWorkflowSnapshot.model_validate(payload)


def test_workflow_snapshot_requires_bounded_retry_activity_key():
    missing = _snapshot_payload()
    missing.pop("retry_activity_key")
    with pytest.raises(ValidationError):
        ChapterWorkflowSnapshot.model_validate(missing)

    invalid = _snapshot_payload()
    invalid["retry_activity_key"] = "x" * 129
    with pytest.raises(ValidationError):
        ChapterWorkflowSnapshot.model_validate(invalid)


@pytest.mark.asyncio(loop_scope="session")
async def test_start_and_duplicate_return_public_snapshot(isolated_pg):
    async with isolated_pg.session_factory() as session:
        await _seed_users_and_project(session)

    async with _client(isolated_pg, user_id=6101) as client:
        created = await client.post("/api/writer/chapter-workflows", json=_start_payload())
        duplicate = await client.post("/api/writer/chapter-workflows", json=_start_payload())

    assert created.status_code == 202
    assert duplicate.status_code == 202
    created_body = created.json()
    duplicate_body = duplicate.json()
    assert created_body["created"] is True
    assert duplicate_body["created"] is False
    assert duplicate_body["snapshot"] == created_body["snapshot"]
    assert created_body["snapshot"]["run_id"] != created_body["snapshot"]["root_job_id"]
    assert created_body["snapshot"]["project_id"] == "workflow-http-project"
    assert created_body["snapshot"]["allowed_commands"] == ["cancel"]
    assert created_body["events_url"].endswith(
        f"stream_type=workflow&stream_id={created_body['snapshot']['run_id']}"
    )
    _assert_private_workflow_data_absent(created_body)

    operation = app.openapi()["paths"]["/api/writer/chapter-workflows/{run_id}/commands"]["post"]
    conflict_schema = operation["responses"]["409"]["content"]["application/json"]["schema"]
    assert conflict_schema["$ref"].endswith("ChapterWorkflowCommandConflictResponse")


@pytest.mark.asyncio(loop_scope="session")
async def test_snapshot_missing_and_foreign_runs_are_identical_404(isolated_pg):
    async with isolated_pg.session_factory() as session:
        await _seed_users_and_project(session)

    async with _client(isolated_pg, user_id=6101) as client:
        created = await client.post("/api/writer/chapter-workflows", json=_start_payload())
        run_id = created.json()["snapshot"]["run_id"]
        missing_run_id = str(uuid4())
        missing = await client.get(f"/api/writer/chapter-workflows/{missing_run_id}")
        missing_command = await client.post(
            f"/api/writer/chapter-workflows/{missing_run_id}/commands",
            json={
                "command_id": str(uuid4()),
                "type": "cancel",
                "payload_version": 1,
                "payload": {},
                "expected_run_revision": 0,
                "expected_chapter_revision": 0,
                "expected_checkpoint_id": "missing-checkpoint",
            },
        )
        missing_project_payload = _start_payload()
        missing_project_payload["project_id"] = "missing-workflow-project"
        missing_project = await client.post(
            "/api/writer/chapter-workflows",
            json=missing_project_payload,
        )

    async with _client(isolated_pg, user_id=6102) as client:
        foreign = await client.get(f"/api/writer/chapter-workflows/{run_id}")
        foreign_command = await client.post(
            f"/api/writer/chapter-workflows/{run_id}/commands",
            json={
                "command_id": str(uuid4()),
                "type": "cancel",
                "payload_version": 1,
                "payload": {},
                "expected_run_revision": 0,
                "expected_chapter_revision": 0,
                "expected_checkpoint_id": "foreign-checkpoint",
            },
        )
        foreign_project = await client.post(
            "/api/writer/chapter-workflows",
            json=_start_payload(),
        )

    assert missing.status_code == foreign.status_code == 404
    assert missing.json() == foreign.json() == {"detail": "章节工作流不存在"}
    assert missing_command.status_code == foreign_command.status_code == 404
    assert missing_command.json() == foreign_command.json() == {"detail": "章节工作流不存在"}
    assert missing_project.status_code == foreign_project.status_code == 404
    assert missing_project.json() == foreign_project.json() == {"detail": "项目不存在"}


@pytest.mark.asyncio(loop_scope="session")
async def test_current_lookup_uses_full_order_and_excludes_successor_predecessor(
    isolated_pg,
    monkeypatch,
):
    async with isolated_pg.session_factory() as session:
        await _seed_users_and_project(session)

    first_run_id = "22222222-2222-4222-8222-222222222222"
    second_run_id = "11111111-1111-4111-8111-111111111111"
    run_ids = iter((UUID(first_run_id), UUID(second_run_id)))
    monkeypatch.setattr(
        "app.services.chapter_workflow_start.uuid4",
        lambda: next(run_ids),
    )
    async with _client(isolated_pg, user_id=6101) as client:
        first_response = await client.post(
            "/api/writer/chapter-workflows",
            json=_start_payload(),
        )
    first_id = first_response.json()["snapshot"]["run_id"]
    assert first_id == first_run_id

    async with isolated_pg.session_factory() as session:
        first = await session.get(ChapterWorkflowRun, first_id)
        assert first is not None
        first_job = await session.get(BackgroundTask, first.root_job_id)
        assert first_job is not None
        first.is_active = False
        first.status = "failed"
        first.node_key = "failed"
        first_job.status = "failed"
        await session.commit()

    async with _client(isolated_pg, user_id=6101) as client:
        second_response = await client.post(
            "/api/writer/chapter-workflows",
            json=_start_payload(),
        )
    second_id = second_response.json()["snapshot"]["run_id"]
    assert second_id == second_run_id

    async with isolated_pg.session_factory() as session:
        first = await session.get(ChapterWorkflowRun, first_id)
        second = await session.get(ChapterWorkflowRun, second_id)
        assert first is not None and second is not None
        first_job = await session.get(BackgroundTask, first.root_job_id)
        assert first_job is not None

        first.is_active = True
        first.status = "queued"
        first.node_key = "freeze_context"
        first.base_revision = 2
        first.successor_run_id = None
        first_job.status = "queued"
        first_job.payload = {**first_job.payload, "base_revision": 2}
        await session.commit()

    async with _client(isolated_pg, user_id=6101) as client:
        multiple_active_current = await client.get(
            "/api/writer/chapter-workflows/current",
            params={"project_id": "workflow-http-project", "chapter_number": 1},
        )

    assert multiple_active_current.status_code == 200
    assert multiple_active_current.json()["snapshot"]["run_id"] == first_id
    assert multiple_active_current.json()["events_url"].endswith(
        f"stream_type=workflow&stream_id={first_id}"
    )

    async with isolated_pg.session_factory() as session:
        first = await session.get(ChapterWorkflowRun, first_id)
        assert first is not None
        first_job = await session.get(BackgroundTask, first.root_job_id)
        assert first_job is not None
        first.is_active = False
        first.status = "failed"
        first.node_key = "failed"
        first.base_revision = 3
        first_job.status = "failed"
        await session.commit()

    async with _client(isolated_pg, user_id=6101) as client:
        active_over_terminal = await client.get(
            "/api/writer/chapter-workflows/current",
            params={"project_id": "workflow-http-project", "chapter_number": 1},
        )
        missing_current = await client.get(
            "/api/writer/chapter-workflows/current",
            params={"project_id": "missing-workflow-project", "chapter_number": 1},
        )
    async with _client(isolated_pg, user_id=6102) as client:
        foreign_current = await client.get(
            "/api/writer/chapter-workflows/current",
            params={"project_id": "workflow-http-project", "chapter_number": 1},
        )

    assert active_over_terminal.status_code == 200
    assert active_over_terminal.json()["snapshot"]["run_id"] == second_id
    assert missing_current.status_code == foreign_current.status_code == 200
    assert missing_current.json() is foreign_current.json() is None

    async with isolated_pg.session_factory() as session:
        first = await session.get(ChapterWorkflowRun, first_id)
        second = await session.get(ChapterWorkflowRun, second_id)
        assert first is not None and second is not None
        first_job = await session.get(BackgroundTask, first.root_job_id)
        second_job = await session.get(BackgroundTask, second.root_job_id)
        assert first_job is not None and second_job is not None

        first.is_active = False
        first.status = "failed"
        first.node_key = "failed"
        first.successor_run_id = None
        first_job.status = "failed"
        second.is_active = False
        second.status = "cancelled"
        second.node_key = "cancelled"
        second_job.status = "cancelled"

        earlier = datetime(2026, 1, 1, tzinfo=timezone.utc)
        later = earlier + timedelta(hours=1)
        await session.execute(
            update(ChapterWorkflowRun)
            .where(ChapterWorkflowRun.id == first_id)
            .values(base_revision=2, updated_at=earlier)
        )
        await session.execute(
            update(ChapterWorkflowRun)
            .where(ChapterWorkflowRun.id == second_id)
            .values(base_revision=1, updated_at=later)
        )
        await session.commit()

        async with _client(isolated_pg, user_id=6101) as client:

            async def current_run_id() -> str:
                response = await client.get(
                    "/api/writer/chapter-workflows/current",
                    params={
                        "project_id": "workflow-http-project",
                        "chapter_number": 1,
                    },
                )
                assert response.status_code == 200
                return response.json()["snapshot"]["run_id"]

            assert await current_run_id() == first_id

            await session.execute(
                update(ChapterWorkflowRun)
                .where(ChapterWorkflowRun.id == first_id)
                .values(base_revision=2, updated_at=later)
            )
            await session.execute(
                update(ChapterWorkflowRun)
                .where(ChapterWorkflowRun.id == second_id)
                .values(base_revision=2, updated_at=earlier)
            )
            await session.commit()
            assert await current_run_id() == first_id

            await session.execute(
                update(ChapterWorkflowRun)
                .where(ChapterWorkflowRun.id == first_id)
                .values(updated_at=later, created_at=earlier)
            )
            await session.execute(
                update(ChapterWorkflowRun)
                .where(ChapterWorkflowRun.id == second_id)
                .values(updated_at=later, created_at=later)
            )
            await session.commit()
            assert await current_run_id() == second_id

            await session.execute(
                update(ChapterWorkflowRun)
                .where(ChapterWorkflowRun.id == first_id)
                .values(updated_at=later, created_at=later)
            )
            await session.execute(
                update(ChapterWorkflowRun)
                .where(ChapterWorkflowRun.id == second_id)
                .values(updated_at=later, created_at=later)
            )
            await session.commit()
            assert await current_run_id() == first_id

            await session.execute(
                update(ChapterWorkflowRun)
                .where(ChapterWorkflowRun.id == first_id)
                .values(successor_run_id=second_id, updated_at=later)
            )
            await session.commit()
            assert await current_run_id() == second_id



@pytest.mark.asyncio(loop_scope="session")
async def test_stale_command_returns_409_with_complete_current_snapshot(isolated_pg):
    async with isolated_pg.session_factory() as session:
        await _seed_users_and_project(session)

    async with _client(isolated_pg, user_id=6101) as client:
        created = await client.post("/api/writer/chapter-workflows", json=_start_payload())
        run_id = created.json()["snapshot"]["run_id"]

    async with isolated_pg.session_factory() as session:
        run = await session.get(ChapterWorkflowRun, run_id)
        assert run is not None
        job = await session.get(BackgroundTask, run.root_job_id)
        assert job is not None
        run.status = "waiting_for_selection"
        run.node_key = "waiting_for_selection"
        run.checkpoint_id = "checkpoint-http"
        job.status = "waiting"
        await session.commit()

    async with _client(isolated_pg, user_id=6101) as client:
        current = await client.get(f"/api/writer/chapter-workflows/{run_id}")
        current_snapshot = current.json()
        stale = await client.post(
            f"/api/writer/chapter-workflows/{run_id}/commands",
            json={
                "command_id": str(uuid4()),
                "type": "select",
                "payload_version": 1,
                "payload": {"selected_version_id": 1},
                "expected_run_revision": current_snapshot["row_revision"] + 1,
                "expected_chapter_revision": current_snapshot["current_chapter_revision"],
                "expected_checkpoint_id": current_snapshot["checkpoint_id"],
            },
        )
        latest = await client.get(f"/api/writer/chapter-workflows/{run_id}")
        accepted_command_id = str(uuid4())
        accepted = await client.post(
            f"/api/writer/chapter-workflows/{run_id}/commands",
            json={
                "command_id": accepted_command_id,
                "type": "cancel",
                "payload_version": 1,
                "payload": {},
                "expected_run_revision": latest.json()["row_revision"],
                "expected_chapter_revision": latest.json()["current_chapter_revision"],
                "expected_checkpoint_id": latest.json()["checkpoint_id"],
            },
        )

    assert stale.status_code == 409
    assert stale.json() == {
        "detail": {
            "reason_code": "stale_run_revision",
            "current_snapshot": latest.json(),
        }
    }
    assert latest.json()["run_id"] == current_snapshot["run_id"]
    assert latest.json()["row_revision"] == current_snapshot["row_revision"]
    assert latest.json()["resume_cursor"] > current_snapshot["resume_cursor"]
    assert accepted.status_code == 202
    assert accepted.json()["command_id"] == accepted_command_id
    assert accepted.json()["type"] == "cancel"
    assert accepted.json()["status"] == "applied"
    assert accepted.json()["snapshot"]["status"] == "cancelled"
    _assert_private_workflow_data_absent(stale.json())
    _assert_private_workflow_data_absent(accepted.json())
