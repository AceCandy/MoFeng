# AIMETA P=章节工作流Graph版本注册表|R=图编译_精确版本路由_稳定thread配置|NR=不执行activity_不管理DB事务|E=build_chapter_workflow_graph_registry|X=internal|A=registry|D=langgraph,pydantic|S=checkpoint|RD=./README.ai
"""Versioned Chapter workflow graph definitions and checkpoint identity."""

from __future__ import annotations

from dataclasses import dataclass
from inspect import isawaitable
from typing import Any, Awaitable, Callable, Literal, TypeAlias

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from ..schemas.chapter_workflow import (
    CHAPTER_WORKFLOW_STATE_SCHEMA_VERSION,
    CHAPTER_WORKFLOW_VERSION,
    ChapterWorkflowState,
    validate_chapter_workflow_run_id,
)

GraphStateUpdate = dict[str, object]
GraphNode: TypeAlias = Callable[
    [ChapterWorkflowState],
    GraphStateUpdate | Awaitable[GraphStateUpdate],
]
GraphResumeNode: TypeAlias = Callable[
    [ChapterWorkflowState, object],
    GraphStateUpdate | Awaitable[GraphStateUpdate],
]


@dataclass(frozen=True)
class ChapterWorkflowGraphBindings:
    """Graph 外部业务节点；运行时依赖只存在于 handler 内存。"""

    freeze_base_context: GraphNode
    retrieve_context: GraphNode
    plan_chapter: GraphNode
    generate_candidate_1: GraphNode
    generate_candidate_2: GraphNode
    review_candidates: GraphNode
    refine_candidate: GraphNode
    enhance_content: GraphNode
    repair_consistency: GraphNode
    optimize_style: GraphNode
    enrich_content: GraphNode
    compress_candidate: GraphNode
    persist_drafts: GraphNode
    apply_selection_resume: GraphResumeNode
    finalize_revision: GraphNode
    apply_projection_resume: GraphResumeNode
    reconcile_projections: GraphNode


GraphCompiler: TypeAlias = Callable[[Any, ChapterWorkflowGraphBindings], Any]
OptionalStageKey: TypeAlias = Literal[
    "enhance_content",
    "repair_consistency",
    "optimize_style",
    "enrich_content",
]


_IMMUTABLE_STATE_FIELDS = {
    "workflow_version",
    "state_schema_version",
    "run_id",
    "context_hash",
    "node_key",
}


