"""Versioned durable Chapter graph contracts."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from pydantic import ValidationError
from sqlalchemy.engine import make_url

from app.db.chapter_workflow_checkpointer import psycopg_dsn_from_sqlalchemy_url
from app.schemas.chapter_context import stable_digest
from app.schemas.chapter_workflow import (
    CHAPTER_WORKFLOW_NODE_KEYS,
    CHAPTER_WORKFLOW_STATE_SCHEMA_VERSION,
    CHAPTER_WORKFLOW_VERSION,
    ChapterWorkflowState,
)
from app.schemas.job import (
    ChapterWorkflowJobPayload,
    ChapterWorkflowRetrievalInputs,
    ChapterWorkflowRuntimeInputs,
)
from app.services.chapter_workflow_graph import (
    ChapterWorkflowGraphBindings,
    build_chapter_workflow_graph_registry,
    chapter_workflow_graph_config,
)


def _graph_bindings(calls: list[str]) -> ChapterWorkflowGraphBindings:
    async def node(name: str, update: dict[str, object] | None = None):
        calls.append(name)
        return update or {}

    async def named(name: str, _state):
        return await node(name)

    async def candidate(name: str, ordinal: int, _state):
        return await node(
            name,
            {
                "activity_refs": {f"candidate:{ordinal}": f"activity-candidate-{ordinal}"},
                "result_refs": {f"candidate:{ordinal}": str(ordinal) * 64},
            },
        )

    async def persist(_state):
        return await node("persist_drafts", {"candidate_version_ids": [101, 102]})

    async def select(_state, resume_value):
        calls.append("apply_selection_resume")
        return {
            "selected_version_id": resume_value["selected_version_id"],
            "last_applied_command_id": resume_value["command_id"],
        }

    async def finalize(_state):
        return await node("finalize_revision", {"target_chapter_revision": 1})

    async def projection_resume(_state, resume_value):
        await node("apply_projection_resume")
        if isinstance(resume_value, dict) and set(resume_value) == {"command_id"}:
            return {"last_applied_command_id": resume_value["command_id"]}
        return {}

    return ChapterWorkflowGraphBindings(
        freeze_base_context=lambda state: named("freeze_base_context", state),
        retrieve_context=lambda state: named("retrieve_context", state),
        plan_chapter=lambda state: named("plan_chapter", state),
        generate_candidate_1=lambda state: candidate("generate_candidate_1", 1, state),
        generate_candidate_2=lambda state: candidate("generate_candidate_2", 2, state),
        review_candidates=lambda state: named("review_candidates", state),
        refine_candidate=lambda state: named("refine_candidate", state),
        enhance_content=lambda state: named("enhance_content", state),
        repair_consistency=lambda state: named("repair_consistency", state),
        optimize_style=lambda state: named("optimize_style", state),
        enrich_content=lambda state: named("enrich_content", state),
        compress_candidate=lambda _state: node(
            "compress_candidate",
            {"skipped_stages": {"compress_candidate": "within_word_limit"}},
        ),
        persist_drafts=persist,
        apply_selection_resume=select,
        finalize_revision=finalize,
        apply_projection_resume=projection_resume,
        reconcile_projections=lambda state: named("reconcile_projections", state),
    )


@pytest.mark.asyncio
async def test_graph_routes_real_nodes_and_preserves_skip_reasons() -> None:
    registry = build_chapter_workflow_graph_registry()
    calls: list[str] = []
    bindings = _graph_bindings(calls)
    definition = registry.get(CHAPTER_WORKFLOW_VERSION)

    assert definition is not None
    assert definition.state_schema_version == CHAPTER_WORKFLOW_STATE_SCHEMA_VERSION
    assert definition.state_type is ChapterWorkflowState
    assert tuple(CHAPTER_WORKFLOW_NODE_KEYS)[-3:] == (
        "wait_for_projections",
        "reconcile_projections",
        "successful",
    )

    state = ChapterWorkflowState.initial(
        run_id=str(uuid4()),
        context_hash="a" * 64,
        candidate_count=1,
        optional_stages={"enhance_content": True},
    )
    app = registry.compile(
        CHAPTER_WORKFLOW_VERSION,
        checkpointer=InMemorySaver(),
        bindings=bindings,
    )
    config = chapter_workflow_graph_config(state.run_id)
    first_result = await app.ainvoke(state.model_dump(mode="json"), config)

    assert first_result["__interrupt__"][0].value["kind"] == "selection"
    assert first_result["skipped_stages"] == {
        "generate_candidate_2": "single_candidate",
        "repair_consistency": "disabled",
        "optimize_style": "disabled",
        "enrich_content": "disabled",
        "compress_candidate": "within_word_limit",
    }
    assert calls == [
        "freeze_base_context",
        "retrieve_context",
        "plan_chapter",
        "generate_candidate_1",
        "review_candidates",
        "refine_candidate",
        "enhance_content",
        "compress_candidate",
        "persist_drafts",
    ]

    selection_command_id = str(uuid4())
    await app.ainvoke(
        Command(
            resume={
                "command_id": selection_command_id,
                "selected_version_id": 101,
            }
        ),
        config,
    )
    retry_command_id = str(uuid4())
    retry_result = await app.ainvoke(
        Command(resume={"command_id": retry_command_id}),
        config,
    )
    retry_snapshot = await app.aget_state(config)

    assert retry_result["__interrupt__"][0].value["kind"] == "projection"
    assert retry_snapshot.values["node_key"] == "wait_for_projections"
    assert retry_snapshot.next == ("wait_for_projections",)
    assert "reconcile_projections" not in calls

    final_result = await app.ainvoke(Command(resume={"ready": True}), config)
    assert final_result["node_key"] == "successful"
    assert calls[-2:] == ["apply_projection_resume", "reconcile_projections"]


@pytest.mark.asyncio
async def test_graph_generates_second_candidate_when_requested() -> None:
    calls: list[str] = []
    state = ChapterWorkflowState.initial(
        run_id=str(uuid4()),
        context_hash="b" * 64,
        candidate_count=2,
    )
    app = build_chapter_workflow_graph_registry().compile(
        CHAPTER_WORKFLOW_VERSION,
        checkpointer=InMemorySaver(),
        bindings=_graph_bindings(calls),
    )

    result = await app.ainvoke(
        state.model_dump(mode="json"),
        chapter_workflow_graph_config(state.run_id),
    )

    assert "generate_candidate_2" in calls
    assert "generate_candidate_2" not in result["skipped_stages"]


@pytest.mark.asyncio
async def test_graph_generates_candidates_concurrently_before_review() -> None:
    calls: list[str] = []
    both_started = asyncio.Event()
    release = asyncio.Event()
    started: set[int] = set()

    async def candidate(ordinal: int):
        started.add(ordinal)
        if len(started) == 2:
            both_started.set()
        await release.wait()
        calls.append(f"generate_candidate_{ordinal}")
        return {
            "activity_refs": {f"candidate:{ordinal}": f"activity-candidate-{ordinal}"},
            "result_refs": {f"candidate:{ordinal}": str(ordinal) * 64},
        }

    bindings = replace(
        _graph_bindings(calls),
        generate_candidate_1=lambda _state: candidate(1),
        generate_candidate_2=lambda _state: candidate(2),
    )
    state = ChapterWorkflowState.initial(
        run_id=str(uuid4()),
        context_hash="c" * 64,
        candidate_count=2,
    )
    app = build_chapter_workflow_graph_registry().compile(
        CHAPTER_WORKFLOW_VERSION,
        checkpointer=InMemorySaver(),
        bindings=bindings,
    )

    invocation = asyncio.create_task(
        app.ainvoke(
            state.model_dump(mode="json"),
            chapter_workflow_graph_config(state.run_id),
        )
    )
    await asyncio.wait_for(both_started.wait(), timeout=1)
    assert "review_candidates" not in calls
    release.set()
    result = await asyncio.wait_for(invocation, timeout=1)

    assert "review_candidates" in calls
    assert result["activity_refs"]["candidate:1"] == "activity-candidate-1"
    assert result["activity_refs"]["candidate:2"] == "activity-candidate-2"


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
