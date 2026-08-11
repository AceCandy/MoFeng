import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.schemas.chapter_context import ContextFallback
from app.services.chapter_context_resolver import (
    ChapterContextPolicy,
    ChapterContextResolver,
    ChapterContextSources,
)
from app.services.knowledge_retrieval_service import KnowledgeRetrievalService

NOW = datetime(2026, 7, 27, tzinfo=timezone.utc)


def _project(*, with_history: bool = True):
    blueprint = SimpleNamespace(
        title="雾城",
        target_audience="成人",
        genre="悬疑",
        style="冷峻",
        tone="克制",
        one_sentence_summary="记者追查匿名信",
        full_synopsis="幕后人是尚未登场的沈策",
        world_setting={"city": "临川"},
        updated_at=NOW,
    )
    characters = [
        SimpleNamespace(
            name="林墨",
            identity="记者",
            personality="执着",
            goals="查明真相",
            abilities="调查",
            relationship_to_protagonist="本人",
            extra={},
            position=1,
        ),
        SimpleNamespace(
            name="沈策",
            identity="商人",
            personality="隐忍",
            goals="保守秘密",
            abilities="布局",
            relationship_to_protagonist="陌生人",
            extra={},
            position=2,
        ),
    ]
    relationships = [
        SimpleNamespace(
            character_from="林墨",
            character_to="沈策",
            description="尚未相识",
            relationship_type="unknown",
            position=1,
        )
    ]
    outlines = [
        SimpleNamespace(
            id=1,
            chapter_number=1,
            title="来信",
            summary="林墨收到匿名信",
            goals="建立悬念",
            highlights=["火漆"],
            character_states={},
            metadata_={},
        ),
        SimpleNamespace(
            id=2,
            chapter_number=2,
            title="地图",
            summary="林墨发现地图",
            goals="推进调查",
            highlights=["旧山道"],
            character_states={},
            metadata_={},
        ),
        SimpleNamespace(
            id=3,
            chapter_number=3,
            title="入山",
            summary="林墨进入旧山道",
            goals="制造危机",
            highlights=["迷雾"],
            character_states={},
            metadata_={},
        ),
    ]
    chapters = []
    if with_history:
        chapters = [
            SimpleNamespace(
                id=11,
                chapter_number=1,
                real_summary="林墨收到一封带火漆的匿名信。",
                status="successful",
                selected_version_id=101,
                selected_version=SimpleNamespace(
                    id=101,
                    content="第一章正文" * 30,
                    created_at=NOW,
                ),
                updated_at=NOW,
            ),
            SimpleNamespace(
                id=12,
                chapter_number=2,
                real_summary=None,
                status="successful",
                selected_version_id=102,
                selected_version=SimpleNamespace(
                    id=102,
                    content="林墨沿着地图寻找旧山道。" * 30,
                    created_at=NOW,
                ),
                updated_at=NOW,
            ),
        ]
    return SimpleNamespace(
        id="project-1",
        blueprint=blueprint,
        characters=characters,
        relationships_=relationships,
        outlines=outlines,
        chapters=chapters,
    )


def _sources(*, with_history: bool = True, memory_version: int = 4) -> ChapterContextSources:
    return ChapterContextSources(
        project=_project(with_history=with_history),
        chapter_blueprint=SimpleNamespace(
            chapter_number=3,
            suspense_density="gradual",
            foreshadowing_ops="reinforce",
            cognitive_twist_level=2,
            chapter_function="推进调查",
            chapter_focus="进入旧山道",
            suspense_type="环境危机",
            emotional_arc="好奇到恐惧",
            involved_foreshadowings=[8],
            mission_constraints={"must": ["发现路标"]},
            brief_summary="林墨入山",
            director_script="保持有限视角",
            beat_sheet={"opening": "入山"},
            updated_at=NOW,
        ),
        constitution=None,
        project_memory=SimpleNamespace(
            global_summary=f"全局摘要 v{memory_version}",
            plot_arcs={"main": "匿名信"},
            story_timeline_summary="第三天",
            last_updated_chapter=2,
            version=memory_version,
            updated_at=NOW,
        ),
        writer_persona=None,
        foreshadows=[
            SimpleNamespace(
                id=8,
                chapter_number=1,
                content="匿名信使用了罕见火漆",
                type="clue",
                keywords=["火漆"],
                status="planted",
                importance="major",
                target_reveal_chapter=5,
                related_plots=["匿名信"],
                updated_at=NOW,
            )
        ],
        character_states=[
            SimpleNamespace(
                id=20,
                chapter_number=2,
                character_name="林墨",
                location="临川北郊",
                emotion="警惕",
                health_status="healthy",
                current_goals=["找到旧山道"],
                extra={"raw_state_text": "林墨在临川北郊，保持警惕。"},
                updated_at=NOW,
            )
        ],
    )


