# AIMETA P=章节工作流Graph版本注册表|R=V1编译_精确版本路由_稳定thread配置|NR=不执行activity_不管理DB事务|E=build_chapter_workflow_graph_registry|X=internal|A=registry|D=langgraph,pydantic|S=checkpoint|RD=./README.ai
"""Versioned Chapter workflow graph definitions and checkpoint identity."""

from __future__ import annotations

from dataclasses import dataclass
from inspect import isawaitable
from typing import Any, Awaitable, Callable

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from ..schemas.chapter_workflow import (
    CHAPTER_WORKFLOW_STATE_SCHEMA_VERSION_V1,
    CHAPTER_WORKFLOW_VERSION_V1,
    ChapterWorkflowStateV1,
    validate_chapter_workflow_run_id,
)

GraphStateUpdate = dict[str, object]
GraphNode = Callable[
    [ChapterWorkflowStateV1],
    GraphStateUpdate | Awaitable[GraphStateUpdate],
]
GraphResumeNode = Callable[
    [ChapterWorkflowStateV1, object],
    GraphStateUpdate | Awaitable[GraphStateUpdate],
]


@dataclass(frozen=True)
class ChapterWorkflowGraphBindingsV1:
    """Graph 外部业务节点；运行时依赖只存在于 handler 内存。"""

    freeze_context: GraphNode
    plan_and_direct: GraphNode
    generate_candidates: GraphNode
    review_candidates: GraphNode
    persist_candidates: GraphNode
    apply_selection_resume: GraphResumeNode
    finalize_revision: GraphNode
    apply_projection_resume: GraphResumeNode
    observe_projection: GraphNode


GraphCompiler = Callable[[Any, ChapterWorkflowGraphBindingsV1], Any]


_IMMUTABLE_STATE_FIELDS = {
    "workflow_version",
    "state_schema_version",
    "run_id",
    "context_hash",
    "node_key",
}


async def _execute_node(
    state: ChapterWorkflowStateV1,
    node: GraphNode,
    *,
    next_node: str,
) -> GraphStateUpdate:
    update = node(state)
    if isawaitable(update):
        update = await update
    return _validated_update(state, update, next_node=next_node)


async def _execute_resume_node(
    state: ChapterWorkflowStateV1,
    node: GraphResumeNode,
    resume_value: object,
    *,
    next_node: str,
) -> GraphStateUpdate:
    update = node(state, resume_value)
    if isawaitable(update):
        update = await update
    return _validated_update(state, update, next_node=next_node)


def _validated_update(
    state: ChapterWorkflowStateV1,
    update: GraphStateUpdate,
    *,
    next_node: str,
) -> GraphStateUpdate:
    if not isinstance(update, dict):
        raise TypeError("workflow graph binding 必须返回 dict")
    immutable = _IMMUTABLE_STATE_FIELDS.intersection(update)
    if immutable:
        raise ValueError(f"workflow graph binding 不可修改字段: {sorted(immutable)}")

    merged = dict(update)
    for field in ("activity_refs", "result_refs"):
        if field in update:
            value = update[field]
            if not isinstance(value, dict):
                raise TypeError(f"workflow graph binding 的 {field} 必须是 dict")
            merged[field] = {**getattr(state, field), **value}
    merged["node_key"] = next_node
    ChapterWorkflowStateV1.model_validate({**state.model_dump(mode="json"), **merged})
    return merged


def _bound_node(
    node: GraphNode,
    *,
    next_node: str,
) -> GraphNode:
    async def execute(state: ChapterWorkflowStateV1) -> GraphStateUpdate:
        return await _execute_node(state, node, next_node=next_node)

    return execute


