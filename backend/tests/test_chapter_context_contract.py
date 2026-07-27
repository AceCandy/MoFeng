import json
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.schemas.chapter_context import (
    ChapterContext,
    ChapterHistory,
    ChapterRAGContext,
    ContextFallback,
    ContextSection,
    ContextSource,
    PreviousChapterContext,
    WriterPersonaContext,
    WriterVisibilityContext,
)
from app.services.chapter_context_adapters import (
    ChapterContextShadowComparator,
    ConsistencyContextAdapter,
    GenerationContextAdapter,
    ReviewContextAdapter,
    WRITER_VISIBILITY_SHADOW_PREFIXES,
)


def _section(value, source: ContextSource, revision: str, **kwargs):
    return ContextSection(
        value=value,
        source=source,
        source_revision=revision,
        **kwargs,
    )


def _build_context(*, created_at: datetime) -> ChapterContext:
    full_blueprint = {
        "title": "雾城",
        "genre": "悬疑",
        "style": "冷峻",
        "full_synopsis": "幕后人是尚未登场的沈策",
        "world_setting": {"city": "临川"},
        "characters": [
            {"name": "林墨", "identity": "记者"},
            {"name": "沈策", "identity": "幕后人"},
        ],
    }
    writer_blueprint = {
        "title": "雾城",
        "genre": "悬疑",
        "style": "冷峻",
        "world_setting": {"city": "临川"},
        "characters": [{"name": "林墨", "identity": "记者"}],
    }
    return ChapterContext(
        project_id="project-1",
        chapter_number=3,
        source_revision="src-3",
        policy_version="chapter-context-policy.v1",
        created_at=created_at,
        blueprint=_section(full_blueprint, ContextSource.NOVEL_BLUEPRINT, "bp-1"),
        outline=_section(
            {"chapter_number": 3, "title": "入山", "summary": "林墨进入旧山道"},
            ContextSource.CHAPTER_OUTLINE,
            "outline-3",
        ),
        chapter_blueprint=_section(
            {"chapter_focus": "追踪线索"},
            ContextSource.CHAPTER_BLUEPRINT,
            "chapter-blueprint-3",
        ),
        chapter_mission=_section(
            {"pov_character": "林墨"},
            ContextSource.RUNTIME_INPUT,
            "mission-3",
        ),
        writing_notes=_section(
            "只写林墨可见的信息",
            ContextSource.RUNTIME_INPUT,
            "writing-notes-3",
        ),
        history=_section(
            ChapterHistory(
                previous_chapter=PreviousChapterContext(
                    chapter_number=2,
                    summary="林墨发现地图",
                    tail_excerpt="地图背面写着一个日期。",
                ),
                completed_chapters=[
                    {"chapter_number": 1, "title": "来信", "summary": "林墨收到匿名信"},
                    {"chapter_number": 2, "title": "地图", "summary": "林墨发现地图"},
                ],
            ),
            ContextSource.CHAPTER_HISTORY,
            "history-2",
        ),
        project_memory=_section(
            {"global_summary": "林墨追查匿名信。", "plot_arcs": {"main": "匿名信"}},
            ContextSource.PROJECT_MEMORY,
            "projection:4",
        ),
        constitution=_section("第三人称有限视角", ContextSource.NOVEL_CONSTITUTION, "constitution-1"),
        writer_persona=_section(
            WriterPersonaContext(prompt_context="语言简洁", name="冷笔"),
            ContextSource.WRITER_PERSONA,
            "persona-2",
        ),
        foreshadows=_section(
            [{"id": 8, "chapter_number": 1, "content": "匿名信的火漆"}],
            ContextSource.FORESHADOWING,
            "foreshadows-8",
        ),
        plot_threads=_section(
            [{"thread_name": "匿名信", "last_mentioned_chapter": 2, "foreshadow_count": 1}],
            ContextSource.FORESHADOWING,
            "foreshadows-8",
        ),
        character_states=_section(
            [{"character_name": "林墨", "raw_state_text": "林墨仍在临川"}],
            ContextSource.CHARACTER_STATE,
            "character-state-2",
        ),
        rag=_section(
            ChapterRAGContext(
                mode="simple",
                query="旧山道 地图",
                chunks=[
                    {
                        "chapter_number": 2,
                        "title": "地图",
                        "content": "地图上标出了旧山道。",
                        "score": 0.12,
                        "rank": 1,
                    }
                ],
                summaries=[
                    {
                        "chapter_number": 2,
                        "title": "地图",
                        "summary": "林墨发现地图",
                        "score": 0.12,
                        "rank": 1,
                    }
                ],
                related_chapters=[
                    {
                        "chapter_number": 2,
                        "title": "地图",
                        "summary": "林墨发现地图",
                        "relevance_score": 0.12,
                        "matched_content": "地图上标出了旧山道。",
                    }
                ],
                retrieval_snapshot_id="rag-1",
            ),
            ContextSource.VECTOR_RETRIEVAL,
            "rag-1",
        ),
        writer_visibility=_section(
            WriterVisibilityContext(
                writer_blueprint=writer_blueprint,
                introduced_characters=["林墨"],
                planned_characters=["林墨"],
                allowed_characters=["林墨"],
                forbidden_characters=["沈策"],
            ),
            ContextSource.VISIBILITY_POLICY,
            "visibility-3",
        ),
    )


