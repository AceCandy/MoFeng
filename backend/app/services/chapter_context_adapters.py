# AIMETA P=章节上下文适配器_下游视图映射|R=生成_评审_一致性纯转换|NR=不含DB与网络读取|E=GenerationContextAdapter,ReviewContextAdapter,ConsistencyContextAdapter|X=internal|A=adapter|D=pydantic|S=memory|RD=./README.ai
from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Union

from ..schemas.chapter_context import ChapterContext


ContextInput = Union[ChapterContext, Dict[str, Any]]

WRITER_VISIBILITY_SHADOW_PREFIXES = (
    "novel_blueprint.chapter_dialogues",
    "novel_blueprint.chapter_details",
    "novel_blueprint.chapter_events",
    "novel_blueprint.chapter_outline",
    "novel_blueprint.chapter_summaries",
    "novel_blueprint.character_timelines",
    "novel_blueprint.characters",
    "novel_blueprint.conversation_history",
    "novel_blueprint.full_synopsis",
    "novel_blueprint.one_sentence_summary",
    "novel_blueprint.relationships",
)


def _coerce_context(context: ContextInput) -> ChapterContext:
    if isinstance(context, ChapterContext):
        return context
    return ChapterContext.model_validate(context)


class GenerationContextAdapter:
    """将 canonical context 映射为现有生成流水线的纯数据视图。"""

    @staticmethod
    def to_context(context: ContextInput) -> Dict[str, Any]:
        canonical = _coerce_context(context)
        history = canonical.history.value
        visibility = canonical.writer_visibility.value
        rag = canonical.rag.value

        rag_chunks = [
            f"### Chunk {index}(来源：{item.title})\n{item.content.strip()}"
            for index, item in enumerate(rag.chunks, start=1)
        ]
        rag_summaries = [
            f"- 第{item.chapter_number}章 - {item.title}:{item.summary.strip()}"
            for item in rag.summaries
        ]

        memory = canonical.project_memory.value
        memory_parts = []
        if memory.get("global_summary"):
            memory_parts.append(f"### 全局摘要\n{memory['global_summary']}")
        if memory.get("plot_arcs"):
            memory_parts.append(
                "### 剧情线追踪\n"
                + json.dumps(memory["plot_arcs"], ensure_ascii=False, sort_keys=True, indent=2)
            )

        previous = history.previous_chapter.model_dump(mode="json")
        completed = [item.model_dump(mode="json") for item in history.completed_chapters]
        outline = canonical.outline.value
        mission = canonical.chapter_mission.value
        rag_stats = dict(rag.stats)
        rag_stats.update(
            {
                "mode": rag.mode,
                "fallback": (
                    canonical.rag.fallback.value if canonical.rag.fallback is not None else None
                ),
                "truncated": canonical.rag.truncated,
                "source_revision": canonical.rag.source_revision,
                "retrieval_snapshot_id": rag.retrieval_snapshot_id,
                "chunks": len(rag.chunks),
                "summaries": len(rag.summaries),
                "related_chapters": len(rag.related_chapters),
            }
        )
        return {
            "blueprint_dict": canonical.blueprint.value,
            "writer_blueprint": visibility.writer_blueprint,
            "all_characters": sorted(
                character.get("name")
                for character in canonical.blueprint.value.get("characters", [])
                if isinstance(character, dict) and character.get("name")
            ),
            "chapter_outline": outline,
            "outline_title": outline.get("title") or f"第{canonical.chapter_number}章",
            "outline_summary": outline.get("summary") or "",
            "chapter_mission": mission,
            "writing_notes": canonical.writing_notes.value,
            "previous_chapter": previous,
            "completed_chapters": completed,
            "history_context": {
                "previous_summary": previous.get("summary") or "暂无（这是第一章）",
                "previous_tail": previous.get("tail_excerpt") or "暂无（这是第一章）",
                "completed_chapters": completed,
                "completed_summaries": [item.get("summary", "") for item in completed],
                "model_calls": [],
                "trace_metrics": {
                    "usable_previous_chapters": len(completed),
                    "summary_model_call_count": 0,
                },
            },
            "visibility_context": visibility.model_dump(mode="json"),
            "introduced_characters": visibility.introduced_characters,
            "allowed_characters": visibility.allowed_characters,
            "forbidden_characters": visibility.forbidden_characters,
            "rag_context": {"chunks": rag_chunks, "summaries": rag_summaries},
            "knowledge_context": rag.knowledge_context or None,
            "rag_stats": rag_stats,
            "project_memory_text": "\n\n".join(memory_parts) or None,
        }


