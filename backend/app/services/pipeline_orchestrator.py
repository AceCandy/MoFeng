# AIMETA P=写作流水线编排_统一生成入口|R=上下文汇聚_生成_审查_优化|NR=不含API路由|E=PipelineOrchestrator|X=internal|A=编排器|D=fastapi,sqlalchemy|S=db,net|RD=./README.ai
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, TypedDict

from fastapi import HTTPException
from langgraph.graph import END, START, StateGraph
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..models.novel import Chapter
from ..models.project_memory import ProjectMemory
from ..repositories.system_config_repository import SystemConfigRepository
from ..services.ai_review_service import AIReviewService
from ..services.chapter_context_service import ChapterContextService
from ..services.chapter_guardrails import ChapterGuardrails
from ..services.chapter_word_count_settings import (
    build_word_count_requirement_text,
    count_chapter_words,
    resolve_word_count_requirements,
    should_compress_chapter,
)
from ..services.consistency_service import ConsistencyService, ViolationSeverity
from ..services.enhanced_writing_flow import EnhancedWritingFlow
from ..services.enrichment_service import EnrichmentService
from ..services.llm_service import LLMService
from ..services.knowledge_retrieval_service import KnowledgeRetrievalService, FilteredContext
from ..services.memory_layer_service import MemoryLayerService
from ..services.novel_service import NovelService
from ..services.preview_generation_service import PreviewGenerationService
from ..services.prompt_service import PromptService
from ..services.reader_simulator_service import ReaderSimulatorService, ReaderType
from ..services.self_critique_service import CritiqueDimension, SelfCritiqueService
from ..services.vector_store_service import VectorStoreService
from ..services.writer_context_builder import WriterContextBuilder
from ..utils.json_utils import remove_think_tags, unwrap_markdown_json

logger = logging.getLogger(__name__)
# 使用固定 UTC+8，避免在 Windows/Python 环境缺少 tzdata 时 ZoneInfo 初始化失败。
CN_TIMEZONE = timezone(timedelta(hours=8), name="Asia/Shanghai")
MIN_CHAPTER_VERSION_COUNT = 1
MAX_CHAPTER_VERSION_COUNT = 2


def _clamp_version_count(value: int) -> int:
    return max(MIN_CHAPTER_VERSION_COUNT, min(MAX_CHAPTER_VERSION_COUNT, int(value)))
WRITER_GENERATION_MAX_TOKENS = 7000


class PipelineGraphState(TypedDict, total=False):
    """LangGraph 节点间传递的高级写作流水线状态。"""

    project_id: str
    chapter_number: int
    user_id: int
    writing_notes: Optional[str]
    flow_config: Optional[Dict[str, Any]]
    config: "PipelineConfig"
    project: Any
    outline: Any
    chapter: Any
    outlines_map: Dict[int, Any]
    history_context: Dict[str, Any]
    project_schema: Any
    blueprint_dict: Dict[str, Any]
    all_characters: List[str]
    outline_title: str
    outline_summary: str
    chapter_mission: Optional[dict]
    allowed_new_characters: List[str]
    visibility_context: Dict[str, Any]
    writer_blueprint: Dict[str, Any]
    forbidden_characters: List[str]
    introduced_characters: List[str]
    enhanced_flow: Optional[Any]
    enhanced_context: Optional[Dict[str, Any]]
    memory_context: Optional[str]
    project_memory_text: Optional[str]
    rag_context: Optional[Dict[str, Any]]
    knowledge_context: Optional[str]
    rag_stats: Optional[Dict[str, Any]]
    writer_prompt: str
    prompt_sections: List[Tuple[str, str]]
    prompt_input: str
    version_count: int
    version_style_hints: List[str]
    versions: List[Dict[str, Any]]
    best_version_index: int
    review_summaries: Dict[str, Any]
    variants: List[Dict[str, Any]]
    response: Dict[str, Any]


@dataclass
class PipelineConfig:
    preset: str = "basic"
    version_count: int = 1
    enable_preview: bool = False
    enable_optimizer: bool = False
    enable_consistency: bool = False
    enable_enrichment: bool = False
    async_finalize: bool = False
    enable_constitution: bool = False
    enable_persona: bool = False
    enable_six_dimension: bool = False
    enable_reader_sim: bool = False
    enable_self_critique: bool = False
    enable_memory: bool = False
    enable_rag: bool = True
    rag_mode: str = "simple"
    enable_foreshadowing: bool = False
    enable_faction: bool = False


