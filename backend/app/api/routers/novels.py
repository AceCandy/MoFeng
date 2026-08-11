# AIMETA P=小说API_项目和章节管理|R=小说CRUD_章节管理|NR=不含内容生成|E=route:GET_POST_/api/novels/*|X=http|A=小说CRUD_章节|D=fastapi,sqlalchemy|S=db|RD=./README.ai
import asyncio
import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import get_current_user
from ...db.session import AsyncSessionLocal
from ...db.session import get_session
from ...schemas.novel import (
    Blueprint,
    BlueprintGenerationResponse,
    BlueprintPatch,
    Chapter as ChapterSchema,
    ConverseRequest,
    ConverseResponse,
    NovelProject as NovelProjectSchema,
    NovelProjectSummary,
    NovelSectionResponse,
    NovelSectionType,
)
from ...schemas.user import UserInDB
from ...services.event_bus import subscribe_chapter_status
from ...services.import_service import ImportService
from ...services.llm_service import LLMService
from ...services.novel_service import NovelService
from ...services.prompt_service import PromptService
from ...utils.json_utils import remove_think_tags, sanitize_json_like_text, unwrap_markdown_json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/novels", tags=["Novels"])

JSON_RESPONSE_INSTRUCTION = """
IMPORTANT: 你的回复必须是合法的 JSON 对象，并严格包含以下字段：
{
  "ai_message": "string",
  "ui_control": {
    "type": "single_choice | text_input | info_display",
    "options": [
      {"id": "option_1", "label": "string"}
    ],
    "placeholder": "string"
  },
  "conversation_state": {},
  "is_complete": false
}
不要输出额外的文本或解释。
"""


def _ensure_prompt(prompt: str | None, name: str) -> str:
    if not prompt:
        raise HTTPException(status_code=500, detail=f"未配置名为 {name} 的提示词，请联系管理员")
    return prompt


def _parse_json_object_from_llm_text(raw_text: str) -> Dict[str, Any]:
    """按模型输出常见形态清洗并解析 JSON 对象。"""
    normalized = unwrap_markdown_json(raw_text)
    sanitized = sanitize_json_like_text(normalized)
    parsed = json.loads(sanitized)
    if not isinstance(parsed, dict):
        raise ValueError("AI 返回的蓝图不是 JSON 对象")
    return parsed


async def _parse_blueprint_json_with_repair(
    *,
    project_id: str,
    user_id: int,
    llm_service: LLMService,
    prompt_service: PromptService,
    blueprint_raw: str,
) -> Dict[str, Any]:
    """先直接解析蓝图 JSON，失败后让模型只做一次语法修复。"""
    parse_error: Exception
    try:
        return _parse_json_object_from_llm_text(blueprint_raw)
    except (json.JSONDecodeError, ValueError) as first_exc:
        parse_error = first_exc
        logger.warning(
            "项目 %s 蓝图 JSON 首次解析失败，尝试自动修复: %s\n原始响应片段: %s",
            project_id,
            parse_error,
            blueprint_raw[:500],
        )

    repair_prompt = _ensure_prompt(
        await prompt_service.get_prompt("blueprint_json_repair"),
        "blueprint_json_repair",
    )
    repair_input = json.dumps(
        {
            "parse_error": str(parse_error),
            "blueprint_raw": blueprint_raw,
        },
        ensure_ascii=False,
    )

    try:
        repaired_raw = await llm_service.get_llm_response(
            system_prompt=repair_prompt,
            conversation_history=[{"role": "user", "content": repair_input}],
            temperature=0.0,
            user_id=user_id,
            timeout=180.0,
            stage="world_blueprint",
        )
        repaired_raw = remove_think_tags(repaired_raw)
        return _parse_json_object_from_llm_text(repaired_raw)
    except Exception as repair_exc:
        logger.error(
            "项目 %s 蓝图 JSON 自动修复失败: first_error=%s repair_error=%s\n修复输入片段: %s",
            project_id,
            parse_error,
            repair_exc,
            blueprint_raw[:500],
        )
        raise HTTPException(
            status_code=500,
            detail=f"蓝图生成失败，AI 返回的内容格式不正确，自动修复也未成功。错误详情: {str(parse_error)}",
        ) from repair_exc