class ReviewContextAdapter:
    """生成 AIReviewService 已有 prompt contract，不执行任何读取。"""

    @staticmethod
    def to_prompt_context(context: ContextInput) -> Dict[str, Any]:
        canonical = _coerce_context(context)
        generation = GenerationContextAdapter.to_context(canonical)
        return {
            "novel_blueprint": generation["writer_blueprint"],
            "chapter_outline": canonical.outline.value,
            "chapter_blueprint": canonical.chapter_blueprint.value,
            "chapter_mission": canonical.chapter_mission.value,
            "project_memory": canonical.project_memory.value,
            "constitution": canonical.constitution.value,
            "writer_persona": canonical.writer_persona.value.prompt_context,
            "previous_chapter": generation["previous_chapter"],
            "completed_chapters": generation["completed_chapters"],
            "pending_foreshadows": canonical.foreshadows.value,
            "related_chapters": [
                item.model_dump(mode="json") for item in canonical.rag.value.related_chapters
            ],
            "active_plot_threads": canonical.plot_threads.value,
        }

    @staticmethod
    def to_legacy_pipeline_context(
        *,
        writer_blueprint: Dict[str, Any],
        blueprint: Dict[str, Any],
        chapter_number: int,
        outline_title: str,
        outline_summary: str,
        chapter_mission: Dict[str, Any],
        history_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """仅供 shadow compare 使用的旧 pipeline 结构，不读取任何来源。"""
        return {
            "novel_blueprint": writer_blueprint or blueprint,
            "chapter_outline": {
                "chapter_number": chapter_number,
                "title": outline_title,
                "summary": outline_summary,
            },
            "chapter_mission": chapter_mission or {},
            "previous_chapter": {
                "summary": history_context.get("previous_summary", ""),
                "tail_excerpt": history_context.get("previous_tail", ""),
            },
            "completed_chapters": history_context.get("completed_chapters", []),
        }

    @staticmethod
    def to_legacy_writer_context(context: ContextInput) -> Dict[str, Any]:
        """独立重建旧 writer contract，避免 shadow oracle 依赖新 adapter。"""
        canonical = _coerce_context(context)
        history = canonical.history.value
        return {
            "novel_blueprint": canonical.blueprint.value,
            "chapter_outline": canonical.outline.value,
            "chapter_blueprint": canonical.chapter_blueprint.value,
            "chapter_mission": canonical.chapter_mission.value,
            "project_memory": canonical.project_memory.value,
            "constitution": canonical.constitution.value,
            "writer_persona": canonical.writer_persona.value.prompt_context,
            "previous_chapter": history.previous_chapter.model_dump(mode="json"),
            "completed_chapters": [
                item.model_dump(mode="json") for item in history.completed_chapters
            ],
            "pending_foreshadows": canonical.foreshadows.value,
            "related_chapters": [
                item.model_dump(mode="json") for item in canonical.rag.value.related_chapters
            ],
            "active_plot_threads": canonical.plot_threads.value,
        }


class ChapterContextShadowComparator:
    """比较 prompt contract，但只返回结构元数据，禁止暴露实际值。"""

    @classmethod
    def compare(
        cls,
        legacy: Dict[str, Any],
        canonical: Dict[str, Any],
        *,
        allowed_prefixes: Iterable[str] = (),
    ) -> Dict[str, Any]:
        allowed = tuple(allowed_prefixes)
        differences: List[Dict[str, Any]] = []
        cls._walk(legacy, canonical, path="", allowed=allowed, output=differences)
        return {
            "difference_count": len(differences),
            "unexplained_count": sum(not item["allowed"] for item in differences),
            "differences": differences,
        }

    @classmethod
    def _walk(
        cls,
        legacy: Any,
        canonical: Any,
        *,
        path: str,
        allowed: tuple[str, ...],
        output: List[Dict[str, Any]],
    ) -> None:
        if isinstance(legacy, dict) and isinstance(canonical, dict):
            for key in sorted(set(legacy) | set(canonical)):
                child_path = f"{path}.{key}" if path else str(key)
                if key not in legacy:
                    cls._append(output, child_path, "canonical_only", None, canonical[key], allowed)
                elif key not in canonical:
                    cls._append(output, child_path, "legacy_only", legacy[key], None, allowed)
                else:
                    cls._walk(
                        legacy[key],
                        canonical[key],
                        path=child_path,
                        allowed=allowed,
                        output=output,
                    )
            return
        if legacy == canonical:
            return
        kind = "list_changed" if isinstance(legacy, list) and isinstance(canonical, list) else "value_changed"
        cls._append(output, path or "$", kind, legacy, canonical, allowed)

    @staticmethod
    def _append(
        output: List[Dict[str, Any]],
        path: str,
        kind: str,
        legacy: Any,
        canonical: Any,
        allowed: tuple[str, ...],
    ) -> None:
        item = {
            "path": path,
            "kind": kind,
            "legacy_type": type(legacy).__name__ if legacy is not None else None,
            "canonical_type": type(canonical).__name__ if canonical is not None else None,
            "allowed": any(path == prefix or path.startswith(f"{prefix}.") for prefix in allowed),
        }
        if isinstance(legacy, (list, dict)):
            item["legacy_size"] = len(legacy)
        if isinstance(canonical, (list, dict)):
            item["canonical_size"] = len(canonical)
        output.append(item)


class ConsistencyContextAdapter:
    """生成 ConsistencyService 的文本输入视图。"""

    @staticmethod
    def to_prompt_context(
        context: ContextInput,
        *,
        include_foreshadowing: bool = True,
    ) -> Dict[str, str]:
        canonical = _coerce_context(context)
        blueprint = canonical.blueprint.value
        setting_parts = []
        if blueprint.get("genre"):
            setting_parts.append(f"类型: {blueprint['genre']}")
        if blueprint.get("style"):
            setting_parts.append(f"风格: {blueprint['style']}")
        if blueprint.get("world_setting"):
            setting_parts.append(
                "世界观: "
                + json.dumps(
                    blueprint["world_setting"],
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
        if blueprint.get("full_synopsis"):
            setting_parts.append(f"故事概要: {blueprint['full_synopsis']}")

        memory = canonical.project_memory.value
        plot_parts = []
        if memory.get("plot_arcs"):
            plot_parts.append(
                json.dumps(memory["plot_arcs"], ensure_ascii=False, sort_keys=True, indent=2)
            )
        if include_foreshadowing and canonical.foreshadows.value:
            plot_parts.append(
                "待回收伏笔:\n"
                + "\n".join(
                    f"- 第{item.get('chapter_number', '?')}章埋设: {item.get('content', '')}"
                    for item in canonical.foreshadows.value
                )
            )

        state_text = ""
        for state in canonical.character_states.value:
            raw_text = state.get("raw_state_text")
            if raw_text:
                state_text = str(raw_text)
                break
        if not state_text and canonical.character_states.value:
            state_text = json.dumps(
                canonical.character_states.value,
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )

        return {
            "novel_setting": "\n".join(setting_parts) or "（未设定）",
            "character_state": state_text or "（未记录）",
            "global_summary": memory.get("global_summary") or "（无前文摘要）",
            "plot_arcs": "\n\n".join(plot_parts) or "（无剧情线记录）",
        }


__all__ = [
    "ChapterContextShadowComparator",
    "ConsistencyContextAdapter",
    "GenerationContextAdapter",
    "ReviewContextAdapter",
    "WRITER_VISIBILITY_SHADOW_PREFIXES",
]