def _compile_graph(checkpointer: Any, bindings: ChapterWorkflowGraphBindings) -> Any:
    builder = StateGraph(ChapterWorkflowState)
    ordered = [
        ("freeze_base_context", bindings.freeze_base_context, "retrieve_context"),
        ("retrieve_context", bindings.retrieve_context, "plan_chapter"),
        ("plan_chapter", bindings.plan_chapter, "generate_candidate_1"),
        ("review_candidates", bindings.review_candidates, "refine_candidate"),
        ("refine_candidate", bindings.refine_candidate, "enhance_content"),
        ("compress_candidate", bindings.compress_candidate, "persist_drafts"),
        ("persist_drafts", bindings.persist_drafts, "wait_for_selection"),
        ("finalize_revision", bindings.finalize_revision, "wait_for_projections"),
        ("reconcile_projections", bindings.reconcile_projections, "successful"),
    ]
    for key, node, next_key in ordered:
        builder.add_node(key, _bound_node(node, next_node=next_key))

    def optional_node(key: OptionalStageKey, node: GraphNode, next_key: str) -> None:
        async def execute(state: ChapterWorkflowState) -> GraphStateUpdate:
            if not state.optional_stages.get(key, False):
                return _validated_update(
                    state,
                    {"skipped_stages": {key: "disabled"}},
                    next_node=next_key,
                )
            return await _execute_node(state, node, next_node=next_key)

        builder.add_node(key, execute)

    optional_node("enhance_content", bindings.enhance_content, "repair_consistency")
    optional_node("repair_consistency", bindings.repair_consistency, "optimize_style")
    optional_node("optimize_style", bindings.optimize_style, "enrich_content")
    optional_node("enrich_content", bindings.enrich_content, "compress_candidate")

    async def candidate_1(state: ChapterWorkflowState) -> GraphStateUpdate:
        return await _execute_node(
            state,
            bindings.generate_candidate_1,
            next_node=None,
        )

    builder.add_node("generate_candidate_1", candidate_1)

    async def candidate_2(state: ChapterWorkflowState) -> GraphStateUpdate:
        if state.candidate_count < 2:
            return _validated_update(
                state,
                {"skipped_stages": {"generate_candidate_2": "single_candidate"}},
                next_node=None,
            )
        return await _execute_node(
            state,
            bindings.generate_candidate_2,
            next_node=None,
        )

    builder.add_node("generate_candidate_2", candidate_2)

    async def wait_selection(state: ChapterWorkflowState) -> GraphStateUpdate:
        if not state.candidate_version_ids:
            raise ValueError("wait_for_selection 缺少候选版本")
        value = interrupt(
            {
                "kind": "selection",
                "run_id": state.run_id,
                "candidate_version_ids": state.candidate_version_ids,
            }
        )
        return await _execute_resume_node(
            state,
            bindings.apply_selection_resume,
            value,
            next_node="finalize_revision",
        )

    builder.add_node("wait_for_selection", wait_selection)

    async def wait_projections(state: ChapterWorkflowState) -> GraphStateUpdate:
        if state.target_chapter_revision is None:
            raise ValueError("wait_for_projections 缺少目标 Chapter revision")
        value = interrupt(
            {
                "kind": "projection",
                "run_id": state.run_id,
                "target_chapter_revision": state.target_chapter_revision,
            }
        )
        next_node = (
            "wait_for_projections"
            if isinstance(value, dict) and set(value) == {"command_id"}
            else "reconcile_projections"
        )
        return await _execute_resume_node(
            state,
            bindings.apply_projection_resume,
            value,
            next_node=next_node,
        )

    builder.add_node("wait_for_projections", wait_projections)
    builder.add_node("successful", lambda _state: {})
    builder.add_edge(START, "freeze_base_context")
    builder.add_edge("freeze_base_context", "retrieve_context")
    builder.add_edge("retrieve_context", "plan_chapter")
    builder.add_edge("plan_chapter", "generate_candidate_1")
    builder.add_edge("plan_chapter", "generate_candidate_2")
    builder.add_edge(["generate_candidate_1", "generate_candidate_2"], "review_candidates")
    builder.add_edge("review_candidates", "refine_candidate")
    builder.add_edge("refine_candidate", "enhance_content")
    builder.add_edge("enhance_content", "repair_consistency")
    builder.add_edge("repair_consistency", "optimize_style")
    builder.add_edge("optimize_style", "enrich_content")
    builder.add_edge("enrich_content", "compress_candidate")
    builder.add_edge("compress_candidate", "persist_drafts")
    builder.add_edge("persist_drafts", "wait_for_selection")
    builder.add_edge("wait_for_selection", "finalize_revision")
    builder.add_edge("finalize_revision", "wait_for_projections")
    builder.add_conditional_edges(
        "wait_for_projections",
        lambda state: state.node_key,
        {
            "wait_for_projections": "wait_for_projections",
            "reconcile_projections": "reconcile_projections",
        },
    )
    builder.add_edge("reconcile_projections", "successful")
    builder.add_edge("successful", END)
    return builder.compile(checkpointer=checkpointer)


async def _execute_node(
    state: ChapterWorkflowState,
    node: GraphNode,
    *,
    next_node: str | None,
) -> GraphStateUpdate:
    update = node(state)
    if isawaitable(update):
        update = await update
    return _validated_update(state, update, next_node=next_node)

async def _execute_resume_node(
    state: ChapterWorkflowState,
    node: GraphResumeNode,
    value: object,
    *,
    next_node: str,
) -> GraphStateUpdate:
    update = node(state, value)
    if isawaitable(update):
        update = await update
    return _validated_update(state, update, next_node=next_node)

