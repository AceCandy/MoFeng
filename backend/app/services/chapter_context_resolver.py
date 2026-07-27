# AIMETA P=章节上下文解析器_统一事实读取入口|R=DB_RAG读取_可见性_预算_降级|NR=不含prompt评审与持久化|E=ChapterContextResolver|X=internal|A=resolver|D=sqlalchemy,pydantic|S=db,net|RD=./README.ai
from __future__ import annotations

import asyncio
import json
import logging
import math
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..models.chapter_blueprint import ChapterBlueprint
from ..models.constitution import NovelConstitution
from ..models.foreshadowing import Foreshadowing
from ..models.memory_layer import CharacterState
from ..models.project_memory import ProjectMemory
from ..models.writer_persona import WriterPersona
from ..repositories.novel_repository import NovelRepository
from ..schemas.chapter_context import (
    MISSING_REVISION,
    ChapterContext,
    ChapterHistory,
    ChapterRAGContext,
    CompletedChapterContext,
    ContextFallback,
    ContextSection,
    ContextSource,
    PreviousChapterContext,
    RAGChunkContext,
    RAGSummaryContext,
    RelatedChapterContext,
    WriterPersonaContext,
    WriterVisibilityContext,
    stable_digest,
    stable_json_dumps,
)
from .knowledge_retrieval_service import KnowledgeRetrievalService
from .llm_service import LLMService
from .vector_store_service import VectorStoreService
from .writer_context_builder import WriterContextBuilder

logger = logging.getLogger(__name__)

_VECTOR_STORE_UNSET = object()


@dataclass(frozen=True)
class ChapterContextPolicy:
    """canonical context v1 的确定性排序与预算策略。"""

    version: str = "chapter-context-policy.v1"
    max_completed_chapters: int = 20
    max_history_summary_chars: int = 1000
    missing_summary_excerpt_chars: int = 800
    previous_tail_chars: int = 500
    max_constitution_chars: int = 6000
    max_persona_chars: int = 4000
    max_memory_summary_chars: int = 4000
    max_timeline_chars: int = 2000
    max_foreshadows: int = 20
    max_foreshadow_content_chars: int = 500
    max_plot_threads: int = 20
    max_character_states: int = 10
    max_rag_chunks: int = 5
    max_rag_summaries: int = 5
    max_rag_query_chars: int = 2000
    max_rag_content_chars: int = 1200
    max_rag_summary_chars: int = 1000
    max_related_chapters: int = 5
    max_related_content_chars: int = 200


@dataclass(frozen=True)
class ChapterContextSources:
    """一次 resolver 读取到的 ORM 来源集合，仅在 resolver 内部流转。"""

    project: Any
    chapter_blueprint: Optional[ChapterBlueprint]
    constitution: Optional[NovelConstitution]
    project_memory: Optional[ProjectMemory]
    writer_persona: Optional[WriterPersona]
    foreshadows: List[Foreshadowing]
    character_states: List[CharacterState]


