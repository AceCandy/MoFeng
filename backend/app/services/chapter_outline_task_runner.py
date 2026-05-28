# AIMETA P=章节大纲后台任务_长耗时AI大纲生成|R=生成后续章节大纲_记录任务日志|NR=不含HTTP路由|E=run_generate_chapters_outline_task|X=job|A=outline_generation|D=sqlalchemy,llm|S=db,net|RD=./README.ai
from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import HTTPException

from ..db.session import AsyncSessionLocal
from ..services.background_task_service import BackgroundTaskService
from ..services.llm_service import LLMService
from ..services.novel_service import NovelService
from ..services.prompt_service import PromptService
from ..utils.json_utils import remove_think_tags, unwrap_markdown_json


logger = logging.getLogger(__name__)


async def _append_task_log(task_id: str, message: str, *, progress: int | None = None) -> None:
    async with AsyncSessionLocal() as session:
        service = BackgroundTaskService(session)
        await service.append_log(task_id, message, progress=progress)


async def _mark_task_running(task_id: str, message: str) -> None:
    async with AsyncSessionLocal() as session:
        service = BackgroundTaskService(session)
        await service.mark_running(task_id, message)


async def _mark_task_succeeded(task_id: str, result: dict[str, Any]) -> None:
    async with AsyncSessionLocal() as session:
        service = BackgroundTaskService(session)
        await service.mark_succeeded(task_id, result=result)


async def _mark_task_failed(task_id: str, error: str) -> None:
    async with AsyncSessionLocal() as session:
        service = BackgroundTaskService(session)
        await service.mark_failed(task_id, error)


async def run_generate_chapters_outline_task(
    task_id: str,
    *,
    project_id: str,
    user_id: int,
    start_chapter: int,
    num_chapters: int,
) -> None:
    """后台生成后续章节大纲，只在完整 JSON 校验通过后写入章节大纲。"""

    await _mark_task_running(task_id, "开始生成章节大纲")

    try:
        async with AsyncSessionLocal() as session:
            novel_service = NovelService(session)
            prompt_service = PromptService(session)
            llm_service = LLMService(session)

            project = await novel_service.ensure_project_owner(project_id, user_id)
            project_schema = await novel_service._serialize_project(project)
            if not project_schema.blueprint:
                raise ValueError("项目还没有可用于续写大纲的世界蓝图")

            await _append_task_log(task_id, "已读取世界蓝图和已有章节大纲", progress=15)

            blueprint_text = json.dumps(project_schema.blueprint.model_dump(), ensure_ascii=False, indent=2)
            existing_outlines = [
                f"第{o.chapter_number}章 - {o.title}: {o.summary}"
                for o in sorted(project.outlines, key=lambda x: x.chapter_number)
            ]
            existing_outlines_text = "\n".join(existing_outlines) if existing_outlines else "暂无"

            outline_prompt = await prompt_service.get_prompt("outline_generation")
            if not outline_prompt:
                raise ValueError("未配置大纲生成提示词")

            prompt_input = f"""
[世界蓝图]
{blueprint_text}

[已有章节大纲]
{existing_outlines_text}

[生成任务]
请从第 {start_chapter} 章开始，续写接下来的 {num_chapters} 章的大纲。
要求返回 JSON 格式，包含一个 chapters 数组，每个元素包含 chapter_number, title, summary。
"""

            await _append_task_log(task_id, "已提交 AI 生成请求，等待模型返回", progress=30)
            response = await llm_service.get_llm_response(
                system_prompt=outline_prompt,
                conversation_history=[{"role": "user", "content": prompt_input}],
                temperature=0.7,
                user_id=user_id,
                timeout=600.0,
                stage="chapter_outline",
            )
            await _append_task_log(task_id, "AI 已返回大纲结果，正在校验 JSON", progress=75)

            cleaned = remove_think_tags(response)
            normalized = unwrap_markdown_json(cleaned)
            data = json.loads(normalized)
            new_outlines = data.get("chapters", [])
            if not isinstance(new_outlines, list) or not new_outlines:
                raise ValueError("AI 未返回有效的 chapters 数组")

            for item in new_outlines:
                await novel_service.update_or_create_outline(
                    project_id,
                    int(item["chapter_number"]),
                    str(item["title"]),
                    str(item["summary"]),
                )
            await session.commit()

            await _append_task_log(task_id, f"已写入 {len(new_outlines)} 条章节大纲", progress=95)
            await _mark_task_succeeded(
                task_id,
                {
                    "project_id": project_id,
                    "start_chapter": start_chapter,
                    "num_chapters": num_chapters,
                    "outline_count": len(new_outlines),
                },
            )
    except HTTPException as exc:
        detail = str(exc.detail or exc)
        logger.exception("章节大纲后台任务失败: task_id=%s detail=%s", task_id, detail)
        await _mark_task_failed(task_id, detail)
    except Exception as exc:
        detail = str(exc) or exc.__class__.__name__
        logger.exception("章节大纲后台任务失败: task_id=%s detail=%s", task_id, detail)
        await _mark_task_failed(task_id, detail)