async def _resolver(
    sources: ChapterContextSources,
    *,
    policy: ChapterContextPolicy | None = None,
    llm_service=None,
    vector_store=None,
) -> ChapterContextResolver:
    resolver = ChapterContextResolver(
        AsyncMock(),
        llm_service=llm_service or AsyncMock(),
        vector_store=vector_store,
        policy=policy,
    )
    resolver._load_sources = AsyncMock(return_value=sources)
    return resolver


@pytest.mark.asyncio
async def test_projection_revision_changes_hash_not_source_revision() -> None:
    first_resolver = await _resolver(_sources(memory_version=4))
    second_resolver = await _resolver(_sources(memory_version=5))

    first = await first_resolver.resolve(
        project_id="project-1",
        chapter_number=3,
        user_id=1,
        writing_notes="只写林墨可见的信息",
    )
    second = await second_resolver.resolve(
        project_id="project-1",
        chapter_number=3,
        user_id=1,
        writing_notes="只写林墨可见的信息",
    )

    assert first.source_revision == second.source_revision
    assert first.input_hash != second.input_hash
    assert first.project_memory.source_revision == "projection:4"
    assert second.project_memory.source_revision == "projection:5"


@pytest.mark.asyncio
async def test_canonical_blueprint_content_changes_source_revision() -> None:
    first_sources = _sources()
    second_sources = _sources()
    second_sources.project.characters[0].personality = "谨慎"
    first_resolver = await _resolver(first_sources)
    second_resolver = await _resolver(second_sources)

    first = await first_resolver.resolve(
        project_id="project-1",
        chapter_number=3,
        user_id=1,
    )
    second = await second_resolver.resolve(
        project_id="project-1",
        chapter_number=3,
        user_id=1,
    )

    assert first.blueprint.source_revision != second.blueprint.source_revision
    assert first.source_revision != second.source_revision


@pytest.mark.asyncio
@pytest.mark.parametrize("changed_source", ["real_summary", "selected_content"])
async def test_successful_history_content_changes_source_revision(
    changed_source: str,
) -> None:
    first_sources = _sources()
    second_sources = _sources()
    if changed_source == "real_summary":
        second_sources.project.chapters[1].real_summary = "林墨在旧山道入口发现新的路标。"
    else:
        second_sources.project.chapters[1].selected_version.content = "林墨发现新的路标。" * 30
    first_resolver = await _resolver(first_sources)
    second_resolver = await _resolver(second_sources)

    first = await first_resolver.resolve(
        project_id="project-1",
        chapter_number=3,
        user_id=1,
    )
    second = await second_resolver.resolve(
        project_id="project-1",
        chapter_number=3,
        user_id=1,
    )

    assert first.history.source_revision != second.history.source_revision
    assert first.source_revision != second.source_revision
    assert first.input_hash != second.input_hash


@pytest.mark.asyncio
async def test_projection_content_changes_section_revision_and_hash_only() -> None:
    first_sources = _sources()
    second_sources = _sources()
    second_sources.foreshadows[0].content = "匿名信使用了黑色火漆"
    first_resolver = await _resolver(first_sources)
    second_resolver = await _resolver(second_sources)

    first = await first_resolver.resolve(
        project_id="project-1",
        chapter_number=3,
        user_id=1,
    )
    second = await second_resolver.resolve(
        project_id="project-1",
        chapter_number=3,
        user_id=1,
    )

    assert first.source_revision == second.source_revision
    assert first.foreshadows.source_revision != second.foreshadows.source_revision
    assert first.input_hash != second.input_hash


