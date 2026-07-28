# AIMETA P=业务任务注册_生产worker路由|R=注册版本化业务handler|NR=不执行worker循环|E=build_job_handler_registry|X=internal|A=composition_root|D=job_registry|S=memory|RD=./README.ai
from .chapter_outline_task_runner import handle_chapter_outline_job
from .chapter_edit_postprocess import handle_chapter_edit_postprocess_job
from .chapter_finalize_task_runner import handle_chapter_finalize_job
from .chapter_generation_task_runner import handle_chapter_generation_job
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
        job_type="chapter_finalize",
        payload_version=1,
        side_effect_class=SideEffectClass.AMBIGUOUS_EXTERNAL,
        handler=handle_chapter_finalize_job,
    )
    return registry


def build_job_handler_registry() -> JobHandlerRegistry:
    return register_job_handlers(JobHandlerRegistry())
