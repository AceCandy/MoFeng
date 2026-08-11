# AIMETA P=章节记忆投影_纯计算与事务内写回|R=记忆输入加载_快照_角色状态制品|NR=不创建session或提交事务|E=compute_memory_projection_apply_memory_projection|X=internal|A=projection|D=sqlalchemy|S=db|RD=./README.ai
"""Pure compute and caller-transaction apply steps for chapter memory."""

from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.memory_layer import CharacterState
from ..models.novel import Chapter
from ..models.project_memory import ChapterSnapshot, ProjectMemory
from .chapter_word_count_settings import count_chapter_words
from .finalize_service import (
    GENERATE_CHAPTER_SUMMARY_PROMPT,
    UPDATE_CHARACTER_STATE_PROMPT,
    UPDATE_GLOBAL_SUMMARY_PROMPT,
    UPDATE_PLOT_ARCS_PROMPT,
    FinalizeService,
)
from .llm_service import LLMService


async def load_memory_input(session: AsyncSession, *, project_id: str) -> dict[str, Any]:
    """Read the stable inputs needed before external memory computation."""

    memory = (
        (await session.execute(select(ProjectMemory).where(ProjectMemory.project_id == project_id)))
        .scalars()
        .first()
    )
    old_state = await FinalizeService(
        session,
        LLMService(session),
    )._get_character_state_text(project_id)
    return {
        "old_summary": memory.global_summary if memory and memory.global_summary else "",
        "old_plot_arcs": memory.plot_arcs if memory and memory.plot_arcs else {},
        "old_state": old_state,
    }