@pytest.mark.asyncio
async def test_equivalent_revision_timezones_have_the_same_source_revision() -> None:
    first_sources = _sources()
    second_sources = _sources()
    second_sources.project.blueprint.updated_at = NOW.astimezone(timezone(timedelta(hours=8)))
    second_sources.project.chapters[0].selected_version.created_at = NOW.astimezone(
        timezone(timedelta(hours=-5))
    )
    first_resolver = await _resolver(first_sources)
    second_resolver = await _resolver(second_sources)

    first = await first_resolver.resolve(
        project_id="project-1",
        chapter_number=3,
        user_id=1,
    )
    second = await second_resolver.resolve(
        project_id="project-1",
        chapter_number=3,
        user_id=1,
    )

    assert first.source_revision == second.source_revision


@pytest.mark.asyncio
async def test_visibility_and_budget_are_applied_before_adapters() -> None:
    policy = ChapterContextPolicy(
        max_completed_chapters=1,
        max_history_summary_chars=12,
        previous_tail_chars=20,
    )
    resolver = await _resolver(_sources(), policy=policy)

    context = await resolver.resolve(
        project_id="project-1",
        chapter_number=3,
        user_id=1,
        writing_notes="林墨进入旧山道",
        chapter_mission={"allowed_new_characters": []},
    )

    assert context.history.truncated is True
    assert context.history.fallback == ContextFallback.BUDGET_TRUNCATED
    assert len(context.history.value.completed_chapters) == 1
    assert len(context.history.value.previous_chapter.tail_excerpt) == 20
    assert context.history.value.previous_chapter.summary
    assert context.writer_visibility.value.allowed_characters == ["林墨"]
    assert context.writer_visibility.value.forbidden_characters == ["沈策"]
    assert "full_synopsis" not in context.writer_visibility.value.writer_blueprint
    assert context.foreshadows.value[0]["content"] == "匿名信使用了罕见火漆"
    assert context.plot_threads.value == [
        {
            "thread_name": "匿名信",
            "status": "ongoing",
            "last_mentioned_chapter": 1,
            "foreshadow_count": 1,
        }
    ]


@pytest.mark.asyncio
async def test_zero_completed_chapter_budget_keeps_only_previous_chapter() -> None:
    resolver = await _resolver(
        _sources(),
        policy=ChapterContextPolicy(max_completed_chapters=0),
    )

    context = await resolver.resolve(
        project_id="project-1",
        chapter_number=3,
        user_id=1,
    )

    assert context.history.truncated is True
    assert context.history.fallback == ContextFallback.BUDGET_TRUNCATED
    assert context.history.value.completed_chapters == []
    assert context.history.value.previous_chapter.chapter_number == 2


@pytest.mark.asyncio
async def test_first_chapter_and_missing_optional_sources_are_explicit() -> None:
    resolver = await _resolver(_sources(with_history=False))

    context = await resolver.resolve(
        project_id="project-1",
        chapter_number=1,
        user_id=1,
    )

    assert context.history.fallback == ContextFallback.FIRST_CHAPTER
    assert context.history.value.previous_chapter.chapter_number is None
    assert context.project_memory.fallback is None
    assert context.constitution.fallback == ContextFallback.SOURCE_MISSING
    assert context.writer_persona.fallback == ContextFallback.SOURCE_MISSING
    assert context.rag.fallback == ContextFallback.DISABLED


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("vector_store", "embedding", "expected"),
    [
        (None, [0.1], ContextFallback.UNAVAILABLE),
        (AsyncMock(), None, ContextFallback.EMBEDDING_FAILED),
        (AsyncMock(), [0.1], ContextFallback.RETRIEVAL_EMPTY),
    ],
)
async def test_rag_degradation_reasons_are_distinct(vector_store, embedding, expected) -> None:
    llm_service = AsyncMock()
    llm_service.get_embedding.return_value = embedding
    if vector_store is not None:
        vector_store.query_chunks.return_value = []
        vector_store.query_summaries.return_value = []
    resolver = await _resolver(
        _sources(),
        llm_service=llm_service,
        vector_store=vector_store,
    )

    context = await resolver.resolve(
        project_id="project-1",
        chapter_number=3,
        user_id=1,
        rag_enabled=True,
        rag_query="旧山道",
    )

    assert context.rag.fallback == expected
    assert context.rag.value.chunks == []
    assert context.rag.value.summaries == []