def _compile_graph_v1(
    checkpointer: Any,
    bindings: ChapterWorkflowGraphBindingsV1,
) -> Any:
    builder = StateGraph(ChapterWorkflowStateV1)
    builder.add_node(
        "freeze_context",
        _bound_node(bindings.freeze_context, next_node="plan_and_direct"),
    )
    builder.add_node(
        "plan_and_direct",
        _bound_node(bindings.plan_and_direct, next_node="generate_candidates"),
    )
    builder.add_node(
        "generate_candidates",
        _bound_node(bindings.generate_candidates, next_node="review_candidates"),
    )
    builder.add_node(
        "review_candidates",
        _bound_node(bindings.review_candidates, next_node="persist_candidates"),
    )
    builder.add_node(
        "persist_candidates",
        _bound_node(bindings.persist_candidates, next_node="waiting_for_selection"),
    )

    async def wait_for_selection(state: ChapterWorkflowStateV1) -> GraphStateUpdate:
        if not state.candidate_version_ids:
            raise ValueError("waiting_for_selection 缺少候选版本")
        resume_value = interrupt(
            {
                "kind": "selection",
                "run_id": state.run_id,
                "candidate_version_ids": state.candidate_version_ids,
            }
        )
        return await _execute_resume_node(
            state,
            bindings.apply_selection_resume,
            resume_value,
            next_node="finalize_revision",
        )

    builder.add_node("waiting_for_selection", wait_for_selection)
    builder.add_node(
        "finalize_revision",
        _bound_node(bindings.finalize_revision, next_node="projection_pending"),
    )

    async def wait_for_projection(state: ChapterWorkflowStateV1) -> GraphStateUpdate:
        if state.target_chapter_revision is None:
            raise ValueError("projection_pending 缺少目标 Chapter revision")
        resume_value = interrupt(
            {
                "kind": "projection",
                "run_id": state.run_id,
                "target_chapter_revision": state.target_chapter_revision,
            }
        )
        next_node = (
            "projection_pending"
            if isinstance(resume_value, dict) and set(resume_value) == {"command_id"}
            else "observe_projection"
        )
        return await _execute_resume_node(
            state,
            bindings.apply_projection_resume,
            resume_value,
            next_node=next_node,
        )

    builder.add_node("projection_pending", wait_for_projection)
    builder.add_node(
        "observe_projection",
        _bound_node(bindings.observe_projection, next_node="successful"),
    )
    builder.add_node("successful", lambda _state: {})
    builder.add_edge(START, "freeze_context")
    builder.add_edge("freeze_context", "plan_and_direct")
    builder.add_edge("plan_and_direct", "generate_candidates")
    builder.add_edge("generate_candidates", "review_candidates")
    builder.add_edge("review_candidates", "persist_candidates")
    builder.add_edge("persist_candidates", "waiting_for_selection")
    builder.add_edge("waiting_for_selection", "finalize_revision")
    builder.add_edge("finalize_revision", "projection_pending")
    builder.add_conditional_edges(
        "projection_pending",
        lambda state: state.node_key,
        {
            "projection_pending": "projection_pending",
            "observe_projection": "observe_projection",
        },
    )
    builder.add_edge("observe_projection", "successful")
    builder.add_edge("successful", END)
    return builder.compile(checkpointer=checkpointer)


@dataclass(frozen=True)
class ChapterWorkflowGraphDefinition:
    """一个已冻结 workflow version 的 state 与 compiler 绑定。"""

    workflow_version: int
    state_schema_version: int
    state_type: type[ChapterWorkflowStateV1]
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
        bindings: ChapterWorkflowGraphBindingsV1,
    ) -> Any:
        definition = self.get(workflow_version)
        if definition is None:
            raise ValueError(f"不支持的 workflow version: {workflow_version}")
        return definition.compiler(checkpointer, bindings)


def build_chapter_workflow_graph_registry() -> ChapterWorkflowGraphRegistry:
    registry = ChapterWorkflowGraphRegistry()
    registry.register(
        ChapterWorkflowGraphDefinition(
            workflow_version=CHAPTER_WORKFLOW_VERSION_V1,
            state_schema_version=CHAPTER_WORKFLOW_STATE_SCHEMA_VERSION_V1,
            state_type=ChapterWorkflowStateV1,
            compiler=_compile_graph_v1,
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