def memory_prompts(
    *,
    chapter_text: str,
    chapter_number: int,
    memory_input: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Build deterministic provider requests for each independently fenced activity."""

    return {
        "global_summary": {
            "prompt": UPDATE_GLOBAL_SUMMARY_PROMPT.format(
                chapter_text=chapter_text,
                global_summary=memory_input.get("old_summary") or "",
            ),
            "max_tokens": 3000,
            "response_format": None,
        },
        "character_state": {
            "prompt": UPDATE_CHARACTER_STATE_PROMPT.format(
                chapter_text=chapter_text,
                old_state=memory_input.get("old_state") or "（暂无角色状态记录）",
            ),
            "max_tokens": 4000,
            "response_format": None,
        },
        "plot_arcs": {
            "prompt": UPDATE_PLOT_ARCS_PROMPT.format(
                chapter_text=chapter_text,
                chapter_number=chapter_number,
                plot_arcs=json.dumps(
                    memory_input.get("old_plot_arcs") or {},
                    ensure_ascii=False,
                    indent=2,
                ),
            ),
            "max_tokens": 2000,
            "response_format": "json_object",
        },
        "chapter_summary": {
            "prompt": GENERATE_CHAPTER_SUMMARY_PROMPT.format(
                chapter_text=chapter_text[:5000],
                chapter_number=chapter_number,
            ),
            "max_tokens": 500,
            "response_format": None,
        },
    }


def parse_memory_results(
    *,
    activity_results: dict[str, dict[str, Any]],
    memory_input: dict[str, Any],
) -> dict[str, Any]:
    """Normalize activity results into a JSON-safe projection artifact."""

    normalized: dict[str, Any] = {
        "old_summary": memory_input.get("old_summary") or "",
        "old_plot_arcs": memory_input.get("old_plot_arcs") or {},
        "errors": [],
    }
    for field in ("global_summary", "character_state", "chapter_summary"):
        response = str(activity_results.get(field, {}).get("response") or "").strip()
        normalized[field] = response or None

    plot_response = str(activity_results.get("plot_arcs", {}).get("response") or "").strip()
    if plot_response.startswith("```"):
        plot_response = plot_response.split("```", 2)[1]
        if plot_response.startswith("json"):
            plot_response = plot_response[4:]
    try:
        normalized["plot_arcs"] = json.loads(plot_response) if plot_response else None
    except json.JSONDecodeError:
        normalized["plot_arcs"] = None
        normalized["errors"].append("invalid_plot_arcs_json")

    valid_fields = [
        normalized.get("global_summary"),
        normalized.get("character_state"),
        normalized.get("plot_arcs"),
        normalized.get("chapter_summary"),
    ]
    normalized["success"] = any(valid_fields)
    normalized["partial_success"] = sum(bool(value) for value in valid_fields) < len(valid_fields)
    return normalized


async def apply_memory_projection(
    session: AsyncSession,
    *,
    project_id: str,
    chapter_number: int,
    chapter_text: str,
    revision: int,
    artifact_generation: str,
    projection_run_id: Optional[str],
    expected_source_hash: Optional[str],
    expected_source_generation: Optional[str],
    prepared: dict[str, Any],
    activate: bool = True,
) -> dict[str, Any]:
    """写入一代 memory；shadow 只创建 inactive snapshot/state。"""

    if not prepared.get("success"):
        raise ValueError("章节记忆投影没有可提交的有效结果")
    if activate and revision > 0:
        if expected_source_hash is None or expected_source_generation is None:
            raise ValueError("canonical 章节记忆缺少 source identity")
        current_chapter_id = await session.scalar(
            select(Chapter.id)
            .where(
                Chapter.project_id == project_id,
                Chapter.chapter_number == chapter_number,
                Chapter.current_revision == revision,
                Chapter.source_hash == expected_source_hash,
                Chapter.projection_generation == expected_source_generation,
                Chapter.tombstone_revision < revision,
            )
            .with_for_update()
        )
        if current_chapter_id is None:
            raise ValueError("章节记忆激活条件已失效")

    memory = None
    if activate:
        memory = (
            (
                await session.execute(
                    select(ProjectMemory)
                    .where(ProjectMemory.project_id == project_id)
                    .with_for_update()
                )
            )
            .scalars()
            .first()
        )
        if memory is None:
            memory = ProjectMemory(
                project_id=project_id,
                global_summary="",
                plot_arcs={
                    "unresolved_hooks": [],
                    "main_conflicts": [],
                    "character_arcs": [],
                },
                projection_revision=0,
            )
            session.add(memory)
            await session.flush()

        await session.execute(
            update(ChapterSnapshot)
            .where(
                ChapterSnapshot.project_id == project_id,
                ChapterSnapshot.chapter_number == chapter_number,
                ChapterSnapshot.is_active.is_(True),
            )
            .values(is_active=False)
        )
        await session.execute(
            update(CharacterState)
            .where(
                CharacterState.project_id == project_id,
                CharacterState.chapter_number == chapter_number,
                CharacterState.is_active.is_(True),
            )
            .values(is_active=False)
        )

    finalizer = FinalizeService(session, LLMService(session))
    character_state = prepared.get("character_state")
    if character_state:
        await finalizer._save_character_state(
            project_id,
            chapter_number,
            str(character_state),
            chapter_revision=revision,
            artifact_generation=artifact_generation,
            projection_run_id=projection_run_id,
            is_active=activate,
        )

    global_summary = prepared.get("global_summary") or prepared.get("old_summary") or ""
    plot_arcs = prepared.get("plot_arcs") or prepared.get("old_plot_arcs") or {}
    await finalizer._create_chapter_snapshot(
        project_id=project_id,
        chapter_number=chapter_number,
        global_summary=global_summary,
        character_states=str(character_state) if character_state else None,
        plot_arcs=plot_arcs,
        chapter_summary=prepared.get("chapter_summary"),
        word_count=count_chapter_words(chapter_text),
        chapter_revision=revision,
        artifact_generation=artifact_generation,
        projection_run_id=projection_run_id,
        is_active=activate,
    )

    conflict = False
    if activate and memory is not None:
        current_position = (
            int(memory.last_updated_chapter or 0),
            int(memory.projection_revision or 0),
        )
        incoming_position = (chapter_number, revision)
        conflict = current_position > incoming_position
        if not conflict:
            if prepared.get("global_summary"):
                memory.global_summary = prepared["global_summary"]
            if prepared.get("plot_arcs"):
                memory.plot_arcs = prepared["plot_arcs"]
            memory.last_updated_chapter = chapter_number
            memory.projection_revision = revision
            memory.projection_generation = artifact_generation
            memory.version = int(memory.version or 0) + 1
        await finalizer._update_blueprint_status(project_id, chapter_number)
    return {
        "conflict": conflict,
        "staged": not activate,
        "partial_success": bool(prepared.get("partial_success")),
        "snapshot_created": True,
        "character_state_updated": bool(character_state),
    }


__all__ = [
    "apply_memory_projection",
    "load_memory_input",
    "memory_prompts",
    "parse_memory_results",
]
