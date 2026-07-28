# AIMETA P=章节大纲持久任务_长耗时AI大纲生成|R=生成校验大纲_返回原子写入结果|NR=不直接提交任务状态|E=handle_chapter_outline_job|X=job|A=durable_handler|D=sqlalchemy,llm|S=db,net|RD=./README.ai
from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException
from pydantic import ValidationError

from ..schemas.job import ChapterOutlineJobPayload
from ..utils.json_utils import remove_think_tags, unwrap_markdown_json
from .job_worker import JobOutcome, PermanentJobError
from .llm_service import LLMService
from .novel_service import NovelService
from .prompt_service import PromptService


_REQUIRED_OUTLINE_FIELDS = (
    "chapter_number",
    "title",
    "summary",
    "goals",
    "highlights",
    "character_states",
)
_OUTLINE_ACTIVITY_KEY = "outline_generation"


def _parse_generated_outline_item(item: Any) -> dict[str, Any]:
    """校验单章大纲结构，缺字段或类型不对时直接失败。"""

    if not isinstance(item, dict):
        raise ValueError("AI 返回的 chapters 元素必须是对象")

    missing = [field for field in _REQUIRED_OUTLINE_FIELDS if field not in item]
    if missing:
        raise ValueError(f"AI 返回章节大纲缺少字段: {', '.join(missing)}")

    highlights = item["highlights"]
    if not isinstance(highlights, list):
        raise ValueError("AI 返回章节大纲字段 highlights 必须是字符串数组")

    character_states = item["character_states"]
    if not isinstance(character_states, dict):
        raise ValueError("AI 返回章节大纲字段 character_states 必须是对象")

    title = str(item["title"]).strip()
    summary = str(item["summary"]).strip()
    goals = str(item["goals"]).strip()
    if not title or not summary or not goals:
        raise ValueError("AI 返回章节大纲的 title/summary/goals 不能为空")

    return {
        "chapter_number": int(item["chapter_number"]),
        "title": title,
        "summary": summary,
        "goals": goals,
        "highlights": [str(value).strip() for value in highlights if str(value).strip()],
        "character_states": {
            str(name).strip(): str(state).strip()
            for name, state in character_states.items()
            if str(name).strip() and str(state).strip()
        },
    }


def _parse_generated_outlines(response: str, payload: ChapterOutlineJobPayload) -> list[dict[str, Any]]:
    cleaned = remove_think_tags(response)
    normalized = unwrap_markdown_json(cleaned)
    data = json.loads(normalized)
    raw_outlines = data.get("chapters", []) if isinstance(data, dict) else []
    if not isinstance(raw_outlines, list) or not raw_outlines:
        raise ValueError("AI 未返回有效的 chapters 数组")

    outlines = [_parse_generated_outline_item(item) for item in raw_outlines]
    chapter_numbers = [item["chapter_number"] for item in outlines]
    expected_numbers = list(range(payload.start_chapter, payload.start_chapter + payload.num_chapters))
    if chapter_numbers != expected_numbers:
        raise ValueError("AI 返回的章节编号或数量与生成请求不一致")
    return outlines


async def handle_chapter_outline_job(context) -> JobOutcome:
    """生成大纲并返回与 job success 同事务提交的数据库写入器。"""

    try:
        payload = ChapterOutlineJobPayload.model_validate(context.lease.payload)
    except ValidationError as exc:
        raise PermanentJobError("invalid_outline_payload", "章节大纲任务参数无效") from exc
    if context.lease.project_id != payload.project_id:
        raise PermanentJobError("outline_project_mismatch", "章节大纲任务项目不匹配")

    try:
        async with context.session_factory() as session:
            novel_service = NovelService(session)
            project = await novel_service.ensure_project_owner(payload.project_id, context.lease.user_id)
            project_schema = await novel_service._serialize_project(project)
            if not project_schema.blueprint:
                raise ValueError("项目还没有可用于续写大纲的世界蓝图")

            blueprint_text = json.dumps(
                project_schema.blueprint.model_dump(),
                ensure_ascii=False,
                indent=2,
            )
            existing_outlines = [
                {
                    "chapter_number": outline.chapter_number,
                    "title": outline.title,
                    "summary": outline.summary or "",
                    "goals": outline.goals or "",
                    "highlights": outline.highlights or [],
                    "character_states": outline.character_states or {},
                }
                for outline in sorted(project.outlines, key=lambda item: item.chapter_number)
            ]
            existing_outlines_text = (
                json.dumps(existing_outlines, ensure_ascii=False, indent=2)
                if existing_outlines
                else "暂无"
            )
            outline_prompt = await PromptService(session).get_prompt("outline_generation")
            if not outline_prompt:
                raise ValueError("未配置大纲生成提示词")
    except HTTPException as exc:
        raise PermanentJobError("outline_project_unavailable", str(exc.detail or "项目不存在")) from exc
    except ValueError as exc:
        raise PermanentJobError("outline_prerequisite_missing", str(exc)) from exc

    await context.progress("已读取世界蓝图和已有章节大纲", progress=15)
    prompt_input = f"""
[世界蓝图]
{blueprint_text}

[已有章节大纲]
{existing_outlines_text}

[生成任务]
请从第 {payload.start_chapter} 章开始，续写接下来的 {payload.num_chapters} 章的大纲。
要求返回 JSON 格式，包含一个 chapters 数组。每个元素必须包含：
- chapter_number: 章节编号
- title: 章节标题
- summary: 单章概要
- goals: 本章目标
- highlights: 看点列表，字符串数组
- character_states: 相关角色的瞬时状态，键为角色名，值为状态说明
"""

    activity = await context.begin_activity(
        _OUTLINE_ACTIVITY_KEY,
        request_payload={
            "project_id": payload.project_id,
            "start_chapter": payload.start_chapter,
            "num_chapters": payload.num_chapters,
        },
    )
    if activity.should_execute:
        await context.progress("已提交 AI 生成请求，等待模型返回", progress=30)
        try:
            response = await LLMService.get_llm_response_detached(
                system_prompt=outline_prompt,
                conversation_history=[{"role": "user", "content": prompt_input}],
                session_factory=context.session_factory,
                temperature=0.7,
                user_id=context.lease.user_id,
                timeout=600.0,
                stage="chapter_outline",
            )
        except Exception:
            await context.mark_activity_ambiguous(
                _OUTLINE_ACTIVITY_KEY,
                provider_request_key=activity.provider_request_key,
                public_message="AI 大纲调用结果不确定，需要人工确认",
            )
            raise
        await context.complete_activity(
            _OUTLINE_ACTIVITY_KEY,
            provider_request_key=activity.provider_request_key,
            result={"response": response},
        )
    else:
        response = str((activity.result or {}).get("response") or "")

    await context.progress("AI 已返回大纲结果，正在校验 JSON", progress=75)
    try:
        outlines = _parse_generated_outlines(response, payload)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise PermanentJobError("invalid_outline_response", "AI 返回的章节大纲格式无效") from exc

    async def write_outlines(session) -> None:
        novel_service = NovelService(session)
        for item in outlines:
            await novel_service.update_or_create_outline(
                payload.project_id,
                item["chapter_number"],
                item["title"],
                item["summary"],
                goals=item["goals"],
                highlights=item["highlights"],
                character_states=item["character_states"],
            )

    await context.progress(f"已校验 {len(outlines)} 条章节大纲", progress=95)
    return JobOutcome(
        result={
            "project_id": payload.project_id,
            "start_chapter": payload.start_chapter,
            "num_chapters": payload.num_chapters,
            "outline_count": len(outlines),
        },
        outcome_writer=write_outlines,
    )
