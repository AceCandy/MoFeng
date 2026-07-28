# AIMETA P=业务任务注册_生产worker路由|R=注册版本化业务handler|NR=不执行worker循环|E=build_job_handler_registry|X=internal|A=composition_root|D=job_registry|S=memory|RD=./README.ai
from .chapter_outline_task_runner import handle_chapter_outline_job
from .chapter_edit_postprocess import handle_chapter_edit_postprocess_job
from .chapter_finalize_task_runner import handle_chapter_finalize_job
from .chapter_generation_task_runner import handle_chapter_generation_job
from .chapter_outbox_dispatcher import handle_chapter_outbox_dispatch
from .chapter_projection_handlers import (
    handle_chapter_foreshadowing_projection,
    handle_chapter_memory_projection,
    handle_chapter_projection_reconcile,
    handle_chapter_projection_tombstone,
    handle_chapter_rag_projection,
    handle_chapter_summary_projection,
    handle_chapter_trace_projection,
)
from .job_registry import JobHandlerRegistry, SideEffectClass


def register_job_handlers(registry: JobHandlerRegistry) -> JobHandlerRegistry:
    """注册生产 worker 支持的全部版本化业务任务。"""

    registry.register(
        job_type="chapter_outline",
        payload_version=1,
        side_effect_class=SideEffectClass.AMBIGUOUS_EXTERNAL,
        handler=handle_chapter_outline_job,
    )
    registry.register(
        job_type="chapter_edit_postprocess",
        payload_version=1,
        side_effect_class=SideEffectClass.AMBIGUOUS_EXTERNAL,
        handler=handle_chapter_edit_postprocess_job,
    )
    registry.register(
        job_type="chapter_generation",
        payload_version=1,
        side_effect_class=SideEffectClass.AMBIGUOUS_EXTERNAL,
        handler=handle_chapter_generation_job,
    )
    registry.register(
        job_type="chapter_outbox_dispatch",
        payload_version=1,
        side_effect_class=SideEffectClass.TRANSACTIONAL,
        handler=handle_chapter_outbox_dispatch,
    )
    registry.register(
        job_type="chapter_finalize",
        payload_version=1,
        side_effect_class=SideEffectClass.AMBIGUOUS_EXTERNAL,
        handler=handle_chapter_finalize_job,
    )
    registry.register(
        job_type="chapter_finalize",
        payload_version=2,
        side_effect_class=SideEffectClass.AMBIGUOUS_EXTERNAL,
        handler=handle_chapter_summary_projection,
    )
    registry.register(
        job_type="chapter_projection_memory",
        payload_version=1,
        side_effect_class=SideEffectClass.AMBIGUOUS_EXTERNAL,
        handler=handle_chapter_memory_projection,
    )
    registry.register(
        job_type="chapter_projection_rag",
        payload_version=1,
        side_effect_class=SideEffectClass.AMBIGUOUS_EXTERNAL,
        handler=handle_chapter_rag_projection,
    )
    registry.register(
        job_type="chapter_projection_foreshadowing",
        payload_version=1,
        side_effect_class=SideEffectClass.AMBIGUOUS_EXTERNAL,
        handler=handle_chapter_foreshadowing_projection,
    )
    registry.register(
        job_type="chapter_projection_trace",
        payload_version=1,
        side_effect_class=SideEffectClass.TRANSACTIONAL,
        handler=handle_chapter_trace_projection,
    )
    registry.register(
        job_type="chapter_projection_reconcile",
        payload_version=1,
        side_effect_class=SideEffectClass.TRANSACTIONAL,
        handler=handle_chapter_projection_reconcile,
    )
    registry.register(
        job_type="chapter_projection_tombstone",
        payload_version=1,
        side_effect_class=SideEffectClass.TRANSACTIONAL,
        handler=handle_chapter_projection_tombstone,
    )
    return registry


def build_job_handler_registry() -> JobHandlerRegistry:
    return register_job_handlers(JobHandlerRegistry())
