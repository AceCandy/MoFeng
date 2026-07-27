from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.chapter_context import ChapterContext, ContextFallback
from app.services.pipeline_orchestrator import PipelineOrchestrator


@pytest.mark.asyncio
@pytest.mark.parametrize("snapshot", [None, {"legacy_context": True}])
async def test_missing_or_invalid_trace_context_is_explicitly_rebuilt(snapshot) -> None:
    rebuilt = MagicMock(spec=ChapterContext)
    resolver = MagicMock()
    resolver.resolve = AsyncMock(return_value=rebuilt)
    orchestrator = PipelineOrchestrator.__new__(PipelineOrchestrator)
    orchestrator.chapter_context_resolver = resolver

    restored = await orchestrator._restore_chapter_context_snapshot(
        snapshot,
        trace_node="context_prep",
        project_id="project-1",
        chapter_number=3,
        user_id=7,
        writing_notes="保持有限视角",
    )

    assert restored is rebuilt
    resolver.resolve.assert_awaited_once_with(
        project_id="project-1",
        chapter_number=3,
        user_id=7,
        writing_notes="保持有限视角",
        chapter_mission=None,
        rag_enabled=False,
        rag_query="",
        rag_mode="simple",
        pov_character=None,
    )


@pytest.mark.asyncio
async def test_trace_context_with_wrong_identity_is_explicitly_rebuilt(monkeypatch) -> None:
    snapshot = ChapterContext.model_construct(
        project_id="another-project",
        chapter_number=9,
    )
    monkeypatch.setattr(ChapterContext, "model_validate", MagicMock(return_value=snapshot))
    rebuilt = ChapterContext.model_construct(project_id="project-1", chapter_number=3)
    resolver = MagicMock()
    resolver.resolve = AsyncMock(return_value=rebuilt)
    orchestrator = PipelineOrchestrator.__new__(PipelineOrchestrator)
    orchestrator.chapter_context_resolver = resolver

    restored = await orchestrator._restore_chapter_context_snapshot(
        snapshot,
        trace_node="context_prep",
        project_id="project-1",
        chapter_number=3,
        user_id=7,
        writing_notes="保持有限视角",
    )

    assert restored is rebuilt
    resolver.with_runtime_inputs.assert_not_called()
    resolver.resolve.assert_awaited_once()


@pytest.mark.asyncio
async def test_valid_trace_context_applies_changed_runtime_inputs_and_refreshes_rag(
    monkeypatch,
) -> None:
    snapshot = ChapterContext.model_construct(
        project_id="project-1",
        chapter_number=3,
        input_hash="original",
    )
    updated = ChapterContext.model_construct(
        project_id="project-1",
        chapter_number=3,
        input_hash="updated",
    )
    refreshed = ChapterContext.model_construct(
        project_id="project-1",
        chapter_number=3,
        input_hash="refreshed",
    )
    monkeypatch.setattr(ChapterContext, "model_validate", MagicMock(return_value=snapshot))
    resolver = MagicMock()
    resolver.with_runtime_inputs.return_value = updated
    resolver.with_retrieval = AsyncMock(return_value=refreshed)
    resolver.resolve = AsyncMock()
    orchestrator = PipelineOrchestrator.__new__(PipelineOrchestrator)
    orchestrator.chapter_context_resolver = resolver

    restored = await orchestrator._restore_chapter_context_snapshot(
        snapshot,
        trace_node="rag_retrieval",
        project_id="project-1",
        chapter_number=3,
        user_id=7,
        writing_notes="改用沈策视角",
        chapter_mission={"pov_character": "沈策"},
        rag_enabled=True,
        rag_query="沈策 旧山道",
        rag_mode="two_stage",
        pov_character="沈策",
    )

    assert restored is refreshed
    resolver.with_runtime_inputs.assert_called_once_with(
        snapshot,
        writing_notes="改用沈策视角",
        chapter_mission={"pov_character": "沈策"},
    )
    resolver.with_retrieval.assert_awaited_once_with(
        updated,
        user_id=7,
        enabled=True,
        query_text="沈策 旧山道",
        mode="two_stage",
        pov_character="沈策",
    )
    resolver.resolve.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "restored_query",
        "requested_query",
        "restored_mode",
        "requested_mode",
        "restored_fallback",
        "rag_enabled",
        "should_refresh",
    ),
    [
        ("旧山道", "新路标", "simple", "simple", None, True, True),
        ("旧山道", "旧山道", "simple", "two_stage", None, True, True),
        ("旧山道", "旧山道", "simple", "simple", None, False, True),
        (
            "旧山道",
            "旧山道",
            "simple",
            "simple",
            ContextFallback.DISABLED,
            True,
            True,
        ),
        ("旧山道", "旧山道", "simple", "simple", None, True, False),
    ],
)
async def test_trace_context_refreshes_only_when_retrieval_inputs_change(
    monkeypatch,
    restored_query,
    requested_query,
    restored_mode,
    requested_mode,
    restored_fallback,
    rag_enabled,
    should_refresh,
) -> None:
    restored_rag = MagicMock()
    restored_rag.value.query = restored_query
    restored_rag.value.mode = restored_mode
    restored_rag.fallback = restored_fallback
    snapshot = ChapterContext.model_construct(
        project_id="project-1",
        chapter_number=3,
        input_hash="stable",
        rag=restored_rag,
    )
    updated = ChapterContext.model_construct(
        project_id="project-1",
        chapter_number=3,
        input_hash="stable",
    )
    refreshed = ChapterContext.model_construct(
        project_id="project-1",
        chapter_number=3,
        input_hash="refreshed",
    )
    monkeypatch.setattr(ChapterContext, "model_validate", MagicMock(return_value=snapshot))
    resolver = MagicMock()
    resolver.with_runtime_inputs.return_value = updated
    resolver.normalize_rag_query.return_value = requested_query
    resolver.with_retrieval = AsyncMock(return_value=refreshed)
    resolver.resolve = AsyncMock()
    orchestrator = PipelineOrchestrator.__new__(PipelineOrchestrator)
    orchestrator.chapter_context_resolver = resolver

    result = await orchestrator._restore_chapter_context_snapshot(
        snapshot,
        trace_node="rag_retrieval",
        project_id="project-1",
        chapter_number=3,
        user_id=7,
        writing_notes="保持有限视角",
        rag_enabled=rag_enabled,
        rag_query=requested_query,
        rag_mode=requested_mode,
    )

    if should_refresh:
        assert result is refreshed
        resolver.with_retrieval.assert_awaited_once_with(
            updated,
            user_id=7,
            enabled=rag_enabled,
            query_text=requested_query,
            mode=requested_mode,
            pov_character=None,
        )
    else:
        assert result is updated
        resolver.with_retrieval.assert_not_awaited()
    resolver.resolve.assert_not_awaited()