class StreamingJSONFieldExtractor:
    """从流式 JSON 文本中增量提取某个字符串字段。"""

    def __init__(self, field_name: str):
        self.field_name = field_name
        self._buffer = ""
        self._raw_value = ""
        self._decoded_value = ""
        self._scan_index = 0
        self._value_started = False
        self._value_complete = False
        self._escaping = False

    def feed(self, chunk: str) -> str:
        if self._value_complete or not chunk:
            return ""

        self._buffer += chunk
        if not self._value_started and not self._start_value_scan():
            return ""

        while self._scan_index < len(self._buffer):
            char = self._buffer[self._scan_index]
            self._scan_index += 1

            if self._escaping:
                self._raw_value += char
                self._escaping = False
                continue

            if char == "\\":
                self._raw_value += char
                self._escaping = True
                continue

            if char == '"':
                self._value_complete = True
                break

            self._raw_value += char

        return self._consume_decoded_delta()

    def _start_value_scan(self) -> bool:
        key = f'"{self.field_name}"'
        key_index = self._buffer.find(key)
        if key_index < 0:
            return False

        colon_index = self._buffer.find(":", key_index + len(key))
        if colon_index < 0:
            return False

        value_index = colon_index + 1
        while value_index < len(self._buffer) and self._buffer[value_index].isspace():
            value_index += 1
        if value_index >= len(self._buffer) or self._buffer[value_index] != '"':
            return False

        self._scan_index = value_index + 1
        self._value_started = True
        return True

    def _consume_decoded_delta(self) -> str:
        try:
            decoded = json.loads(f'"{self._raw_value}"')
        except json.JSONDecodeError:
            return ""

        delta = decoded[len(self._decoded_value) :]
        self._decoded_value = decoded
        return delta


def _sse_event(event: str, payload: Dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _sse_response(stream: AsyncGenerator[str, None]) -> StreamingResponse:
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("", response_model=NovelProjectSchema, status_code=status.HTTP_201_CREATED)
async def create_novel(
    title: str = Body(...),
    initial_prompt: str = Body(...),
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    """为当前用户创建一个新的小说项目。"""
    novel_service = NovelService(session)
    project_status = "draft"
    if novel_service.is_inspiration_seed(title, initial_prompt):
        existing_project = await novel_service.find_unfinished_inspiration_project(current_user.id)
        if existing_project:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "unfinished_inspiration",
                    "message": "已有未完成的灵感对话，请先继续完成并保存蓝图。",
                    "project_id": existing_project.id,
                },
            )
        project_status = novel_service.INSPIRATION_ACTIVE_STATUS

    project = await novel_service.create_project(
        current_user.id, title, initial_prompt, status=project_status
    )
    logger.info("用户 %s 创建项目 %s", current_user.id, project.id)
    return await novel_service.get_project_schema(project.id, current_user.id)


