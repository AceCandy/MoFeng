# AIMETA P=写作API_章节生成和大纲创建|R=章节生成_大纲生成_评审_L2导演脚本_护栏检查|NR=不含数据存储|E=route:POST_/api/writer/*|X=http|A=生成_评审_过滤|D=fastapi,openai|S=net,db|RD=./README.ai
"""
Writer API Router - 人类化起点长篇写作系统

核心架构：
- L1 Planner：全知规划层（蓝图/大纲）
- L2 Director：章节导演脚本（ChapterMission）
- L3 Writer：有限视角正文生成

关键改进：
1. 信息可见性过滤：L3 Writer 只能看到已登场角色
2. 跨章 1234 逻辑：通过 ChapterMission 控制每章只写一个节拍
3. 后置护栏检查：自动检测并修复违规内容
"""
import asyncio
import json
import logging
import re
from typing import Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ...core.config import settings
from ...core.dependencies import get_current_user
from ...db.session import AsyncSessionLocal, get_session
from ...models.chapter_blueprint import ChapterBlueprint
from ...models.constitution import NovelConstitution
from ...models.foreshadowing import Foreshadowing, ForeshadowingStatusHistory
from ...models.novel import Chapter, ChapterOutline, ChapterVersion
from ...models.project_memory import ProjectMemory
from ...models.writer_persona import WriterPersona
from ...schemas.novel import (
    Chapter as ChapterSchema,
    ChapterGenerationStatus,
    AdvancedGenerateRequest,
    AdvancedGenerateResponse,
    DeleteChapterRequest,
    EditChapterRequest,
    EvaluateChapterRequest,
    FinalizeChapterRequest,
    FinalizeChapterResponse,
    GenerateChapterRequest,
    GenerateOutlineRequest,
    NovelProject as NovelProjectSchema,
    SelectVersionRequest,
    UpdateChapterOutlineRequest,
)
from ...schemas.task import BackgroundTaskResponse
from ...schemas.user import UserInDB
from ...services.background_task_service import BackgroundTaskService
from ...services.chapter_word_count_settings import count_chapter_words
from ...services.chapter_outline_task_runner import run_generate_chapters_outline_task
from ...services.chapter_ingest_service import ChapterIngestionService
from ...services.llm_service import LLMService
from ...services.novel_service import NovelService
from ...services.prompt_service import PromptService
from ...services.vector_store_service import VectorStoreService
from ...services.ai_review_service import AIReviewService
from ...services.finalize_service import FinalizeService
from ...services.review_context_builder import ReviewContextBuilder
from ...utils.json_utils import remove_think_tags, unwrap_markdown_json
from ...services.pipeline_orchestrator import PipelineOrchestrator

router = APIRouter(prefix="/api/writer", tags=["Writer"])
logger = logging.getLogger(__name__)
MAX_AUTO_FORESHADOWINGS_PER_CHAPTER = 3
LLM_FORESHADOWING_REVIEW_LIMIT = 8
LLM_FORESHADOWING_ACTIVE_LIMIT = 12

_FORESHADOWING_RULES = [
    {
        "type": "mystery",
        "importance": "major",
        "confidence": 0.76,
        "keywords": ["神秘", "秘密", "真相", "谜团", "身份", "来历", "幕后", "蹊跷", "古怪", "诡异", "不对劲"],
    },
    {
        "type": "question",
        "importance": "major",
        "confidence": 0.72,
        "keywords": ["为什么", "为何", "到底", "究竟", "不明白", "不知道", "怎么会", "何以", "难道"],
    },
    {
        "type": "clue",
        "importance": "minor",
        "confidence": 0.64,
        "keywords": ["线索", "可疑", "异常", "不寻常", "暗示", "蛛丝马迹", "痕迹"],
    },
    {
        "type": "setup",
        "importance": "minor",
        "confidence": 0.61,
        "keywords": ["将来", "日后", "以后", "将会", "埋下", "伏笔", "悬念", "预感", "迟早", "终有一天"],
    },
]
_PAYOFF_MARKERS = ["原来", "真相", "答案", "揭晓", "揭开", "终于明白", "其实", "果然", "解释了", "应验"]
_REINFORCE_MARKERS = ["再次", "又", "仍", "依旧", "继续", "再度", "回想", "提到", "印证"]
_QUESTION_CUES = ["为什么", "为何", "到底", "究竟", "怎么会", "何以", "难道", "是谁", "是什么", "怎么", "吗"]
_TYPE_LIMITS = {"question": 2, "mystery": 2, "clue": 1, "setup": 1}
_MYSTERY_STRONG_CUES = {"秘密", "真相", "谜团", "身份", "来历", "幕后"}
_KEYWORD_STOPWORDS = {
    "这个", "那个", "一些", "一种", "已经", "还是", "就是", "如果", "但是", "因为",
    "他们", "我们", "你们", "自己", "事情", "时候", "没有", "不会", "不能", "然后",
    "以及", "为了", "这里", "那里", "这样", "那样", "非常", "特别", "可能", "突然",
}


async def _load_project_schema(service: NovelService, project_id: str, user_id: int) -> NovelProjectSchema:
    return await service.get_project_schema(project_id, user_id)


def _build_generation_failure_detail(exc: Exception, max_length: int = 300) -> str:
    """保留章节生成失败根因，同时避免把敏感配置原样回传给前端。"""
    raw_detail = str(exc).strip() or exc.__class__.__name__
    normalized = re.sub(r"\s+", " ", raw_detail).strip()
    if not normalized:
        return "生成章节失败：未收到具体错误信息，请查看后端日志。"

    redacted = re.sub(
        r"(?i)\b(api[_-]?key|authorization|bearer|token|secret|password)\b(\s*[=:]\s*)([^,\s;]+)",
        r"\1\2[已隐藏]",
        normalized,
    )
    if len(redacted) > max_length:
        redacted = redacted[:max_length].rstrip() + "..."

    if redacted.startswith("生成章节失败"):
        return redacted
    return f"生成章节失败：{redacted}"


def _extract_tail_excerpt(text: Optional[str], limit: int = 500) -> str:
    """截取章节结尾文本，默认保留 500 字。"""
    if not text:
        return ""
    stripped = text.strip()
    if len(stripped) <= limit:
        return stripped
    return stripped[-limit:]