def _validated_update(
    state: ChapterWorkflowState,
    update: GraphStateUpdate,
    *,
    next_node: str | None,
) -> GraphStateUpdate:
    if not isinstance(update, dict):
        raise TypeError("workflow graph binding 必须返回 dict")
    immutable = _IMMUTABLE_STATE_FIELDS.intersection(update)
    if immutable:
        raise ValueError(f"workflow graph binding 不可修改字段: {sorted(immutable)}")
    merged = dict(update)
    if next_node is not None:
        merged["node_key"] = next_node
    validation_update = dict(merged)
    for field in ("activity_refs", "result_refs", "skipped_stages"):
        if field in update:
            value = update[field]
            if not isinstance(value, dict):
                raise TypeError(f"workflow graph binding 的 {field} 必须是 dict")
            validation_update[field] = {**getattr(state, field), **value}
    ChapterWorkflowState.model_validate(
        {**state.model_dump(mode="json"), **validation_update}
    )
    return merged

def _bound_node(node: GraphNode, *, next_node: str) -> GraphNode:
    async def execute(state: ChapterWorkflowState) -> GraphStateUpdate:
        return await _execute_node(state, node, next_node=next_node)

    return execute


@dataclass(frozen=True)
class ChapterWorkflowGraphDefinition:
    """一个已冻结 workflow version 的 state 与 compiler 绑定。"""

    workflow_version: int
    state_schema_version: int
    state_type: type[ChapterWorkflowState]
    compiler: GraphCompiler


class ChapterWorkflowGraphRegistry:
    """按 workflow_version 精确选择 graph；未知版本禁止 fallback。"""

    def __init__(self) -> None:
        self._definitions: dict[int, ChapterWorkflowGraphDefinition] = {}

    def register(
        self,
        definition: ChapterWorkflowGraphDefinition,
    ) -> ChapterWorkflowGraphDefinition:
        if definition.workflow_version < 1:
            raise ValueError("workflow version 必须大于等于 1")
        if definition.state_schema_version < 1:
            raise ValueError("state schema version 必须大于等于 1")
        if definition.workflow_version in self._definitions:
            raise ValueError(f"workflow version 已注册: {definition.workflow_version}")
        self._definitions[definition.workflow_version] = definition
        return definition

    def get(self, workflow_version: int) -> ChapterWorkflowGraphDefinition | None:
        return self._definitions.get(workflow_version)

    def compile(
        self,
        workflow_version: int,
        *,
        checkpointer: Any,
        bindings: ChapterWorkflowGraphBindings,
    ) -> Any:
        definition = self.get(workflow_version)
        if definition is None:
            raise ValueError(f"不支持的 workflow version: {workflow_version}")
        return definition.compiler(checkpointer, bindings)


def build_chapter_workflow_graph_registry() -> ChapterWorkflowGraphRegistry:
    registry = ChapterWorkflowGraphRegistry()
    registry.register(
        ChapterWorkflowGraphDefinition(
            workflow_version=CHAPTER_WORKFLOW_VERSION,
            state_schema_version=CHAPTER_WORKFLOW_STATE_SCHEMA_VERSION,
            state_type=ChapterWorkflowState,
            compiler=_compile_graph,
        )
    )
    return registry


def chapter_workflow_graph_config(
    run_id: str,
    *,
    checkpoint_id: str | None = None,
) -> RunnableConfig:
    """构造 run_id == LangGraph thread_id 的唯一 runtime config。"""

    validate_chapter_workflow_run_id(run_id)

    configurable = {"thread_id": run_id}
    if checkpoint_id is not None:
        normalized_checkpoint_id = checkpoint_id.strip()
        if not normalized_checkpoint_id:
            raise ValueError("checkpoint_id 不能为空")
        configurable["checkpoint_id"] = normalized_checkpoint_id
    return {"configurable": configurable}
