# AIMETA P=写作流水线编排_统一生成入口|R=上下文汇聚_生成_审查_优化|NR=不含API路由|E=PipelineOrchestrator|X=internal|A=编排器|D=fastapi,sqlalchemy|S=db,net|RD=./README.ai
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple, TypedDict

from fastapi import HTTPException
from langgraph.graph import END, START, StateGraph
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..core.config import settings
from ..models.novel import Chapter
from ..models.project_memory import ProjectMemory
from ..repositories.system_config_repository import SystemConfigRepository
from ..services.ai_review_service import AIReviewService
from ..services.chapter_context_service import ChapterContextService
from ..services.chapter_generation_trace_service import ChapterGenerationTraceService
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
from ..services.event_bus import publish_chapter_status
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
from ..schemas.novel import ChapterGenerationStatus
from ..utils.json_utils import remove_think_tags, unwrap_markdown_json

logger = logging.getLogger(__name__)
# 使用固定 UTC+8，避免在 Windows/Python 环境缺少 tzdata 时 ZoneInfo 初始化失败。
CN_TIMEZONE = timezone(timedelta(hours=8), name="Asia/Shanghai")
VERSION_REFERENCE_PATTERN = re.compile(r"版本\s*(\d+)|第\s*(\d+)\s*(?:个\s*)?(?:版本|版)")
MIN_CHAPTER_VERSION_COUNT = 1
MAX_CHAPTER_VERSION_COUNT = 2


def _clamp_version_count(value: int) -> int:
    return max(MIN_CHAPTER_VERSION_COUNT, min(MAX_CHAPTER_VERSION_COUNT, int(value)))
WRITER_GENERATION_MAX_TOKENS = 7000
TRACE_NODE_META: Dict[str, Tuple[str, str]] = {
    "context_prep": ("整理前文", "context_prep"),
    "director_mission": ("规划剧情", "chapter_mission"),
    "rag_retrieval": ("调用设定", "rag_retrieval"),
    "draft_generation": ("生成正文", "chapter_writing"),
    "quality_review": ("AI评审", "version_review"),
    "review_refinement": ("修复润色", "chapter_optimization"),
    "persist_versions": ("保存草稿", "save_draft"),
}

# trace node_key → GRAPH_SEQUENCE 节点名；save_draft 兼容旧 trace
TRACE_KEY_TO_GRAPH_NODE: Dict[str, str] = {
    "context_prep": "collect_context",
    "director_mission": "generate_chapter_mission",
    "rag_retrieval": "prepare_retrieval_context",
    "draft_generation": "generate_versions",
    "quality_review": "review_versions",
    "review_refinement": "apply_post_generation_reviews",
    "persist_versions": "persist_versions",
    "save_draft": "persist_versions",
}
# 恢复子图强制前置的纯计算节点，用于重建 enhanced_flow / memory_context / visibility_context
RECOVERY_PREREQ_NODES: Tuple[str, ...] = (
    "build_visibility_context",
    "prepare_enhanced_context",
    "prepare_memory_context",
)
# 节点级恢复起点对应的 UI 进度与 step_index（仅展示用）
_RESUME_PROGRESS: Dict[str, int] = {
    "context_prep": 10,
    "director_mission": 25,
    "rag_retrieval": 35,
    "draft_generation": 55,
    "quality_review": 70,
    "review_refinement": 85,
    "persist_versions": 95,
}
_RESUME_STEP_INDEX: Dict[str, int] = {
    "context_prep": 1,
    "director_mission": 2,
    "rag_retrieval": 3,
    "draft_generation": 4,
    "quality_review": 5,
    "review_refinement": 6,
    "persist_versions": 7,
}


class PipelineGraphState(TypedDict, total=False):
    """LangGraph 节点间传递的高级写作流水线状态。"""

    project_id: str
    chapter_number: int
    user_id: int
    writing_notes: Optional[str]
    flow_config: Optional[Dict[str, Any]]
    config: "PipelineConfig"
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