async def _build_review_context(
    *,
    session: AsyncSession,
    novel_service: NovelService,
    project,
    project_id: str,
    chapter_number: int,
    user_id: int,
    chapter_mission: Optional[dict] = None,
    chapter_content: Optional[str] = None,
) -> Dict[str, object]:
    blueprint_schema = novel_service._build_blueprint_schema(project)
    outline = await novel_service.get_outline(project_id, chapter_number)

    chapters = sorted(project.chapters or [], key=lambda item: item.chapter_number)
    completed_chapters = []
    previous_summary = "暂无（这是第一章）"
    previous_tail = "暂无（这是第一章）"
    latest_previous_number = -1

    outline_map = {item.chapter_number: item for item in (project.outlines or [])}
    for existing in chapters:
        if existing.chapter_number >= chapter_number:
            continue
        selected_version = existing.selected_version
        if not selected_version or not selected_version.content:
            continue

        summary = existing.real_summary or ""
        existing_outline = outline_map.get(existing.chapter_number)
        completed_chapters.append(
            {
                "chapter_number": existing.chapter_number,
                "title": existing_outline.title if existing_outline and existing_outline.title else f"第{existing.chapter_number}章",
                "summary": summary,
            }
        )

        if existing.chapter_number > latest_previous_number:
            latest_previous_number = existing.chapter_number
            previous_summary = summary or "暂无（这是第一章）"
            previous_tail = _extract_tail_excerpt(selected_version.content) or "暂无（这是第一章）"

    chapter_blueprint_stmt = select(ChapterBlueprint).where(
        ChapterBlueprint.project_id == project_id,
        ChapterBlueprint.chapter_number == chapter_number,
    )
    constitution_stmt = select(NovelConstitution).where(NovelConstitution.project_id == project_id)
    project_memory_stmt = select(ProjectMemory).where(ProjectMemory.project_id == project_id)
    writer_persona_stmt = (
        select(WriterPersona)
        .where(WriterPersona.project_id == project_id, WriterPersona.is_active.is_(True))
        .limit(1)
    )

    chapter_blueprint = (await session.execute(chapter_blueprint_stmt)).scalars().first()
    constitution = (await session.execute(constitution_stmt)).scalars().first()
    project_memory = (await session.execute(project_memory_stmt)).scalars().first()
    writer_persona = (await session.execute(writer_persona_stmt)).scalars().first()

    chapter_blueprint_payload = {}
    if chapter_blueprint:
        chapter_blueprint_payload = {
            "chapter_function": chapter_blueprint.chapter_function,
            "chapter_focus": chapter_blueprint.chapter_focus,
            "suspense_type": chapter_blueprint.suspense_type,
            "emotional_arc": chapter_blueprint.emotional_arc,
            "mission_constraints": chapter_blueprint.mission_constraints or {},
            "brief_summary": chapter_blueprint.brief_summary or "",
            "director_script": chapter_blueprint.director_script or "",
            "beat_sheet": chapter_blueprint.beat_sheet or {},
        }

    project_memory_payload = {}
    if project_memory:
        project_memory_payload = {
            "global_summary": project_memory.global_summary or "",
            "plot_arcs": project_memory.plot_arcs or {},
            "story_timeline_summary": project_memory.story_timeline_summary or "",
            "last_updated_chapter": project_memory.last_updated_chapter,
        }

    chapter_outline_payload = {
        "chapter_number": chapter_number,
        "title": outline.title if outline else f"第{chapter_number}章",
        "summary": outline.summary if outline else "",
        "metadata": outline.metadata if outline and outline.metadata else {},
    }

    base_context = {
        "novel_blueprint": blueprint_schema.model_dump(),
        "chapter_outline": chapter_outline_payload,
        "chapter_blueprint": chapter_blueprint_payload,
        "chapter_mission": chapter_mission or {},
        "project_memory": project_memory_payload,
        "constitution": constitution.to_prompt_context() if constitution else "",
        "writer_persona": writer_persona.to_prompt_context() if writer_persona else "",
        "previous_chapter": {
            "summary": previous_summary,
            "tail_excerpt": previous_tail,
        },
        "completed_chapters": completed_chapters,
    }

    # 使用 ReviewContextBuilder 增强上下文
    try:
        vector_store = VectorStoreService()
        llm_service = LLMService(session)
        context_builder = ReviewContextBuilder(session, vector_store, llm_service)
        enhanced_context = await context_builder.build_review_context(
            project_id=project_id,
            chapter_number=chapter_number,
            user_id=user_id,
            chapter_content=chapter_content,
            base_context=base_context,
        )
        return enhanced_context
    except Exception:
        logger.exception("构建增强评审上下文失败，使用基础上下文")
        return base_context