class PipelineOrchestrator:
    """统一写作流水线编排器。"""

    GRAPH_SEQUENCE = (
        "initialize_chapter",
        "collect_context",
        "generate_chapter_mission",
        "build_visibility_context",
        "prepare_enhanced_context",
        "prepare_memory_context",
        "prepare_retrieval_context",
        "build_writer_prompt",
        "generate_versions",
        "review_versions",
        "apply_post_generation_reviews",
        "persist_versions",
        "build_response",
    )

    def __init__(self, session: AsyncSession):
        self.session = session
        self.llm_service = LLMService(session)
        self.prompt_service = PromptService(session)
        self.novel_service = NovelService(session)
        self.context_builder = WriterContextBuilder()
        self.guardrails = ChapterGuardrails()

    async def generate_chapter(
        self,
        *,
        project_id: str,
        chapter_number: int,
        user_id: int,
        writing_notes: Optional[str] = None,
        flow_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        initial_state: PipelineGraphState = {
            "project_id": project_id,
            "chapter_number": chapter_number,
            "user_id": user_id,
            "writing_notes": writing_notes,
            "flow_config": flow_config,
        }
        graph = self._build_generation_graph()
        final_state = await graph.ainvoke(initial_state)
        return final_state["response"]

    def _build_generation_graph(self):
        """构建高级写作 LangGraph，节点顺序完整覆盖原流水线阶段。"""
        workflow = StateGraph(PipelineGraphState)
        for node_name in self.GRAPH_SEQUENCE:
            workflow.add_node(node_name, getattr(self, f"_graph_{node_name}"))

        previous = START
        for node_name in self.GRAPH_SEQUENCE:
            workflow.add_edge(previous, node_name)
            previous = node_name
        workflow.add_edge(previous, END)
        return workflow.compile()

    async def _graph_initialize_chapter(self, state: PipelineGraphState) -> PipelineGraphState:
        config = await self._resolve_config(state.get("flow_config"))
        project_id = state["project_id"]
        chapter_number = state["chapter_number"]
        project = await self.novel_service.ensure_project_owner(project_id, state["user_id"])

        outline = await self.novel_service.get_outline(project_id, chapter_number)
        if not outline:
            raise HTTPException(status_code=404, detail="蓝图中未找到对应章节纲要")

        chapter = await self.novel_service.get_or_create_chapter(project_id, chapter_number)
        chapter.real_summary = None
        chapter.selected_version_id = None
        chapter.selected_version = None
        chapter.status = "generating"
        chapter.generation_started_at = datetime.now(CN_TIMEZONE)
        chapter.generation_progress = 3
        chapter.generation_step = "context_prep"
        chapter.generation_step_index = 1
        chapter.generation_step_total = 7
        await self.session.commit()

        return {
            "config": config,
            "project": project,
            "outline": outline,
            "chapter": chapter,
            "outlines_map": {item.chapter_number: item for item in project.outlines},
            "outline_title": outline.title or f"第{outline.chapter_number}章",
            "outline_summary": outline.summary or "暂无摘要",
            "writing_notes": state.get("writing_notes") or "无额外写作指令",
        }

    async def _graph_collect_context(self, state: PipelineGraphState) -> PipelineGraphState:
        history_context = await self._collect_history_context(
            project_id=state["project_id"],
            chapter_number=state["chapter_number"],
            outlines_map=state["outlines_map"],
            chapters=state["project"].chapters,
            user_id=state["user_id"],
        )
        project_schema = await self.novel_service._serialize_project(state["project"])
        blueprint_dict = self._normalize_blueprint(project_schema.blueprint.model_dump())
        all_characters = [c.get("name") for c in blueprint_dict.get("characters", []) if c.get("name")]

        return {
            "history_context": history_context,
            "project_schema": project_schema,
            "blueprint_dict": blueprint_dict,
            "all_characters": all_characters,
        }

    async def _graph_generate_chapter_mission(self, state: PipelineGraphState) -> PipelineGraphState:
        chapter_mission = await self._generate_chapter_mission(
            blueprint_dict=state["blueprint_dict"],
            previous_summary=state["history_context"]["previous_summary"],
            previous_tail=state["history_context"]["previous_tail"],
            outline_title=state["outline_title"],
            outline_summary=state["outline_summary"],
            writing_notes=state["writing_notes"],
            introduced_characters=[],
            all_characters=state["all_characters"],
            user_id=state["user_id"],
        )
        chapter = state["chapter"]
        chapter.generation_progress = 28
        chapter.generation_step = "director_mission"
        chapter.generation_step_index = 2
        await self.session.commit()

        return {
            "chapter_mission": chapter_mission,
            "allowed_new_characters": chapter_mission.get("allowed_new_characters", []) if chapter_mission else [],
        }

    async def _graph_build_visibility_context(self, state: PipelineGraphState) -> PipelineGraphState:
        visibility_context = self.context_builder.build_visibility_context(
            blueprint=state["blueprint_dict"],
            completed_summaries=state["history_context"]["completed_summaries"],
            previous_tail=state["history_context"]["previous_tail"],
            outline_title=state["outline_title"],
            outline_summary=state["outline_summary"],
            writing_notes=state["writing_notes"],
            allowed_new_characters=state["allowed_new_characters"],
        )
        writer_blueprint = visibility_context["writer_blueprint"]
        forbidden_characters = visibility_context["forbidden_characters"]
        introduced_characters = visibility_context["introduced_characters"]

        logger.info(
            "Pipeline context: project=%s chapter=%s introduced=%d allowed_new=%d forbidden=%d",
            state["project_id"],
            state["chapter_number"],
            len(introduced_characters),
            len(state["allowed_new_characters"]),
            len(forbidden_characters),
        )

        return {
            "visibility_context": visibility_context,
            "writer_blueprint": writer_blueprint,
            "forbidden_characters": forbidden_characters,
            "introduced_characters": introduced_characters,
        }

    async def _graph_prepare_enhanced_context(self, state: PipelineGraphState) -> PipelineGraphState:
        config = state["config"]
        enhanced_flow = None
        enhanced_context = None
        if config.enable_constitution or config.enable_persona or config.enable_foreshadowing or config.enable_faction:
            enhanced_flow = EnhancedWritingFlow(self.session, self.llm_service, self.prompt_service)
            enhanced_context = await enhanced_flow.prepare_writing_context(
                project_id=state["project_id"],
                chapter_number=state["chapter_number"],
                chapter_outline=state["outline_summary"],
            )

        return {"enhanced_flow": enhanced_flow, "enhanced_context": enhanced_context}

    async def _graph_prepare_memory_context(self, state: PipelineGraphState) -> PipelineGraphState:
        memory_context = None
        if state["config"].enable_memory:
            memory_context = await self._get_memory_context(
                project_id=state["project_id"],
                chapter_number=state["chapter_number"],
                involved_characters=state["introduced_characters"],
            )

        return {
            "memory_context": memory_context,
            "project_memory_text": await self._get_project_memory_text(state["project_id"]),
        }

    async def _graph_prepare_retrieval_context(self, state: PipelineGraphState) -> PipelineGraphState:
        config = state["config"]
        rag_context = None
        knowledge_context = None
        rag_stats = None
        if config.enable_rag:
            if config.rag_mode == "two_stage":
                knowledge_context, rag_stats = await self._get_two_stage_rag_context(
                    project_id=state["project_id"],
                    chapter_number=state["chapter_number"],
                    writing_notes=state["writing_notes"],
                    pov_character=self._resolve_pov_character(state.get("chapter_mission")),
                    user_id=state["user_id"],
                )
            else:
                rag_context = await self._get_rag_context(
                    project_id=state["project_id"],
                    outline_title=state["outline_title"],
                    outline_summary=state["outline_summary"],
                    writing_notes=state["writing_notes"],
                    user_id=state["user_id"],
                )
                rag_stats = {
                    "mode": "simple",
                    "chunks": len(rag_context.get("chunks", [])) if rag_context else 0,
                    "summaries": len(rag_context.get("summaries", [])) if rag_context else 0,
                }

        return {
            "rag_context": rag_context,
            "knowledge_context": knowledge_context,
            "rag_stats": rag_stats,
        }

    async def _graph_build_writer_prompt(self, state: PipelineGraphState) -> PipelineGraphState:
        writer_prompt = await self.prompt_service.get_prompt("writing_v2")
        if not writer_prompt:
            writer_prompt = await self.prompt_service.get_prompt("writing")
        if not writer_prompt:
            raise HTTPException(status_code=500, detail="缺少写作提示词，请联系管理员配置")

        prompt_sections = await self._build_prompt_sections(
            writer_blueprint=state["writer_blueprint"],
            previous_summary=state["history_context"]["previous_summary"],
            previous_tail=state["history_context"]["previous_tail"],
            chapter_mission=state.get("chapter_mission"),
            rag_context=state.get("rag_context"),
            knowledge_context=state.get("knowledge_context"),
            outline_title=state["outline_title"],
            outline_summary=state["outline_summary"],
            writing_notes=state["writing_notes"],
            forbidden_characters=state["forbidden_characters"],
            project_memory_text=state.get("project_memory_text"),
            memory_context=state.get("memory_context"),
        )

        enhanced_flow = state.get("enhanced_flow")
        enhanced_context = state.get("enhanced_context")
        if enhanced_flow and enhanced_context:
            prompt_sections = enhanced_flow.build_enhanced_prompt_sections(prompt_sections, enhanced_context)

        prompt_input = "\n\n".join(f"{title}\n{content}" for title, content in prompt_sections if content)
        logger.debug("Pipeline prompt length: %s chars", len(prompt_input))
        chapter = state["chapter"]
        chapter.generation_progress = 55
        chapter.generation_step = "draft_generation"
        chapter.generation_step_index = 4
        await self.session.commit()

        version_count = state["config"].version_count
        return {
            "writer_prompt": writer_prompt,
            "prompt_sections": prompt_sections,
            "prompt_input": prompt_input,
            "version_count": version_count,
            "version_style_hints": self._resolve_style_hints(enhanced_context, version_count),
        }

    async def _graph_generate_versions(self, state: PipelineGraphState) -> PipelineGraphState:
        versions: List[Dict[str, Any]] = []
        version_count = state["version_count"]
        for idx in range(version_count):
            style_hint = (
                state["version_style_hints"][idx]
                if idx < len(state["version_style_hints"])
                else None
            )
            chapter = state["chapter"]
            chapter.generation_progress = 55 + int((idx / max(version_count, 1)) * 25)
            chapter.generation_step = "draft_generation"
            chapter.generation_step_index = 4
            await self.session.commit()
            versions.append(
                await self._generate_single_version(
                    index=idx,
                    prompt_input=state["prompt_input"],
                    writer_prompt=state["writer_prompt"],
                    style_hint=style_hint,
                    project_id=state["project_id"],
                    chapter_number=state["chapter_number"],
                    outline_title=state["outline_title"],
                    outline_summary=state["outline_summary"],
                    chapter_mission=state.get("chapter_mission"),
                    forbidden_characters=state["forbidden_characters"],
                    allowed_new_characters=state["allowed_new_characters"],
                    user_id=state["user_id"],
                    writer_blueprint=state["writer_blueprint"],
                    memory_context=state.get("memory_context"),
                    enhanced_context=state.get("enhanced_context"),
                    config=state["config"],
                )
            )
            chapter.generation_progress = 55 + int(((idx + 1) / max(version_count, 1)) * 25)
            chapter.generation_step = "draft_generation"
            chapter.generation_step_index = 4
            await self.session.commit()

        return {"versions": versions}

    async def _graph_review_versions(self, state: PipelineGraphState) -> PipelineGraphState:
        chapter = state["chapter"]
        chapter.generation_progress = 86
        chapter.generation_step = "quality_review"
        chapter.generation_step_index = 5
        await self.session.commit()

        best_version_index, ai_review_result = await self._run_ai_review(
            versions=state["versions"],
            chapter_mission=state.get("chapter_mission"),
            user_id=state["user_id"],
            context=self._build_review_context(
                writer_blueprint=state["writer_blueprint"],
                blueprint_dict=state["blueprint_dict"],
                chapter_number=state["chapter_number"],
                outline_title=state["outline_title"],
                outline_summary=state["outline_summary"],
                chapter_mission=state.get("chapter_mission"),
                history_context=state["history_context"],
            ),
        )

        review_summaries: Dict[str, Any] = {}
        if ai_review_result:
            review_summaries["ai_review"] = ai_review_result

        versions = state["versions"]
        if versions:
            best_version_index = max(0, min(best_version_index, len(versions) - 1))
        else:
            best_version_index = 0

        return {"best_version_index": best_version_index, "review_summaries": review_summaries}

    async def _graph_apply_post_generation_reviews(self, state: PipelineGraphState) -> PipelineGraphState:
        versions = state["versions"]
        if not versions:
            return {"versions": versions, "review_summaries": state["review_summaries"]}

        config = state["config"]
        review_summaries = state["review_summaries"]
        best_version = versions[state["best_version_index"]]
        best_content = best_version["content"]

        enhanced_flow = state.get("enhanced_flow")
        if enhanced_flow and config.enable_six_dimension:
            review_result = await enhanced_flow.post_generation_review(
                project_id=state["project_id"],
                chapter_number=state["chapter_number"],
                chapter_title=state["outline_title"],
                chapter_content=best_content,
                chapter_plan=json.dumps(state.get("chapter_mission"), ensure_ascii=False)
                if state.get("chapter_mission")
                else None,
                previous_summary=state["history_context"]["previous_summary"],
            )
            review_summaries["enhanced_review"] = review_result

        if config.enable_self_critique:
            best_content, critique_summary = await self._run_self_critique(
                best_content,
                user_id=state["user_id"],
                context={
                    "character_profiles": json.dumps(
                        state["writer_blueprint"].get("characters", []),
                        ensure_ascii=False,
                    ),
                    "previous_summary": state["history_context"]["previous_summary"],
                },
            )
            review_summaries["self_critique"] = critique_summary

        if config.enable_reader_sim:
            reader_feedback = await self._run_reader_simulation(
                best_content,
                chapter_number=state["chapter_number"],
                previous_summary=state["history_context"]["previous_summary"],
                user_id=state["user_id"],
            )
            review_summaries["reader_simulator"] = reader_feedback

        if config.enable_consistency:
            best_content, consistency_report = await self._run_consistency_check(
                project_id=state["project_id"],
                chapter_text=best_content,
                user_id=state["user_id"],
            )
            review_summaries["consistency"] = consistency_report

        if config.enable_optimizer:
            best_content, optimizer_report = await self._run_optimizer(
                best_content,
                user_id=state["user_id"],
            )
            review_summaries["optimizer"] = optimizer_report

        if config.enable_enrichment:
            best_content, enrichment_report = await self._run_enrichment(
                best_content,
                user_id=state["user_id"],
            )
            if enrichment_report:
                review_summaries["enrichment"] = enrichment_report

        best_version["content"] = best_content
        best_version.setdefault("metadata", {})["review_summaries"] = review_summaries
        return {"versions": versions, "review_summaries": review_summaries}

    async def _graph_persist_versions(self, state: PipelineGraphState) -> PipelineGraphState:
        versions = state["versions"]
        contents = [v.get("content", "") for v in versions]
        metadata = [v.get("metadata") for v in versions]
        chapter = state["chapter"]
        chapter.generation_progress = 96
        chapter.generation_step = "persist_versions"
        chapter.generation_step_index = 6
        await self.session.commit()
        versions_models = await self.novel_service.replace_chapter_versions(chapter, contents, metadata)

        variants = []
        for idx, version_model in enumerate(versions_models):
            variants.append(
                {
                    "index": idx,
                    "version_id": version_model.id,
                    "content": versions[idx].get("content", ""),
                    "metadata": versions[idx].get("metadata"),
                }
            )

        return {"variants": variants}

    async def _graph_build_response(self, state: PipelineGraphState) -> PipelineGraphState:
        config = state["config"]
        return {
            "response": {
                "project_id": state["project_id"],
                "chapter_number": state["chapter_number"],
                "preset": config.preset,
                "best_version_index": state["best_version_index"],
                "variants": state["variants"],
                "review_summaries": state["review_summaries"],
                "debug_metadata": {
                    "version_count": state["version_count"],
                    "stages": self._build_stage_flags(config),
                    "retrieval_stats": state.get("rag_stats"),
                },
            }
        }

    async def _resolve_config(self, flow_config: Optional[Dict[str, Any]]) -> PipelineConfig:
        flow_config = flow_config or {}
        preset = flow_config.get("preset", "basic")

        config = PipelineConfig(preset=preset)
        config.version_count = await self._resolve_version_count(flow_config.get("versions"))

        if preset in ("enhanced", "ultimate"):
            config.enable_constitution = True
            config.enable_persona = True
            config.enable_foreshadowing = True
            config.enable_faction = True
            config.rag_mode = "two_stage"

        if preset == "enhanced":
            config.enable_six_dimension = True

        if preset == "ultimate":
            config.enable_memory = True

        if preset == "basic":
            config.enable_rag = True

        for key in (
            "enable_preview",
            "enable_optimizer",
            "enable_consistency",
            "enable_enrichment",
            "async_finalize",
            "enable_rag",
        ):
            if key in flow_config and flow_config[key] is not None:
                setattr(config, key, bool(flow_config[key]))

        if flow_config.get("rag_mode"):
            config.rag_mode = str(flow_config["rag_mode"])

        if preset == "ultimate":
            config.enable_preview = False
            config.enable_optimizer = False
            config.enable_consistency = False
            config.enable_enrichment = False
            config.enable_six_dimension = False
            config.enable_reader_sim = False
            config.enable_self_critique = False

        return config

    async def _resolve_version_count(self, requested_count: Optional[int]) -> int:
        if requested_count:
            try:
                count = int(requested_count)
                return _clamp_version_count(count)
            except (TypeError, ValueError):
                pass

        repo = SystemConfigRepository(self.session)
        for key in ("writer.chapter_versions", "writer.version_count"):
            record = await repo.get_by_key(key)
            if record and record.value:
                try:
                    val = int(record.value)
                    if val >= 1:
                        return _clamp_version_count(val)
                except ValueError:
                    pass

        for env in ("WRITER_CHAPTER_VERSION_COUNT", "WRITER_CHAPTER_VERSIONS", "WRITER_VERSION_COUNT"):
            v = os.getenv(env)
            if v:
                try:
                    val = int(v)
                    if val >= 1:
                        return _clamp_version_count(val)
                except ValueError:
                    pass

        return _clamp_version_count(int(settings.writer_chapter_versions))

    async def _collect_history_context(
        self,
        *,
        project_id: str,
        chapter_number: int,
        outlines_map: Dict[int, Any],
        chapters: List[Chapter],
        user_id: int,
    ) -> Dict[str, Any]:
        completed_summaries = []
        completed_chapters = []
        latest_prev_number = -1
        previous_summary_text = ""
        previous_tail_excerpt = ""

        for existing in chapters:
            if existing.chapter_number >= chapter_number:
                continue
            if existing.selected_version is None or not existing.selected_version.content:
                continue
            if not existing.real_summary:
                summary = await self.llm_service.get_summary(
                    existing.selected_version.content,
                    temperature=0.15,
                    user_id=user_id,
                    timeout=180.0,
                )
                existing.real_summary = remove_think_tags(summary)
                await self.session.commit()

            completed_chapters.append(
                {
                    "chapter_number": existing.chapter_number,
                    "title": outlines_map.get(existing.chapter_number).title
                    if outlines_map.get(existing.chapter_number)
                    else f"第{existing.chapter_number}章",
                    "summary": existing.real_summary,
                }
            )
            completed_summaries.append(existing.real_summary or "")

            if existing.chapter_number > latest_prev_number:
                latest_prev_number = existing.chapter_number
                previous_summary_text = existing.real_summary or ""
                previous_tail_excerpt = self._extract_tail_excerpt(existing.selected_version.content)

        return {
            "completed_chapters": completed_chapters,
            "completed_summaries": completed_summaries,
            "previous_summary": previous_summary_text or "暂无（这是第一章）",
            "previous_tail": previous_tail_excerpt or "暂无（这是第一章）",
        }

    @staticmethod
    def _extract_tail_excerpt(text: Optional[str], limit: int = 500) -> str:
        if not text:
            return ""
        stripped = text.strip()
        if len(stripped) <= limit:
            return stripped
        return stripped[-limit:]

    @staticmethod
    def _normalize_blueprint(blueprint_dict: Dict[str, Any]) -> Dict[str, Any]:
        if "relationships" in blueprint_dict and blueprint_dict["relationships"]:
            for relation in blueprint_dict["relationships"]:
                if "character_from" in relation:
                    relation["from"] = relation.pop("character_from")
                if "character_to" in relation:
                    relation["to"] = relation.pop("character_to")
        return blueprint_dict

    async def _generate_chapter_mission(
        self,
        *,
        blueprint_dict: Dict[str, Any],
        previous_summary: str,
        previous_tail: str,
        outline_title: str,
        outline_summary: str,
        writing_notes: str,
        introduced_characters: List[str],
        all_characters: List[str],
        user_id: int,
    ) -> Optional[dict]:
        plan_prompt = await self.prompt_service.get_prompt("chapter_plan")
        if not plan_prompt:
            logger.warning("未配置 chapter_plan 提示词，跳过导演脚本生成")
            return None

        plan_input = f"""
[上一章摘要]
{previous_summary}

[上一章结尾]
{previous_tail}

[当前章节大纲]
标题：{outline_title}
摘要：{outline_summary}

[已登场角色]
{json.dumps(introduced_characters, ensure_ascii=False) if introduced_characters else "暂无"}

[全部角色]
{json.dumps(all_characters, ensure_ascii=False)}

[写作指令]
{writing_notes}
"""

        try:
            response = await self.llm_service.get_llm_response(
                system_prompt=plan_prompt,
                conversation_history=[{"role": "user", "content": plan_input}],
                temperature=0.3,
                user_id=user_id,
                timeout=120.0,
            )
            cleaned = remove_think_tags(response)
            normalized = unwrap_markdown_json(cleaned)
            mission = json.loads(normalized)
            logger.info("章节导演脚本生成完成: macro_beat=%s", mission.get("macro_beat"))
            return mission
        except Exception as exc:
            logger.warning("生成章节导演脚本失败，将使用默认模式: %s", exc)
            return None

    async def _get_rag_context(
        self,
        *,
        project_id: str,
        outline_title: str,
        outline_summary: str,
        writing_notes: str,
        user_id: int,
    ) -> Dict[str, Any]:
        if not settings.vector_store_enabled:
            return {"chunks": [], "summaries": []}

        try:
            vector_store = VectorStoreService()
        except RuntimeError as exc:
            logger.warning("向量库初始化失败，跳过 RAG: %s", exc)
            return {"chunks": [], "summaries": []}

        query_parts = [outline_title, outline_summary]
        if writing_notes:
            query_parts.append(writing_notes)
        rag_query = "\n".join(part for part in query_parts if part)

        context_service = ChapterContextService(llm_service=self.llm_service, vector_store=vector_store)
        rag_context = await context_service.retrieve_for_generation(
            project_id=project_id,
            query_text=rag_query or outline_title or outline_summary,
            user_id=user_id,
        )
        return {
            "chunks": rag_context.chunk_texts() if rag_context.chunks else [],
            "summaries": rag_context.summary_lines() if rag_context.summaries else [],
        }

    async def _get_two_stage_rag_context(
        self,
        *,
        project_id: str,
        chapter_number: int,
        writing_notes: str,
        pov_character: Optional[str],
        user_id: int,
    ) -> Tuple[Optional[str], Dict[str, Any]]:
        if not settings.vector_store_enabled:
            return None, {"mode": "two_stage", "enabled": False}

        try:
            vector_store = VectorStoreService()
        except RuntimeError as exc:
            logger.warning("向量库初始化失败，跳过两层 RAG: %s", exc)
            return None, {"mode": "two_stage", "enabled": False, "error": str(exc)}

        sync_session = getattr(self.session, "sync_session", self.session)
        retrieval_service = KnowledgeRetrievalService(sync_session, self.llm_service, vector_store)
        filtered = await retrieval_service.retrieve_and_filter(
            project_id=project_id,
            chapter_number=chapter_number,
            user_id=user_id,
            pov_character=pov_character,
            user_guidance=writing_notes,
            top_k=settings.vector_top_k_chunks,
        )
        context_text = self._format_filtered_context(filtered)
        stats = filtered.stats or {}
        stats["mode"] = "two_stage"
        return context_text, stats

    async def _get_project_memory_text(self, project_id: str) -> Optional[str]:
        result = await self.session.execute(
            select(ProjectMemory).where(ProjectMemory.project_id == project_id)
        )
        memory = result.scalars().first()
        if not memory:
            return None

        parts = []
        if memory.global_summary:
            parts.append(f"### 全局摘要\n{memory.global_summary}")
        if memory.plot_arcs:
            parts.append("### 剧情线追踪\n" + json.dumps(memory.plot_arcs, ensure_ascii=False, indent=2))
        if not parts:
            return None
        return "\n\n".join(parts)

    async def _get_memory_context(
        self,
        *,
        project_id: str,
        chapter_number: int,
        involved_characters: List[str],
    ) -> str:
        memory_layer = MemoryLayerService(self.session, self.llm_service, self.prompt_service)
        return await memory_layer.get_memory_context(project_id, chapter_number, involved_characters)

    async def _build_prompt_sections(
        self,
        *,
        writer_blueprint: Dict[str, Any],
        previous_summary: str,
        previous_tail: str,
        chapter_mission: Optional[dict],
        rag_context: Optional[Dict[str, Any]],
        knowledge_context: Optional[str],
        outline_title: str,
        outline_summary: str,
        writing_notes: str,
        forbidden_characters: List[str],
        project_memory_text: Optional[str],
        memory_context: Optional[str],
    ) -> List[Tuple[str, str]]:
        blueprint_text = json.dumps(writer_blueprint, ensure_ascii=False, indent=2)
        mission_text = json.dumps(chapter_mission, ensure_ascii=False, indent=2) if chapter_mission else "无导演脚本"
        forbidden_text = json.dumps(forbidden_characters, ensure_ascii=False) if forbidden_characters else "无"

        sections: List[Tuple[str, str]] = [
            ("[世界蓝图](JSON，已裁剪)", blueprint_text),
        ]

        if project_memory_text:
            sections.append(("[项目长期记忆](摘要/剧情线)", project_memory_text))
        if memory_context:
            sections.append(("[记忆层上下文]", memory_context))

        target_word_count, _minimum_word_count = await resolve_word_count_requirements(
            SystemConfigRepository(self.session)
        )

        sections.extend(
            [
                ("[上一章摘要]", previous_summary or "暂无（这是第一章）"),
                ("[上一章结尾]", previous_tail or "暂无（这是第一章）"),
                ("[章节导演脚本](JSON)", mission_text),
            ]
        )

        if knowledge_context:
            sections.append(("[RAG精筛上下文](含POV裁剪)", knowledge_context))

        if rag_context:
            rag_chunks_text = "\n\n".join(rag_context.get("chunks", [])) or "未检索到章节片段"
            rag_summaries_text = "\n".join(rag_context.get("summaries", [])) or "未检索到章节摘要"
            sections.append(("[检索到的剧情上下文](Markdown)", rag_chunks_text))
            sections.append(("[检索到的章节摘要](Markdown)", rag_summaries_text))

        sections.extend(
            [
                ("[当前章节目标]", f"标题：{outline_title}\n摘要：{outline_summary}\n写作要求：{writing_notes}"),
                (
                    "[篇幅与排版要求]",
                    build_word_count_requirement_text(target_word_count)
                    + "段落清晰，尽量保持自然段首行空两格。",
                ),
                ("[禁止角色](本章不允许提及)", forbidden_text),
            ]
        )

        return sections

    @staticmethod
    def _resolve_style_hints(
        enhanced_context: Optional[Dict[str, Any]],
        version_count: int,
    ) -> List[str]:
        if enhanced_context and enhanced_context.get("version_style_hints"):
            hints = enhanced_context["version_style_hints"]
            if isinstance(hints, list) and hints:
                return hints[:version_count]
        return [
            "情绪更细腻，节奏更慢，多写内心戏和感官描写",
            "冲突更强，节奏更快，多写动作和对话",
            "悬念更重，多埋伏笔，结尾钩子更强",
        ][:version_count]

    @staticmethod
    def _resolve_pov_character(chapter_mission: Optional[dict]) -> Optional[str]:
        if not chapter_mission:
            return None
        return chapter_mission.get("pov") or chapter_mission.get("pov_character")

    @staticmethod
    def _build_review_context(
        *,
        writer_blueprint: Dict[str, Any],
        blueprint_dict: Dict[str, Any],
        chapter_number: int,
        outline_title: str,
        outline_summary: str,
        chapter_mission: Optional[dict],
        history_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """构建 AI 评审上下文，优先使用写作可见性裁剪后的蓝图。"""
        return {
            "novel_blueprint": writer_blueprint or blueprint_dict,
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

    async def _generate_single_version(
        self,
        *,
        index: int,
        prompt_input: str,
        writer_prompt: str,
        style_hint: Optional[str],
        project_id: str,
        chapter_number: int,
        outline_title: str,
        outline_summary: str,
        chapter_mission: Optional[dict],
        forbidden_characters: List[str],
        allowed_new_characters: List[str],
        user_id: int,
        writer_blueprint: Dict[str, Any],
        memory_context: Optional[str],
        enhanced_context: Optional[Dict[str, Any]],
        config: PipelineConfig,
    ) -> Dict[str, Any]:
        metadata: Dict[str, Any] = {
            "chapter_mission": chapter_mission,
            "style_hint": style_hint,
            "pipeline": {"preset": config.preset},
        }

        content = ""
        if config.enable_preview:
            content, preview_meta = await self._generate_with_preview(
                project_id=project_id,
                chapter_number=chapter_number,
                outline_title=outline_title,
                outline_summary=outline_summary,
                writer_blueprint=writer_blueprint,
                memory_context=memory_context,
                style_hint=style_hint,
                enhanced_context=enhanced_context,
                user_id=user_id,
            )
            metadata["preview"] = preview_meta

        if not content:
            final_prompt_input = prompt_input
            if style_hint:
                final_prompt_input += f"\n\n[版本风格提示]\n{style_hint}"

            response = await self.llm_service.get_llm_response(
                system_prompt=writer_prompt,
                conversation_history=[{"role": "user", "content": final_prompt_input}],
                temperature=0.9,
                user_id=user_id,
                timeout=600.0,
                response_format=None,
                max_tokens=WRITER_GENERATION_MAX_TOKENS,
            )
            cleaned = remove_think_tags(response)
            content = unwrap_markdown_json(cleaned)

        guardrail_result = self.guardrails.check(
            generated_text=content,
            forbidden_characters=forbidden_characters,
            allowed_new_characters=allowed_new_characters,
            pov=chapter_mission.get("pov") if chapter_mission else None,
        )
        guardrail_metadata = {"passed": guardrail_result.passed, "violations": []}

        if not guardrail_result.passed:
            guardrail_metadata["violations"] = [
                {"type": v.type, "severity": v.severity, "description": v.description}
                for v in guardrail_result.violations
            ]
            violations_text = self.guardrails.format_violations_for_rewrite(guardrail_result)
            content = await self._rewrite_with_guardrails(
                original_text=content,
                chapter_mission=chapter_mission,
                violations_text=violations_text,
                user_id=user_id,
            )

        parsed_json = None
        extracted_text = None
        try:
            parsed_json = json.loads(content)
            extracted_text = self._extract_text(parsed_json)
        except Exception:
            parsed_json = None

        metadata["guardrail"] = guardrail_metadata
        if parsed_json is not None:
            metadata["parsed_json"] = parsed_json

        resolved_content = extracted_text or content
        target_word_count, _minimum_word_count = await resolve_word_count_requirements(
            SystemConfigRepository(self.session)
        )
        resolved_content = await self._compress_chapter_to_word_limit(
            content=resolved_content,
            target_word_count=target_word_count,
            user_id=user_id,
            chapter_number=chapter_number,
            version_index=index + 1,
        )
        metadata["word_limit"] = {
            "target": target_word_count,
            "actual": count_chapter_words(resolved_content),
        }

        return {
            "index": index,
            "content": resolved_content,
            "metadata": metadata,
        }

    async def _compress_chapter_to_word_limit(
        self,
        *,
        content: str,
        target_word_count: int,
        user_id: int,
        chapter_number: int,
        version_index: int,
    ) -> str:
        """当模型明显超出章节目标字数时，做一次只删减不扩写的压缩兜底。"""
        if not should_compress_chapter(content, target_word_count):
            return content

        current_word_count = count_chapter_words(content)
        logger.info(
            "Pipeline 第 %s 章版本 %s 超出字数上限，开始压缩: current=%s target=%s",
            chapter_number,
            version_index,
            current_word_count,
            target_word_count,
        )
        prompt = f"""
请把下面小说章节压缩到约 {target_word_count} 字，最多不得超过 {int(target_word_count * 1.1)} 字。

要求：
- 只删减冗余描写、重复心理活动、过密铺垫，不新增剧情。
- 保留关键事件、人物关系、冲突转折和结尾钩子。
- 直接输出压缩后的章节正文，不要解释，不要输出 JSON。

原文字数约 {current_word_count} 字：
{content}
""".strip()

        try:
            response = await self.llm_service.get_llm_response(
                system_prompt="你是小说章节压缩编辑，只做删减压缩，不新增剧情。",
                conversation_history=[{"role": "user", "content": prompt}],
                temperature=0.2,
                user_id=user_id,
                timeout=300.0,
                response_format=None,
                max_tokens=WRITER_GENERATION_MAX_TOKENS,
            )
            compressed = unwrap_markdown_json(remove_think_tags(response)).strip()
            return compressed or content
        except Exception as exc:
            logger.warning(
                "Pipeline 第 %s 章版本 %s 压缩失败，保留原文: %s",
                chapter_number,
                version_index,
                exc,
            )
            return content

    async def _generate_with_preview(
        self,
        *,
        project_id: str,
        chapter_number: int,
        outline_title: str,
        outline_summary: str,
        writer_blueprint: Dict[str, Any],
        memory_context: Optional[str],
        style_hint: Optional[str],
        enhanced_context: Optional[Dict[str, Any]],
        user_id: int,
    ) -> Tuple[str, Dict[str, Any]]:
        preview_service = PreviewGenerationService(self.session, self.llm_service, self.prompt_service)
        blueprint_context = json.dumps(writer_blueprint, ensure_ascii=False, indent=2)

        extra_constraints = []
        if enhanced_context:
            if enhanced_context.get("constitution"):
                extra_constraints.append(enhanced_context["constitution"])
            if enhanced_context.get("writer_persona"):
                extra_constraints.append(enhanced_context["writer_persona"])

        if extra_constraints:
            blueprint_context = blueprint_context + "\n\n" + "\n\n".join(extra_constraints)

        preview_result = await preview_service.generate_with_preview(
            project_id=project_id,
            chapter_number=chapter_number,
            outline={"title": outline_title, "summary": outline_summary},
            blueprint_context=blueprint_context,
            emotion_context="（无情绪曲线指导）",
            memory_context=memory_context or "（无记忆层上下文）",
            style_hint=style_hint or "",
            user_id=user_id,
        )

        return preview_result.get("full_chapter", ""), preview_result

    async def _rewrite_with_guardrails(
        self,
        *,
        original_text: str,
        chapter_mission: Optional[dict],
        violations_text: str,
        user_id: int,
    ) -> str:
        rewrite_prompt = await self.prompt_service.get_prompt("rewrite_guardrails")
        if not rewrite_prompt:
            logger.warning("未配置 rewrite_guardrails 提示词，跳过自动修复")
            return original_text

        rewrite_input = f"""
[原文]
{original_text}

[章节导演脚本]
{json.dumps(chapter_mission, ensure_ascii=False, indent=2) if chapter_mission else "无"}

[违规列表]
{violations_text}
"""

        try:
            response = await self.llm_service.get_llm_response(
                system_prompt=rewrite_prompt,
                conversation_history=[{"role": "user", "content": rewrite_input}],
                temperature=0.3,
                user_id=user_id,
                timeout=300.0,
                response_format=None,
                max_tokens=WRITER_GENERATION_MAX_TOKENS,
            )
            cleaned = remove_think_tags(response)
            return cleaned
        except Exception as exc:
            logger.warning("自动修复失败，返回原文: %s", exc)
            return original_text

    @staticmethod
    def _extract_text(value: object) -> Optional[str]:
        if not value:
            return None
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            for key in ("content", "chapter_content", "chapter_text", "text", "body", "story"):
                if value.get(key):
                    nested = PipelineOrchestrator._extract_text(value.get(key))
                    if nested:
                        return nested
            return None
        if isinstance(value, list):
            parts: List[str] = []
            for item in value:
                nested = PipelineOrchestrator._extract_text(item)
                if nested and nested.strip():
                    parts.append(nested.strip())
            if parts:
                return "\n\n".join(parts)
        return None

    async def _run_ai_review(
        self,
        *,
        versions: List[Dict[str, Any]],
        chapter_mission: Optional[dict],
        user_id: int,
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[int, Optional[Dict[str, Any]]]:
        if len(versions) <= 1:
            return 0, None

        contents = [v.get("content", "") for v in versions]
        try:
            ai_review_service = AIReviewService(self.llm_service, self.prompt_service)
            ai_review_result = await ai_review_service.review_versions(
                versions=contents,
                chapter_mission=chapter_mission,
                user_id=user_id,
                review_context=context,
            )
        except Exception as exc:
            logger.warning("AI 评审失败，跳过: %s", exc)
            return 0, None

        if not ai_review_result:
            return 0, None

        review_map = {
            review.version_number: review for review in ai_review_result.version_reviews
        }
        for idx, variant in enumerate(versions):
            version_review = review_map.get(idx + 1)
            variant.setdefault("metadata", {})["ai_review"] = {
                "is_best": idx == ai_review_result.best_version_index,
                "scores": version_review.scores if version_review else ai_review_result.scores,
                "evaluation": version_review.overall_review if version_review else None,
                "pros": version_review.pros if version_review else [],
                "cons": version_review.cons if version_review else [],
                "flaws": ai_review_result.critical_flaws if idx == ai_review_result.best_version_index else None,
                "suggestions": ai_review_result.refinement_suggestions if idx == ai_review_result.best_version_index else None,
            }

        return ai_review_result.best_version_index, {
            "best_version_index": ai_review_result.best_version_index,
            "scores": ai_review_result.scores,
            "evaluation": ai_review_result.overall_evaluation,
            "flaws": ai_review_result.critical_flaws,
            "suggestions": ai_review_result.refinement_suggestions,
            "version_reviews": [
                {
                    "version_number": review.version_number,
                    "pros": review.pros,
                    "cons": review.cons,
                    "overall_review": review.overall_review,
                    "scores": review.scores,
                }
                for review in ai_review_result.version_reviews
            ],
        }

    async def _run_self_critique(
        self,
        chapter_content: str,
        *,
        user_id: int,
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        service = SelfCritiqueService(self.session, self.llm_service, self.prompt_service)
        critique = await service.critique_and_revise_loop(
            chapter_content=chapter_content,
            max_iterations=1,
            target_score=75.0,
            dimensions=[
                CritiqueDimension.LOGIC,
                CritiqueDimension.CHARACTER,
                CritiqueDimension.WRITING,
            ],
            context=context,
            user_id=user_id,
        )
        return critique.get("final_content", chapter_content), {
            "iterations": len(critique.get("iterations", [])),
            "final_score": critique.get("final_score", 0),
            "improvement": critique.get("improvement", 0),
            "status": critique.get("status", "unknown"),
        }

    async def _run_reader_simulation(
        self,
        chapter_content: str,
        *,
        chapter_number: int,
        previous_summary: Optional[str],
        user_id: int,
    ) -> Dict[str, Any]:
        service = ReaderSimulatorService(self.session, self.llm_service, self.prompt_service)
        return await service.simulate_reading_experience(
            chapter_content=chapter_content,
            chapter_number=chapter_number,
            reader_types=[ReaderType.THRILL_SEEKER, ReaderType.CRITIC, ReaderType.CASUAL],
            previous_summary=previous_summary,
            user_id=user_id,
        )

    async def _run_consistency_check(
        self,
        *,
        project_id: str,
        chapter_text: str,
        user_id: int,
    ) -> Tuple[str, Dict[str, Any]]:
        sync_session = getattr(self.session, "sync_session", self.session)
        service = ConsistencyService(sync_session, self.llm_service)
        result = await service.check_consistency(project_id, chapter_text, user_id, include_foreshadowing=True)
        report = {
            "is_consistent": result.is_consistent,
            "summary": result.summary,
            "check_time_ms": result.check_time_ms,
            "violations": [
                {
                    "severity": v.severity.value if hasattr(v.severity, "value") else v.severity,
                    "category": v.category,
                    "description": v.description,
                    "location": v.location,
                    "suggested_fix": v.suggested_fix,
                    "confidence": v.confidence,
                }
                for v in result.violations
            ],
        }

        needs_fix = any(
            v.severity in (ViolationSeverity.CRITICAL, ViolationSeverity.MAJOR)
            for v in result.violations
        )
        if needs_fix:
            fixed = await service.auto_fix(project_id, chapter_text, result.violations, user_id)
            if fixed:
                report["auto_fix_applied"] = True
                return fixed, report

        report["auto_fix_applied"] = False
        return chapter_text, report

    async def _run_optimizer(self, chapter_content: str, *, user_id: int) -> Tuple[str, Dict[str, Any]]:
        prompt_map = {
            "dialogue": "optimize_dialogue",
            "environment": "optimize_environment",
            "psychology": "optimize_psychology",
            "rhythm": "optimize_rhythm",
        }

        optimized_content = chapter_content
        notes = []
        for dimension, prompt_name in prompt_map.items():
            prompt = await self.prompt_service.get_prompt(prompt_name)
            if not prompt:
                logger.warning("缺少优化提示词 %s，跳过 %s 维度", prompt_name, dimension)
                continue

            optimize_input = {
                "original_content": optimized_content,
                "additional_notes": "在不改变剧情走向的前提下优化该维度。",
            }
            try:
                response = await self.llm_service.get_llm_response(
                    system_prompt=prompt,
                    conversation_history=[{"role": "user", "content": json.dumps(optimize_input, ensure_ascii=False)}],
                    temperature=0.7,
                    user_id=user_id,
                    timeout=600.0,
                )
                cleaned = remove_think_tags(response)
                normalized = unwrap_markdown_json(cleaned)
                try:
                    parsed = json.loads(normalized)
                    optimized_content = parsed.get("optimized_content", cleaned)
                    notes.append(
                        {
                            "dimension": dimension,
                            "notes": parsed.get("optimization_notes", "优化完成"),
                        }
                    )
                except json.JSONDecodeError:
                    optimized_content = cleaned
                    notes.append({"dimension": dimension, "notes": "优化完成（响应格式非标准JSON）"})
            except Exception as exc:
                logger.warning("优化维度 %s 失败: %s", dimension, exc)

        return optimized_content, {"steps": notes}

    async def _run_enrichment(
        self,
        chapter_content: str,
        *,
        user_id: int,
        target_word_count: int = 3000,
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        service = EnrichmentService(self.session, self.llm_service)
        result = await service.check_and_enrich(
            chapter_text=chapter_content,
            target_word_count=target_word_count,
            user_id=user_id,
        )
        if not result:
            return chapter_content, None

        return result.enriched_content, {
            "original_word_count": result.original_word_count,
            "enriched_word_count": result.enriched_word_count,
            "enrichment_ratio": result.enrichment_ratio,
            "enrichment_type": result.enrichment_type,
        }

    @staticmethod
    def _build_stage_flags(config: PipelineConfig) -> Dict[str, bool]:
        return {
            "preview": config.enable_preview,
            "optimizer": config.enable_optimizer,
            "consistency": config.enable_consistency,
            "enrichment": config.enable_enrichment,
            "constitution": config.enable_constitution,
            "persona": config.enable_persona,
            "six_dimension": config.enable_six_dimension,
            "reader_sim": config.enable_reader_sim,
            "self_critique": config.enable_self_critique,
            "memory": config.enable_memory,
            "rag": config.enable_rag,
            "rag_mode": config.rag_mode == "two_stage",
        }

    @staticmethod
    def _format_filtered_context(filtered: FilteredContext) -> Optional[str]:
        if not filtered:
            return None

        sections = []
        if filtered.plot_fuel:
            sections.append("## 情节燃料\n" + "\n".join(f"- {item}" for item in filtered.plot_fuel))
        if filtered.character_info:
            sections.append("## 人物维度\n" + "\n".join(f"- {item}" for item in filtered.character_info))
        if filtered.world_fragments:
            sections.append("## 世界碎片\n" + "\n".join(f"- {item}" for item in filtered.world_fragments))
        if filtered.narrative_techniques:
            sections.append("## 叙事技法\n" + "\n".join(f"- {item}" for item in filtered.narrative_techniques))
        if filtered.warnings:
            sections.append("## 冲突警告\n" + "\n".join(f"- {item}" for item in filtered.warnings))

        if not sections:
            return "（未检索到有效上下文）"

        return "\n\n".join(sections)


__all__ = ["PipelineOrchestrator", "PipelineConfig"]
