"""Versioned durable Chapter graph contracts."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from pydantic import ValidationError
from sqlalchemy.engine import make_url

from app.db.chapter_workflow_checkpointer import psycopg_dsn_from_sqlalchemy_url
from app.schemas.chapter_context import stable_digest
from app.schemas.chapter_workflow import (
    CHAPTER_WORKFLOW_NODE_KEYS_V1,
    CHAPTER_WORKFLOW_STATE_SCHEMA_VERSION_V1,
    CHAPTER_WORKFLOW_VERSION_V1,
    ChapterWorkflowStateV1,
)
from app.schemas.job import (
    ChapterWorkflowJobPayload,
    ChapterWorkflowRetrievalInputs,
    ChapterWorkflowRuntimeInputs,
)
from app.services.chapter_workflow_graph import (
    ChapterWorkflowGraphBindingsV1,
    build_chapter_workflow_graph_registry,
    chapter_workflow_graph_config,
)


def _initial_state() -> ChapterWorkflowStateV1:
    return ChapterWorkflowStateV1.initial(
        run_id=str(uuid4()),
        context_hash="a" * 64,
    )


def _graph_bindings(calls: list[str]) -> ChapterWorkflowGraphBindingsV1:
    async def node(name: str, update: dict[str, object] | None = None):
        calls.append(name)
        return update or {}

    async def freeze(_state):
        return await node("freeze_context")

    async def plan(_state):
        return await node(
            "plan_and_direct",
            {"activity_refs": {"plan": "activity-plan"}},
        )

    async def generate(_state):
        return await node(
            "generate_candidates",
            {"activity_refs": {"candidate:1": "activity-candidate-1"}},
        )

    async def review(_state):
        return await node(
            "review_candidates",
            {"result_refs": {"review": "a" * 64}},
        )

    async def persist(_state):
        return await node(
            "persist_candidates",
            {"candidate_version_ids": [101, 102]},
        )

    async def select(_state, resume_value):
        calls.append("apply_selection_resume")
        return {
            "selected_version_id": resume_value["selected_version_id"],
            "last_applied_command_id": resume_value["command_id"],
        }

    async def finalize(_state):
        return await node(
            "finalize_revision",
            {"target_chapter_revision": 1},
        )

    async def projection_resume(_state, resume_value):
        await node("apply_projection_resume")
        if isinstance(resume_value, dict) and set(resume_value) == {"command_id"}:
            return {"last_applied_command_id": resume_value["command_id"]}
        return {}

    async def observe(_state):
        return await node("observe_projection")

    return ChapterWorkflowGraphBindingsV1(
        freeze_context=freeze,
        plan_and_direct=plan,
        generate_candidates=generate,
        review_candidates=review,
        persist_candidates=persist,
        apply_selection_resume=select,
        finalize_revision=finalize,
        apply_projection_resume=projection_resume,
        observe_projection=observe,
    )


def test_graph_v1_state_is_a_strict_serializable_reference_contract() -> None:
    state = _initial_state()
    payload = state.model_dump(mode="json")

    assert set(payload) == {
        "workflow_version",
        "state_schema_version",
        "run_id",
        "node_key",
        "context_hash",
        "activity_refs",
        "result_refs",
        "candidate_version_ids",
        "selected_version_id",
        "last_applied_command_id",
        "target_chapter_revision",
        "error_category",
    }
    assert json.loads(json.dumps(payload)) == payload
    assert payload["node_key"] == "freeze_context"
    assert tuple(CHAPTER_WORKFLOW_NODE_KEYS_V1) == (
        "freeze_context",
        "plan_and_direct",
        "generate_candidates",
        "review_candidates",
        "persist_candidates",
        "waiting_for_selection",
        "finalize_revision",
        "projection_pending",
        "observe_projection",
        "successful",
    )

    with pytest.raises(ValidationError, match="prompt"):
        ChapterWorkflowStateV1.model_validate({**payload, "prompt": "private body"})
    with pytest.raises(ValidationError, match="activity_refs"):
        ChapterWorkflowStateV1.model_validate({**payload, "activity_refs": {"generate": object()}})


@pytest.mark.asyncio
async def test_graph_registry_routes_v1_without_version_fallback() -> None:
    registry = build_chapter_workflow_graph_registry()
    calls: list[str] = []
    bindings = _graph_bindings(calls)
    definition = registry.get(CHAPTER_WORKFLOW_VERSION_V1)

    assert definition is not None
    assert definition.workflow_version == CHAPTER_WORKFLOW_VERSION_V1
    assert definition.state_schema_version == CHAPTER_WORKFLOW_STATE_SCHEMA_VERSION_V1
    assert definition.state_type is ChapterWorkflowStateV1
    assert registry.get(999) is None
    with pytest.raises(ValueError, match="workflow version"):
        registry.compile(999, checkpointer=InMemorySaver(), bindings=bindings)

    state = _initial_state()
    app = registry.compile(
        CHAPTER_WORKFLOW_VERSION_V1,
        checkpointer=InMemorySaver(),
        bindings=bindings,
    )
    config = chapter_workflow_graph_config(state.run_id)
    first_result = await app.ainvoke(state.model_dump(mode="json"), config)
    selection_snapshot = await app.aget_state(config)

    assert first_result["__interrupt__"][0].value == {
        "kind": "selection",
        "run_id": state.run_id,
        "candidate_version_ids": [101, 102],
    }
    assert selection_snapshot.values["node_key"] == "waiting_for_selection"
    assert selection_snapshot.next == ("waiting_for_selection",)
    assert selection_snapshot.config["configurable"]["thread_id"] == state.run_id
    assert selection_snapshot.config["configurable"]["checkpoint_id"]
    assert calls == [
        "freeze_context",
        "plan_and_direct",
        "generate_candidates",
        "review_candidates",
        "persist_candidates",
    ]

    command_id = str(uuid4())
    second_result = await app.ainvoke(
        Command(
            resume={
                "command_id": command_id,
                "selected_version_id": 101,
            }
        ),
        config,
    )
    projection_snapshot = await app.aget_state(config)

    assert second_result["__interrupt__"][0].value == {
        "kind": "projection",
        "run_id": state.run_id,
        "target_chapter_revision": 1,
    }
    assert projection_snapshot.values["node_key"] == "projection_pending"
    assert projection_snapshot.next == ("projection_pending",)
    assert calls[-2:] == ["apply_selection_resume", "finalize_revision"]

    projection_command_id = str(uuid4())
    retry_result = await app.ainvoke(
        Command(resume={"command_id": projection_command_id}),
        config,
    )
    retry_snapshot = await app.aget_state(config)

    assert retry_result["__interrupt__"][0].value == {
        "kind": "projection",
        "run_id": state.run_id,
        "target_chapter_revision": 1,
    }
    assert retry_snapshot.values["node_key"] == "projection_pending"
    assert retry_snapshot.values["last_applied_command_id"] == projection_command_id
    assert retry_snapshot.next == ("projection_pending",)
    assert calls[-1] == "apply_projection_resume"
    assert "observe_projection" not in calls

    final_result = await app.ainvoke(Command(resume={"ready": True}), config)
    final_snapshot = await app.aget_state(config)

    assert final_result["node_key"] == "successful"
    assert final_result["selected_version_id"] == 101
    assert final_result["last_applied_command_id"] == projection_command_id
    assert final_snapshot.next == ()
    assert calls == [
        "freeze_context",
        "plan_and_direct",
        "generate_candidates",
        "review_candidates",
        "persist_candidates",
        "apply_selection_resume",
        "finalize_revision",
        "apply_projection_resume",
        "apply_projection_resume",
        "observe_projection",
    ]


def test_graph_config_uses_run_id_for_thread_and_optional_checkpoint() -> None:
    run_id = str(uuid4())

    assert chapter_workflow_graph_config(run_id) == {"configurable": {"thread_id": run_id}}
    assert chapter_workflow_graph_config(run_id, checkpoint_id="checkpoint-1") == {
        "configurable": {
            "thread_id": run_id,
            "checkpoint_id": "checkpoint-1",
        }
    }
    with pytest.raises(ValueError, match="run_id"):
        chapter_workflow_graph_config("not-a-run-id")


def test_root_payload_rejects_run_id_that_cannot_become_thread_id() -> None:
    runtime_inputs = ChapterWorkflowRuntimeInputs(
        project_id="project-id",
        chapter_number=1,
        retrieval_inputs=ChapterWorkflowRetrievalInputs(
            enabled=True,
            mode="simple",
            query_text="第一章",
        ),
    )
    runtime_payload = runtime_inputs.model_dump(mode="json")

    with pytest.raises(ValidationError, match="run_id"):
        ChapterWorkflowJobPayload(
            run_id="x" * 36,
            project_id="project-id",
            chapter_id=1,
            chapter_number=1,
            base_revision=0,
            context_hash="a" * 64,
            runtime_input_hash=stable_digest(runtime_payload),
            runtime_inputs=runtime_inputs,
        )


def test_checkpointer_dsn_is_derived_structurally() -> None:
    dsn = psycopg_dsn_from_sqlalchemy_url(
        "postgresql+asyncpg://workflow:p%40ss@db.example:5433/mofeng?sslmode=require"
    )
    parsed = make_url(dsn)

    assert parsed.drivername == "postgresql"
    assert parsed.username == "workflow"
    assert parsed.password == "p@ss"
    assert parsed.host == "db.example"
    assert parsed.port == 5433
    assert parsed.database == "mofeng"
    assert parsed.query == {"sslmode": "require"}

    with pytest.raises(ValueError, match="PostgreSQL"):
        psycopg_dsn_from_sqlalchemy_url("sqlite+aiosqlite:///local.db")