def test_snapshot_and_hash_ignore_created_at() -> None:
    first = _build_context(created_at=datetime(2026, 7, 27, tzinfo=timezone.utc))
    second = _build_context(
        created_at=datetime(2026, 7, 27, tzinfo=timezone.utc) + timedelta(hours=1)
    )

    assert first.input_hash == second.input_hash
    assert first.snapshot_json() == second.snapshot_json()
    assert "created_at" not in first.snapshot_payload()
    assert ChapterContext.model_validate(first.model_dump(mode="json")) == first


def test_snapshot_normalizes_sets_and_equivalent_timezones() -> None:
    first = _build_context(created_at=datetime.now(timezone.utc)).with_updates(
        project_memory=_section(
            {
                "tags": {"beta", "alpha"},
                "observed_at": datetime(2026, 7, 27, tzinfo=timezone.utc),
            },
            ContextSource.PROJECT_MEMORY,
            "projection:stable",
        )
    )
    second = _build_context(created_at=datetime.now(timezone.utc)).with_updates(
        project_memory=_section(
            {
                "tags": frozenset(("alpha", "beta")),
                "observed_at": datetime(
                    2026,
                    7,
                    27,
                    8,
                    tzinfo=timezone(timedelta(hours=8)),
                ),
            },
            ContextSource.PROJECT_MEMORY,
            "projection:stable",
        )
    )

    assert first.input_hash == second.input_hash
    assert first.snapshot_json() == second.snapshot_json()
    assert first.snapshot_payload()["project_memory"]["value"] == {
        "observed_at": "2026-07-27T00:00:00Z",
        "tags": ["alpha", "beta"],
    }


def test_snapshot_rejects_tampered_input_hash() -> None:
    context = _build_context(created_at=datetime.now(timezone.utc))
    payload = context.snapshot_payload()
    payload["outline"]["value"]["title"] = "被篡改的标题"

    with pytest.raises(ValidationError, match="input_hash"):
        ChapterContext.model_validate(payload)


def test_adapters_share_canonical_values_without_leaking_private_blueprint() -> None:
    context = _build_context(created_at=datetime.now(timezone.utc))

    generation = GenerationContextAdapter.to_context(context)
    review = ReviewContextAdapter.to_prompt_context(context)
    consistency = ConsistencyContextAdapter.to_prompt_context(context)

    assert generation["writer_blueprint"] == review["novel_blueprint"]
    assert review["chapter_outline"] == generation["chapter_outline"]
    assert review["previous_chapter"] == generation["previous_chapter"]
    assert review["completed_chapters"] == generation["completed_chapters"]
    assert review["project_memory"]["global_summary"] == "林墨追查匿名信。"
    assert consistency["global_summary"] == "林墨追查匿名信。"

    serialized_writer_view = str(review["novel_blueprint"])
    assert "沈策" not in serialized_writer_view
    assert "full_synopsis" not in review["novel_blueprint"]
    assert "沈策" in str(context.blueprint.value)
    assert "幕后人是尚未登场的沈策" in consistency["novel_setting"]


def test_section_fallback_is_explicit_and_serializable() -> None:
    context = _build_context(created_at=datetime.now(timezone.utc))
    missing_memory = ContextSection(
        value={},
        source=ContextSource.PROJECT_MEMORY,
        source_revision="missing",
        truncated=False,
        fallback=ContextFallback.SOURCE_MISSING,
    )
    updated = context.with_updates(project_memory=missing_memory)

    payload = updated.snapshot_payload()
    assert payload["project_memory"]["value"] == {}
    assert payload["project_memory"]["source_revision"] == "missing"
    assert payload["project_memory"]["fallback"] == "source_missing"
    assert updated.input_hash != context.input_hash


