# AIMETA P=章节工作流Graph执行适配器|R=同thread恢复_interrupt转waiting_command_marker补偿|NR=不实现业务节点或command收件箱持久化|E=ChapterWorkflowRuntime|X=internal|A=workflow_runtime|D=langgraph,pydantic|S=checkpoint,db|RD=./README.ai
"""Run one durable Chapter graph turn and map interrupts to root job waiting."""

from __future__ import annotations

from typing import Any, Awaitable, Callable, cast

from langgraph.types import Command
from sqlalchemy.engine import URL

from ..db.chapter_workflow_checkpointer import open_chapter_workflow_checkpointer
from ..schemas.chapter_workflow import ChapterWorkflowState
from ..schemas.job import ChapterWorkflowJobPayload, validate_chapter_workflow_job_payload
from .chapter_workflow_graph import (
    ChapterWorkflowGraphBindings,
    ChapterWorkflowGraphRegistry,
    build_chapter_workflow_graph_registry,
    chapter_workflow_graph_config,
)
from .chapter_workflow_transition import ChapterWorkflowTransition
from .job_worker import JobExecutionContext, JobOutcome, JobWaitOutcome

_NO_RESUME = object()
_WAIT_PROGRESS = {
    "wait_for_selection": 60,
    "wait_for_projections": 90,
}
_WAIT_STATUS = {
    "wait_for_selection": "waiting_for_selection",
    "wait_for_projections": "projection_pending",
}