@pytest.mark.asyncio
async def test_rag_snapshot_is_normalized_and_filters_future_chapters() -> None:
    llm_service = AsyncMock()
    llm_service.get_embedding.return_value = [0.1, 0.2]
    vector_store = AsyncMock()
    vector_store.query_chunks.return_value = [
        SimpleNamespace(
            chapter_number=2,
            chapter_title="地图",
            content="地图上标出了旧山道。",
            score=0.12,
            metadata={"kind": "plot"},
        ),
        SimpleNamespace(
            chapter_number=4,
            chapter_title="未来",
            content="不应进入快照",
            score=0.01,
            metadata={},
        ),
    ]
    vector_store.query_summaries.return_value = [
        SimpleNamespace(
            chapter_number=2,
            title="地图",
            summary="林墨发现地图",
            score=0.11,
        )
    ]
    resolver = await _resolver(
        _sources(),
        llm_service=llm_service,
        vector_store=vector_store,
    )

    context = await resolver.resolve(
        project_id="project-1",
        chapter_number=3,
        user_id=1,
        rag_enabled=True,
        rag_query="  旧山道   地图  ",
    )

    assert context.rag.fallback is None
    assert context.rag.value.query == "旧山道 地图"
    assert [item.chapter_number for item in context.rag.value.chunks] == [2]
    assert [item.chapter_number for item in context.rag.value.related_chapters] == [2]
    related = context.rag.value.related_chapters[0]
    assert related.summary == "林墨发现地图"
    assert related.relevance_score == 0.12
    assert related.matched_content == "地图上标出了旧山道。"
    assert context.rag.value.retrieval_snapshot_id != "missing"
    vector_store.query_chunks.assert_awaited_once_with(
        resolver.session,
        project_id="project-1",
        embedding=[0.1, 0.2],
        top_k=resolver.policy.max_rag_chunks,
    )
    vector_store.query_summaries.assert_awaited_once_with(
        resolver.session,
        project_id="project-1",
        embedding=[0.1, 0.2],
        top_k=resolver.policy.max_rag_summaries,
    )


@pytest.mark.asyncio
async def test_rag_vector_queries_do_not_overlap_on_shared_session() -> None:
    llm_service = AsyncMock()
    llm_service.get_embedding.return_value = [0.1]
    vector_store = AsyncMock()
    chunks_running = False

    async def query_chunks(*_args, **_kwargs):
        nonlocal chunks_running
        chunks_running = True
        await asyncio.sleep(0)
        chunks_running = False
        return []

    async def query_summaries(*_args, **_kwargs):
        assert chunks_running is False
        return []

    vector_store.query_chunks.side_effect = query_chunks
    vector_store.query_summaries.side_effect = query_summaries
    resolver = await _resolver(
        _sources(),
        llm_service=llm_service,
        vector_store=vector_store,
    )

    context = await resolver.resolve(
        project_id="project-1",
        chapter_number=3,
        user_id=1,
        rag_enabled=True,
        rag_query="旧山道",
    )

    assert context.rag.fallback == ContextFallback.RETRIEVAL_EMPTY


@pytest.mark.asyncio
async def test_rag_query_is_normalized_and_truncated_before_embedding() -> None:
    llm_service = AsyncMock()
    llm_service.get_embedding.return_value = [0.1]
    vector_store = AsyncMock()
    vector_store.query_chunks.return_value = []
    vector_store.query_summaries.return_value = []
    resolver = await _resolver(
        _sources(),
        policy=ChapterContextPolicy(max_rag_query_chars=12),
        llm_service=llm_service,
        vector_store=vector_store,
    )

    context = await resolver.resolve(
        project_id="project-1",
        chapter_number=3,
        user_id=1,
        rag_enabled=True,
        rag_query="  旧山道   地图   以及超出预算的正文  ",
    )

    assert context.rag.truncated is True
    assert len(context.rag.value.query) == 12
    llm_service.get_embedding.assert_awaited_once_with(
        context.rag.value.query,
        user_id=1,
        stage="rag_embedding",
    )


@pytest.mark.asyncio
async def test_rag_summary_budget_is_enforced() -> None:
    llm_service = AsyncMock()
    llm_service.get_embedding.return_value = [0.1]
    vector_store = AsyncMock()
    vector_store.query_chunks.return_value = []
    vector_store.query_summaries.return_value = [
        SimpleNamespace(
            chapter_number=2,
            title="地图",
            summary="过长摘要" * 20,
            score=0.11,
        )
    ]
    resolver = await _resolver(
        _sources(),
        policy=ChapterContextPolicy(max_rag_summary_chars=12),
        llm_service=llm_service,
        vector_store=vector_store,
    )

    context = await resolver.resolve(
        project_id="project-1",
        chapter_number=3,
        user_id=1,
        rag_enabled=True,
        rag_query="旧山道",
    )

    assert len(context.rag.value.summaries[0].summary) == 12
    assert context.rag.truncated is True
    assert context.rag.fallback == ContextFallback.BUDGET_TRUNCATED


