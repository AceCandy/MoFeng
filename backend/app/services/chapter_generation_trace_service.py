# AIMETA P=章节生成Trace服务_真实输入输出落库|R=trace记录_查询_清理|NR=不含AI调用|E=ChapterGenerationTraceService|X=internal|A=trace|D=sqlalchemy|S=db|RD=./README.ai
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Chapter, ChapterGenerationTrace


CN_TIMEZONE = timezone(timedelta(hours=8), name="Asia/Shanghai")
SECRET_VALUE_PATTERN = re.compile(
    r"(?i)(api[_-]?key|authorization|token|secret|password)(\s*[:=]\s*)([^\s,;]+)"
)


def _safe_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = str(value)
    return SECRET_VALUE_PATTERN.sub(r"\1\2[已隐藏]", text)


def _json_text(value: Optional[Any]) -> Optional[str]:
    if value is None:
        return None
    return _safe_text(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def _merge_metadata(
    metadata: Optional[Dict[str, Any]],
    *,
    input_payload: Optional[Dict[str, Any]] = None,
    output_payload: Optional[Dict[str, Any]] = None,
    uses_llm: Optional[bool] = None,
    duration_ms: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    merged = dict(metadata or {})
    if input_payload is not None and "input_payload" not in merged:
        merged["input_payload"] = input_payload
    if output_payload is not None and "output_payload" not in merged:
        merged["output_payload"] = output_payload
    if uses_llm is not None:
        merged["uses_llm"] = uses_llm
    if duration_ms is not None:
        merged["duration_ms"] = duration_ms
    return merged or None


def _metadata_uses_llm(metadata: Optional[Dict[str, Any]]) -> Optional[bool]:
    if not metadata:
        return None
    explicit = metadata.get("uses_llm")
    if isinstance(explicit, bool):
        return explicit
    model_calls = metadata.get("model_calls")
    if isinstance(model_calls, list):
        return len(model_calls) > 0
    return None


def _infer_uses_llm(
    *,
    metadata: Optional[Dict[str, Any]],
    system_prompt: Optional[str],
    user_prompt: Optional[str],
    raw_response: Optional[str],
) -> bool:
    metadata_value = _metadata_uses_llm(metadata)
    if metadata_value is not None:
        return metadata_value
    return any(
        bool((value or "").strip())
        for value in (system_prompt, user_prompt, raw_response)
    )


def _calculate_duration_ms(started_at: Optional[datetime], ended_at: Optional[datetime]) -> Optional[int]:
    if not started_at or not ended_at:
        return None
    duration = ended_at - started_at
    return max(0, int(duration.total_seconds() * 1000))


class ChapterGenerationTraceService:
    """记录章节生成节点的真实输入输出，供前端节点详情展示。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def clear_for_chapter(self, *, project_id: str, chapter_number: int) -> None:
        chapter = await self._get_chapter(project_id=project_id, chapter_number=chapter_number)
        await self.session.execute(
            delete(ChapterGenerationTrace).where(ChapterGenerationTrace.chapter_id == chapter.id)
        )
        await self.session.commit()

    async def record_success(
        self,
        *,
        project_id: str,
        chapter_number: int,
        node_key: str,
        node_label: str,
        stage: Optional[str] = None,
        system_prompt: Optional[str] = None,
        user_prompt: Optional[str] = None,
        raw_response: Optional[str] = None,
        cleaned_output: Optional[str] = None,
        input_payload: Optional[Dict[str, Any]] = None,
        output_payload: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        uses_llm: Optional[bool] = None,
        started_at: Optional[datetime] = None,
        ended_at: Optional[datetime] = None,
    ) -> ChapterGenerationTrace:
        resolved_uses_llm = _infer_uses_llm(
            metadata=metadata,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            raw_response=raw_response,
        ) if uses_llm is None else uses_llm
        duration_ms = _calculate_duration_ms(started_at, ended_at)
        return await self._record(
            project_id=project_id,
            chapter_number=chapter_number,
            node_key=node_key,
            node_label=node_label,
            stage=stage,
            status="success",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            raw_response=raw_response,
            cleaned_output=cleaned_output,
            metadata=_merge_metadata(
                metadata,
                input_payload=input_payload,
                output_payload=output_payload,
                uses_llm=resolved_uses_llm,
                duration_ms=duration_ms,
            ),
            started_at=started_at,
            ended_at=ended_at,
        )

    async def record_failure(
        self,
        *,
        project_id: str,
        chapter_number: int,
        node_key: str,
        node_label: str,
        stage: Optional[str] = None,
        system_prompt: Optional[str] = None,
        user_prompt: Optional[str] = None,
        error: Optional[str] = None,
        input_payload: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        uses_llm: Optional[bool] = None,
        started_at: Optional[datetime] = None,
        ended_at: Optional[datetime] = None,
    ) -> ChapterGenerationTrace:
        resolved_uses_llm = _infer_uses_llm(
            metadata=metadata,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            raw_response=None,
        ) if uses_llm is None else uses_llm
        duration_ms = _calculate_duration_ms(started_at, ended_at)
        return await self._record(
            project_id=project_id,
            chapter_number=chapter_number,
            node_key=node_key,
            node_label=node_label,
            stage=stage,
            status="failed",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            error=error,
            metadata=_merge_metadata(
                metadata,
                input_payload=input_payload,
                uses_llm=resolved_uses_llm,
                duration_ms=duration_ms,
            ),
            started_at=started_at,
            ended_at=ended_at,
        )

    async def list_for_chapter(self, *, project_id: str, chapter_number: int) -> List[ChapterGenerationTrace]:
        chapter = await self._get_chapter(project_id=project_id, chapter_number=chapter_number)
        result = await self.session.execute(
            select(ChapterGenerationTrace)
            .where(ChapterGenerationTrace.chapter_id == chapter.id)
            .order_by(ChapterGenerationTrace.created_at, ChapterGenerationTrace.id)
        )
        return list(result.scalars().all())

    async def _record(
        self,
        *,
        project_id: str,
        chapter_number: int,
        node_key: str,
        node_label: str,
        status: str,
        stage: Optional[str] = None,
        system_prompt: Optional[str] = None,
        user_prompt: Optional[str] = None,
        raw_response: Optional[str] = None,
        cleaned_output: Optional[str] = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        started_at: Optional[datetime] = None,
        ended_at: Optional[datetime] = None,
    ) -> ChapterGenerationTrace:
        chapter = await self._get_chapter(project_id=project_id, chapter_number=chapter_number)
        now = datetime.now(CN_TIMEZONE)
        trace = ChapterGenerationTrace(
            chapter=chapter,
            chapter_id=chapter.id,
            project_id=project_id,
            chapter_number=chapter_number,
            node_key=node_key,
            node_label=node_label,
            stage=stage,
            status=status,
            system_prompt=_safe_text(system_prompt),
            user_prompt=_safe_text(user_prompt),
            raw_response=_safe_text(raw_response),
            cleaned_output=_safe_text(cleaned_output),
            error=_safe_text(error),
            metadata=metadata,
            started_at=started_at or now,
            ended_at=ended_at or now,
        )
        self.session.add(trace)
        await self.session.commit()
        await self.session.refresh(trace)
        return trace

    async def _get_chapter(self, *, project_id: str, chapter_number: int) -> Chapter:
        result = await self.session.execute(
            select(Chapter).where(
                Chapter.project_id == project_id,
                Chapter.chapter_number == chapter_number,
            )
        )
        chapter = result.scalars().first()
        if not chapter:
            raise HTTPException(status_code=404, detail="章节不存在，无法记录生成Trace")
        return chapter