def _normalize_snippet(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    return normalized.strip("，。！？!?；;：:、 ")


def _extract_keyword_anchors(text: str, max_count: int = 8) -> List[str]:
    """从中文文本中提取可用于匹配的锚词。"""
    anchors: List[str] = []
    seen = set()
    for token in re.findall(r"[\u4e00-\u9fff]{2,6}", text):
        if token in _KEYWORD_STOPWORDS:
            continue
        if token in seen:
            continue
        seen.add(token)
        anchors.append(token)
        if len(anchors) >= max_count:
            break
    return anchors


def _build_auto_foreshadowing_name(content: str, foreshadowing_type: str) -> str:
    anchors = _extract_keyword_anchors(content, max_count=2)
    if anchors:
        return f"{foreshadowing_type}:{'·'.join(anchors)}"
    return f"{foreshadowing_type}:第1线索"


def _split_candidate_sentences(text: str) -> List[str]:
    """按句切分候选文本，避免同一段被多次窗口截断命中。"""
    raw_sentences = re.findall(r"[^。！？!?;\n]{6,120}[。！？!?;]?", text)
    sentences: List[str] = []
    for raw in raw_sentences:
        sentence = re.sub(r"\s+", " ", raw).strip()
        if 10 <= len(sentence) <= 90:
            sentences.append(sentence)
    return sentences


def _extract_foreshadowing_candidates(content: str) -> List[dict]:
    """
    从章节内容提取自动伏笔候选（精度优先规则）。
    返回字段：content/type/keywords/importance/confidence。
    """
    normalized_content = re.sub(r"\s+", " ", content or "").strip()
    if not normalized_content:
        return []

    candidates: List[dict] = []
    seen_snippets = set()
    type_counter = {key: 0 for key in _TYPE_LIMITS}
    sentences = _split_candidate_sentences(normalized_content)
    if not sentences:
        return []

    def add_candidate(snippet: str, foreshadowing_type: str, confidence: float, importance: str, keywords: List[str]) -> None:
        if type_counter.get(foreshadowing_type, 0) >= _TYPE_LIMITS.get(foreshadowing_type, 1):
            return
        normalized_snippet = _normalize_snippet(snippet)
        if len(normalized_snippet) < 10:
            return
        dedupe_key = normalized_snippet[:120]
        if dedupe_key in seen_snippets:
            return
        seen_snippets.add(dedupe_key)
        merged_keywords = keywords[:] if keywords else []
        if not merged_keywords:
            merged_keywords = _extract_keyword_anchors(normalized_snippet, max_count=6)
        candidates.append(
            {
                "content": normalized_snippet,
                "type": foreshadowing_type,
                "keywords": merged_keywords,
                "importance": importance,
                "confidence": confidence,
            }
        )
        type_counter[foreshadowing_type] = type_counter.get(foreshadowing_type, 0) + 1

    # 1) 问题型伏笔：有问句结构且包含关键疑问词
    for sentence in sentences:
        has_question_mark = ("？" in sentence or "?" in sentence)
        cue_hits = [kw for kw in _QUESTION_CUES if kw in sentence]
        if has_question_mark and cue_hits:
            add_candidate(sentence, "question", 0.74, "major", cue_hits[:3])
        if len(candidates) >= LLM_FORESHADOWING_REVIEW_LIMIT:
            return candidates[:LLM_FORESHADOWING_REVIEW_LIMIT]

    # 2) 神秘/线索/铺垫：按句匹配，不再整段窗口切割，减少重叠噪声
    for sentence in sentences:
        for rule in _FORESHADOWING_RULES:
            if rule["type"] == "question":
                continue
            matched_keywords = [keyword for keyword in rule["keywords"] if keyword in sentence]
            if not matched_keywords:
                continue
            # mystery 需要更强触发：
            # - 至少 1 个强线索词 + 至少 2 个命中词；或
            # - 问句结构 + 至少 1 个强线索词。
            if rule["type"] == "mystery":
                strong_hits = [kw for kw in matched_keywords if kw in _MYSTERY_STRONG_CUES]
                has_question_structure = ("？" in sentence or "?" in sentence) and any(cue in sentence for cue in _QUESTION_CUES)
                if not ((len(strong_hits) >= 1 and len(matched_keywords) >= 2) or (has_question_structure and len(strong_hits) >= 1)):
                    continue
            # clue/setup 至少要求 2 个锚词，或一个强触发词（线索/伏笔/悬念）
            if rule["type"] in ("clue", "setup"):
                strong_markers = {"线索", "伏笔", "悬念"}
                if len(matched_keywords) < 2 and not any(marker in matched_keywords for marker in strong_markers):
                    continue
            add_candidate(
                sentence,
                rule["type"],
                rule["confidence"],
                rule["importance"],
                matched_keywords[:4],
            )
            if len(candidates) >= LLM_FORESHADOWING_REVIEW_LIMIT:
                return candidates[:LLM_FORESHADOWING_REVIEW_LIMIT]

    return candidates[:LLM_FORESHADOWING_REVIEW_LIMIT]


async def _refine_foreshadowing_candidates_with_llm(
    session: AsyncSession,
    *,
    user_id: Optional[int],
    chapter_number: int,
    content: str,
    candidates: List[dict],
) -> List[dict]:
    if not candidates:
        return []

    limited_candidates = candidates[:LLM_FORESHADOWING_REVIEW_LIMIT]
    candidate_payload = [
        {
            "id": idx,
            "content": candidate["content"],
            "type": candidate["type"],
            "keywords": candidate.get("keywords") or [],
            "importance": candidate.get("importance") or "minor",
            "confidence": candidate.get("confidence") or 0.5,
        }
        for idx, candidate in enumerate(limited_candidates)
    ]
    try:
        system_prompt = await PromptService(session).get_prompt("foreshadowing_candidate_review")
        if not system_prompt:
            raise RuntimeError("缺少提示词配置: foreshadowing_candidate_review")
        prompt = json.dumps(
            {
                "chapter_number": chapter_number,
                "max_items": MAX_AUTO_FORESHADOWINGS_PER_CHAPTER,
                "candidates": candidate_payload,
                "content_excerpt": content[:4000],
            },
            ensure_ascii=False,
        )
        response = await LLMService(session).get_llm_response(
            system_prompt=system_prompt,
            conversation_history=[{"role": "user", "content": prompt}],
            temperature=0.1,
            user_id=user_id,
            timeout=90.0,
            response_format="json_object",
            max_tokens=1200,
            stage="foreshadowing",
        )
        normalized = unwrap_markdown_json(remove_think_tags(response))
        data = json.loads(normalized)
    except Exception as exc:
        logger.warning(
            "LLM 伏笔候选精筛失败，使用规则候选 project_chapter=%s user_id=%s err=%s",
            chapter_number,
            user_id,
            exc,
        )
        return candidates[:MAX_AUTO_FORESHADOWINGS_PER_CHAPTER]

    raw_items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(raw_items, list):
        return candidates[:MAX_AUTO_FORESHADOWINGS_PER_CHAPTER]

    refined: List[dict] = []
    seen_ids = set()
    allowed_types = {"mystery", "question", "clue", "setup"}
    allowed_importance = {"major", "minor", "subtle"}
    for item in raw_items:
        if not isinstance(item, dict) or not item.get("keep"):
            continue
        item_id = item.get("id")
        if not isinstance(item_id, int) or item_id in seen_ids or item_id < 0 or item_id >= len(limited_candidates):
            continue
        seen_ids.add(item_id)
        source = limited_candidates[item_id]
        keywords = [
            keyword.strip()
            for keyword in item.get("keywords", [])
            if isinstance(keyword, str) and 2 <= len(keyword.strip()) <= 8
        ][:5]
        if not keywords:
            keywords = source.get("keywords") or _extract_keyword_anchors(source["content"], max_count=5)
        confidence = item.get("confidence")
        if not isinstance(confidence, (int, float)):
            confidence = source.get("confidence") or 0.5
        refined.append(
            {
                "content": source["content"],
                "type": item.get("type") if item.get("type") in allowed_types else source["type"],
                "keywords": keywords,
                "importance": item.get("importance") if item.get("importance") in allowed_importance else source.get("importance", "minor"),
                "confidence": max(0.0, min(1.0, float(confidence))),
            }
        )
        if len(refined) >= MAX_AUTO_FORESHADOWINGS_PER_CHAPTER:
            break

    return refined


async def _judge_foreshadowing_status_with_llm(
    session: AsyncSession,
    *,
    user_id: Optional[int],
    chapter_number: int,
    content: str,
    foreshadowings: List[Foreshadowing],
) -> Dict[int, str]:
    if not foreshadowings:
        return {}

    payload = []
    for fs in foreshadowings[:LLM_FORESHADOWING_ACTIVE_LIMIT]:
        payload.append(
            {
                "id": fs.id,
                "status": fs.status,
                "content": fs.content,
                "keywords": fs.keywords or [],
            }
        )
    try:
        system_prompt = await PromptService(session).get_prompt("foreshadowing_status_judge")
        if not system_prompt:
            raise RuntimeError("缺少提示词配置: foreshadowing_status_judge")
        prompt = json.dumps(
            {
                "chapter_number": chapter_number,
                "content_excerpt": content[:5000],
                "foreshadowings": payload,
            },
            ensure_ascii=False,
        )
        response = await LLMService(session).get_llm_response(
            system_prompt=system_prompt,
            conversation_history=[{"role": "user", "content": prompt}],
            temperature=0.1,
            user_id=user_id,
            timeout=90.0,
            response_format="json_object",
            max_tokens=1200,
            stage="foreshadowing",
        )
        normalized = unwrap_markdown_json(remove_think_tags(response))
        data = json.loads(normalized)
    except Exception as exc:
        logger.warning(
            "LLM 伏笔状态判定失败，使用规则状态 project_chapter=%s user_id=%s err=%s",
            chapter_number,
            user_id,
            exc,
        )
        return {}

    raw_items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(raw_items, list):
        return {}

    allowed_statuses = {"revealed", "developing", "unchanged"}
    result: Dict[int, str] = {}
    valid_ids = {fs.id for fs in foreshadowings}
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        item_id = item.get("id")
        status = item.get("status")
        if isinstance(item_id, int) and item_id in valid_ids and status in allowed_statuses:
            result[item_id] = status
    return result


def _contains_any(text: str, needles: List[str]) -> bool:
    return any(needle and needle in text for needle in needles)


def _is_payoff_signal(content: str, anchors: List[str]) -> bool:
    if not _contains_any(content, _PAYOFF_MARKERS):
        return False
    if anchors and _contains_any(content, anchors):
        return True
    return False


def _is_reinforce_signal(content: str, anchors: List[str]) -> bool:
    if anchors and _contains_any(content, anchors):
        return True
    if _contains_any(content, _REINFORCE_MARKERS):
        return True
    return False


async def _sync_foreshadowings_for_chapter(
    session: AsyncSession,
    *,
    project_id: str,
    chapter: Chapter,
    content: str,
    user_id: Optional[int] = None,
) -> dict:
    """
    将定稿章节内容同步到 foreshadowings 表：
    1) 重建当前章节的自动伏笔（is_manual=False）
    2) 推进历史活跃伏笔状态（planted/developing/partial -> developing/revealed）
    """
    normalized_content = (content or "").strip()

    candidates: List[dict] = []
    active_foreshadowings: List[Foreshadowing] = []
    status_decisions: Dict[int, str] = {}

    if normalized_content:
        candidates = _extract_foreshadowing_candidates(normalized_content)
        candidates = await _refine_foreshadowing_candidates_with_llm(
            session,
            user_id=user_id,
            chapter_number=chapter.chapter_number,
            content=normalized_content,
            candidates=candidates,
        )

        active_result = await session.execute(
            select(Foreshadowing).where(
                Foreshadowing.project_id == project_id,
                Foreshadowing.chapter_number < chapter.chapter_number,
                Foreshadowing.status.in_(["planted", "developing", "partial"]),
            )
        )
        active_foreshadowings = active_result.scalars().all()
        status_decisions = await _judge_foreshadowing_status_with_llm(
            session,
            user_id=user_id,
            chapter_number=chapter.chapter_number,
            content=normalized_content,
            foreshadowings=active_foreshadowings,
        )

    await session.execute(
        delete(Foreshadowing).where(
            Foreshadowing.project_id == project_id,
            Foreshadowing.chapter_id == chapter.id,
            Foreshadowing.is_manual.is_(False),
        )
    )

    created_count = 0
    revealed_count = 0
    developing_count = 0

    if normalized_content:
        reveal_offset_by_importance = {"major": 8, "minor": 4, "subtle": 12}
        for candidate in candidates:
            target_offset = reveal_offset_by_importance.get(candidate["importance"], 6)
            foreshadowing = Foreshadowing(
                project_id=project_id,
                chapter_id=chapter.id,
                chapter_number=chapter.chapter_number,
                content=candidate["content"],
                type=candidate["type"],
                keywords=candidate["keywords"],
                status="planted",
                target_reveal_chapter=chapter.chapter_number + target_offset,
                name=_build_auto_foreshadowing_name(candidate["content"], candidate["type"]),
                importance=candidate["importance"],
                is_manual=False,
                ai_confidence=candidate["confidence"],
            )
            session.add(foreshadowing)
        created_count = len(candidates)

        for fs in active_foreshadowings:
            anchors = [kw for kw in (fs.keywords or []) if isinstance(kw, str) and len(kw) >= 2]
            if not anchors:
                anchors = _extract_keyword_anchors(fs.content, max_count=6)

            decision = status_decisions.get(fs.id)
            if decision is None:
                if _is_payoff_signal(normalized_content, anchors):
                    decision = "revealed"
                elif fs.status == "planted" and _is_reinforce_signal(normalized_content, anchors):
                    decision = "developing"
                else:
                    decision = "unchanged"

            if decision == "revealed":
                old_status = fs.status
                fs.status = "revealed"
                fs.resolved_chapter_id = chapter.id
                fs.resolved_chapter_number = chapter.chapter_number
                session.add(
                    ForeshadowingStatusHistory(
                        foreshadowing_id=fs.id,
                        old_status=old_status,
                        new_status="revealed",
                        chapter_number=chapter.chapter_number,
                        reason="语义判定本章已回收该伏笔",
                    )
                )
                revealed_count += 1
                continue

            if fs.status == "planted" and decision == "developing":
                fs.status = "developing"
                session.add(
                    ForeshadowingStatusHistory(
                        foreshadowing_id=fs.id,
                        old_status="planted",
                        new_status="developing",
                        chapter_number=chapter.chapter_number,
                        reason="语义判定本章继续推进该伏笔",
                    )
                )
                developing_count += 1

    await session.commit()
    return {
        "created": created_count,
        "revealed": revealed_count,
        "developing": developing_count,
    }


async def _sync_foreshadowings_after_finalize(
    project_id: str,
    chapter_number: int,
    content: str,
    user_id: Optional[int] = None,
) -> None:
    """后台任务：在章节定稿/手改后同步伏笔表。"""
    async with AsyncSessionLocal() as session:
        try:
            chapter_result = await session.execute(
                select(Chapter).where(
                    Chapter.project_id == project_id,
                    Chapter.chapter_number == chapter_number,
                )
            )
            chapter = chapter_result.scalars().first()
            if not chapter:
                logger.warning("伏笔同步跳过：章节不存在 project=%s chapter=%s", project_id, chapter_number)
                return

            stats = await _sync_foreshadowings_for_chapter(
                session,
                project_id=project_id,
                chapter=chapter,
                content=content,
                user_id=user_id,
            )
            logger.info(
                "伏笔同步完成 project=%s chapter=%s created=%s revealed=%s developing=%s",
                project_id,
                chapter_number,
                stats["created"],
                stats["revealed"],
                stats["developing"],
            )
        except Exception as exc:
            await session.rollback()
            logger.exception("伏笔同步失败 project=%s chapter=%s err=%s", project_id, chapter_number, exc)


async def _refresh_edit_summary_and_ingest(
    project_id: str,
    chapter_number: int,
    content: str,
    user_id: Optional[int],
) -> None:
    async with AsyncSessionLocal() as session:
        llm_service = LLMService(session)

        stmt = (
            select(Chapter)
            .options(selectinload(Chapter.selected_version))
            .where(
                Chapter.project_id == project_id,
                Chapter.chapter_number == chapter_number,
            )
        )
        result = await session.execute(stmt)
        chapter = result.scalars().first()
        if not chapter:
            return

        summary_text = None
        try:
            summary = await llm_service.get_summary(
                content,
                temperature=0.15,
                user_id=user_id,
                stage="summary_memory",
            )
            summary_text = remove_think_tags(summary)
        except Exception as exc:
            logger.warning("编辑章节后自动生成摘要失败: %s", exc)

        if summary_text and chapter.selected_version and chapter.selected_version.content == content:
            chapter.real_summary = summary_text
            await session.commit()

        try:
            outline_stmt = select(ChapterOutline).where(
                ChapterOutline.project_id == project_id,
                ChapterOutline.chapter_number == chapter_number,
            )
            outline_result = await session.execute(outline_stmt)
            outline = outline_result.scalars().first()
            title = outline.title if outline and outline.title else f"第{chapter_number}章"
            ingest_service = ChapterIngestionService(llm_service=llm_service)
            await ingest_service.ingest_chapter(
                project_id=project_id,
                chapter_number=chapter_number,
                title=title,
                content=content,
                summary=None,
                user_id=user_id or 0,
            )
            logger.info("章节 %s 向量化入库成功", chapter_number)
        except Exception as exc:
            logger.error("章节 %s 向量化入库失败: %s", chapter_number, exc)


async def _finalize_chapter_async(
    project_id: str,
    chapter_number: int,
    selected_version_id: int,
    user_id: int,
    skip_vector_update: bool = False,
) -> None:
    async with AsyncSessionLocal() as session:
        llm_service = LLMService(session)

        stmt = (
            select(Chapter)
            .options(selectinload(Chapter.versions))
            .where(
                Chapter.project_id == project_id,
                Chapter.chapter_number == chapter_number,
            )
        )
        result = await session.execute(stmt)
        chapter = result.scalars().first()
        if not chapter:
            return

        selected_version = next(
            (v for v in chapter.versions if v.id == selected_version_id),
            None,
        )
        if not selected_version or not selected_version.content:
            return

        chapter.selected_version_id = selected_version.id
        chapter.status = ChapterGenerationStatus.SUCCESSFUL.value
        chapter.generation_progress = 100
        chapter.generation_step = "completed"
        chapter.generation_step_index = 7
        chapter.generation_step_total = 7
        chapter.word_count = count_chapter_words(selected_version.content or "")
        await session.commit()

        vector_store = None
        if settings.vector_store_enabled:
            try:
                vector_store = VectorStoreService()
            except RuntimeError as exc:
                logger.warning("向量库初始化失败，跳过定稿写入: %s", exc)

        sync_session = getattr(session, "sync_session", session)
        finalize_service = FinalizeService(sync_session, llm_service, vector_store)
        await finalize_service.finalize_chapter(
            project_id=project_id,
            chapter_number=chapter_number,
            chapter_text=selected_version.content,
            user_id=user_id,
            skip_vector_update=skip_vector_update,
        )
        try:
            stats = await _sync_foreshadowings_for_chapter(
                session,
                project_id=project_id,
                chapter=chapter,
                content=selected_version.content,
                user_id=user_id,
            )
            logger.info(
                "异步定稿伏笔同步完成 project=%s chapter=%s created=%s revealed=%s developing=%s",
                project_id,
                chapter_number,
                stats["created"],
                stats["revealed"],
                stats["developing"],
            )
        except Exception as exc:
            await session.rollback()
            logger.exception(
                "异步定稿伏笔同步失败 project=%s chapter=%s err=%s",
                project_id,
                chapter_number,
                exc,
            )


def _schedule_finalize_task(
    project_id: str,
    chapter_number: int,
    selected_version_id: int,
    user_id: int,
    skip_vector_update: bool = False,
) -> None:
    asyncio.create_task(
        _finalize_chapter_async(
            project_id=project_id,
            chapter_number=chapter_number,
            selected_version_id=selected_version_id,
            user_id=user_id,
            skip_vector_update=skip_vector_update,
        )
    )


@router.post("/advanced/generate", response_model=AdvancedGenerateResponse)
async def advanced_generate_chapter(
    request: AdvancedGenerateRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> AdvancedGenerateResponse:
    """
    高级写作入口：通过 PipelineOrchestrator 统一编排生成流程。
    """
    orchestrator = PipelineOrchestrator(session)
    result = await orchestrator.generate_chapter(
        project_id=request.project_id,
        chapter_number=request.chapter_number,
        writing_notes=request.writing_notes,
        user_id=current_user.id,
        flow_config=request.flow_config.model_dump(),
    )

    flow_config = request.flow_config
    if flow_config.async_finalize and result.get("variants"):
        best_index = result.get("best_version_index", 0)
        variants = result["variants"]
        if 0 <= best_index < len(variants):
            selected_version_id = variants[best_index]["version_id"]
            background_tasks.add_task(
                _schedule_finalize_task,
                request.project_id,
                request.chapter_number,
                selected_version_id,
                current_user.id,
                False,
            )

    return AdvancedGenerateResponse(**result)


@router.post("/chapters/{chapter_number}/finalize", response_model=FinalizeChapterResponse)
async def finalize_chapter(
    chapter_number: int,
    request: FinalizeChapterRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> FinalizeChapterResponse:
    """
    定稿入口：选中版本后触发 FinalizeService 进行记忆更新与快照写入。
    """
    novel_service = NovelService(session)
    await novel_service.ensure_project_owner(request.project_id, current_user.id)

    stmt = (
        select(Chapter)
        .options(selectinload(Chapter.versions))
        .where(
            Chapter.project_id == request.project_id,
            Chapter.chapter_number == chapter_number,
        )
    )
    result = await session.execute(stmt)
    chapter = result.scalars().first()
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")

    selected_version = next(
        (v for v in chapter.versions if v.id == request.selected_version_id),
        None,
    )
    if not selected_version or not selected_version.content:
        raise HTTPException(status_code=400, detail="选中的版本不存在或内容为空")

    chapter.selected_version_id = selected_version.id
    chapter.status = ChapterGenerationStatus.SUCCESSFUL.value
    chapter.generation_progress = 100
    chapter.generation_step = "completed"
    chapter.generation_step_index = 7
    chapter.generation_step_total = 7
    chapter.word_count = count_chapter_words(selected_version.content or "")
    await session.commit()

    vector_store = None
    if settings.vector_store_enabled and not request.skip_vector_update:
        try:
            vector_store = VectorStoreService()
        except RuntimeError as exc:
            logger.warning("向量库初始化失败，跳过定稿写入: %s", exc)

    sync_session = getattr(session, "sync_session", session)
    finalize_service = FinalizeService(sync_session, LLMService(session), vector_store)
    finalize_result = await finalize_service.finalize_chapter(
        project_id=request.project_id,
        chapter_number=chapter_number,
        chapter_text=selected_version.content,
        user_id=current_user.id,
        skip_vector_update=request.skip_vector_update or False,
    )
    background_tasks.add_task(
        _sync_foreshadowings_after_finalize,
        request.project_id,
        chapter_number,
        selected_version.content,
        current_user.id,
    )

    return FinalizeChapterResponse(
        project_id=request.project_id,
        chapter_number=chapter_number,
        selected_version_id=selected_version.id,
        result=finalize_result,
    )


@router.post("/novels/{project_id}/chapters/generate", response_model=NovelProjectSchema)
async def generate_chapter(
    project_id: str,
    request: GenerateChapterRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    """
    生成章节正文 - 统一委托 LangGraph 编排器执行。

    前端仍调用原普通生成接口；接口层只负责鉴权上下文和响应转换，
    具体的上下文、RAG、写作、评审、版本落盘都在 PipelineOrchestrator 节点内完成。
    """
    novel_service = NovelService(session)
    orchestrator = PipelineOrchestrator(session)
    try:
        await orchestrator.generate_chapter(
            project_id=project_id,
            chapter_number=request.chapter_number,
            writing_notes=request.writing_notes,
            user_id=current_user.id,
            flow_config={
                "preset": "basic",
                "enable_rag": True,
            },
        )
        return await _load_project_schema(novel_service, project_id, current_user.id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "项目 %s 第 %s 章 LangGraph 生成流程失败: %s",
            project_id,
            request.chapter_number,
            exc,
        )
        raise HTTPException(status_code=500, detail=_build_generation_failure_detail(exc)) from exc


@router.post("/novels/{project_id}/chapters/select", response_model=NovelProjectSchema)
async def select_chapter_version(
    project_id: str,
    request: SelectVersionRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    chapter = await novel_service.get_or_create_chapter(project_id, request.chapter_number)

    chapter.status = ChapterGenerationStatus.SELECTING.value
    chapter.generation_progress = 95
    chapter.generation_step = "selecting_version"
    chapter.generation_step_index = 6
    chapter.generation_step_total = 7
    await session.commit()

    # 使用 novel_service.select_chapter_version 确保排序一致
    # 该函数会按 created_at 排序并校验索引
    try:
        selected_version = await novel_service.select_chapter_version(chapter, request.version_index)
    except HTTPException:
        chapter.status = ChapterGenerationStatus.WAITING_FOR_CONFIRM.value
        chapter.generation_progress = 100
        chapter.generation_step = "waiting_for_confirm"
        chapter.generation_step_index = 7
        chapter.generation_step_total = 7
        await session.commit()
        raise

    # 校验内容是否为空
    if not selected_version.content or len(selected_version.content.strip()) == 0:
        # 回滚状态，不标记为 successful
        await session.rollback()
        raise HTTPException(status_code=400, detail="选中的版本内容为空，无法确认为最终版")

    # 异步触发向量化入库
    try:
        llm_service = LLMService(session)
        ingest_service = ChapterIngestionService(llm_service=llm_service)
        outline_stmt = select(ChapterOutline).where(
            ChapterOutline.project_id == project_id,
            ChapterOutline.chapter_number == request.chapter_number,
        )
        outline_result = await session.execute(outline_stmt)
        outline = outline_result.scalars().first()
        chapter_title = outline.title if outline and outline.title else f"第{request.chapter_number}章"
        await ingest_service.ingest_chapter(
            project_id=project_id,
            chapter_number=request.chapter_number,
            title=chapter_title,
            content=selected_version.content,
            summary=None,
            user_id=current_user.id,
        )
        logger.info(f"章节 {request.chapter_number} 向量化入库成功")
    except Exception as e:
        logger.error(f"章节 {request.chapter_number} 向量化入库失败: {e}")
        # 向量化失败不应阻止版本选择，仅记录错误
    background_tasks.add_task(
        _sync_foreshadowings_after_finalize,
        project_id,
        request.chapter_number,
        selected_version.content,
        current_user.id,
    )

    return await _load_project_schema(novel_service, project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/evaluate", response_model=NovelProjectSchema)
async def evaluate_chapter(
    project_id: str,
    request: EvaluateChapterRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    # 确保预加载 selected_version 与 versions 关系
    from sqlalchemy.orm import selectinload
    stmt = (
        select(Chapter)
        .options(
            selectinload(Chapter.selected_version),
            selectinload(Chapter.versions),
        )
        .where(
            Chapter.project_id == project_id,
            Chapter.chapter_number == request.chapter_number,
        )
    )
    result = await session.execute(stmt)
    chapter = result.scalars().first()

    if not chapter:
        chapter = await novel_service.get_or_create_chapter(project_id, request.chapter_number)

    ordered_versions = sorted(
        [version for version in (chapter.versions or []) if version.content and version.content.strip()],
        key=lambda item: item.created_at,
    )

    version_to_evaluate = chapter.selected_version
    if version_to_evaluate and (not version_to_evaluate.content or not version_to_evaluate.content.strip()):
        version_to_evaluate = None

    if not ordered_versions and not version_to_evaluate:
        raise HTTPException(status_code=400, detail="该章节还没有生成任何版本，无法进行评审")

    chapter.status = "evaluating"
    chapter.generation_progress = 84
    chapter.generation_step = "evaluating"
    chapter.generation_step_index = 2
    chapter.generation_step_total = 3
    await session.commit()

    evaluation_feedback: Optional[str] = None
    evaluation_version: Optional[ChapterVersion] = None

    try:
        # 获取章节内容用于上下文增强
        chapter_content = None
        if ordered_versions:
            # 使用最新版本的内容
            chapter_content = ordered_versions[-1].content
        elif version_to_evaluate and version_to_evaluate.content:
            chapter_content = version_to_evaluate.content

        review_context = await _build_review_context(
            session=session,
            novel_service=novel_service,
            project=project,
            project_id=project_id,
            chapter_number=request.chapter_number,
            user_id=current_user.id,
            chapter_content=chapter_content,
        )

        if len(ordered_versions) > 1:
            ai_review_service = AIReviewService(llm_service, prompt_service)
            ai_review_result = await ai_review_service.review_versions(
                versions=[version.content for version in ordered_versions],
                chapter_mission=review_context.get("chapter_mission") if isinstance(review_context.get("chapter_mission"), dict) else None,
                user_id=current_user.id,
                review_context=review_context,
            )
            if not ai_review_result:
                raise ValueError("多版本评审失败")

            evaluation_feedback = json.dumps(
                ai_review_result.to_evaluation_payload(),
                ensure_ascii=False,
            )
        else:
            if not version_to_evaluate:
                version_to_evaluate = ordered_versions[-1]
            if not version_to_evaluate or not version_to_evaluate.content:
                raise HTTPException(status_code=400, detail="版本内容为空，无法进行评审")

            ai_review_service = AIReviewService(llm_service, prompt_service)
            evaluation_text = await ai_review_service.review_single_version(
                version_content=version_to_evaluate.content,
                user_id=current_user.id,
                review_context=review_context,
            )
            if not evaluation_text or len(evaluation_text.strip()) == 0:
                raise ValueError("评审结果为空")
            evaluation_feedback = evaluation_text
            evaluation_version = version_to_evaluate

        await novel_service.add_chapter_evaluation(
            chapter=chapter,
            version=evaluation_version,
            feedback=evaluation_feedback,
            decision="reviewed"
        )
        logger.info("项目 %s 第 %s 章评审成功", project_id, request.chapter_number)
    except Exception as exc:
        logger.exception("项目 %s 第 %s 章评审失败: %s", project_id, request.chapter_number, exc)
        # 回滚事务，恢复状态
        await session.rollback()

        # 重新加载 chapter 对象（因为 rollback 后对象已脱离 session）
        stmt = (
            select(Chapter)
            .where(
                Chapter.project_id == project_id,
                Chapter.chapter_number == request.chapter_number,
            )
        )
        result = await session.execute(stmt)
        chapter = result.scalars().first()

        if chapter:
            # 使用 add_chapter_evaluation 创建失败记录
            # 注意：这里不能再用 add_chapter_evaluation，因为它会设置状态为 waiting_for_confirm
            # 失败时应该设置为 evaluation_failed
            from app.models.novel import ChapterEvaluation
            evaluation_record = ChapterEvaluation(
                chapter_id=chapter.id,
                version_id=version_to_evaluate.id if version_to_evaluate else None,
                decision="failed",
                feedback="评审失败，请重试",
                score=None
            )
            session.add(evaluation_record)
            chapter.status = "evaluation_failed"
            chapter.generation_progress = 0
            chapter.generation_step = "evaluation_failed"
            chapter.generation_step_index = 0
            chapter.generation_step_total = 3
            await session.commit()

        # 抛出异常，让前端知道评审失败
        raise HTTPException(status_code=500, detail="评审失败，请重试")

    return await _load_project_schema(novel_service, project_id, current_user.id)



@router.post("/novels/{project_id}/chapters/update-outline", response_model=NovelProjectSchema)
async def update_chapter_outline(
    project_id: str,
    request: UpdateChapterOutlineRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    await novel_service.ensure_project_owner(project_id, current_user.id)

    outline = await novel_service.get_outline(project_id, request.chapter_number)
    if not outline:
        raise HTTPException(status_code=404, detail="未找到对应章节大纲")

    outline.title = request.title
    outline.summary = request.summary
    await session.commit()

    return await _load_project_schema(novel_service, project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/delete", response_model=NovelProjectSchema)
async def delete_chapters(
    project_id: str,
    request: DeleteChapterRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    await novel_service.ensure_project_owner(project_id, current_user.id)

    for ch_num in request.chapter_numbers:
        await novel_service.delete_chapter(project_id, ch_num)

    await session.commit()
    return await _load_project_schema(novel_service, project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/outline", response_model=BackgroundTaskResponse, status_code=202)
async def generate_chapters_outline(
    project_id: str,
    request: GenerateOutlineRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> BackgroundTaskResponse:
    novel_service = NovelService(session)
    await novel_service.ensure_project_owner(project_id, current_user.id)

    task_service = BackgroundTaskService(session)
    # 后台任务内部仍使用 stage="chapter_outline" 路由到章节大纲模型。
    task = await task_service.create_task(
        user_id=current_user.id,
        project_id=project_id,
        task_type="chapter_outline",
        title=f"生成第 {request.start_chapter} 章起的后续大纲",
        payload={
            "project_id": project_id,
            "start_chapter": request.start_chapter,
            "num_chapters": request.num_chapters,
        },
    )
    background_tasks.add_task(
        run_generate_chapters_outline_task,
        task.id,
        project_id=project_id,
        user_id=current_user.id,
        start_chapter=request.start_chapter,
        num_chapters=request.num_chapters,
    )

    return task


@router.post("/novels/{project_id}/chapters/edit", response_model=NovelProjectSchema)
async def edit_chapter_content(
    project_id: str,
    request: EditChapterRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)

    await novel_service.ensure_project_owner(project_id, current_user.id)
    chapter = await novel_service.get_or_create_chapter(project_id, request.chapter_number)

    # 更新内容：优先更新选中版本，否则选最新版本或创建新版本
    target_version = chapter.selected_version
    if not target_version and chapter.versions:
        target_version = sorted(chapter.versions, key=lambda item: item.created_at)[-1]

    if target_version:
        target_version.content = request.content
        if not chapter.selected_version_id:
            chapter.selected_version_id = target_version.id
        chapter.selected_version = target_version
    else:
        target_version = ChapterVersion(
            chapter_id=chapter.id,
            content=request.content,
            version_label="manual_edit",
        )
        session.add(target_version)
        await session.flush()
        chapter.selected_version_id = target_version.id
        chapter.selected_version = target_version

    chapter.status = "successful"
    chapter.generation_progress = 100
    chapter.generation_step = "completed"
    chapter.generation_step_index = 7
    chapter.generation_step_total = 7
    chapter.word_count = count_chapter_words(request.content or "")
    await session.commit()

    background_tasks.add_task(
        _refresh_edit_summary_and_ingest,
        project_id,
        request.chapter_number,
        request.content,
        current_user.id,
    )
    background_tasks.add_task(
        _sync_foreshadowings_after_finalize,
        project_id,
        request.chapter_number,
        request.content,
        current_user.id,
    )

    return await _load_project_schema(novel_service, project_id, current_user.id)


@router.post("/novels/{project_id}/chapters/edit-fast", response_model=ChapterSchema)
async def edit_chapter_content_fast(
    project_id: str,
    request: EditChapterRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> ChapterSchema:
    novel_service = NovelService(session)

    await novel_service.ensure_project_owner(project_id, current_user.id)
    chapter = await novel_service.get_or_create_chapter(project_id, request.chapter_number)

    target_version = chapter.selected_version
    if not target_version and chapter.versions:
        target_version = sorted(chapter.versions, key=lambda item: item.created_at)[-1]

    if target_version:
        target_version.content = request.content
        if not chapter.selected_version_id:
            chapter.selected_version_id = target_version.id
        chapter.selected_version = target_version
    else:
        target_version = ChapterVersion(
            chapter_id=chapter.id,
            content=request.content,
            version_label="manual_edit",
        )
        session.add(target_version)
        await session.flush()
        chapter.selected_version_id = target_version.id
        chapter.selected_version = target_version

    chapter.status = "successful"
    chapter.generation_progress = 100
    chapter.generation_step = "completed"
    chapter.generation_step_index = 7
    chapter.generation_step_total = 7
    chapter.word_count = count_chapter_words(request.content or "")
    await session.commit()

    background_tasks.add_task(
        _refresh_edit_summary_and_ingest,
        project_id,
        request.chapter_number,
        request.content,
        current_user.id,
    )
    background_tasks.add_task(
        _sync_foreshadowings_after_finalize,
        project_id,
        request.chapter_number,
        request.content,
        current_user.id,
    )

    stmt = (
        select(Chapter)
        .options(
            selectinload(Chapter.versions),
            selectinload(Chapter.evaluations),
            selectinload(Chapter.selected_version),
        )
        .where(
            Chapter.project_id == project_id,
            Chapter.chapter_number == request.chapter_number,
        )
    )
    result = await session.execute(stmt)
    chapter = result.scalars().first()
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")

    outline_stmt = select(ChapterOutline).where(
        ChapterOutline.project_id == project_id,
        ChapterOutline.chapter_number == request.chapter_number,
    )
    outline_result = await session.execute(outline_stmt)
    outline = outline_result.scalars().first()

    title = outline.title if outline else f"第{request.chapter_number}章"
    summary = outline.summary if outline else ""
    real_summary = chapter.real_summary
    selected_version = None
    if chapter.selected_version_id and chapter.versions:
        selected_version = next((v for v in chapter.versions if v.id == chapter.selected_version_id), None)
    if (
        selected_version is None
        and chapter.selected_version
        and (
            chapter.selected_version_id is None
            or chapter.selected_version.id == chapter.selected_version_id
        )
    ):
        selected_version = chapter.selected_version
    content = selected_version.content if selected_version else None
    versions = (
        [v.content for v in sorted(chapter.versions, key=lambda item: item.created_at)]
        if chapter.versions
        else None
    )
    evaluation_text = None
    if chapter.evaluations:
        latest = sorted(chapter.evaluations, key=lambda item: item.created_at)[-1]
        evaluation_text = latest.feedback or latest.decision
    status_value = chapter.status or ChapterGenerationStatus.NOT_GENERATED.value

    return ChapterSchema(
        chapter_number=request.chapter_number,
        title=title,
        summary=summary,
        real_summary=real_summary,
        content=content,
        versions=versions,
        evaluation=evaluation_text,
        generation_status=ChapterGenerationStatus(status_value),
        generation_progress=chapter.generation_progress,
        generation_step=chapter.generation_step,
        generation_step_index=chapter.generation_step_index,
        generation_step_total=chapter.generation_step_total,
        generation_started_at=chapter.__dict__.get("generation_started_at"),
        status_updated_at=chapter.__dict__.get("updated_at"),
        word_count=chapter.word_count or 0,
    )