@router.post("/import", response_model=Dict[str, str], status_code=status.HTTP_201_CREATED)
async def import_novel(
    file: UploadFile,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> Dict[str, str]:
    """上传并导入小说文件。"""
    import_service = ImportService(session)
    project_id = await import_service.import_novel_from_file(current_user.id, file)
    logger.info("用户 %s 导入项目 %s", current_user.id, project_id)
    return {"id": project_id}


@router.get("", response_model=List[NovelProjectSummary])
async def list_novels(
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> List[NovelProjectSummary]:
    """列出用户的全部小说项目摘要信息。"""
    novel_service = NovelService(session)
    projects = await novel_service.list_projects_for_user(current_user.id)
    logger.info("用户 %s 获取项目列表，共 %s 个", current_user.id, len(projects))
    return projects


@router.get("/{project_id}", response_model=NovelProjectSchema)
async def get_novel(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    logger.info("用户 %s 查询项目 %s", current_user.id, project_id)
    return await novel_service.get_project_schema(project_id, current_user.id)


@router.get("/{project_id}/sections/{section}", response_model=NovelSectionResponse)
async def get_novel_section(
    project_id: str,
    section: NovelSectionType,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelSectionResponse:
    novel_service = NovelService(session)
    logger.info("用户 %s 获取项目 %s 的 %s 区段", current_user.id, project_id, section)
    return await novel_service.get_section_data(project_id, current_user.id, section)


@router.get("/{project_id}/chapters/{chapter_number}", response_model=ChapterSchema)
async def get_chapter(
    project_id: str,
    chapter_number: int,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> ChapterSchema:
    novel_service = NovelService(session)
    logger.info("用户 %s 获取项目 %s 第 %s 章", current_user.id, project_id, chapter_number)
    return await novel_service.get_chapter_schema(project_id, current_user.id, chapter_number)


@router.get("/{project_id}/chapters/{chapter_number}/events")
async def stream_chapter_status(
    project_id: str,
    chapter_number: int,
    request: Request,
    wait_for_active: bool = Query(default=False),
    current_user: UserInDB = Depends(get_current_user),
) -> StreamingResponse:
    """推送单章生成状态，事件驱动（Redis pub-sub），替代前端定时轮询章节接口。"""

    active_statuses = {"generating", "evaluating", "selecting", "finalizing"}
    terminal_statuses = {"waiting_for_confirm", "successful", "failed", "evaluation_failed"}

    async def fetch_payload() -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """查 DB 取章节快照，返回 (payload, error_event)；成功时 error_event 为 None。"""
        try:
            async with AsyncSessionLocal() as session:
                service = NovelService(session)
                chapter = await service.get_chapter_schema(
                    project_id, current_user.id, chapter_number
                )
            return chapter.model_dump(mode="json"), None
        except HTTPException as exc:
            return None, _sse_event("error", {"detail": str(exc.detail)})
        except Exception as exc:
            logger.exception(
                "章节状态 SSE 读取失败: project_id=%s chapter=%s user_id=%s",
                project_id,
                chapter_number,
                current_user.id,
            )
            return None, _sse_event("error", {"detail": f"章节状态同步失败: {str(exc)}"})

    async def event_stream() -> AsyncGenerator[str, None]:
        last_payload: str | None = None
        has_seen_active_status = False

        def build_event(payload: Dict[str, Any]) -> Tuple[Optional[str], bool]:
            """JSON 快照去重后构造 SSE 事件，返回 (事件文本, 是否终态)；无变化返回 (None, False)。"""
            nonlocal last_payload, has_seen_active_status
            payload_text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
            status_value = payload.get("generation_status")
            if status_value in active_statuses:
                has_seen_active_status = True
            if payload_text == last_payload:
                return None, False
            can_close_as_final = status_value in terminal_statuses and (
                not wait_for_active or has_seen_active_status
            )
            event_name = "final" if can_close_as_final else "chapter"
            last_payload = payload_text
            return _sse_event(event_name, payload), can_close_as_final

        async def poll_loop() -> AsyncGenerator[str, None]:
            """降级轮询：Redis 不可用时每 5s 查 DB 推送，终态或错误时停止。"""
            while True:
                if await request.is_disconnected():
                    return
                await asyncio.sleep(5.0)
                payload, error_event = await fetch_payload()
                if error_event is not None:
                    yield error_event
                    return
                event, is_final = build_event(payload)
                if event is not None:
                    yield event
                    if is_final:
                        return

        # 1. 初始态：subscribe 前先查 DB 发一次快照，覆盖订阅前已发生的状态变更。
        payload, error_event = await fetch_payload()
        if error_event is not None:
            yield error_event
            return
        event, is_final = build_event(payload)
        if event is not None:
            yield event
            if is_final:
                return

        # 2. 订阅 Redis pub-sub channel；不可用回退轮询。
        pubsub = await subscribe_chapter_status(project_id, chapter_number)
        if pubsub is None:
            async for evt in poll_loop():
                yield evt
            return

        # 3. 事件驱动：收到状态变更通知即查 DB 推送，终态后关闭。
        #    运行中 Redis 断连时 get_message 抛异常，回退轮询避免连接抖动。
        redis_disconnected = False
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                except Exception:
                    logger.warning(
                        "章节状态 SSE pubsub 读取异常，回退轮询: project_id=%s chapter=%s",
                        project_id,
                        chapter_number,
                    )
                    redis_disconnected = True
                    break
                if message is None:
                    continue
                payload, error_event = await fetch_payload()
                if error_event is not None:
                    yield error_event
                    break
                event, is_final = build_event(payload)
                if event is not None:
                    yield event
                    if is_final:
                        break
        finally:
            try:
                await pubsub.aclose()
            except Exception:
                pass

        # 4. 事件驱动因 Redis 断连退出且未到终态：回退轮询。
        if redis_disconnected:
            async for evt in poll_loop():
                yield evt

    return _sse_response(event_stream())


@router.delete("", status_code=status.HTTP_200_OK)
async def delete_novels(
    project_ids: List[str] = Body(...),
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> Dict[str, str]:
    novel_service = NovelService(session)
    await novel_service.delete_projects(project_ids, current_user.id)
    logger.info("用户 %s 删除项目 %s", current_user.id, project_ids)
    return {"status": "success", "message": f"成功删除 {len(project_ids)} 个项目"}


@router.post("/{project_id}/concept/converse", response_model=ConverseResponse)
async def converse_with_concept(
    project_id: str,
    request: ConverseRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> ConverseResponse:
    """与概念设计师（LLM）进行对话，引导蓝图筹备。"""
    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)

    history_records = await novel_service.list_conversations(project_id)
    logger.info(
        "项目 %s 概念对话请求，用户 %s，历史记录 %s 条",
        project_id,
        current_user.id,
        len(history_records),
    )
    conversation_history = [
        {"role": record.role, "content": record.content} for record in history_records
    ]
    user_content = json.dumps(request.user_input, ensure_ascii=False)
    conversation_history.append({"role": "user", "content": user_content})

    system_prompt = _ensure_prompt(await prompt_service.get_prompt("concept"), "concept")
    system_prompt = f"{system_prompt}\n{JSON_RESPONSE_INSTRUCTION}"

    llm_response = await llm_service.get_llm_response(
        system_prompt=system_prompt,
        conversation_history=conversation_history,
        temperature=0.8,
        user_id=current_user.id,
        timeout=240.0,
        stage="concept_conversation",
    )
    llm_response = remove_think_tags(llm_response)

    try:
        normalized = unwrap_markdown_json(llm_response)
        sanitized = sanitize_json_like_text(normalized)
        parsed = json.loads(sanitized)
    except json.JSONDecodeError as exc:
        logger.exception(
            "Failed to parse concept converse response: project_id=%s user_id=%s error=%s\nOriginal response: %s\nNormalized: %s\nSanitized: %s",
            project_id,
            current_user.id,
            exc,
            llm_response[:1000],
            normalized[:1000] if "normalized" in locals() else "N/A",
            sanitized[:1000] if "sanitized" in locals() else "N/A",
        )
        raise HTTPException(
            status_code=500,
            detail=f"概念对话失败，AI 返回的内容格式不正确。请重试或联系管理员。错误详情: {str(exc)}",
        ) from exc

    await novel_service.append_conversation(project_id, "user", user_content)
    await novel_service.append_conversation(project_id, "assistant", normalized)

    logger.info("项目 %s 概念对话完成，is_complete=%s", project_id, parsed.get("is_complete"))

    if parsed.get("is_complete"):
        parsed["ready_for_blueprint"] = True

    parsed.setdefault("conversation_state", parsed.get("conversation_state", {}))
    return ConverseResponse(**parsed)


@router.post("/{project_id}/concept/converse/stream")
async def converse_with_concept_stream(
    project_id: str,
    request: ConverseRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> StreamingResponse:
    """与概念设计师进行流式对话，边生成边返回 ai_message。"""
    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    history_records = await novel_service.list_conversations(project_id)
    logger.info(
        "项目 %s 流式概念对话请求，用户 %s，历史记录 %s 条",
        project.id,
        current_user.id,
        len(history_records),
    )

    conversation_history = [
        {"role": record.role, "content": record.content} for record in history_records
    ]
    user_content = json.dumps(request.user_input, ensure_ascii=False)
    conversation_history.append({"role": "user", "content": user_content})

    system_prompt = _ensure_prompt(await prompt_service.get_prompt("concept"), "concept")
    system_prompt = f"{system_prompt}\n{JSON_RESPONSE_INSTRUCTION}"

    async def event_stream() -> AsyncGenerator[str, None]:
        raw_response = ""
        extractor = StreamingJSONFieldExtractor("ai_message")

        try:
            async for chunk in llm_service.stream_llm_response(
                system_prompt=system_prompt,
                conversation_history=conversation_history,
                temperature=0.8,
                user_id=current_user.id,
                timeout=240.0,
                stage="concept_conversation",
            ):
                raw_response += chunk
                delta = extractor.feed(chunk)
                if delta:
                    yield _sse_event("delta", {"delta": delta})

            llm_response = remove_think_tags(raw_response)
            normalized = unwrap_markdown_json(llm_response)
            sanitized = sanitize_json_like_text(normalized)
            parsed = json.loads(sanitized)

            await novel_service.append_conversation(project_id, "user", user_content)
            await novel_service.append_conversation(project_id, "assistant", normalized)

            logger.info(
                "项目 %s 流式概念对话完成，is_complete=%s", project_id, parsed.get("is_complete")
            )

            if parsed.get("is_complete"):
                parsed["ready_for_blueprint"] = True
            parsed.setdefault("conversation_state", parsed.get("conversation_state", {}))

            response = ConverseResponse(**parsed)
            yield _sse_event("final", response.model_dump())
        except json.JSONDecodeError as exc:
            logger.exception(
                "Failed to parse streaming concept response: project_id=%s user_id=%s error=%s raw=%s",
                project_id,
                current_user.id,
                exc,
                raw_response[:1000],
            )
            yield _sse_event(
                "error",
                {"detail": f"概念对话失败，AI 返回的内容格式不正确。错误详情: {str(exc)}"},
            )
        except HTTPException as exc:
            yield _sse_event("error", {"detail": str(exc.detail)})
        except Exception as exc:
            logger.exception(
                "流式概念对话失败: project_id=%s user_id=%s", project_id, current_user.id
            )
            yield _sse_event(
                "error",
                {"detail": f"概念对话失败: {str(exc)}"},
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{project_id}/blueprint/generate", response_model=BlueprintGenerationResponse)
async def generate_blueprint(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> BlueprintGenerationResponse:
    """根据完整对话生成可执行的小说蓝图。"""
    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    logger.info("项目 %s 开始生成蓝图", project_id)

    history_records = await novel_service.list_conversations(project_id)
    if not history_records:
        logger.warning("项目 %s 缺少对话历史，无法生成蓝图", project_id)
        raise HTTPException(status_code=400, detail="缺少对话历史，请先完成概念对话后再生成蓝图")

    formatted_history: List[Dict[str, str]] = []
    for record in history_records:
        role = record.role
        content = record.content
        if not role or not content:
            continue
        try:
            normalized = unwrap_markdown_json(content)
            data = json.loads(normalized)
            if role == "user":
                user_value = data.get("value", data)
                if isinstance(user_value, str):
                    formatted_history.append({"role": "user", "content": user_value})
            elif role == "assistant":
                ai_message = data.get("ai_message") if isinstance(data, dict) else None
                if ai_message:
                    formatted_history.append({"role": "assistant", "content": ai_message})
        except (json.JSONDecodeError, AttributeError):
            continue

    if not formatted_history:
        logger.warning("项目 %s 对话历史格式异常，无法提取有效内容", project_id)
        raise HTTPException(
            status_code=400,
            detail="无法从历史对话中提取有效内容，请检查对话历史格式或重新进行概念对话",
        )

    system_prompt = _ensure_prompt(
        await prompt_service.get_prompt("screenwriting"), "screenwriting"
    )
    blueprint_raw = await llm_service.get_llm_response(
        system_prompt=system_prompt,
        conversation_history=formatted_history,
        temperature=0.3,
        user_id=current_user.id,
        timeout=480.0,
        stage="world_blueprint",
    )
    blueprint_raw = remove_think_tags(blueprint_raw)

    blueprint_data = await _parse_blueprint_json_with_repair(
        project_id=project_id,
        user_id=current_user.id,
        llm_service=llm_service,
        prompt_service=prompt_service,
        blueprint_raw=blueprint_raw,
    )

    blueprint = Blueprint(**blueprint_data)
    is_inspiration_flow = novel_service.is_unfinished_inspiration_project(project)
    await novel_service.replace_blueprint(project_id, blueprint)
    if blueprint.title and not is_inspiration_flow:
        project.title = blueprint.title
    project.status = (
        novel_service.INSPIRATION_BLUEPRINT_GENERATED_STATUS
        if is_inspiration_flow
        else novel_service.INSPIRATION_COMPLETE_STATUS
    )
    await session.commit()
    logger.info("项目 %s 更新标题为 %s，并标记为 %s", project_id, blueprint.title, project.status)

    ai_message = (
        "太棒了！我已经根据我们的对话整理出完整的小说蓝图。请确认是否进入写作阶段，或提出修改意见。"
    )
    return BlueprintGenerationResponse(blueprint=blueprint, ai_message=ai_message)


@router.post("/{project_id}/blueprint/save", response_model=NovelProjectSchema)
async def save_blueprint(
    project_id: str,
    blueprint_data: Blueprint | None = Body(None),
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    """保存蓝图信息，可用于手动覆盖自动生成结果。"""
    novel_service = NovelService(session)
    project = await novel_service.ensure_project_owner(project_id, current_user.id)

    if blueprint_data:
        await novel_service.replace_blueprint(project_id, blueprint_data)
        if blueprint_data.title:
            project.title = blueprint_data.title
        project.status = novel_service.INSPIRATION_COMPLETE_STATUS
        await session.commit()
        logger.info("项目 %s 手动保存蓝图", project_id)
    else:
        logger.warning("项目 %s 保存蓝图时未提供蓝图数据", project_id)
        raise HTTPException(status_code=400, detail="缺少蓝图数据，请提供有效的蓝图内容")

    return await novel_service.get_project_schema(project_id, current_user.id)


@router.patch("/{project_id}/blueprint", response_model=NovelProjectSchema)
async def patch_blueprint(
    project_id: str,
    payload: BlueprintPatch,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    """局部更新蓝图字段，对世界观或角色做微调。"""
    novel_service = NovelService(session)
    project = await novel_service.ensure_project_owner(project_id, current_user.id)

    update_data = payload.model_dump(exclude_unset=True)
    await novel_service.patch_blueprint(project_id, update_data)
    logger.info("项目 %s 局部更新蓝图字段：%s", project_id, list(update_data.keys()))
    return await novel_service.get_project_schema(project_id, current_user.id)