class ChapterContextResolver:
    """章节上下文唯一解析入口，集中负责读取、可见性、预算和降级。"""

    def __init__(
        self,
        session: AsyncSession,
        *,
        llm_service: Optional[LLMService] = None,
        vector_store: Any = _VECTOR_STORE_UNSET,
        policy: Optional[ChapterContextPolicy] = None,
    ) -> None:
        self.session = session
        self.llm_service = llm_service or LLMService(session)
        self.policy = policy or ChapterContextPolicy()
        self._repo = NovelRepository(session)
        self._visibility_builder = WriterContextBuilder()
        self._vector_store_error = False

        if vector_store is _VECTOR_STORE_UNSET:
            self.vector_store: Optional[VectorStoreService] = None
            if settings.vector_store_enabled:
                try:
                    self.vector_store = VectorStoreService()
                except Exception:
                    self._vector_store_error = True
                    logger.warning("canonical context 初始化向量库失败")
        else:
            self.vector_store = vector_store

    async def resolve(
        self,
        *,
        project_id: str,
        chapter_number: int,
        user_id: int,
        writing_notes: Optional[str] = None,
        chapter_mission: Optional[Dict[str, Any]] = None,
        rag_enabled: bool = False,
        rag_query: Optional[str] = None,
        rag_mode: str = "simple",
        pov_character: Optional[str] = None,
        require_outline: bool = True,
    ) -> ChapterContext:
        sources = await self._load_sources(project_id=project_id, chapter_number=chapter_number)
        full_blueprint = self._build_blueprint_payload(sources.project)
        outline = self._find_outline(sources.project, chapter_number)
        if outline is None and require_outline:
            raise HTTPException(status_code=404, detail="蓝图中未找到对应章节纲要")
        outline_payload = (
            self._build_outline_payload(outline)
            if outline is not None
            else {
                "chapter_number": chapter_number,
                "title": f"第{chapter_number}章",
                "summary": "",
                "goals": "",
                "highlights": [],
                "character_states": {},
                "metadata": {},
            }
        )

        history, history_revisions = self._build_history(
            sources.project,
            chapter_number=chapter_number,
        )
        blueprint_revision = self._record_revision(
            getattr(sources.project, "blueprint", None),
            full_blueprint,
        )
        outline_revision = (
            f"content:{stable_digest(outline_payload)}" if outline is not None else MISSING_REVISION
        )
        chapter_blueprint = self._build_chapter_blueprint_section(sources.chapter_blueprint)
        constitution = self._build_text_section(
            record=sources.constitution,
            value=sources.constitution.to_prompt_context() if sources.constitution else "",
            source=ContextSource.NOVEL_CONSTITUTION,
            limit=self.policy.max_constitution_chars,
        )
        writer_persona = self._build_writer_persona_section(sources.writer_persona)
        project_memory = self._build_project_memory_section(sources.project_memory)
        foreshadows = self._build_foreshadow_section(sources.foreshadows)
        plot_threads = self._build_plot_threads_section(sources.foreshadows)
        character_states = self._build_character_states_section(sources.character_states)
        mission_section = self._build_runtime_dict_section(chapter_mission)
        notes_section = self._build_runtime_text_section(writing_notes)
        visibility = self._build_visibility_section(
            blueprint=full_blueprint,
            history=history,
            outline=outline_payload,
            writing_notes=notes_section.value,
            chapter_mission=mission_section.value,
            blueprint_revision=blueprint_revision,
        )

        source_revision = stable_digest(
            {
                "schema": "chapter-source-revision.v1",
                "project_id": project_id,
                "chapter_number": chapter_number,
                "blueprint": blueprint_revision,
                "outline": outline_revision,
                "chapter_blueprint": chapter_blueprint.source_revision,
                "constitution": constitution.source_revision,
                "writer_persona": writer_persona.source_revision,
                "successful_chapters": history_revisions,
            }
        )
        initial_query, query_truncated = self._normalize_rag_query(rag_query or "")
        initial_rag = self._empty_rag_section(
            mode=rag_mode,
            query=initial_query,
            fallback=ContextFallback.DISABLED,
        )
        if query_truncated:
            initial_rag = initial_rag.model_copy(update={"truncated": True})
        context = ChapterContext(
            project_id=project_id,
            chapter_number=chapter_number,
            source_revision=source_revision,
            policy_version=self.policy.version,
            blueprint=ContextSection(
                value=full_blueprint,
                source=ContextSource.NOVEL_BLUEPRINT,
                source_revision=blueprint_revision,
                fallback=(
                    None
                    if getattr(sources.project, "blueprint", None) is not None
                    else ContextFallback.SOURCE_MISSING
                ),
            ),
            outline=ContextSection(
                value=outline_payload,
                source=ContextSource.CHAPTER_OUTLINE,
                source_revision=outline_revision,
                fallback=None if outline is not None else ContextFallback.SOURCE_MISSING,
            ),
            chapter_blueprint=chapter_blueprint,
            chapter_mission=mission_section,
            writing_notes=notes_section,
            history=history,
            project_memory=project_memory,
            constitution=constitution,
            writer_persona=writer_persona,
            foreshadows=foreshadows,
            plot_threads=plot_threads,
            character_states=character_states,
            rag=initial_rag,
            writer_visibility=visibility,
        )
        if not rag_enabled:
            return context
        return await self.with_retrieval(
            context,
            user_id=user_id,
            enabled=True,
            query_text=rag_query or "",
            mode=rag_mode,
            pov_character=pov_character,
        )

    async def resolve_for_consistency(
        self,
        *,
        project_id: str,
        user_id: int,
        chapter_number: Optional[int] = None,
    ) -> ChapterContext:
        """为兼容未携带章节号的检查 API，在 resolver 内统一推断目标章节。"""
        resolved_number = chapter_number
        if resolved_number is None:
            project = await self._repo.get_by_id(project_id)
            if project is None:
                raise HTTPException(status_code=404, detail="项目不存在")
            known_numbers = [
                item.chapter_number
                for item in (
                    list(getattr(project, "outlines", []) or [])
                    + list(getattr(project, "chapters", []) or [])
                )
            ]
            resolved_number = max(known_numbers, default=1)
        return await self.resolve(
            project_id=project_id,
            chapter_number=resolved_number,
            user_id=user_id,
            rag_enabled=False,
            require_outline=False,
        )

    def with_runtime_inputs(
        self,
        context: ChapterContext,
        *,
        chapter_mission: Optional[Dict[str, Any]] = None,
        writing_notes: Optional[str] = None,
    ) -> ChapterContext:
        """将运行时导演脚本写入快照，并按同一策略重新计算 writer visibility。"""
        mission = (
            self._build_runtime_dict_section(chapter_mission)
            if chapter_mission is not None
            else context.chapter_mission
        )
        notes = (
            self._build_runtime_text_section(writing_notes)
            if writing_notes is not None
            else context.writing_notes
        )
        visibility = self._build_visibility_section(
            blueprint=context.blueprint.value,
            history=context.history,
            outline=context.outline.value,
            writing_notes=notes.value,
            chapter_mission=mission.value,
            blueprint_revision=context.blueprint.source_revision,
        )
        return context.with_updates(
            chapter_mission=mission,
            writing_notes=notes,
            writer_visibility=visibility,
        )

    async def with_retrieval(
        self,
        context: ChapterContext,
        *,
        user_id: int,
        enabled: bool,
        query_text: str,
        mode: str = "simple",
        pov_character: Optional[str] = None,
    ) -> ChapterContext:
        query, query_truncated = self._normalize_rag_query(query_text)
        if not enabled:
            rag = self._empty_rag_section(
                mode=mode,
                query=query,
                fallback=ContextFallback.DISABLED,
            )
        elif not settings.vector_store_enabled or self._vector_store_error or self.vector_store is None:
            rag = self._empty_rag_section(
                mode=mode,
                query=query,
                fallback=ContextFallback.UNAVAILABLE,
            )
        elif mode == "two_stage":
            rag = await self._retrieve_two_stage(
                context,
                user_id=user_id,
                query=query,
                pov_character=pov_character,
            )
        else:
            rag = await self._retrieve_simple(
                context,
                user_id=user_id,
                query=query,
                mode=mode,
            )
        if query_truncated:
            rag = rag.model_copy(update={"truncated": True})
        return context.with_updates(rag=rag)

    def normalize_rag_query(self, query_text: str) -> str:
        """按 canonical policy 规范化检索查询，供恢复逻辑比较冻结输入。"""
        return self._normalize_rag_query(query_text)[0]

    async def _load_sources(
        self,
        *,
        project_id: str,
        chapter_number: int,
    ) -> ChapterContextSources:
        project = await self._repo.get_by_id(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="项目不存在")

        chapter_blueprint = (
            await self.session.execute(
                select(ChapterBlueprint).where(
                    ChapterBlueprint.project_id == project_id,
                    ChapterBlueprint.chapter_number == chapter_number,
                )
            )
        ).scalars().first()
        constitution = (
            await self.session.execute(
                select(NovelConstitution).where(NovelConstitution.project_id == project_id)
            )
        ).scalars().first()
        project_memory = (
            await self.session.execute(
                select(ProjectMemory).where(ProjectMemory.project_id == project_id)
            )
        ).scalars().first()
        writer_persona = (
            await self.session.execute(
                select(WriterPersona)
                .where(
                    WriterPersona.project_id == project_id,
                    WriterPersona.is_active.is_(True),
                )
                .order_by(WriterPersona.updated_at.desc(), WriterPersona.id.desc())
                .limit(1)
            )
        ).scalars().first()
        foreshadows = list(
            (
                await self.session.execute(
                    select(Foreshadowing)
                    .where(
                        Foreshadowing.project_id == project_id,
                        Foreshadowing.chapter_number < chapter_number,
                        Foreshadowing.status.in_(["planted", "developing", "partial"]),
                    )
                    .order_by(Foreshadowing.chapter_number, Foreshadowing.id)
                )
            ).scalars().all()
        )
        character_states = list(
            (
                await self.session.execute(
                    select(CharacterState)
                    .where(
                        CharacterState.project_id == project_id,
                        CharacterState.chapter_number < chapter_number,
                    )
                    .order_by(CharacterState.chapter_number.desc(), CharacterState.id.desc())
                    .limit(self.policy.max_character_states + 1)
                )
            ).scalars().all()
        )
        return ChapterContextSources(
            project=project,
            chapter_blueprint=chapter_blueprint,
            constitution=constitution,
            project_memory=project_memory,
            writer_persona=writer_persona,
            foreshadows=foreshadows,
            character_states=character_states,
        )

    def _build_blueprint_payload(self, project: Any) -> Dict[str, Any]:
        record = getattr(project, "blueprint", None)
        characters = [
            {
                "name": item.name,
                "identity": item.identity,
                "personality": item.personality,
                "goals": item.goals,
                "abilities": item.abilities,
                "relationship_to_protagonist": item.relationship_to_protagonist,
                **(item.extra or {}),
            }
            for item in sorted(
                getattr(project, "characters", []) or [],
                key=lambda value: (getattr(value, "position", 0), getattr(value, "name", "")),
            )
        ]
        relationships = [
            {
                "from": item.character_from,
                "to": item.character_to,
                "description": item.description or "",
                "relationship_type": getattr(item, "relationship_type", None),
            }
            for item in sorted(
                getattr(project, "relationships_", []) or [],
                key=lambda value: (
                    getattr(value, "position", 0),
                    getattr(value, "character_from", ""),
                    getattr(value, "character_to", ""),
                ),
            )
        ]
        outlines = [
            self._build_outline_payload(item)
            for item in sorted(
                getattr(project, "outlines", []) or [],
                key=lambda value: value.chapter_number,
            )
        ]
        return {
            "title": getattr(record, "title", "") or "",
            "target_audience": getattr(record, "target_audience", "") or "",
            "genre": getattr(record, "genre", "") or "",
            "style": getattr(record, "style", "") or "",
            "tone": getattr(record, "tone", "") or "",
            "one_sentence_summary": getattr(record, "one_sentence_summary", "") or "",
            "full_synopsis": getattr(record, "full_synopsis", "") or "",
            "world_setting": self._normalize_json(getattr(record, "world_setting", None) or {}),
            "characters": self._normalize_json(characters),
            "relationships": self._normalize_json(relationships),
            "chapter_outline": outlines,
        }

    @staticmethod
    def _build_outline_payload(outline: Any) -> Dict[str, Any]:
        return {
            "chapter_number": outline.chapter_number,
            "title": outline.title or f"第{outline.chapter_number}章",
            "summary": outline.summary or "",
            "goals": outline.goals or "",
            "highlights": ChapterContextResolver._normalize_json(outline.highlights or []),
            "character_states": ChapterContextResolver._normalize_json(
                outline.character_states or {}
            ),
            "metadata": ChapterContextResolver._normalize_json(
                getattr(outline, "metadata_", None) or {}
            ),
        }

    @staticmethod
    def _find_outline(project: Any, chapter_number: int) -> Optional[Any]:
        return next(
            (
                item
                for item in (getattr(project, "outlines", []) or [])
                if item.chapter_number == chapter_number
            ),
            None,
        )

    def _build_history(
        self,
        project: Any,
        *,
        chapter_number: int,
    ) -> tuple[ContextSection[ChapterHistory], List[Dict[str, Any]]]:
        outlines = {
            item.chapter_number: item for item in (getattr(project, "outlines", []) or [])
        }
        candidates = []
        revisions = []
        summary_missing = False
        text_truncated = False
        prior_successful_count = 0
        for chapter in sorted(
            getattr(project, "chapters", []) or [],
            key=lambda value: value.chapter_number,
        ):
            if chapter.chapter_number >= chapter_number or chapter.status != "successful":
                continue
            prior_successful_count += 1
            selected = getattr(chapter, "selected_version", None)
            selected_content = (getattr(selected, "content", None) or "").strip()
            if selected is None or not selected_content:
                continue
            summary = (chapter.real_summary or "").strip()
            if not summary:
                summary_missing = True
                summary, was_truncated = self._truncate_text(
                    selected_content,
                    self.policy.missing_summary_excerpt_chars,
                )
            else:
                summary, was_truncated = self._truncate_text(
                    summary,
                    self.policy.max_history_summary_chars,
                )
            revisions.append(
                {
                    "chapter_number": chapter.chapter_number,
                    "selected_version_id": chapter.selected_version_id,
                    "selected_version_created_at": self._datetime_value(
                        selected.created_at
                    ),
                    "selected_content_hash": stable_digest(selected_content),
                    "real_summary_hash": stable_digest(
                        (chapter.real_summary or "").strip()
                    ),
                }
            )
            text_truncated = text_truncated or was_truncated
            outline = outlines.get(chapter.chapter_number)
            candidates.append(
                {
                    "chapter": chapter,
                    "selected": selected,
                    "summary": summary,
                    "title": (
                        outline.title
                        if outline is not None and outline.title
                        else f"第{chapter.chapter_number}章"
                    ),
                }
            )

        completed_limit = max(0, self.policy.max_completed_chapters)
        list_truncated = len(candidates) > completed_limit
        selected_candidates = candidates[-completed_limit:] if completed_limit else []
        completed = [
            CompletedChapterContext(
                chapter_number=item["chapter"].chapter_number,
                title=item["title"],
                summary=item["summary"],
            )
            for item in selected_candidates
        ]
        previous = PreviousChapterContext()
        if candidates:
            latest = candidates[-1]
            tail, tail_truncated = self._truncate_text(
                latest["selected"].content,
                self.policy.previous_tail_chars,
                from_end=True,
            )
            text_truncated = text_truncated or tail_truncated
            previous = PreviousChapterContext(
                chapter_number=latest["chapter"].chapter_number,
                summary=latest["summary"],
                tail_excerpt=tail,
            )

        truncated = list_truncated or text_truncated
        fallback: Optional[ContextFallback]
        if truncated:
            fallback = ContextFallback.BUDGET_TRUNCATED
        elif summary_missing:
            fallback = ContextFallback.SUMMARY_MISSING
        elif not candidates and chapter_number <= 1:
            fallback = ContextFallback.FIRST_CHAPTER
        elif not candidates and prior_successful_count:
            fallback = ContextFallback.SOURCE_MISSING
        elif not candidates:
            fallback = ContextFallback.FIRST_CHAPTER
        else:
            fallback = None
        revision = f"history:{stable_digest(revisions)}" if revisions else MISSING_REVISION
        return (
            ContextSection(
                value=ChapterHistory(
                    previous_chapter=previous,
                    completed_chapters=completed,
                ),
                source=ContextSource.CHAPTER_HISTORY,
                source_revision=revision,
                truncated=truncated,
                fallback=fallback,
            ),
            revisions,
        )

    def _build_chapter_blueprint_section(
        self,
        record: Optional[ChapterBlueprint],
    ) -> ContextSection[Dict[str, Any]]:
        if record is None:
            return ContextSection(
                value={},
                source=ContextSource.CHAPTER_BLUEPRINT,
                source_revision=MISSING_REVISION,
                fallback=ContextFallback.SOURCE_MISSING,
            )
        value = {
            "chapter_number": record.chapter_number,
            "suspense_density": record.suspense_density,
            "foreshadowing_ops": record.foreshadowing_ops,
            "cognitive_twist_level": record.cognitive_twist_level,
            "chapter_function": record.chapter_function,
            "chapter_focus": record.chapter_focus,
            "suspense_type": record.suspense_type,
            "emotional_arc": record.emotional_arc,
            "involved_foreshadowings": self._normalize_json(
                record.involved_foreshadowings or []
            ),
            "mission_constraints": self._normalize_json(record.mission_constraints or {}),
            "brief_summary": record.brief_summary or "",
            "director_script": record.director_script or "",
            "beat_sheet": self._normalize_json(record.beat_sheet or {}),
        }
        return ContextSection(
            value=value,
            source=ContextSource.CHAPTER_BLUEPRINT,
            source_revision=self._record_revision(record, value),
        )

    def _build_project_memory_section(
        self,
        record: Optional[ProjectMemory],
    ) -> ContextSection[Dict[str, Any]]:
        if record is None:
            return ContextSection(
                value={},
                source=ContextSource.PROJECT_MEMORY,
                source_revision=MISSING_REVISION,
                fallback=ContextFallback.SOURCE_MISSING,
            )
        summary, summary_truncated = self._truncate_text(
            record.global_summary or "",
            self.policy.max_memory_summary_chars,
        )
        timeline, timeline_truncated = self._truncate_text(
            record.story_timeline_summary or "",
            self.policy.max_timeline_chars,
        )
        version = getattr(record, "version", None)
        return ContextSection(
            value={
                "global_summary": summary,
                "plot_arcs": self._normalize_json(record.plot_arcs or {}),
                "story_timeline_summary": timeline,
                "last_updated_chapter": record.last_updated_chapter,
            },
            source=ContextSource.PROJECT_MEMORY,
            source_revision=f"projection:{version}" if version is not None else "unknown",
            truncated=summary_truncated or timeline_truncated,
            fallback=(
                ContextFallback.BUDGET_TRUNCATED
                if summary_truncated or timeline_truncated
                else None
            ),
        )

    def _build_writer_persona_section(
        self,
        record: Optional[WriterPersona],
    ) -> ContextSection[WriterPersonaContext]:
        if record is None:
            return ContextSection(
                value=WriterPersonaContext(),
                source=ContextSource.WRITER_PERSONA,
                source_revision=MISSING_REVISION,
                fallback=ContextFallback.SOURCE_MISSING,
            )
        prompt_context, truncated = self._truncate_text(
            record.to_prompt_context(),
            self.policy.max_persona_chars,
        )
        value = WriterPersonaContext(
            prompt_context=prompt_context,
            name=record.name or "",
            catchphrases=self._normalize_json(record.catchphrases or []),
            imperfection_patterns=self._normalize_json(record.imperfection_patterns or []),
            avoid_patterns=self._normalize_json(record.avoid_patterns or []),
        )
        return ContextSection(
            value=value,
            source=ContextSource.WRITER_PERSONA,
            source_revision=self._record_revision(record, value.model_dump(mode="json")),
            truncated=truncated,
            fallback=ContextFallback.BUDGET_TRUNCATED if truncated else None,
        )

    def _build_text_section(
        self,
        *,
        record: Any,
        value: str,
        source: ContextSource,
        limit: int,
    ) -> ContextSection[str]:
        if record is None:
            return ContextSection(
                value="",
                source=source,
                source_revision=MISSING_REVISION,
                fallback=ContextFallback.SOURCE_MISSING,
            )
        resolved, truncated = self._truncate_text(value, limit)
        return ContextSection(
            value=resolved,
            source=source,
            source_revision=self._record_revision(record, resolved),
            truncated=truncated,
            fallback=ContextFallback.BUDGET_TRUNCATED if truncated else None,
        )

    def _build_foreshadow_section(
        self,
        records: List[Foreshadowing],
    ) -> ContextSection[List[Dict[str, Any]]]:
        list_truncated = len(records) > self.policy.max_foreshadows
        values = []
        text_truncated = False
        for record in records[: self.policy.max_foreshadows]:
            content, truncated = self._truncate_text(
                record.content or "",
                self.policy.max_foreshadow_content_chars,
            )
            text_truncated = text_truncated or truncated
            values.append(
                {
                    "id": record.id,
                    "chapter_number": record.chapter_number,
                    "content": content,
                    "type": record.type,
                    "keywords": self._normalize_json(record.keywords or []),
                    "status": record.status,
                    "importance": record.importance,
                    "target_reveal_chapter": record.target_reveal_chapter,
                    "related_plots": self._normalize_json(record.related_plots or []),
                    "name": getattr(record, "name", None),
                    "urgency": getattr(record, "urgency", None),
                }
            )
        revision = self._collection_revision(records, values)
        truncated = list_truncated or text_truncated
        return ContextSection(
            value=values,
            source=ContextSource.FORESHADOWING,
            source_revision=revision,
            truncated=truncated,
            fallback=(
                ContextFallback.BUDGET_TRUNCATED
                if truncated
                else ContextFallback.SOURCE_MISSING if not values else None
            ),
        )

    def _build_plot_threads_section(
        self,
        records: List[Foreshadowing],
    ) -> ContextSection[List[Dict[str, Any]]]:
        grouped: Dict[str, Dict[str, Any]] = {}
        for record in records:
            for name in sorted(set(record.related_plots or [])):
                current = grouped.setdefault(
                    name,
                    {
                        "thread_name": name,
                        "status": "ongoing",
                        "last_mentioned_chapter": record.chapter_number,
                        "foreshadow_count": 0,
                    },
                )
                current["last_mentioned_chapter"] = max(
                    current["last_mentioned_chapter"],
                    record.chapter_number,
                )
                current["foreshadow_count"] += 1
        values = [grouped[name] for name in sorted(grouped)]
        truncated = len(values) > self.policy.max_plot_threads
        values = values[: self.policy.max_plot_threads]
        return ContextSection(
            value=values,
            source=ContextSource.FORESHADOWING,
            source_revision=self._collection_revision(records, values),
            truncated=truncated,
            fallback=(
                ContextFallback.BUDGET_TRUNCATED
                if truncated
                else ContextFallback.SOURCE_MISSING if not values else None
            ),
        )

    def _build_character_states_section(
        self,
        records: List[CharacterState],
    ) -> ContextSection[List[Dict[str, Any]]]:
        truncated = len(records) > self.policy.max_character_states
        values = []
        for record in records[: self.policy.max_character_states]:
            extra = record.extra or {}
            values.append(
                {
                    "id": record.id,
                    "chapter_number": record.chapter_number,
                    "character_name": record.character_name,
                    "location": record.location,
                    "emotion": record.emotion,
                    "health_status": record.health_status,
                    "current_goals": self._normalize_json(record.current_goals or []),
                    "raw_state_text": extra.get("raw_state_text", ""),
                }
            )
        return ContextSection(
            value=values,
            source=ContextSource.CHARACTER_STATE,
            source_revision=self._collection_revision(records, values),
            truncated=truncated,
            fallback=(
                ContextFallback.BUDGET_TRUNCATED
                if truncated
                else ContextFallback.SOURCE_MISSING if not values else None
            ),
        )

    def _build_runtime_dict_section(
        self,
        value: Optional[Dict[str, Any]],
    ) -> ContextSection[Dict[str, Any]]:
        normalized = self._normalize_json(value or {})
        return ContextSection(
            value=normalized,
            source=ContextSource.RUNTIME_INPUT,
            source_revision=(
                f"runtime:{stable_digest(normalized)}" if normalized else MISSING_REVISION
            ),
            fallback=None if normalized else ContextFallback.NOT_PROVIDED,
        )

    def _build_runtime_text_section(self, value: Optional[str]) -> ContextSection[str]:
        normalized = (value or "").strip()
        return ContextSection(
            value=normalized,
            source=ContextSource.RUNTIME_INPUT,
            source_revision=(
                f"runtime:{stable_digest(normalized)}" if normalized else MISSING_REVISION
            ),
            fallback=None if normalized else ContextFallback.NOT_PROVIDED,
        )

    def _build_visibility_section(
        self,
        *,
        blueprint: Dict[str, Any],
        history: ContextSection[ChapterHistory],
        outline: Dict[str, Any],
        writing_notes: str,
        chapter_mission: Dict[str, Any],
        blueprint_revision: str,
    ) -> ContextSection[WriterVisibilityContext]:
        completed_summaries = [item.summary for item in history.value.completed_chapters]
        visible = self._visibility_builder.build_visibility_context(
            blueprint=deepcopy(blueprint),
            completed_summaries=completed_summaries,
            previous_tail=history.value.previous_chapter.tail_excerpt,
            outline_title=outline.get("title", ""),
            outline_summary=outline.get("summary", ""),
            writing_notes=writing_notes,
            allowed_new_characters=chapter_mission.get("allowed_new_characters") or [],
        )
        value = WriterVisibilityContext(
            writer_blueprint=self._normalize_json(visible["writer_blueprint"]),
            introduced_characters=visible["introduced_characters"],
            planned_characters=visible["planned_characters"],
            allowed_characters=visible["allowed_characters"],
            forbidden_characters=visible["forbidden_characters"],
        )
        revision = stable_digest(
            {
                "policy": self.policy.version,
                "blueprint": blueprint_revision,
                "history": history.source_revision,
                "outline": outline,
                "writing_notes": writing_notes,
                "chapter_mission": chapter_mission,
            }
        )
        return ContextSection(
            value=value,
            source=ContextSource.VISIBILITY_POLICY,
            source_revision=f"visibility:{revision}",
        )

    async def _retrieve_simple(
        self,
        context: ChapterContext,
        *,
        user_id: int,
        query: str,
        mode: str,
    ) -> ContextSection[ChapterRAGContext]:
        if not query:
            return self._empty_rag_section(
                mode=mode,
                query=query,
                fallback=ContextFallback.QUERY_EMPTY,
            )
        try:
            embedding = await self.llm_service.get_embedding(
                query,
                user_id=user_id,
                stage="rag_embedding",
            )
        except Exception:
            logger.warning("canonical context 生成 RAG embedding 失败")
            return self._empty_rag_section(
                mode=mode,
                query=query,
                fallback=ContextFallback.EMBEDDING_FAILED,
            )
        if not embedding:
            return self._empty_rag_section(
                mode=mode,
                query=query,
                fallback=ContextFallback.EMBEDDING_FAILED,
            )

        try:
            raw_chunks, raw_summaries = await asyncio.gather(
                self.vector_store.query_chunks(
                    project_id=context.project_id,
                    embedding=embedding,
                    top_k=self.policy.max_rag_chunks,
                ),
                self.vector_store.query_summaries(
                    project_id=context.project_id,
                    embedding=embedding,
                    top_k=self.policy.max_rag_summaries,
                ),
            )
        except Exception:
            logger.warning("canonical context 查询 RAG snapshot 失败")
            return self._empty_rag_section(
                mode=mode,
                query=query,
                fallback=ContextFallback.RETRIEVAL_FAILED,
            )

        chunks = []
        truncated = False
        for rank, item in enumerate(raw_chunks, start=1):
            if item.chapter_number >= context.chapter_number:
                continue
            content, content_truncated = self._truncate_text(
                item.content or "",
                self.policy.max_rag_content_chars,
            )
            truncated = truncated or content_truncated
            chunks.append(
                RAGChunkContext(
                    chapter_number=item.chapter_number,
                    title=item.chapter_title or f"第{item.chapter_number}章",
                    content=content,
                    score=self._safe_score(item.score),
                    rank=rank,
                    metadata=self._normalize_json(item.metadata or {}),
                )
            )
        summaries = []
        for rank, item in enumerate(raw_summaries, start=1):
            if item.chapter_number >= context.chapter_number:
                continue
            summary, summary_truncated = self._truncate_text(
                item.summary or "",
                self.policy.max_rag_summary_chars,
            )
            truncated = truncated or summary_truncated
            summaries.append(
                RAGSummaryContext(
                    chapter_number=item.chapter_number,
                    title=item.title or f"第{item.chapter_number}章",
                    summary=summary,
                    score=self._safe_score(item.score),
                    rank=rank,
                )
            )
        related = self._merge_related_chapters(chunks, summaries)
        value_payload = {
            "mode": mode,
            "query": query,
            "chunks": [item.model_dump(mode="json") for item in chunks],
            "summaries": [item.model_dump(mode="json") for item in summaries],
            "related_chapters": [item.model_dump(mode="json") for item in related],
            "knowledge_context": "",
            "stats": {
                "mode": mode,
                "chunks": len(chunks),
                "summaries": len(summaries),
            },
        }
        snapshot_id = stable_digest(value_payload)
        value = ChapterRAGContext(
            **value_payload,
            retrieval_snapshot_id=snapshot_id,
        )
        empty = not chunks and not summaries
        return ContextSection(
            value=value,
            source=ContextSource.VECTOR_RETRIEVAL,
            source_revision=f"retrieval:{snapshot_id}",
            truncated=truncated,
            fallback=(
                ContextFallback.RETRIEVAL_EMPTY
                if empty
                else ContextFallback.BUDGET_TRUNCATED if truncated else None
            ),
        )

    async def _retrieve_two_stage(
        self,
        context: ChapterContext,
        *,
        user_id: int,
        query: str,
        pov_character: Optional[str],
    ) -> ContextSection[ChapterRAGContext]:
        try:
            service = KnowledgeRetrievalService(
                self.session,
                self.llm_service,
                self.vector_store,
            )
            filtered = await service.retrieve_and_filter(
                project_id=context.project_id,
                chapter_number=context.chapter_number,
                user_id=user_id,
                pov_character=pov_character,
                user_guidance=context.writing_notes.value,
                top_k=settings.vector_top_k_chunks,
                chapter_blueprint=context.chapter_blueprint.value,
                global_summary=str(
                    context.project_memory.value.get("global_summary") or ""
                ),
            )
        except Exception:
            logger.warning("canonical context 两阶段 RAG 失败")
            return self._empty_rag_section(
                mode="two_stage",
                query=query,
                fallback=ContextFallback.RETRIEVAL_FAILED,
            )
        knowledge_context, context_truncated = self._truncate_text(
            self._format_filtered_context(filtered),
            self.policy.max_rag_content_chars * self.policy.max_rag_chunks,
        )
        stats = self._normalize_json(filtered.stats or {})
        stats["mode"] = "two_stage"
        payload = {
            "mode": "two_stage",
            "query": query,
            "chunks": [],
            "summaries": [],
            "related_chapters": [],
            "knowledge_context": knowledge_context,
            "stats": stats,
        }
        snapshot_id = stable_digest(payload)
        value = ChapterRAGContext(**payload, retrieval_snapshot_id=snapshot_id)
        empty = not any(
            (
                filtered.plot_fuel,
                filtered.character_info,
                filtered.world_fragments,
                filtered.narrative_techniques,
                filtered.warnings,
            )
        )
        return ContextSection(
            value=value,
            source=ContextSource.VECTOR_RETRIEVAL,
            source_revision=f"retrieval:{snapshot_id}",
            truncated=context_truncated,
            fallback=(
                ContextFallback.RETRIEVAL_EMPTY
                if empty
                else ContextFallback.BUDGET_TRUNCATED if context_truncated else None
            ),
        )

    def _empty_rag_section(
        self,
        *,
        mode: str,
        query: str,
        fallback: ContextFallback,
    ) -> ContextSection[ChapterRAGContext]:
        return ContextSection(
            value=ChapterRAGContext(
                mode=mode,
                query=query,
                stats={"mode": mode, "fallback": fallback.value},
            ),
            source=ContextSource.VECTOR_RETRIEVAL,
            source_revision=MISSING_REVISION,
            fallback=fallback,
        )

    def _merge_related_chapters(
        self,
        chunks: List[RAGChunkContext],
        summaries: List[RAGSummaryContext],
    ) -> List[RelatedChapterContext]:
        merged: Dict[int, Dict[str, Any]] = {}
        for item in chunks:
            current = merged.setdefault(
                item.chapter_number,
                {
                    "chapter_number": item.chapter_number,
                    "title": item.title,
                    "summary": "",
                    "relevance_score": item.score,
                    "matched_content": item.content[: self.policy.max_related_content_chars],
                },
            )
            current["relevance_score"] = max(current["relevance_score"], item.score)
        for item in summaries:
            current = merged.setdefault(
                item.chapter_number,
                {
                    "chapter_number": item.chapter_number,
                    "title": item.title,
                    "summary": "",
                    "relevance_score": item.score,
                    "matched_content": "",
                },
            )
            current["summary"] = item.summary
            current["relevance_score"] = max(current["relevance_score"], item.score)
        ordered = sorted(
            merged.values(),
            key=lambda item: (-item["relevance_score"], item["chapter_number"]),
        )[: self.policy.max_related_chapters]
        return [RelatedChapterContext(**item) for item in ordered]

    @staticmethod
    def _format_filtered_context(filtered: Any) -> str:
        sections = []
        for title, values in (
            ("情节燃料", filtered.plot_fuel),
            ("人物维度", filtered.character_info),
            ("世界碎片", filtered.world_fragments),
            ("叙事技法", filtered.narrative_techniques),
            ("冲突警告", filtered.warnings),
        ):
            if values:
                sections.append(f"## {title}\n" + "\n".join(f"- {item}" for item in values))
        return "\n\n".join(sections) or "（未检索到有效上下文）"

    @staticmethod
    def _record_revision(record: Any, value: Any) -> str:
        if record is None:
            return MISSING_REVISION
        return "record:" + stable_digest(
            {
                "updated_at": ChapterContextResolver._datetime_value(
                    getattr(record, "updated_at", None)
                ),
                "value": value,
            }
        )

    @staticmethod
    def _collection_revision(records: List[Any], value: Any) -> str:
        if not records:
            return MISSING_REVISION
        return "collection:" + stable_digest(
            {
                "records": [
                    {
                        "id": getattr(item, "id", None),
                        "updated_at": ChapterContextResolver._datetime_value(
                            getattr(item, "updated_at", None)
                        ),
                    }
                    for item in records
                ],
                "value": value,
            }
        )

    @staticmethod
    def _datetime_value(value: Optional[datetime]) -> Optional[str]:
        if value is None:
            return None
        if value.tzinfo is not None and value.utcoffset() is not None:
            value = value.astimezone(timezone.utc)
            return value.isoformat().replace("+00:00", "Z")
        return value.isoformat()

    @staticmethod
    def _truncate_text(text: str, limit: int, *, from_end: bool = False) -> tuple[str, bool]:
        normalized = (text or "").strip()
        if limit <= 0:
            return "", bool(normalized)
        if len(normalized) <= limit:
            return normalized, False
        return (normalized[-limit:] if from_end else normalized[:limit]), True

    @staticmethod
    def _normalize_text(value: str) -> str:
        return " ".join((value or "").split())

    def _normalize_rag_query(self, value: str) -> tuple[str, bool]:
        return self._truncate_text(
            self._normalize_text(value),
            self.policy.max_rag_query_chars,
        )

    @staticmethod
    def _safe_score(value: Any) -> float:
        score = float(value)
        return round(score, 8) if math.isfinite(score) else 0.0

    @staticmethod
    def _normalize_json(value: Any) -> Any:
        if value is None or isinstance(value, (str, int, bool)):
            return value
        if isinstance(value, float):
            return value if math.isfinite(value) else 0.0
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, dict):
            return {
                str(key): ChapterContextResolver._normalize_json(item)
                for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            }
        if isinstance(value, (list, tuple)):
            return [ChapterContextResolver._normalize_json(item) for item in value]
        if isinstance(value, (set, frozenset)):
            normalized = [ChapterContextResolver._normalize_json(item) for item in value]
            return sorted(normalized, key=stable_json_dumps)
        return str(value)


__all__ = [
    "ChapterContextPolicy",
    "ChapterContextResolver",
    "ChapterContextSources",
]
