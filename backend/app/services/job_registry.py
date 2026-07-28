# AIMETA P=任务handler注册表_副作用契约|R=版本化handler注册_副作用分类|NR=不执行任务或管理事务|E=JobHandlerRegistry|X=internal|A=registry|D=typing|S=memory|RD=./README.ai
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Awaitable, Callable, Optional


class SideEffectClass(str, Enum):
    """handler/activity 对数据库外部世界的副作用保证。"""

    TRANSACTIONAL = "transactional"
    IDEMPOTENT_EXTERNAL = "idempotent_external"
    AMBIGUOUS_EXTERNAL = "ambiguous_external"


JobHandler = Callable[[Any], Awaitable[Any]]


@dataclass(frozen=True)
class JobHandlerDefinition:
    job_type: str
    payload_version: int
    side_effect_class: SideEffectClass
    handler: JobHandler


class JobHandlerRegistry:
    """按 job_type + payload_version 精确路由 handler。"""

    def __init__(self) -> None:
        self._handlers: dict[tuple[str, int], JobHandlerDefinition] = {}

    def register(
        self,
        *,
        job_type: str,
        payload_version: int,
        side_effect_class: SideEffectClass,
        handler: JobHandler,
    ) -> JobHandlerDefinition:
        normalized_type = job_type.strip()
        if not normalized_type:
            raise ValueError("job_type 不能为空")
        if payload_version < 1:
            raise ValueError("payload_version 必须大于等于 1")
        key = (normalized_type, payload_version)
        if key in self._handlers:
            raise ValueError(f"handler 已注册: {normalized_type} v{payload_version}")
        definition = JobHandlerDefinition(
            job_type=normalized_type,
            payload_version=payload_version,
            side_effect_class=side_effect_class,
            handler=handler,
        )
        self._handlers[key] = definition
        return definition

    def get(self, job_type: str, payload_version: int) -> Optional[JobHandlerDefinition]:
        return self._handlers.get((job_type, payload_version))


job_handler_registry = JobHandlerRegistry()