@pytest.mark.asyncio
async def test_two_stage_retrieval_exception_is_explicit(monkeypatch) -> None:
    async def fail_retrieval(*args, **kwargs):
        raise RuntimeError("vector unavailable")

    monkeypatch.setattr(
        "app.services.chapter_context_resolver.KnowledgeRetrievalService.retrieve_and_filter",
        fail_retrieval,
    )
    resolver = await _resolver(
        _sources(),
        llm_service=AsyncMock(),
        vector_store=AsyncMock(),
    )

    context = await resolver.resolve(
        project_id="project-1",
        chapter_number=3,
        user_id=1,
        rag_enabled=True,
        rag_query="旧山道",
        rag_mode="two_stage",
    )

    assert context.rag.fallback == ContextFallback.RETRIEVAL_FAILED
    assert context.rag.value.stats["fallback"] == "retrieval_failed"


@pytest.mark.asyncio
async def test_two_stage_filter_failure_is_not_reported_as_empty() -> None:
    llm_service = AsyncMock()
    llm_service.generate.side_effect = [
        "旧山道·地图",
        RuntimeError("filter unavailable"),
    ]
    vector_store = AsyncMock()
    vector_store.search.return_value = [
        {
            "content": "地图上标出了旧山道",
            "source": "chapter",
            "chapter_number": 2,
            "score": 0.9,
        }
    ]
    resolver = await _resolver(
        _sources(),
        llm_service=llm_service,
        vector_store=vector_store,
    )

    context = await resolver.resolve(
        project_id="project-1",
        chapter_number=3,
        user_id=1,
        rag_enabled=True,
        rag_query="旧山道",
        rag_mode="two_stage",
    )

    assert context.rag.fallback == ContextFallback.RETRIEVAL_FAILED
    assert context.rag.value.stats["fallback"] == "retrieval_failed"


@pytest.mark.asyncio
async def test_two_stage_retrieval_receives_only_frozen_canonical_sources(monkeypatch) -> None:
    captured = {}

    async def retrieve_from_context(*args, **kwargs):
        captured.update(kwargs)
        from app.services.knowledge_retrieval_service import FilteredContext

        return FilteredContext(
            plot_fuel=[],
            character_info=[],
            world_fragments=[],
            narrative_techniques=[],
            warnings=[],
        )

    monkeypatch.setattr(
        "app.services.chapter_context_resolver.KnowledgeRetrievalService.retrieve_and_filter",
        retrieve_from_context,
    )
    resolver = await _resolver(
        _sources(),
        llm_service=AsyncMock(),
        vector_store=AsyncMock(),
    )

    context = await resolver.resolve(
        project_id="project-1",
        chapter_number=3,
        user_id=1,
        writing_notes="只写冻结上下文",
        rag_enabled=True,
        rag_query="旧山道",
        rag_mode="two_stage",
    )

    assert captured["chapter_blueprint"] == context.chapter_blueprint.value
    assert captured["global_summary"] == "全局摘要 v4"
    assert captured["chapter_blueprint"]["suspense_density"] == "gradual"


@pytest.mark.asyncio
async def test_two_stage_service_skips_db_when_canonical_sources_are_supplied() -> None:
    session = AsyncMock()
    llm_service = AsyncMock()
    llm_service.generate.return_value = "旧山道·地图"
    vector_store = AsyncMock()
    vector_store.search.return_value = []
    service = KnowledgeRetrievalService(session, llm_service, vector_store)

    result = await service.retrieve_and_filter(
        project_id="project-1",
        chapter_number=3,
        user_id=1,
        chapter_blueprint={
            "chapter_number": 3,
            "brief_summary": "林墨入山",
            "chapter_focus": "进入旧山道",
            "chapter_function": "推进调查",
            "suspense_density": "gradual",
            "foreshadowing_ops": "reinforce",
            "cognitive_twist_level": 2,
        },
        global_summary="冻结的全局摘要",
    )

    session.execute.assert_not_awaited()
    assert result.stats["query_count"] == 1
    assert result.stats["retrieved_count"] == 0