class ChapterWorkflowRuntime:
    """在短生命周期 saver 连接内执行或恢复一次 Graph。"""

    def __init__(
        self,
        execution: JobExecutionContext,
        *,
        database_url: str | URL,
        bindings: ChapterWorkflowGraphBindings,
        registry: ChapterWorkflowGraphRegistry | None = None,
    ) -> None:
        self.execution = execution
        self.database_url = database_url
        self.bindings = bindings
        self.registry = registry or build_chapter_workflow_graph_registry()

    async def execute(
        self,
        *,
        resume_value: object = _NO_RESUME,
        command_id: str | None = None,
        expected_checkpoint_id: str | None = None,
        on_command_checkpointed: Callable[[str, str], Awaitable[None]] | None = None,
    ) -> JobOutcome | JobWaitOutcome:
        command_handshake = command_id is not None
        if command_handshake != (expected_checkpoint_id is not None):
            raise ValueError("command id 与 expected checkpoint 必须同时提供")
        if command_handshake != (on_command_checkpointed is not None):
            raise ValueError("command marker callback 必须与 command identity 同时提供")
        if command_handshake and resume_value is _NO_RESUME:
            raise ValueError("command checkpoint handshake 缺少 resume value")
        if command_handshake:
            assert command_id is not None
            assert expected_checkpoint_id is not None
            assert on_command_checkpointed is not None
        checkpoint_command_id = cast(str, command_id)
        checkpoint_callback = cast(
            Callable[[str, str], Awaitable[None]],
            on_command_checkpointed,
        )

        payload = self._payload()
        definition = self.registry.get(payload.workflow_version)
        if (
            definition is None
            or definition.state_schema_version != payload.state_schema_version
        ):
            raise ValueError("workflow payload 与 graph state schema 不匹配")
        state_type = definition.state_type
        config = chapter_workflow_graph_config(payload.run_id)
        async with open_chapter_workflow_checkpointer(self.database_url) as saver:
            app = self.registry.compile(
                payload.workflow_version,
                checkpointer=saver,
                bindings=self.bindings,
            )
            snapshot = await app.aget_state(config)
            marker_already_written = False
            if command_handshake and snapshot.values:
                state = state_type.model_validate(snapshot.values)
                marker_already_written = state.last_applied_command_id == checkpoint_command_id

            if marker_already_written:
                marker_checkpoint_id = self._checkpoint_id(snapshot)
                await checkpoint_callback(checkpoint_command_id, marker_checkpoint_id)
            elif resume_value is _NO_RESUME:
                waiting = self._waiting_outcome(snapshot, state_type=state_type)
                if waiting is not None:
                    return waiting
                graph_input: Any = (
                    None
                    if snapshot.values
                    else self._initial_state(payload).model_dump(mode="json")
                )
            else:
                if not snapshot.values:
                    raise ValueError("workflow resume 缺少已有 checkpoint")
                waiting = self._waiting_outcome(snapshot, state_type=state_type)
                if waiting is None:
                    raise ValueError("workflow resume 只能应用于当前 interrupt checkpoint")
                if command_handshake:
                    current_checkpoint_id = self._checkpoint_id(snapshot)
                    if current_checkpoint_id != expected_checkpoint_id:
                        raise ValueError("pending command 的 expected checkpoint 已漂移")
                    state = state_type.model_validate(snapshot.values)
                    self._validate_command_resume(
                        state=state,
                        node_key=waiting.workflow_transition.node_key,
                        command_id=checkpoint_command_id,
                        resume_value=resume_value,
                    )
                graph_input = Command(resume=resume_value)

            if not marker_already_written:
                invoke_error: Exception | None = None
                try:
                    await app.ainvoke(graph_input, config)
                except Exception as error:
                    invoke_error = error
                snapshot = await app.aget_state(config)
                if command_handshake:
                    state = state_type.model_validate(snapshot.values)
                    if state.last_applied_command_id == checkpoint_command_id:
                        await checkpoint_callback(
                            checkpoint_command_id,
                            self._checkpoint_id(snapshot),
                        )
                    elif invoke_error is None:
                        raise RuntimeError("workflow resume 未写入 command checkpoint marker")
                if invoke_error is not None:
                    raise invoke_error

        waiting = self._waiting_outcome(snapshot, state_type=state_type)
        if waiting is not None:
            return waiting
        if snapshot.next:
            raise RuntimeError("workflow graph 停在未知的非 interrupt 节点")

        state = state_type.model_validate(snapshot.values)
        if state.node_key != "successful":
            raise RuntimeError("workflow graph 终态不是 successful")
        return JobOutcome(
            result={
                "run_id": state.run_id,
                "selected_version_id": state.selected_version_id,
                "target_chapter_revision": state.target_chapter_revision,
            }
        )

    def _payload(self) -> ChapterWorkflowJobPayload:
        lease = self.execution.lease
        if lease.job_type != "chapter_workflow":
            raise ValueError("JobLease 不是 Chapter workflow root")
        return validate_chapter_workflow_job_payload(
            lease.payload_version,
            lease.payload,
        )

    @staticmethod
    def _initial_state(payload: ChapterWorkflowJobPayload) -> ChapterWorkflowState:
        return ChapterWorkflowState.initial(
            run_id=payload.run_id,
            context_hash=payload.context_hash,
            candidate_count=payload.candidate_count,
            optional_stages={str(key): enabled for key, enabled in payload.optional_stages.items()},
        )

    @staticmethod
    def _waiting_outcome(
        snapshot: Any,
        *,
        state_type: type[ChapterWorkflowState],
    ) -> JobWaitOutcome | None:
        if len(snapshot.next) != 1:
            return None
        node_key = snapshot.next[0]
        if node_key not in _WAIT_PROGRESS:
            return None
        state = state_type.model_validate(snapshot.values)
        if state.node_key != node_key:
            raise RuntimeError("workflow checkpoint node_key 与 pending task 不一致")
        checkpoint_id = snapshot.config["configurable"].get("checkpoint_id")
        if not checkpoint_id:
            raise RuntimeError("workflow interrupt 缺少 checkpoint_id")
        return JobWaitOutcome(
            workflow_transition=ChapterWorkflowTransition(
                status=_WAIT_STATUS[node_key],
                node_key=node_key,
                checkpoint_id=checkpoint_id,
                progress=_WAIT_PROGRESS[node_key],
            )
        )

    @staticmethod
    def _checkpoint_id(snapshot: Any) -> str:
        checkpoint_id = snapshot.config["configurable"].get("checkpoint_id")
        if not isinstance(checkpoint_id, str) or not checkpoint_id:
            raise RuntimeError("workflow checkpoint 缺少 checkpoint_id")
        return checkpoint_id

    @staticmethod
    def _validate_command_resume(
        *,
        state: ChapterWorkflowState,
        node_key: str,
        command_id: str,
        resume_value: object,
    ) -> None:
        if not isinstance(resume_value, dict) or resume_value.get("command_id") != command_id:
            raise ValueError("workflow resume command identity 不一致")
        if node_key == "wait_for_selection":
            selected_version_id = resume_value.get("selected_version_id")
            if (
                set(resume_value) != {"command_id", "selected_version_id"}
                or isinstance(selected_version_id, bool)
                or not isinstance(selected_version_id, int)
                or selected_version_id not in state.candidate_version_ids
            ):
                raise ValueError("select command 未引用当前 checkpoint candidate")
            return
        if node_key == "wait_for_projections" and set(resume_value) == {"command_id"}:
            return
        raise ValueError("workflow command 与当前 interrupt 类型不一致")


__all__ = ["ChapterWorkflowRuntime"]