class _RebuildError(Exception):
    """节点级恢复从 trace 还原 State 失败时抛出，调用方应回退到更早节点或全量生成。"""


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
        self.trace_service = ChapterGenerationTraceService(session)

    async def generate_chapter(
        self,
        *,
        project_id: str,
        chapter_number: int,
        user_id: int,
        writing_notes: Optional[str] = None,
        flow_config: Optional[Dict[str, Any]] = None,
        from_node_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        if from_node_key:
            return await self._resume_generation(
                project_id=project_id,
                chapter_number=chapter_number,
                user_id=user_id,
                from_node_key=from_node_key,
                writing_notes=writing_notes,
                flow_config=flow_config,
            )
        initial_state: PipelineGraphState = {
            "project_id": project_id,
            "chapter_number": chapter_number,
            "user_id": user_id,
            "writing_notes": writing_notes,
            "flow_config": flow_config,
        }
        graph = self._build_generation_graph()
        try:
            final_state = await graph.ainvoke(initial_state)
        except HTTPException as e:
            await self._mark_generation_failed(project_id=project_id, chapter_number=chapter_number, error=e)
            raise
        except Exception as e:
            await self._mark_generation_failed(project_id=project_id, chapter_number=chapter_number, error=e)
            raise
        return final_state["response"]

    async def _resume_generation(
        self,
        *,
        project_id: str,
        chapter_number: int,
        user_id: int,
        from_node_key: str,
        writing_notes: Optional[str] = None,
        flow_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """从指定 trace 节点恢复生成：还原前置 State → 清目标及之后 trace → 跑恢复子图。"""
        normalized_key = self._normalize_trace_key(from_node_key)
        if normalized_key is None:
            raise HTTPException(status_code=400, detail=f"不支持的恢复节点: {from_node_key}")
        start_graph_node = TRACE_KEY_TO_GRAPH_NODE[normalized_key]

        traces = await self.trace_service.list_for_chapter(
            project_id=project_id, chapter_number=chapter_number,
        )
        if not traces:
            raise HTTPException(status_code=409, detail="无可恢复的 trace 记录，请使用整章生成")

        try:
            rebuilt_state = await self._rebuild_state_from_traces(
                traces=traces,
                from_node_key=normalized_key,
                project_id=project_id,
                chapter_number=chapter_number,
                user_id=user_id,
                writing_notes=writing_notes,
                flow_config=flow_config,
            )
        except _RebuildError as exc:
            raise HTTPException(
                status_code=409,
                detail=f"无法从 {from_node_key} 恢复，请尝试更早的节点或整章生成：{exc}",
            ) from exc

        node_order = {
            key: self.GRAPH_SEQUENCE.index(graph_node)
            for key, graph_node in TRACE_KEY_TO_GRAPH_NODE.items()
        }
        await self.trace_service.clear_from_node(
            project_id=project_id,
            chapter_number=chapter_number,
            from_node_key=normalized_key,
            node_order=node_order,
        )

        await self._set_chapter_generation_state(
            project_id=project_id,
            chapter_number=chapter_number,
            status="generating",
            progress=_RESUME_PROGRESS.get(normalized_key, 0),
            step=normalized_key,
            step_index=_RESUME_STEP_INDEX.get(normalized_key, 1),
            step_total=7,
            reset_selected_version=True,
        )

        graph = self._build_recovery_graph(start_graph_node=start_graph_node)
        try:
            final_state = await graph.ainvoke(rebuilt_state)
        except HTTPException as exc:
            await self._mark_generation_failed_resume(
                project_id=project_id,
                chapter_number=chapter_number,
                error=exc,
                from_node_key=normalized_key,
            )
            raise
        except Exception as exc:
            await self._mark_generation_failed_resume(
                project_id=project_id,
                chapter_number=chapter_number,
                error=exc,
                from_node_key=normalized_key,
            )
            raise
        return final_state["response"]

    @staticmethod
    def _normalize_trace_key(raw: str) -> Optional[str]:
        """归一化外部传入的 node_key 到 TRACE_KEY_TO_GRAPH_NODE 的键空间。"""
        key = (raw or "").strip()
        return key if key in TRACE_KEY_TO_GRAPH_NODE else None

    async def _mark_generation_failed_resume(
        self,
        *,
        project_id: str,
        chapter_number: int,
        error: Optional[Exception],
        from_node_key: str,
    ) -> None:
        """恢复生成失败：不清空全部 trace，failed 记录挂在 from_node_key 上并覆盖旧 failed。"""
        try:
            await self.session.rollback()
        except Exception:
            pass
        try:
            result = await self.session.execute(
                select(Chapter).where(
                    Chapter.project_id == project_id,
                    Chapter.chapter_number == chapter_number,
                )
            )
            chapter = result.scalars().first()
            if not chapter:
                return

            error_msg = ""
            if error:
                error_msg = str(getattr(error, "detail", None) or error)
            chapter.status = "failed"
            chapter.generation_progress = 0
            truncated = error_msg[:50] if error_msg else ""
            chapter.generation_step = f"failed|error={truncated}" if error_msg else "failed"
            chapter.generation_step_index = 0
            chapter.generation_step_total = 7
            await self.session.commit()
            await publish_chapter_status(project_id, chapter_number)

            await self.trace_service.delete_failed_traces(
                project_id=project_id, chapter_number=chapter_number,
            )
            label, stage = TRACE_NODE_META.get(from_node_key, (from_node_key, from_node_key))
            await self.trace_service.record_failure(
                project_id=project_id,
                chapter_number=chapter_number,
                node_key=from_node_key,
                node_label=label,
                stage=stage,
                error=error_msg or "恢复生成流程失败",
                metadata={
                    "trace_kind": "workflow",
                    "call_type": "generation_failure",
                    "summary": f"从 {from_node_key} 恢复生成失败",
                    "model_calls": [],
                },
                uses_llm=False,
            )
        except Exception:
            logger.exception(
                "Pipeline 项目 %s 第 %s 章恢复失败后标记 failed 失败",
                project_id,
                chapter_number,
            )

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

    def _build_recovery_graph(self, *, start_graph_node: str):
        """构建节点级恢复子图：从 start_graph_node 起、含其后所有节点、到 END。

        不含 initialize_chapter（避免触发 clear_for_chapter 清空前置 trace）；
        强制前置排在 start 之前的 RECOVERY_PREREQ_NODES 纯计算节点，以重建
        enhanced_flow / memory_context / visibility_context 等不可序列化产物。
        """
        if start_graph_node not in self.GRAPH_SEQUENCE:
            raise ValueError(f"未知的恢复起点节点: {start_graph_node}")
        start_idx = self.GRAPH_SEQUENCE.index(start_graph_node)
        prereq_to_add = [
            node for node in RECOVERY_PREREQ_NODES
            if self.GRAPH_SEQUENCE.index(node) < start_idx
        ]
        ordered = prereq_to_add + list(self.GRAPH_SEQUENCE[start_idx:])

        workflow = StateGraph(PipelineGraphState)
        for node_name in ordered:
            workflow.add_node(node_name, getattr(self, f"_graph_{node_name}"))
        previous = START
        for node_name in ordered:
            workflow.add_edge(previous, node_name)
            previous = node_name
        workflow.add_edge(previous, END)
        return workflow.compile()

    @staticmethod
    def _replay_ai_review_side_effect(
        *,
        versions: List[Dict[str, Any]],
        review_summaries: Dict[str, Any],
        best_version_index: int,
    ) -> None:
        """从 quality_review 落盘的 review_summaries.ai_review 重放 versions[idx].metadata.ai_review 副作用。

        quality_review 节点在图返回外给 versions 写入了 ai_review 副作用（未进 State、未进 trace 的
        output_payload），节点级恢复还原到 quality_review 之后的状态时需据此重建该副作用。
        """
        ai_review = (review_summaries or {}).get("ai_review")
        if not isinstance(ai_review, dict) or not versions:
            return
        if ai_review.get("mode") == "single":
            versions[0].setdefault("metadata", {})["ai_review"] = {
                "is_best": True,
                "evaluation": ai_review.get("evaluation"),
                "suggestions": ai_review.get("suggestions"),
                "mode": "single",
            }
            return
        version_reviews = ai_review.get("version_reviews") or []
        review_map = {
            vr.get("version_number"): vr
            for vr in version_reviews
            if isinstance(vr, dict) and vr.get("version_number") is not None
        }
        for idx, variant in enumerate(versions):
            vr = review_map.get(idx + 1)
            variant.setdefault("metadata", {})["ai_review"] = {
                "is_best": idx == best_version_index,
                "scores": vr.get("scores") if vr else ai_review.get("scores"),
                "evaluation": vr.get("overall_review") if vr else None,
                "pros": (vr.get("pros") or []) if vr else [],
                "cons": (vr.get("cons") or []) if vr else [],
                "flaws": ai_review.get("flaws") if idx == best_version_index else None,
                "suggestions": ai_review.get("suggestions") if idx == best_version_index else None,
            }

    def _trace_node_seq(self, node_key: str) -> int:
        """trace node_key 在 GRAPH_SEQUENCE 中的序号；未知 key 返回 -1。"""
        graph_node = TRACE_KEY_TO_GRAPH_NODE.get(node_key)
        if graph_node is None or graph_node not in self.GRAPH_SEQUENCE:
            return -1
        return self.GRAPH_SEQUENCE.index(graph_node)

    async def _rebuild_state_from_traces(
        self,
        *,
        traces: List[ChapterGenerationTrace],
        from_node_key: str,
        project_id: str,
        chapter_number: int,
        user_id: int,
        writing_notes: Optional[str] = None,
        flow_config: Optional[Dict[str, Any]] = None,
    ) -> PipelineGraphState:
        """从 from_node_key 之前的 success trace 还原 LangGraph State。

        只还原 trace 节点产物；纯计算节点产物由恢复子图重算。
        versions 按 from_node_key 取对应时序快照（draft 定稿 → ai_review 副作用 → 润色改写）。
        """
        from_seq = self._trace_node_seq(from_node_key)
        if from_seq < 0:
            raise _RebuildError(f"未知的恢复节点: {from_node_key}")

        def latest_success(key: str) -> Optional[ChapterGenerationTrace]:
            candidates = [t for t in traces if t.node_key == key and t.status == "success"]
            if not candidates:
                return None
            return max(candidates, key=lambda t: (t.created_at, t.id))

        def output_of(t: Optional[ChapterGenerationTrace]) -> Dict[str, Any]:
            return (t.metadata_ or {}).get("output_payload") or {} if t is not None else {}

        def input_of(t: Optional[ChapterGenerationTrace]) -> Dict[str, Any]:
            return (t.metadata_ or {}).get("input_payload") or {} if t is not None else {}

        state: PipelineGraphState = {
            "project_id": project_id,
            "chapter_number": chapter_number,
            "user_id": user_id,
        }
        if writing_notes is not None:
            state["writing_notes"] = writing_notes
        if flow_config is not None:
            state["flow_config"] = flow_config

        if from_seq > self._trace_node_seq("context_prep"):
            ctx = latest_success("context_prep")
            if ctx is None:
                raise _RebuildError("缺少 context_prep 的成功记录，无法还原前文与蓝图")
            op = output_of(ctx)
            ip = input_of(ctx)
            completed = op.get("completed_chapters") or []
            completed_summaries = op.get("completed_summaries") or [
                c.get("summary", "")
                for c in completed
                if isinstance(c, dict) and c.get("summary")
            ]
            state["history_context"] = {
                "previous_summary": op.get("previous_summary", ""),
                "previous_tail": op.get("previous_tail", ""),
                "completed_chapters": completed,
                "completed_summaries": completed_summaries,
                "model_calls": [],
                "trace_metrics": {},
            }
            blueprint_dict = op.get("blueprint_dict") or {}
            state["blueprint_dict"] = blueprint_dict
            state["all_characters"] = op.get("all_characters") or [
                c.get("name")
                for c in blueprint_dict.get("characters", [])
                if isinstance(c, dict) and c.get("name")
            ]
            state["outline_title"] = ip.get("outline_title") or f"第{chapter_number}章"
            state["outline_summary"] = ip.get("outline_summary") or ""
            state["writing_notes"] = state.get("writing_notes") or ip.get("writing_notes") or "无额外写作指令"
            state["config"] = await self._resolve_config_from_trace_or_flow(op, flow_config)

        if from_seq > self._trace_node_seq("director_mission"):
            dm = latest_success("director_mission")
            if dm is None or not dm.cleaned_output:
                raise _RebuildError("缺少 director_mission 的成功记录，无法还原章节导演脚本")
            try:
                mission = json.loads(dm.cleaned_output)
            except (json.JSONDecodeError, TypeError) as exc:
                raise _RebuildError(f"director_mission 记录无法解析为 JSON: {exc}")
            state["chapter_mission"] = mission
            if isinstance(mission, dict):
                state["allowed_new_characters"] = mission.get("allowed_new_characters") or []

        if from_seq > self._trace_node_seq("rag_retrieval"):
            rag = latest_success("rag_retrieval")
            if rag is not None:
                op = output_of(rag)
                state["rag_context"] = op.get("rag_context")
                state["knowledge_context"] = op.get("knowledge_context")
                state["rag_stats"] = op.get("rag_stats")

        if from_seq > self._trace_node_seq("draft_generation"):
            versions = self._rebuild_versions(traces)
            if not versions:
                raise _RebuildError("缺少 draft_generation 的成功记录，无法还原候选版本")
            state["versions"] = versions

        if from_seq > self._trace_node_seq("quality_review"):
            qr = latest_success("quality_review")
            if qr is None:
                raise _RebuildError("缺少 quality_review 的成功记录，无法还原评审结果")
            op = output_of(qr)
            versions = state.get("versions") or []
            best_idx = op.get("best_version_index", 0)
            if versions:
                best_idx = max(0, min(int(best_idx), len(versions) - 1))
            state["best_version_index"] = best_idx
            review_summaries = op.get("review_summaries") or {}
            state["review_summaries"] = review_summaries
            if versions:
                self._replay_ai_review_side_effect(
                    versions=versions,
                    review_summaries=review_summaries,
                    best_version_index=best_idx,
                )

        if from_seq > self._trace_node_seq("review_refinement"):
            rr = latest_success("review_refinement")
            if rr is None or not rr.cleaned_output:
                raise _RebuildError("缺少 review_refinement 的成功记录，无法还原润色结果")
            versions = state.get("versions") or []
            best_idx = state.get("best_version_index", 0)
            if versions and 0 <= best_idx < len(versions):
                versions[best_idx]["content"] = rr.cleaned_output

        return state

    async def _resolve_config_from_trace_or_flow(
        self,
        trace_output: Dict[str, Any],
        flow_config: Optional[Dict[str, Any]],
    ) -> PipelineConfig:
        """优先从 context_prep trace 的 config 字段还原，否则用 flow_config 重算。"""
        cfg_dict = trace_output.get("config")
        if isinstance(cfg_dict, dict):
            valid = PipelineConfig.__dataclass_fields__
            kwargs = {k: v for k, v in cfg_dict.items() if k in valid}
            if kwargs:
                return PipelineConfig(**kwargs)
        if flow_config is not None:
            return await self._resolve_config(flow_config)
        raise _RebuildError("trace 未记录 config 且未重传 flow_config，无法还原流水线配置")

    def _rebuild_versions(
        self,
        traces: List[ChapterGenerationTrace],
    ) -> List[Dict[str, Any]]:
        """从 trace 组装 versions，优先取 quality_review input_payload 的完整正文，其次 draft 定稿 trace。"""
        qr_candidates = [
            t for t in traces
            if t.node_key == "quality_review" and t.status == "success"
        ]
        if qr_candidates:
            qr_latest = max(qr_candidates, key=lambda t: (t.created_at, t.id))
            qr_versions = (qr_latest.metadata_ or {}).get("input_payload", {}).get("versions")
            if isinstance(qr_versions, list) and qr_versions:
                return [
                    {
                        "index": idx,
                        "content": (v.get("content") if isinstance(v, dict) else "") or "",
                        "metadata": (v.get("metadata") if isinstance(v, dict) else {}) or {},
                    }
                    for idx, v in enumerate(qr_versions)
                ]

        by_version: Dict[int, ChapterGenerationTrace] = {}
        for t in traces:
            if t.node_key != "draft_generation" or t.status != "success":
                continue
            meta = t.metadata_ or {}
            op = meta.get("output_payload") or {}
            metrics = meta.get("metrics") or {}
            idx = op.get("version_index") or metrics.get("version_index")
            if idx is None:
                continue
            existing = by_version.get(idx)
            if existing is None or (t.created_at, t.id) > (existing.created_at, existing.id):
                by_version[idx] = t
        versions: List[Dict[str, Any]] = []
        for idx in sorted(by_version.keys()):
            t = by_version[idx]
            op = (t.metadata_ or {}).get("output_payload") or {}
            full = op.get("full_content")
            if not full:
                full = t.cleaned_output or ""
                logger.warning("draft_generation trace 缺 full_content，退化使用 cleaned_output（可能含定稿前内容）")
            versions.append({
                "index": len(versions),
                "content": full,
                "metadata": op.get("version_metadata") or {},
            })
        return versions

    async def _mark_generation_failed(
        self, *, project_id: str, chapter_number: int, error: Optional[Exception] = None
    ) -> None:
        """生成图中任一节点失败后，把已初始化章节收敛到 failed。"""
        try:
            await self.session.rollback()
        except Exception:
            pass

        try:
            result = await self.session.execute(
                select(Chapter).where(
                    Chapter.project_id == project_id,
                    Chapter.chapter_number == chapter_number,
                )
            )
            chapter = result.scalars().first()
            if not chapter:
                return

            current_step = chapter.generation_step or ""
            error_msg = ""
            if error:
                if hasattr(error, "detail") and error.detail:
                    error_msg = str(error.detail)
                else:
                    error_msg = str(error)
            node_key, node_label, stage = self._resolve_failure_trace_node(
                current_step=current_step,
                error_msg=error_msg,
            )

            chapter.status = "failed"
            chapter.generation_progress = 0
            if error:
                truncated_msg = error_msg[:50]
                chapter.generation_step = f"failed|error={truncated_msg}"
            else:
                chapter.generation_step = "failed"
            chapter.generation_step_index = 0
            chapter.generation_step_total = 7
            await self.session.commit()
            await publish_chapter_status(project_id, chapter_number)
            await self._record_terminal_failure_trace(
                project_id=project_id,
                chapter_number=chapter_number,
                node_key=node_key,
                node_label=node_label,
                stage=stage,
                error_msg=error_msg or "生成流程失败，但未收到具体错误信息",
            )
        except Exception:
            logger.exception(
                "Pipeline 项目 %s 第 %s 章标记 failed 失败",
                project_id,
                chapter_number,
            )

    @staticmethod
    def _resolve_failure_trace_node(*, current_step: str, error_msg: str) -> Tuple[str, str, str]:
        base_key = (current_step or "").split("|", 1)[0].strip()
        if base_key in TRACE_NODE_META:
            label, stage = TRACE_NODE_META[base_key]
            return base_key, label, stage

        lower_error = (error_msg or "").lower()
        if any(token in lower_error for token in ("润色", "修复", "optimization", "refinement")):
            return "review_refinement", *TRACE_NODE_META["review_refinement"]
        if any(token in lower_error for token in ("评审", "评分", "连贯", "evaluation", "review")):
            return "quality_review", *TRACE_NODE_META["quality_review"]
        if any(token in lower_error for token in ("保存", "存储", "save", "persist")):
            return "persist_versions", *TRACE_NODE_META["persist_versions"]
        if any(token in lower_error for token in ("设定", "retrieval", "rag")):
            return "rag_retrieval", *TRACE_NODE_META["rag_retrieval"]
        if any(token in lower_error for token in ("剧情", "规划", "director", "mission")):
            return "director_mission", *TRACE_NODE_META["director_mission"]
        if any(token in lower_error for token in ("前文", "上下文", "context")):
            return "context_prep", *TRACE_NODE_META["context_prep"]
        return "draft_generation", *TRACE_NODE_META["draft_generation"]

    async def _record_terminal_failure_trace(
        self,
        *,
        project_id: str,
        chapter_number: int,
        node_key: str,
        node_label: str,
        stage: str,
        error_msg: str,
    ) -> None:
        """兜底记录未被具体节点捕获的失败，便于刷新后仍能查看真实错误。"""
        try:
            traces = await self.trace_service.list_for_chapter(
                project_id=project_id,
                chapter_number=chapter_number,
            )
            if any(trace.status == "failed" for trace in traces):
                return
            now = datetime.now(CN_TIMEZONE)
            await self.trace_service.record_failure(
                project_id=project_id,
                chapter_number=chapter_number,
                node_key=node_key,
                node_label=node_label,
                stage=stage,
                error=error_msg,
                metadata={
                    "trace_kind": "workflow",
                    "call_type": "generation_failure",
                    "summary": "生成流程异常终止，系统已将章节标记为生成失败。",
                    "actions": [
                        "捕获 LangGraph 生成流程异常",
                        "写入章节 failed 状态",
                        "保留完整错误原因供前端失败卡片和节点详情展示",
                    ],
                    "model_calls": [],
                },
                uses_llm=False,
                started_at=now,
                ended_at=now,
            )
        except Exception:
            logger.exception(
                "Pipeline 项目 %s 第 %s 章记录 failed trace 失败",
                project_id,
                chapter_number,
            )

    async def _load_generation_project_schema(self, project_id: str, user_id: int):
        """显式重新加载项目快照，避免复用跨 commit 的 ORM 关系对象。"""
        return await self.novel_service.get_project_schema(project_id, user_id)

    async def _get_chapter_for_update(self, *, project_id: str, chapter_number: int) -> Chapter:
        stmt = select(Chapter).where(
            Chapter.project_id == project_id,
            Chapter.chapter_number == chapter_number,
        )
        result = await self.session.execute(stmt)
        chapter = result.scalars().first()
        if chapter:
            return chapter
        return await self.novel_service.get_or_create_chapter(project_id, chapter_number)

    async def _set_chapter_generation_state(
        self,
        *,
        project_id: str,
        chapter_number: int,
        progress: int,
        step: str,
        step_index: int,
        status: Optional[str] = None,
        step_total: Optional[int] = None,
        started_at: Optional[datetime] = None,
        reset_selected_version: bool = False,
    ) -> Chapter:
        """用显式查询更新章节状态，避免 LangGraph state 保存旧 ORM 实体。"""
        chapter = await self._get_chapter_for_update(
            project_id=project_id,
            chapter_number=chapter_number,
        )
        if reset_selected_version:
            chapter.real_summary = None
            chapter.selected_version_id = None
            chapter.selected_version = None
        if status is not None:
            chapter.status = status
        if started_at is not None:
            chapter.generation_started_at = started_at
        chapter.generation_progress = progress
        chapter.generation_step = step
        chapter.generation_step_index = step_index
        if step_total is not None:
            chapter.generation_step_total = step_total
        await self.session.commit()
        await publish_chapter_status(project_id, chapter_number)
        return chapter

    async def _graph_initialize_chapter(self, state: PipelineGraphState) -> PipelineGraphState:
        config = await self._resolve_config(state.get("flow_config"))
        project_id = state["project_id"]
        chapter_number = state["chapter_number"]
        await self.novel_service.ensure_project_owner(project_id, state["user_id"])

        outline = await self.novel_service.get_outline(project_id, chapter_number)
        if not outline:
            raise HTTPException(status_code=404, detail="蓝图中未找到对应章节纲要")

        await self._set_chapter_generation_state(
            project_id=project_id,
            chapter_number=chapter_number,
            status="generating",
            progress=3,
            step="context_prep",
            step_index=1,
            step_total=7,
            started_at=datetime.now(CN_TIMEZONE),
            reset_selected_version=True,
        )
        await self.trace_service.clear_for_chapter(
            project_id=project_id,
            chapter_number=chapter_number,
        )

        return {
            "config": config,
            "outline_title": outline.title or f"第{outline.chapter_number}章",
            "outline_summary": outline.summary or "暂无摘要",
            "writing_notes": state.get("writing_notes") or "无额外写作指令",
        }

    async def _graph_collect_context(self, state: PipelineGraphState) -> PipelineGraphState:
        started_at = datetime.now(CN_TIMEZONE)
        project_schema = await self._load_generation_project_schema(
            state["project_id"],
            state["user_id"],
        )
        outlines = project_schema.blueprint.chapter_outline if project_schema.blueprint else []
        outlines_map = {item.chapter_number: item for item in outlines}
        history_context = await self._collect_history_context(
            project_id=state["project_id"],
            chapter_number=state["chapter_number"],
            outlines_map=outlines_map,
            user_id=state["user_id"],
        )
        blueprint_dict = self._normalize_blueprint(project_schema.blueprint.model_dump())
        all_characters = [c.get("name") for c in blueprint_dict.get("characters", []) if c.get("name")]
        await self.trace_service.record_success(
            project_id=state["project_id"],
            chapter_number=state["chapter_number"],
            node_key="context_prep",
            node_label="整理前文",
            stage="context_prep",
            input_payload={
                "outline_title": state["outline_title"],
                "outline_summary": state["outline_summary"],
                "writing_notes": state["writing_notes"],
            },
            output_payload={
                "previous_summary": history_context.get("previous_summary"),
                "previous_tail": history_context.get("previous_tail"),
                "completed_chapters": history_context.get("completed_chapters"),
                "completed_summaries": history_context.get("completed_summaries", []),
                "blueprint_dict": blueprint_dict,
                "all_characters": all_characters,
                "config": asdict(state["config"]),
            },
            metadata={
                "trace_kind": "workflow",
                "call_type": "database_context",
                "summary": "读取前文章节与项目蓝图，整理上一章摘要、上一章结尾和已完成章节列表。",
                "actions": [
                    "读取项目蓝图与章节大纲",
                    "查询当前章节之前已选中正文的章节",
                    "提取上一章结尾片段",
                    "是否调用摘要模型由前文章节是否缺少 real_summary 决定",
                ],
                "data_reads": [
                    "NovelProject / NovelBlueprint",
                    "Chapter.selected_version",
                    "Chapter.real_summary",
                ],
                "model_calls": history_context.get("model_calls", []),
                "skip_reason": None
                if history_context.get("model_calls")
                else "前文章节均已有摘要，或这是第一章，无需补摘要模型调用",
                "metrics": history_context.get("trace_metrics", {}),
            },
            started_at=started_at,
            ended_at=datetime.now(CN_TIMEZONE),
        )

        return {
            "history_context": history_context,
            "project_schema": project_schema,
            "blueprint_dict": blueprint_dict,
            "all_characters": all_characters,
        }

    async def _graph_generate_chapter_mission(self, state: PipelineGraphState) -> PipelineGraphState:
        await self._set_chapter_generation_state(
            project_id=state["project_id"],
            chapter_number=state["chapter_number"],
            progress=12,
            step="director_mission",
            step_index=2,
        )
        chapter_mission = await self._generate_chapter_mission(
            project_id=state["project_id"],
            chapter_number=state["chapter_number"],
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
        await self._set_chapter_generation_state(
            project_id=state["project_id"],
            chapter_number=state["chapter_number"],
            progress=28,
            step="director_mission",
            step_index=2,
        )

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
        started_at = datetime.now(CN_TIMEZONE)
        await self._set_chapter_generation_state(
            project_id=state["project_id"],
            chapter_number=state["chapter_number"],
            progress=42,
            step="rag_retrieval",
            step_index=3,
        )
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
        await self.trace_service.record_success(
            project_id=state["project_id"],
            chapter_number=state["chapter_number"],
            node_key="rag_retrieval",
            node_label="调用设定",
            stage="rag_retrieval",
            input_payload={
                "rag_enabled": config.enable_rag,
                "rag_mode": config.rag_mode,
                "outline_title": state["outline_title"],
                "outline_summary": state["outline_summary"],
                "writing_notes": state["writing_notes"],
            },
            output_payload={
                "rag_stats": rag_stats,
                "rag_context": rag_context,
                "knowledge_context": knowledge_context,
            },
            metadata={
                "trace_kind": "workflow",
                "call_type": "rag_retrieval",
                "summary": "按 RAG 配置检索本章可引用的历史片段、章节摘要或精筛设定上下文。",
                "actions": [
                    "检查 RAG 是否启用",
                    "根据章节标题、摘要和写作指令构造检索依据",
                    "simple 模式调用向量模型生成查询 embedding 后检索",
                    "two_stage 模式先生成检索词，再做向量检索和知识过滤",
                ],
                "data_reads": [
                    "向量库 rag_chunks / rag_summaries",
                    "ProjectMemory.global_summary（two_stage 模式）",
                    "ChapterBlueprint（two_stage 模式）",
                ],
                "model_calls": self._describe_rag_model_calls(config, rag_stats),
                "skip_reason": self._resolve_rag_skip_reason(config, rag_stats),
                "metrics": rag_stats or {},
            },
            started_at=started_at,
            ended_at=datetime.now(CN_TIMEZONE),
        )

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
        await self._set_chapter_generation_state(
            project_id=state["project_id"],
            chapter_number=state["chapter_number"],
            progress=55,
            step="draft_generation",
            step_index=4,
        )

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
            await self._set_chapter_generation_state(
                project_id=state["project_id"],
                chapter_number=state["chapter_number"],
                progress=55 + int((idx / max(version_count, 1)) * 25),
                step="draft_generation",
                step_index=4,
            )
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
            await self._set_chapter_generation_state(
                project_id=state["project_id"],
                chapter_number=state["chapter_number"],
                progress=55 + int(((idx + 1) / max(version_count, 1)) * 25),
                step="draft_generation",
                step_index=4,
            )

        return {"versions": versions}

    async def _graph_review_versions(self, state: PipelineGraphState) -> PipelineGraphState:
        started_at = datetime.now(CN_TIMEZONE)
        await self._set_chapter_generation_state(
            project_id=state["project_id"],
            chapter_number=state["chapter_number"],
            progress=86,
            step="quality_review",
            step_index=5,
        )

        review_context = self._build_review_context(
            writer_blueprint=state["writer_blueprint"],
            blueprint_dict=state["blueprint_dict"],
            chapter_number=state["chapter_number"],
            outline_title=state["outline_title"],
            outline_summary=state["outline_summary"],
            chapter_mission=state.get("chapter_mission"),
            history_context=state["history_context"],
        )
        try:
            best_version_index, ai_review_result = await self._run_ai_review(
                versions=state["versions"],
                chapter_mission=state.get("chapter_mission"),
                user_id=state["user_id"],
                context=review_context,
            )
        except Exception as exc:
            await self.trace_service.record_failure(
                project_id=state["project_id"],
                chapter_number=state["chapter_number"],
                node_key="quality_review",
                node_label="AI评审",
                stage="version_review",
                error=str(exc),
                input_payload={
                    "version_count": len(state["versions"]),
                    "content_lengths": [
                        len(version.get("content", "") or "") for version in state["versions"]
                    ],
                },
                metadata={
                    "trace_kind": "llm",
                    "call_type": "chat_llm",
                    "summary": "AI评审候选版本失败，生成流程终止。",
                    "actions": [
                        "整理候选版本",
                        "单版本生成修改意见，或多版本对比选优并生成修改意见",
                    ],
                    "model_calls": [
                        {
                            "stage": "version_review",
                            "call_type": "chat_llm",
                            "purpose": "AI评审候选版本并产出修复润色建议",
                        }
                    ],
                },
                started_at=started_at,
                ended_at=datetime.now(CN_TIMEZONE),
            )
            raise

        review_summaries: Dict[str, Any] = {}
        if ai_review_result:
            review_summaries["ai_review"] = ai_review_result

        versions = state["versions"]
        if versions:
            best_version_index = max(0, min(best_version_index, len(versions) - 1))
        else:
            best_version_index = 0

        await self.trace_service.record_success(
            project_id=state["project_id"],
            chapter_number=state["chapter_number"],
            node_key="quality_review",
            node_label="AI评审",
            stage="version_review",
            input_payload={
                "version_count": len(versions),
                "content_lengths": [len(version.get("content", "") or "") for version in versions],
                "versions": [
                    {
                        "index": idx,
                        "content": version.get("content", ""),
                        "metadata": version.get("metadata", {}),
                    }
                    for idx, version in enumerate(versions)
                ],
            },
            output_payload={
                "best_version_index": best_version_index,
                "review_summaries": review_summaries,
                "review_mode": "single" if len(versions) == 1 else "compare",
            },
            metadata={
                "trace_kind": "llm",
                "call_type": "chat_llm",
                "summary": "AI评审候选正文版本；单版本产出修改意见，多版本对比选出最佳版本并产出修改建议。",
                "actions": [
                    "统计候选版本数量和正文长度",
                    "单版本调用评审模型产出修改意见",
                    "多版本调用评审模型比较版本并选出最佳",
                    "保留评审结果供后续自动修复润色使用",
                ],
                "model_calls": [
                    {
                        "stage": "version_review",
                        "call_type": "chat_llm",
                        "purpose": "AI评审候选版本并产出修复润色建议",
                    }
                ],
                "skip_reason": None,
                "metrics": {
                    "version_count": len(versions),
                    "content_lengths": [len(version.get("content", "") or "") for version in versions],
                    "best_version_index": best_version_index,
                },
            },
            started_at=started_at,
            ended_at=datetime.now(CN_TIMEZONE),
        )

        return {"best_version_index": best_version_index, "review_summaries": review_summaries}

    async def _graph_apply_post_generation_reviews(self, state: PipelineGraphState) -> PipelineGraphState:
        versions = state["versions"]
        if not versions:
            return {"versions": versions, "review_summaries": state["review_summaries"]}

        config = state["config"]
        review_summaries = state["review_summaries"]
        best_version = versions[state["best_version_index"]]
        best_content = best_version["content"]
        await self._set_chapter_generation_state(
            project_id=state["project_id"],
            chapter_number=state["chapter_number"],
            progress=92,
            step="review_refinement",
            step_index=6,
        )
        review_summary = self._build_review_refinement_summary(
            review_summaries.get("ai_review"),
            state["best_version_index"],
        )
        refined_content, refinement_report = await self._run_review_guided_refinement(
            project_id=state["project_id"],
            chapter_number=state["chapter_number"],
            source_content=best_content,
            review_summary=review_summary,
            version_number=state["best_version_index"] + 1,
            version_review=self._extract_best_version_review(
                review_summaries.get("ai_review"),
                state["best_version_index"],
            ),
            user_id=state["user_id"],
        )
        best_content = refined_content
        review_summaries["review_guided_refinement"] = refinement_report

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
        started_at = datetime.now(CN_TIMEZONE)
        versions = state["versions"]
        contents = [v.get("content", "") for v in versions]
        metadata = [v.get("metadata") for v in versions]
        evaluation_feedback = self._build_chapter_evaluation_feedback(state.get("review_summaries"))
        chapter = await self._set_chapter_generation_state(
            project_id=state["project_id"],
            chapter_number=state["chapter_number"],
            progress=98,
            step="persist_versions",
            step_index=7,
        )
        versions_models = await self.novel_service.replace_chapter_versions(
            chapter,
            contents,
            metadata,
            evaluation_feedback=evaluation_feedback,
        )

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
        await self.trace_service.record_success(
            project_id=state["project_id"],
            chapter_number=state["chapter_number"],
            node_key="persist_versions",
            node_label="保存草稿",
            stage="save_draft",
            input_payload={
                "version_count": len(contents),
                "content_lengths": [len(content or "") for content in contents],
                "recommended_version_index": state["best_version_index"],
            },
            output_payload={
                "versions": [
                    {"index": item["index"], "version_id": item["version_id"]}
                    for item in variants
                ],
                "status": ChapterGenerationStatus.WAITING_FOR_CONFIRM.value,
            },
            metadata={
                "trace_kind": "workflow",
                "call_type": "database_write",
                "summary": "将候选草稿写入版本表，等待人工确认定稿。",
                "actions": [
                    "更新章节生成状态为保存草稿",
                    "替换本轮章节候选版本列表",
                    "保留 AI 推荐版本索引供前端默认选中",
                    "将章节状态标记为待确认定稿",
                ],
                "data_writes": [
                    "chapters",
                    "chapter_versions",
                ],
                "model_calls": [],
                "skip_reason": "保存草稿节点不调用模型",
                "metrics": {
                    "version_count": len(contents),
                    "content_lengths": [len(content or "") for content in contents],
                    "recommended_version_index": state["best_version_index"],
                },
            },
            started_at=started_at,
            ended_at=datetime.now(CN_TIMEZONE),
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
        user_id: int,
    ) -> Dict[str, Any]:
        completed_summaries = []
        completed_chapters = []
        latest_prev_number = -1
        previous_summary_text = ""
        previous_tail_excerpt = ""
        summary_model_calls = []
        skipped_chapters = 0
        stmt = (
            select(Chapter)
            .options(selectinload(Chapter.selected_version))
            .where(
                Chapter.project_id == project_id,
                Chapter.chapter_number < chapter_number,
            )
            .order_by(Chapter.chapter_number)
        )
        result = await self.session.execute(stmt)
        chapters = result.scalars().all()

        for existing in chapters:
            if existing.selected_version is None or not existing.selected_version.content:
                skipped_chapters += 1
                continue
            if not existing.real_summary:
                summary = await self.llm_service.get_summary(
                    existing.selected_version.content,
                    temperature=0.15,
                    user_id=user_id,
                    timeout=180.0,
                    stage="summary_memory",
                )
                existing.real_summary = remove_think_tags(summary)
                summary_model_calls.append(
                    {
                        "stage": "summary_memory",
                        "call_type": "chat_llm",
                        "reason": f"第 {existing.chapter_number} 章缺少 real_summary，补生成前文摘要",
                        "input": "该章选中版本正文",
                        "output": "写回 Chapter.real_summary",
                    }
                )
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
            "model_calls": summary_model_calls,
            "trace_metrics": {
                "loaded_previous_chapters": len(chapters),
                "usable_previous_chapters": len(completed_chapters),
                "skipped_previous_chapters": skipped_chapters,
                "summary_model_call_count": len(summary_model_calls),
            },
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
        project_id: str,
        chapter_number: int,
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
            raise RuntimeError("规划剧情失败：缺少 chapter_plan 提示词，请联系管理员配置")

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

        started_at = datetime.now(CN_TIMEZONE)
        try:
            response = await self.llm_service.get_llm_response(
                system_prompt=plan_prompt,
                conversation_history=[{"role": "user", "content": plan_input}],
                temperature=0.3,
                user_id=user_id,
                timeout=120.0,
                stage="chapter_mission",
            )
            cleaned = remove_think_tags(response)
            normalized = unwrap_markdown_json(cleaned)
            mission = json.loads(normalized)
            await self.trace_service.record_success(
                project_id=project_id,
                chapter_number=chapter_number,
                node_key="director_mission",
                node_label="规划剧情",
                stage="chapter_mission",
                system_prompt=plan_prompt,
                user_prompt=plan_input,
                raw_response=response,
                cleaned_output=normalized,
                metadata={
                    "trace_kind": "llm",
                    "call_type": "chat_llm",
                    "summary": "调用章节规划模型，把前文、当前大纲和写作指令整理成章节导演脚本。",
                    "actions": [
                        "读取 chapter_plan 提示词",
                        "组装上一章摘要、上一章结尾、当前章节大纲、角色列表和写作指令",
                        "调用聊天模型生成结构化章节导演脚本",
                        "解析模型返回 JSON",
                    ],
                    "model_calls": [
                        {
                            "stage": "chapter_mission",
                            "call_type": "chat_llm",
                            "purpose": "生成本章冲突、节奏、POV 和允许新增角色",
                            "temperature": 0.3,
                            "timeout_seconds": 120,
                        }
                    ],
                    "metrics": {"macro_beat": mission.get("macro_beat")},
                },
                started_at=started_at,
                ended_at=datetime.now(CN_TIMEZONE),
            )
            logger.info("章节导演脚本生成完成: macro_beat=%s", mission.get("macro_beat"))
            return mission
        except Exception as exc:
            await self.trace_service.record_failure(
                project_id=project_id,
                chapter_number=chapter_number,
                node_key="director_mission",
                node_label="规划剧情",
                stage="chapter_mission",
                system_prompt=plan_prompt,
                user_prompt=plan_input,
                error=str(exc),
                metadata={
                    "trace_kind": "llm",
                    "call_type": "chat_llm",
                    "summary": "调用章节规划模型失败，生成流程终止。",
                    "actions": [
                        "读取 chapter_plan 提示词",
                        "组装章节规划输入",
                        "调用聊天模型生成章节导演脚本",
                    ],
                    "model_calls": [
                        {
                            "stage": "chapter_mission",
                            "call_type": "chat_llm",
                            "purpose": "生成本章导演脚本",
                            "temperature": 0.3,
                            "timeout_seconds": 120,
                        }
                    ],
                },
                started_at=started_at,
                ended_at=datetime.now(CN_TIMEZONE),
            )
            logger.error("生成章节导演脚本失败，终止生成流程: %s", exc)
            message = str(exc)
            if message.startswith("规划剧情失败"):
                raise
            raise RuntimeError(f"规划剧情失败：{message}") from exc

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
    def _describe_rag_model_calls(
        config: PipelineConfig,
        rag_stats: Optional[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if not config.enable_rag:
            return []

        if config.rag_mode == "two_stage":
            enabled = bool((rag_stats or {}).get("enabled", True))
            if not enabled:
                return []
            return [
                {
                    "stage": "chapter_writing",
                    "call_type": "chat_llm",
                    "purpose": "生成知识库检索关键词",
                },
                {
                    "stage": "rag_embedding",
                    "call_type": "embedding",
                    "purpose": "为每组检索词生成向量",
                },
                {
                    "stage": "chapter_writing",
                    "call_type": "chat_llm",
                    "purpose": "过滤检索结果并按情节、人物、世界碎片重组",
                },
            ]

        return [
            {
                "stage": "rag_embedding",
                "call_type": "embedding",
                "purpose": "为章节标题、摘要和写作指令生成查询向量",
            }
        ]

    @staticmethod
    def _resolve_rag_skip_reason(
        config: PipelineConfig,
        rag_stats: Optional[Dict[str, Any]],
    ) -> Optional[str]:
        if not config.enable_rag:
            return "本轮配置关闭 RAG，因此未检索设定"
        if not settings.vector_store_enabled:
            return "向量库未启用，因此跳过设定检索"
        if config.rag_mode == "two_stage" and rag_stats and rag_stats.get("enabled") is False:
            return str(rag_stats.get("error") or "两层 RAG 未启用或向量库不可用")
        return None

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
            await self.trace_service.record_success(
                project_id=project_id,
                chapter_number=chapter_number,
                node_key="draft_generation",
                node_label="生成正文",
                stage="chapter_preview",
                input_payload={
                    "outline_title": outline_title,
                    "outline_summary": outline_summary,
                    "style_hint": style_hint,
                    "memory_context": memory_context,
                    "enhanced_context_keys": sorted((enhanced_context or {}).keys()),
                },
                output_payload={
                    "full_chapter": content,
                    "preview_status": preview_meta.get("status") if isinstance(preview_meta, dict) else None,
                },
                metadata={
                    "trace_kind": "workflow",
                    "call_type": "preview_generation",
                    "summary": "使用预览生成服务分阶段生成章节正文。",
                    "actions": [
                        "组装章节预览输入",
                        "调用预览生成服务",
                        "返回完整章节和预览状态",
                    ],
                    "model_calls": [
                        {
                            "stage": "chapter_preview",
                            "call_type": "chat_llm",
                            "purpose": "分阶段生成章节预览和正文",
                        }
                    ],
                    "metrics": {
                        "version_index": index + 1,
                        "preview": True,
                        "preview_status": preview_meta.get("status") if isinstance(preview_meta, dict) else None,
                        "output_chars": len(content or ""),
                    },
                },
            )

        if not content:
            final_prompt_input = prompt_input
            if style_hint:
                final_prompt_input += f"\n\n[版本风格提示]\n{style_hint}"

            started_at = datetime.now(CN_TIMEZONE)
            try:
                response = await self.llm_service.get_llm_response(
                    system_prompt=writer_prompt,
                    conversation_history=[{"role": "user", "content": final_prompt_input}],
                    temperature=0.9,
                    user_id=user_id,
                    timeout=600.0,
                    response_format=None,
                    max_tokens=WRITER_GENERATION_MAX_TOKENS,
                    stage="chapter_writing",
                )
            except Exception as exc:
                await self.trace_service.record_failure(
                    project_id=project_id,
                    chapter_number=chapter_number,
                    node_key="draft_generation",
                    node_label="生成正文",
                    stage="chapter_writing",
                    system_prompt=writer_prompt,
                    user_prompt=final_prompt_input,
                    error=str(exc),
                    metadata={
                        "trace_kind": "llm",
                        "call_type": "chat_llm",
                        "summary": "调用正文生成模型失败。",
                        "actions": [
                            "组装世界蓝图、前文摘要、导演脚本、RAG 上下文和篇幅要求",
                            "追加版本风格提示",
                            "调用聊天模型生成完整章节正文",
                        ],
                        "model_calls": [
                            {
                                "stage": "chapter_writing",
                                "call_type": "chat_llm",
                                "purpose": "生成章节正文",
                                "temperature": 0.9,
                                "timeout_seconds": 600,
                                "max_tokens": WRITER_GENERATION_MAX_TOKENS,
                            }
                        ],
                        "metrics": {
                            "version_index": index + 1,
                            "style_hint": style_hint,
                            "prompt_chars": len(final_prompt_input),
                        },
                    },
                    started_at=started_at,
                    ended_at=datetime.now(CN_TIMEZONE),
                )
                raise
            cleaned = remove_think_tags(response)
            content = unwrap_markdown_json(cleaned)
            await self.trace_service.record_success(
                project_id=project_id,
                chapter_number=chapter_number,
                node_key="draft_generation",
                node_label="生成正文",
                stage="chapter_writing",
                system_prompt=writer_prompt,
                user_prompt=final_prompt_input,
                raw_response=response,
                cleaned_output=content,
                metadata={
                    "trace_kind": "llm",
                    "call_type": "chat_llm",
                    "summary": "调用正文生成模型，输出本章候选草稿。",
                    "actions": [
                        "组装世界蓝图、前文摘要、导演脚本、RAG 上下文和篇幅要求",
                        "追加版本风格提示",
                        "调用聊天模型生成完整章节正文",
                        "清理模型思考标签并提取正文",
                    ],
                    "model_calls": [
                        {
                            "stage": "chapter_writing",
                            "call_type": "chat_llm",
                            "purpose": "生成章节正文",
                            "temperature": 0.9,
                            "timeout_seconds": 600,
                            "max_tokens": WRITER_GENERATION_MAX_TOKENS,
                        }
                    ],
                    "metrics": {
                        "version_index": index + 1,
                        "style_hint": style_hint,
                        "prompt_chars": len(final_prompt_input),
                        "raw_response_chars": len(response or ""),
                        "cleaned_output_chars": len(content or ""),
                    },
                },
                started_at=started_at,
                ended_at=datetime.now(CN_TIMEZONE),
            )

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

        resolved_content = extracted_text
        if not resolved_content and isinstance(content, str):
            stripped = content.strip()
            if stripped:
                looks_like_json = (
                    (stripped.startswith("{") and stripped.endswith("}"))
                    or (stripped.startswith("[") and stripped.endswith("]"))
                )
                # 避免把无法提取正文的结构化包装直接写入章节正文。
                if not looks_like_json or parsed_json is None:
                    resolved_content = stripped

        if not resolved_content:
            logger.error(
                "Pipeline 项目 %s 第 %s 章版本 %s 未提取到正文: preview=%s",
                project_id,
                chapter_number,
                index + 1,
                (content or "")[:400],
            )
            raise HTTPException(
                status_code=502,
                detail=f"生成章节第 {index + 1} 个版本失败：模型未返回有效正文，请重试。",
            )

        target_word_count, minimum_word_count = await resolve_word_count_requirements(
            SystemConfigRepository(self.session)
        )
        resolved_content = await self._expand_chapter_to_minimum_word_count(
            content=resolved_content,
            minimum_word_count=minimum_word_count,
            target_word_count=target_word_count,
            user_id=user_id,
            chapter_number=chapter_number,
            version_index=index + 1,
        )
        resolved_content = await self._compress_chapter_to_word_limit(
            content=resolved_content,
            target_word_count=target_word_count,
            user_id=user_id,
            chapter_number=chapter_number,
            version_index=index + 1,
        )
        actual_word_count = count_chapter_words(resolved_content)
        minimum_acceptable_word_count = int(minimum_word_count * 0.85)
        if actual_word_count < minimum_acceptable_word_count:
            logger.error(
                "Pipeline 第 %s 章版本 %s 字数严重不足，终止入库: actual=%s minimum=%s acceptable=%s target=%s",
                chapter_number,
                index + 1,
                actual_word_count,
                minimum_word_count,
                minimum_acceptable_word_count,
                target_word_count,
            )
            raise HTTPException(
                status_code=502,
                detail=(
                    f"生成章节第 {index + 1} 个版本失败：字数仅 {actual_word_count}，"
                    f"低于最低要求 {minimum_word_count}（容错阈值 {minimum_acceptable_word_count}）。请重试。"
                ),
            )
        metadata["word_limit"] = {
            "target": target_word_count,
            "minimum": minimum_word_count,
            "actual": actual_word_count,
        }

        # 记录定稿后的候选正文，作为节点级恢复还原 versions 的权威来源
        await self.trace_service.record_success(
            project_id=project_id,
            chapter_number=chapter_number,
            node_key="draft_generation",
            node_label="生成正文",
            stage="chapter_writing",
            cleaned_output=resolved_content,
            input_payload={
                "version_index": index + 1,
                "outline_title": outline_title,
                "outline_summary": outline_summary,
            },
            output_payload={
                "full_content": resolved_content,
                "version_metadata": metadata,
                "version_index": index + 1,
            },
            metadata={
                "trace_kind": "workflow",
                "call_type": "postprocess",
                "summary": "正文定稿：guardrail 校验与字数补写/压缩后的最终候选正文。",
                "actions": [
                    "执行角色可见性 guardrail 校验",
                    "提取并解析正文",
                    "按字数要求补写或压缩",
                ],
                "model_calls": [],
                "metrics": {
                    "version_index": index + 1,
                    "final_chars": len(resolved_content or ""),
                    "actual_word_count": actual_word_count,
                },
            },
        )

        return {
            "index": index,
            "content": resolved_content,
            "metadata": metadata,
        }

    async def _expand_chapter_to_minimum_word_count(
        self,
        *,
        content: str,
        minimum_word_count: int,
        target_word_count: int,
        user_id: int,
        chapter_number: int,
        version_index: int,
    ) -> str:
        """当版本正文明显偏短时，做循环补写兜底，避免异常短稿入库。"""
        max_attempts = 3
        best_content = (content or "").strip()
        best_word_count = count_chapter_words(best_content)
        if best_word_count >= minimum_word_count:
            return best_content

        logger.info(
            "Pipeline 第 %s 章版本 %s 低于最小字数，开始循环补写: current=%s minimum=%s target=%s attempts=%s",
            chapter_number,
            version_index,
            best_word_count,
            minimum_word_count,
            target_word_count,
            max_attempts,
        )
        current_content = best_content
        current_word_count = best_word_count

        for attempt in range(1, max_attempts + 1):
            prompt = f"""
请在不改变主线剧情与关键事件的前提下，对下面章节做补写扩展。

目标要求：
- 扩展后字数目标约 {target_word_count} 字，至少不少于 {minimum_word_count} 字。
- 补充环境、动作、心理和过渡细节，但不得新增与主线冲突的新设定。
- 保持人物关系、时间顺序和结尾钩子不变。
- 直接输出补写后的完整章节正文，不要解释，不要输出 JSON。

当前正文（约 {current_word_count} 字）：
{current_content}
""".strip()
            try:
                response = await self.llm_service.get_llm_response(
                    system_prompt="你是网文章节润色编辑，负责在不改剧情主线的前提下补写细节。",
                    conversation_history=[{"role": "user", "content": prompt}],
                    temperature=0.4,
                    user_id=user_id,
                    timeout=300.0,
                    response_format=None,
                    max_tokens=WRITER_GENERATION_MAX_TOKENS,
                    stage="chapter_enrichment",
                )
                enriched = unwrap_markdown_json(remove_think_tags(response)).strip()
                if not enriched:
                    logger.warning(
                        "Pipeline 第 %s 章版本 %s 第 %s 次补写返回空内容，沿用当前文本",
                        chapter_number,
                        version_index,
                        attempt,
                    )
                    continue

                enriched_word_count = count_chapter_words(enriched)
                if enriched_word_count > best_word_count:
                    best_content = enriched
                    best_word_count = enriched_word_count

                if enriched_word_count <= current_word_count:
                    logger.warning(
                        "Pipeline 第 %s 章版本 %s 第 %s 次补写未增量: before=%s after=%s",
                        chapter_number,
                        version_index,
                        attempt,
                        current_word_count,
                        enriched_word_count,
                    )
                    continue

                current_content = enriched
                current_word_count = enriched_word_count
                if current_word_count >= minimum_word_count:
                    logger.info(
                        "Pipeline 第 %s 章版本 %s 第 %s 次补写达标: after=%s minimum=%s",
                        chapter_number,
                        version_index,
                        attempt,
                        current_word_count,
                        minimum_word_count,
                    )
                    return current_content
            except Exception as exc:
                logger.warning(
                    "Pipeline 第 %s 章版本 %s 第 %s 次补写失败，继续尝试: %s",
                    chapter_number,
                    version_index,
                    attempt,
                    exc,
                )

        if best_word_count < minimum_word_count:
            logger.warning(
                "Pipeline 第 %s 章版本 %s 多轮补写后仍低于最小字数: final=%s minimum=%s",
                chapter_number,
                version_index,
                best_word_count,
                minimum_word_count,
            )
        return best_content

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
        system_prompt = await self.prompt_service.get_prompt("chapter_compression")
        if not system_prompt:
            raise RuntimeError("缺少提示词，请联系管理员配置 'chapter_compression'")
        prompt = json.dumps(
            {
                "target_word_count": target_word_count,
                "maximum_word_count": int(target_word_count * 1.1),
                "current_word_count": current_word_count,
                "content": content,
            },
            ensure_ascii=False,
        )

        try:
            response = await self.llm_service.get_llm_response(
                system_prompt=system_prompt,
                conversation_history=[{"role": "user", "content": prompt}],
                temperature=0.2,
                user_id=user_id,
                timeout=300.0,
                response_format=None,
                max_tokens=WRITER_GENERATION_MAX_TOKENS,
                stage="chapter_compression",
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
                stage="chapter_rewrite",
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

    @staticmethod
    def _extract_best_version_review(
        ai_review: Optional[Dict[str, Any]],
        best_version_index: int,
    ) -> Dict[str, Any]:
        if not isinstance(ai_review, dict):
            return {}
        target_number = best_version_index + 1
        for review in ai_review.get("version_reviews") or []:
            if isinstance(review, dict) and review.get("version_number") == target_number:
                return review
        return {}

    @classmethod
    def _build_review_refinement_summary(
        cls,
        ai_review: Optional[Dict[str, Any]],
        best_version_index: int,
    ) -> str:
        if not isinstance(ai_review, dict):
            return ""

        pieces: List[str] = []
        mode = ai_review.get("mode")
        if mode == "single":
            pieces.append("单版本评审：请根据以下评审意见直接修复润色唯一候选版本。")
            for label, value in (
                ("总体评价", ai_review.get("evaluation")),
                ("修改建议", ai_review.get("suggestions")),
                ("最终推荐", ai_review.get("final_recommendation")),
            ):
                if value:
                    pieces.append(f"{label}：{value}")
        elif mode == "compare":
            pieces.append(
                f"多版本对比评审：推荐采用第 {best_version_index + 1} 个版本，并根据以下意见修复润色。"
            )
            # 多版本模式必须以结构化 best_version_index 为准，避免模型自然语言推荐互相矛盾。
            suggestions = ai_review.get("suggestions")
            if suggestions and not cls._has_conflicting_version_reference(
                str(suggestions),
                best_version_index + 1,
            ):
                pieces.append(f"推荐版本修复建议：{suggestions}")
        else:
            for label, value in (
                ("总体评价", ai_review.get("evaluation")),
                ("修改建议", ai_review.get("suggestions")),
                ("最终推荐", ai_review.get("final_recommendation")),
            ):
                if value:
                    pieces.append(f"{label}：{value}")

        flaws = ai_review.get("flaws")
        if isinstance(flaws, list) and flaws:
            pieces.append("需修复问题：\n" + "\n".join(f"- {item}" for item in flaws if item))

        best_review = cls._extract_best_version_review(ai_review, best_version_index)
        if best_review:
            if best_review.get("overall_review"):
                pieces.append(f"推荐版本局部评价：{best_review['overall_review']}")
            cons = best_review.get("cons")
            if isinstance(cons, list) and cons:
                pieces.append("推荐版本缺点：\n" + "\n".join(f"- {item}" for item in cons if item))

        return "\n\n".join(piece for piece in pieces if piece).strip()

    @staticmethod
    def _referenced_version_numbers(text: str) -> set[int]:
        numbers: set[int] = set()
        for match in VERSION_REFERENCE_PATTERN.finditer(text or ""):
            raw_number = match.group(1) or match.group(2)
            try:
                numbers.add(int(raw_number))
            except (TypeError, ValueError):
                continue
        return numbers

    @classmethod
    def _has_conflicting_version_reference(cls, text: str, best_choice: int) -> bool:
        referenced_numbers = cls._referenced_version_numbers(text)
        return bool(referenced_numbers and best_choice not in referenced_numbers)

    @classmethod
    def _build_consistent_reason_for_choice(
        cls,
        ai_review: Dict[str, Any],
        best_choice: int,
        evaluation: Dict[str, Dict[str, Any]],
    ) -> str:
        final_recommendation = str(ai_review.get("final_recommendation") or "").strip()
        if final_recommendation and not cls._has_conflicting_version_reference(
            final_recommendation,
            best_choice,
        ):
            return final_recommendation

        best_review = evaluation.get(f"version{best_choice}") or {}
        best_overall_review = str(best_review.get("overall_review") or "").strip()
        if best_overall_review:
            return best_overall_review

        for value in (ai_review.get("suggestions"), ai_review.get("evaluation")):
            text = str(value or "").strip()
            if text and not cls._has_conflicting_version_reference(text, best_choice):
                return text

        return f"推荐采用版本{best_choice}"

    @classmethod
    def _build_chapter_evaluation_feedback(
        cls,
        review_summaries: Optional[Dict[str, Any]],
    ) -> Optional[str]:
        """把自动评审结果转换成前端评阅面板已有的 evaluation JSON 结构。"""
        if not isinstance(review_summaries, dict):
            return None
        ai_review = review_summaries.get("ai_review")
        if not isinstance(ai_review, dict):
            return None

        version_reviews = ai_review.get("version_reviews") or []
        evaluation: Dict[str, Dict[str, Any]] = {}
        for review in version_reviews:
            if not isinstance(review, dict):
                continue
            try:
                version_number = int(review.get("version_number") or 0)
            except (TypeError, ValueError):
                version_number = 0
            if version_number <= 0:
                continue
            evaluation[f"version{version_number}"] = {
                "pros": review.get("pros") if isinstance(review.get("pros"), list) else [],
                "cons": review.get("cons") if isinstance(review.get("cons"), list) else [],
                "overall_review": str(review.get("overall_review") or ""),
                "scores": review.get("scores") if isinstance(review.get("scores"), dict) else {},
            }

        try:
            best_choice = int(ai_review.get("best_version_index") or 0) + 1
        except (TypeError, ValueError):
            best_choice = 1
        if best_choice <= 0:
            best_choice = 1

        if not evaluation:
            evaluation["version1"] = {
                "pros": [],
                "cons": [],
                "overall_review": str(
                    ai_review.get("evaluation")
                    or ai_review.get("suggestions")
                    or ai_review.get("final_recommendation")
                    or "AI评审已完成"
                ),
                "scores": ai_review.get("scores") if isinstance(ai_review.get("scores"), dict) else {},
            }
            best_choice = 1

        payload = {
            "best_choice": best_choice,
            "reason_for_choice": cls._build_consistent_reason_for_choice(
                ai_review,
                best_choice,
                evaluation,
            ),
            "evaluation": evaluation,
        }
        return json.dumps(payload, ensure_ascii=False)

    @staticmethod
    def _parse_review_guided_refinement_response(raw_response: str) -> Tuple[str, str]:
        cleaned = remove_think_tags(raw_response)
        normalized = unwrap_markdown_json(cleaned).strip()
        candidates = [normalized, cleaned.strip()]

        for candidate in candidates:
            if not candidate:
                continue
            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if not isinstance(parsed, dict):
                continue
            optimized_content = parsed.get("optimized_content")
            if isinstance(optimized_content, str) and optimized_content.strip():
                notes = parsed.get("optimization_notes")
                return optimized_content.strip(), str(notes or "修复润色完成")

        fallback = normalized or cleaned.strip()
        return fallback, "修复润色完成（响应格式非标准JSON）"

    async def _run_review_guided_refinement(
        self,
        *,
        project_id: str,
        chapter_number: int,
        source_content: str,
        review_summary: str,
        version_number: int,
        version_review: Dict[str, Any],
        user_id: int,
    ) -> Tuple[str, Dict[str, Any]]:
        started_at = datetime.now(CN_TIMEZONE)
        system_prompt: Optional[str] = None
        user_prompt: Optional[str] = None
        try:
            source_content = (source_content or "").strip()
            review_summary = (review_summary or "").strip()
            if not source_content:
                raise RuntimeError("修复润色失败：最佳版本正文为空")
            if not review_summary:
                raise RuntimeError("修复润色失败：缺少AI评审建议")

            system_prompt = await self.prompt_service.get_prompt("optimize_recommended_version")
            if not system_prompt:
                raise RuntimeError("修复润色失败：缺少 optimize_recommended_version 提示词")

            optimize_input = {
                "source_content": source_content,
                "review_summary": review_summary,
                "version_number": version_number,
                "version_review": version_review or {},
            }
            user_prompt = json.dumps(optimize_input, ensure_ascii=False)
            response = await self.llm_service.get_llm_response(
                system_prompt=system_prompt,
                conversation_history=[{"role": "user", "content": user_prompt}],
                temperature=0.7,
                user_id=user_id,
                timeout=600.0,
                stage="chapter_optimization",
            )
            refined_content, optimization_notes = self._parse_review_guided_refinement_response(response)
            if not refined_content.strip():
                raise RuntimeError("修复润色失败：模型返回的最终正文为空")

            report = {
                "version_number": version_number,
                "optimization_notes": optimization_notes,
                "source_chars": len(source_content),
                "refined_chars": len(refined_content),
            }
            await self.trace_service.record_success(
                project_id=project_id,
                chapter_number=chapter_number,
                node_key="review_refinement",
                node_label="修复润色",
                stage="chapter_optimization",
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                raw_response=response,
                cleaned_output=refined_content,
                input_payload={
                    "version_number": version_number,
                    "review_summary": review_summary,
                    "source_chars": len(source_content),
                },
                output_payload={
                    "optimization_notes": optimization_notes,
                    "refined_chars": len(refined_content),
                },
                metadata={
                    "trace_kind": "llm",
                    "call_type": "chat_llm",
                    "summary": "根据 AI 评审选择的版本和修改建议，自动修复润色成最终正文。",
                    "actions": [
                        "读取 optimize_recommended_version 提示词",
                        "组装推荐版本正文和 AI 评审建议",
                        "调用聊天模型输出修复润色后的完整正文",
                        "解析 optimized_content 和 optimization_notes",
                    ],
                    "model_calls": [
                        {
                            "stage": "chapter_optimization",
                            "call_type": "chat_llm",
                            "purpose": "按 AI 评审建议修复润色推荐版本",
                            "temperature": 0.7,
                            "timeout_seconds": 600,
                        }
                    ],
                    "metrics": report,
                },
                started_at=started_at,
                ended_at=datetime.now(CN_TIMEZONE),
            )
            return refined_content, report
        except Exception as exc:
            await self.trace_service.record_failure(
                project_id=project_id,
                chapter_number=chapter_number,
                node_key="review_refinement",
                node_label="修复润色",
                stage="chapter_optimization",
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                error=str(exc),
                input_payload={
                    "version_number": version_number,
                    "source_chars": len(source_content or ""),
                    "review_summary": review_summary,
                },
                metadata={
                    "trace_kind": "llm",
                    "call_type": "chat_llm",
                    "summary": "按 AI 评审建议修复润色失败，生成流程终止。",
                    "actions": [
                        "读取修复润色提示词",
                        "组装推荐版本正文和 AI 评审建议",
                        "调用聊天模型输出最终正文",
                    ],
                    "model_calls": [
                        {
                            "stage": "chapter_optimization",
                            "call_type": "chat_llm",
                            "purpose": "按 AI 评审建议修复润色推荐版本",
                        }
                    ],
                },
                started_at=started_at,
                ended_at=datetime.now(CN_TIMEZONE),
            )
            message = str(exc)
            if message.startswith("修复润色失败"):
                raise
            raise RuntimeError(f"修复润色失败：{message}") from exc

    async def _run_ai_review(
        self,
        *,
        versions: List[Dict[str, Any]],
        chapter_mission: Optional[dict],
        user_id: int,
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[int, Optional[Dict[str, Any]]]:
        contents = [v.get("content", "") for v in versions]
        if not contents:
            raise RuntimeError("AI评审失败：没有可评审的候选版本")

        ai_review_service = AIReviewService(self.llm_service, self.prompt_service)
        if len(contents) == 1:
            evaluation_text = await ai_review_service.review_single_version(
                version_content=contents[0],
                user_id=user_id,
                review_context=context,
                strict=True,
            )
            if not evaluation_text or not evaluation_text.strip():
                raise RuntimeError("AI评审失败：单版本评审结果为空")
            versions[0].setdefault("metadata", {})["ai_review"] = {
                "is_best": True,
                "evaluation": evaluation_text,
                "suggestions": evaluation_text,
                "mode": "single",
            }
            return 0, {
                "mode": "single",
                "best_version_index": 0,
                "evaluation": evaluation_text,
                "flaws": [],
                "suggestions": evaluation_text,
                "final_recommendation": "采用唯一版本",
                "version_reviews": [
                    {
                        "version_number": 1,
                        "overall_review": evaluation_text,
                        "pros": [],
                        "cons": [],
                        "scores": {},
                    }
                ],
            }

        try:
            ai_review_result = await ai_review_service.review_versions(
                versions=contents,
                chapter_mission=chapter_mission,
                user_id=user_id,
                review_context=context,
                strict=True,
            )
        except Exception as exc:
            raise RuntimeError(f"AI评审失败：{exc}") from exc

        if not ai_review_result:
            raise RuntimeError("AI评审失败：多版本评审结果为空")

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
            "mode": "compare",
            "best_version_index": ai_review_result.best_version_index,
            "scores": ai_review_result.scores,
            "evaluation": ai_review_result.overall_evaluation,
            "flaws": ai_review_result.critical_flaws,
            "suggestions": ai_review_result.refinement_suggestions,
            "final_recommendation": ai_review_result.final_recommendation,
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
        service = ConsistencyService(self.session, self.llm_service)
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
                    stage="chapter_optimization",
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