def test_every_section_has_provenance_and_snapshot_is_json_only() -> None:
    context = _build_context(created_at=datetime.now(timezone.utc))
    payload = context.snapshot_payload()
    section_names = (
        "blueprint",
        "outline",
        "chapter_blueprint",
        "chapter_mission",
        "writing_notes",
        "history",
        "project_memory",
        "constitution",
        "writer_persona",
        "foreshadows",
        "plot_threads",
        "character_states",
        "rag",
        "writer_visibility",
    )

    for section_name in section_names:
        section = payload[section_name]
        assert set(section) == {
            "value",
            "source",
            "source_revision",
            "truncated",
            "fallback",
        }
        assert section["source"]
        assert section["source_revision"]
        assert isinstance(section["truncated"], bool)

    assert json.loads(context.snapshot_json()) == payload


def test_generation_adapter_preserves_rag_provenance() -> None:
    context = _build_context(created_at=datetime.now(timezone.utc))
    rag = ContextSection(
        value=ChapterRAGContext(mode="simple", query="旧山道"),
        source=ContextSource.VECTOR_RETRIEVAL,
        source_revision="missing",
        truncated=True,
        fallback=ContextFallback.RETRIEVAL_EMPTY,
    )

    stats = GenerationContextAdapter.to_context(context.with_updates(rag=rag))["rag_stats"]

    assert stats == {
        "mode": "simple",
        "fallback": "retrieval_empty",
        "truncated": True,
        "source_revision": "missing",
        "retrieval_snapshot_id": "missing",
        "chunks": 0,
        "summaries": 0,
        "related_chapters": 0,
    }


def test_representative_pipeline_shadow_has_only_declared_differences() -> None:
    context = _build_context(created_at=datetime.now(timezone.utc))
    generation = GenerationContextAdapter.to_context(context)
    canonical = ReviewContextAdapter.to_prompt_context(context)
    legacy = ReviewContextAdapter.to_legacy_pipeline_context(
        writer_blueprint=generation["writer_blueprint"],
        blueprint=generation["blueprint_dict"],
        chapter_number=context.chapter_number,
        outline_title=generation["outline_title"],
        outline_summary=generation["outline_summary"],
        chapter_mission=generation["chapter_mission"],
        history_context=generation["history_context"],
    )

    report = ChapterContextShadowComparator.compare(
        legacy,
        canonical,
        allowed_prefixes=(
            "active_plot_threads",
            "chapter_blueprint",
            "constitution",
            "pending_foreshadows",
            "previous_chapter.chapter_number",
            "project_memory",
            "related_chapters",
            "writer_persona",
        ),
    )

    assert report["unexplained_count"] == 0


def test_representative_writer_shadow_only_allows_visibility_differences() -> None:
    context = _build_context(created_at=datetime.now(timezone.utc))
    canonical = ReviewContextAdapter.to_prompt_context(context)
    legacy = ReviewContextAdapter.to_legacy_writer_context(context)

    report = ChapterContextShadowComparator.compare(
        legacy,
        canonical,
        allowed_prefixes=WRITER_VISIBILITY_SHADOW_PREFIXES,
    )

    assert report["unexplained_count"] == 0
    assert {item["path"] for item in report["differences"]} == {
        "novel_blueprint.characters",
        "novel_blueprint.full_synopsis",
    }
    assert all(item["allowed"] for item in report["differences"])


def test_legacy_writer_shadow_mapping_is_independent(monkeypatch) -> None:
    context = _build_context(created_at=datetime.now(timezone.utc))

    def fail_if_called(_context):
        raise AssertionError(
            "legacy shadow mapping must not call the canonical review adapter"
        )

    monkeypatch.setattr(ReviewContextAdapter, "to_prompt_context", fail_if_called)

    legacy = ReviewContextAdapter.to_legacy_writer_context(context)

    assert legacy["novel_blueprint"] == context.blueprint.value
    assert legacy["previous_chapter"] == context.history.value.previous_chapter.model_dump(
        mode="json"
    )
    assert legacy["pending_foreshadows"] == context.foreshadows.value


def test_shadow_diff_contains_structure_only() -> None:
    report = ChapterContextShadowComparator.compare(
        {"chapter": {"content": "旧正文", "count": 1}},
        {"chapter": {"content": "新正文", "count": 1}, "new_section": "敏感配置"},
        allowed_prefixes=("new_section",),
    )

    assert report["difference_count"] == 2
    assert report["unexplained_count"] == 1
    serialized = str(report)
    assert "旧正文" not in serialized
    assert "新正文" not in serialized
    assert "敏感配置" not in serialized
