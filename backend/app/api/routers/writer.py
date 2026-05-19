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
import os
import re
from datetime import datetime, timedelta, timezone
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
from ...schemas.user import UserInDB
from ...services.chapter_context_service import ChapterContextService
from ...services.chapter_ingest_service import ChapterIngestionService
from ...services.llm_service import LLMService
from ...services.novel_service import NovelService
from ...services.prompt_service import PromptService
from ...services.vector_store_service import VectorStoreService
from ...services.writer_context_builder import WriterContextBuilder
from ...services.chapter_guardrails import ChapterGuardrails
from ...services.ai_review_service import AIReviewService
from ...services.finalize_service import FinalizeService
from ...services.review_context_builder import ReviewContextBuilder
from ...utils.json_utils import remove_think_tags, unwrap_markdown_json
from ...repositories.system_config_repository import SystemConfigRepository
from ...services.pipeline_orchestrator import PipelineOrchestrator
from ...services.chapter_word_count_settings import (
    build_word_count_requirement_text,
    count_chapter_words,
    resolve_word_count_requirements,
    should_compress_chapter,
)

router = APIRouter(prefix="/api/writer", tags=["Writer"])
logger = logging.getLogger(__name__)
# 使用固定 UTC+8，避免在 Windows/Python 环境缺少 tzdata 时 ZoneInfo 初始化失败。
CN_TIMEZONE = timezone(timedelta(hours=8), name="Asia/Shanghai")
WRITER_GENERATION_MAX_TOKENS = 7000
MIN_CHAPTER_VERSION_COUNT = 1
MAX_CHAPTER_VERSION_COUNT = 2
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


def _clamp_version_count(value: int) -> int:
    return max(MIN_CHAPTER_VERSION_COUNT, min(MAX_CHAPTER_VERSION_COUNT, int(value)))


async def _load_project_schema(service: NovelService, project_id: str, user_id: int) -> NovelProjectSchema:
    return await service.get_project_schema(project_id, user_id)


def _extract_tail_excerpt(text: Optional[str], limit: int = 500) -> str:
    """截取章节结尾文本，默认保留 500 字。"""
    if not text:
        return ""
    stripped = text.strip()
    if len(stripped) <= limit:
        return stripped
    return stripped[-limit:]


async def _expand_chapter_to_minimum_word_count(
    *,
    llm_service: LLMService,
    content: str,
    minimum_word_count: int,
    target_word_count: int,
    user_id: int,
    project_id: str,
    chapter_number: int,
    version_index: int,
) -> str:
    """
    当版本正文明显偏短时，做循环补写兜底，避免出现异常短稿。
    """
    max_attempts = 3
    best_content = (content or "").strip()
    best_word_count = count_chapter_words(best_content)
    if best_word_count >= minimum_word_count:
        return best_content

    logger.info(
        "项目 %s 第 %s 章版本 %s 低于最小字数，开始循环补写: current=%s minimum=%s target=%s attempts=%s",
        project_id,
        chapter_number,
        version_index,
        best_word_count,
        minimum_word_count,
        target_word_count,
        max_attempts,
    )

    current_content = best_content
    current_word_count = best_word_count

    for attempt in range(1, max_attempts + 1):
        prompt = f"""
请在不改变主线剧情与关键事件的前提下，对下面章节做补写扩展。

目标要求：
- 扩展后字数目标约 {target_word_count} 字，至少不少于 {minimum_word_count} 字。
- 补充环境、动作、心理和过渡细节，但不得新增与主线冲突的新设定。
- 保持人物关系、时间顺序和结尾钩子不变。
- 直接输出补写后的完整章节正文，不要解释，不要输出 JSON。

当前正文（约 {current_word_count} 字）：
{current_content}
""".strip()

        try:
            response = await llm_service.get_llm_response(
                system_prompt="你是网文章节润色编辑，负责在不改剧情主线的前提下补写细节。",
                conversation_history=[{"role": "user", "content": prompt}],
                temperature=0.4,
                user_id=user_id,
                timeout=300.0,
                response_format=None,
                max_tokens=WRITER_GENERATION_MAX_TOKENS,
                stage="chapter_enrichment",
            )
            enriched = unwrap_markdown_json(remove_think_tags(response)).strip()
            if not enriched:
                logger.warning(
                    "项目 %s 第 %s 章版本 %s 第 %s 次补写返回空内容，沿用当前文本",
                    project_id,
                    chapter_number,
                    version_index,
                    attempt,
                )
                continue

            enriched_word_count = count_chapter_words(enriched)
            if enriched_word_count > best_word_count:
                best_content = enriched
                best_word_count = enriched_word_count

            if enriched_word_count <= current_word_count:
                logger.warning(
                    "项目 %s 第 %s 章版本 %s 第 %s 次补写未增量: before=%s after=%s",
                    project_id,
                    chapter_number,
                    version_index,
                    attempt,
                    current_word_count,
                    enriched_word_count,
                )
                continue

            current_content = enriched
            current_word_count = enriched_word_count

            if current_word_count >= minimum_word_count:
                logger.info(
                    "项目 %s 第 %s 章版本 %s 第 %s 次补写达标: after=%s minimum=%s",
                    project_id,
                    chapter_number,
                    version_index,
                    attempt,
                    current_word_count,
                    minimum_word_count,
                )
                return current_content
        except Exception as exc:
            logger.warning(
                "项目 %s 第 %s 章版本 %s 第 %s 次补写失败，继续尝试: %s",
                project_id,
                chapter_number,
                version_index,
                attempt,
                exc,
            )

    if best_word_count < minimum_word_count:
        logger.warning(
            "项目 %s 第 %s 章版本 %s 多轮补写后仍低于最小字数: final=%s minimum=%s",
            project_id,
            chapter_number,
            version_index,
            best_word_count,
            minimum_word_count,
        )

    return best_content


async def _compress_chapter_to_word_limit(
    *,
    llm_service: LLMService,
    content: str,
    target_word_count: int,
    user_id: int,
    project_id: str,
    chapter_number: int,
    version_index: int,
) -> str:
    """当模型明显超出章节目标字数时，做一次只删减不扩写的压缩兜底。"""
    if not should_compress_chapter(content, target_word_count):
        return content

    current_word_count = count_chapter_words(content)
    logger.info(
        "项目 %s 第 %s 章版本 %s 超出字数上限，开始压缩: current=%s target=%s",
        project_id,
        chapter_number,
        version_index,
        current_word_count,
        target_word_count,
    )
    prompt = f"""
请把下面小说章节压缩到约 {target_word_count} 字，最多不得超过 {int(target_word_count * 1.1)} 字。

要求：
- 只删减冗余描写、重复心理活动、过密铺垫，不新增剧情。
- 保留关键事件、人物关系、冲突转折和结尾钩子。
- 直接输出压缩后的章节正文，不要解释，不要输出 JSON。

原文字数约 {current_word_count} 字：
{content}
""".strip()

    try:
        response = await llm_service.get_llm_response(
            system_prompt="你是小说章节压缩编辑，只做删减压缩，不新增剧情。",
            conversation_history=[{"role": "user", "content": prompt}],
            temperature=0.2,
            user_id=user_id,
            timeout=300.0,
            response_format=None,
            max_tokens=WRITER_GENERATION_MAX_TOKENS,
            stage="chapter_compression",
        )
        compressed = unwrap_markdown_json(remove_think_tags(response)).strip()
        return compressed or content
    except Exception as exc:
        logger.warning(
            "项目 %s 第 %s 章版本 %s 压缩失败，保留原文: %s",
            project_id,
            chapter_number,
            version_index,
            exc,
        )
        return content

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
    prompt = f"""
你是长篇小说伏笔编辑，只保留真正有后续叙事价值的伏笔。

判定标准：
- 保留会制造明确悬念、承诺、异常线索、身份/真相问题，或后文需要兑现的信息。
- 删除普通心理描写、气氛描写、一次性动作、泛泛疑问、普通计划、重复背景信息。
- 数量必须克制；没有足够意义就返回空数组。
- 每章最多保留 {MAX_AUTO_FORESHADOWINGS_PER_CHAPTER} 个，优先保留最强的。
- 不要创造候选之外的新伏笔。

输出 JSON：
{{
  "items": [
    {{
      "id": 0,
      "keep": true,
      "type": "mystery|question|clue|setup",
      "importance": "major|minor|subtle",
      "keywords": ["2到6字关键词"],
      "confidence": 0.0
    }}
  ]
}}

第 {chapter_number} 章候选：
{json.dumps(candidate_payload, ensure_ascii=False)}

章节内容节选：
{content[:4000]}
""".strip()

    try:
        response = await LLMService(session).get_llm_response(
            system_prompt="你只输出合法 JSON，不输出解释。",
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
    prompt = f"""
你是长篇小说伏笔编辑，判断本章是否真正推进或回收历史伏笔。

状态只能选择：
- revealed：本章明确给出答案、真相、兑现承诺，读者能确认该伏笔已回收。
- developing：本章只是重新提及、强化、给出新线索，但还没有真正回收。
- unchanged：只是词语重复、氛围相似、无关提及，不能算推进或回收。

要求：
- 不要因为出现关键词就判定回收。
- 回收必须有语义上的解释、揭示、兑现或因果闭合。
- 输出 JSON，不要解释。

输出 JSON：
{{
  "items": [
    {{"id": 1, "status": "revealed|developing|unchanged"}}
  ]
}}

第 {chapter_number} 章内容节选：
{content[:5000]}

历史伏笔：
{json.dumps(payload, ensure_ascii=False)}
""".strip()

    try:
        response = await LLMService(session).get_llm_response(
            system_prompt="你只输出合法 JSON，不输出解释。",
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


async def _resolve_version_count(session: AsyncSession) -> int:
    """
    解析章节版本数量配置，优先级：
    1) SystemConfig: writer.chapter_versions
    2) SystemConfig: writer.version_count（兼容旧键）
    3) ENV: WRITER_CHAPTER_VERSION_COUNT / WRITER_CHAPTER_VERSIONS（与 config.py 对齐）
    4) ENV: WRITER_VERSION_COUNT（兼容旧）
    5) settings.writer_chapter_versions（默认=1）
    """
    repo = SystemConfigRepository(session)
    # 1) 新键优先，兼容旧键
    for key in ("writer.chapter_versions", "writer.version_count"):
        record = await repo.get_by_key(key)
        if record and record.value:
            try:
                val = int(record.value)
                if val >= 1:
                    return _clamp_version_count(val)
            except ValueError:
                pass
    # 2) 环境变量（与 Settings 对齐）
    for env in ("WRITER_CHAPTER_VERSION_COUNT", "WRITER_CHAPTER_VERSIONS", "WRITER_VERSION_COUNT"):
        v = os.getenv(env)
        if v:
            try:
                val = int(v)
                if val >= 1:
                    return _clamp_version_count(val)
            except ValueError:
                pass
    # 3) 默认值
    return _clamp_version_count(int(settings.writer_chapter_versions))


async def _generate_chapter_mission(
    llm_service: LLMService,
    prompt_service: PromptService,
    blueprint_dict: dict,
    previous_summary: str,
    previous_tail: str,
    outline_title: str,
    outline_summary: str,
    writing_notes: str,
    introduced_characters: List[str],
    all_characters: List[str],
    user_id: int,
) -> Optional[dict]:
    """
    L2 Director: 生成章节导演脚本（ChapterMission）
    """
    plan_prompt = await prompt_service.get_prompt("chapter_plan")
    if not plan_prompt:
        logger.warning("未配置 chapter_plan 提示词，跳过导演脚本生成")
        return None

    plan_input = f"""
[上一章摘要]
{previous_summary or "暂无（这是第一章）"}

[上一章结尾]
{previous_tail or "暂无（这是第一章）"}

[当前章节大纲]
标题：{outline_title}
摘要：{outline_summary}

[已登场角色]
{json.dumps(introduced_characters, ensure_ascii=False) if introduced_characters else "暂无"}

[全部角色]
{json.dumps(all_characters, ensure_ascii=False)}

[写作指令]
{writing_notes or "无额外指令"}
"""

    try:
        response = await llm_service.get_llm_response(
            system_prompt=plan_prompt,
            conversation_history=[{"role": "user", "content": plan_input}],
            temperature=0.3,
            user_id=user_id,
            timeout=120.0,
            stage="chapter_mission",
        )
        cleaned = remove_think_tags(response)
        normalized = unwrap_markdown_json(cleaned)
        mission = json.loads(normalized)
        logger.info("成功生成章节导演脚本: macro_beat=%s", mission.get("macro_beat"))
        return mission
    except Exception as exc:
        logger.warning("生成章节导演脚本失败，将使用默认模式: %s", exc)
        return None


async def _rewrite_with_guardrails(
    llm_service: LLMService,
    prompt_service: PromptService,
    original_text: str,
    chapter_mission: Optional[dict],
    violations_text: str,
    user_id: int,
) -> str:
    """
    使用护栏修复提示词重写违规内容
    """
    rewrite_prompt = await prompt_service.get_prompt("rewrite_guardrails")
    if not rewrite_prompt:
        logger.warning("未配置 rewrite_guardrails 提示词，跳过自动修复")
        return original_text

    rewrite_input = f"""
[原文]
{original_text}

[章节导演脚本]
{json.dumps(chapter_mission, ensure_ascii=False, indent=2) if chapter_mission else "无"}

[违规列表]
{violations_text}
"""

    try:
        response = await llm_service.get_llm_response(
            system_prompt=rewrite_prompt,
            conversation_history=[{"role": "user", "content": rewrite_input}],
            temperature=0.3,
            user_id=user_id,
            timeout=300.0,
            response_format=None,
            max_tokens=WRITER_GENERATION_MAX_TOKENS,
            stage="chapter_rewrite",
        )
        cleaned = remove_think_tags(response)
        logger.info("成功修复违规内容")
        return cleaned
    except Exception as exc:
        logger.warning("自动修复失败，返回原文: %s", exc)
        return original_text


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
        chapter.word_count = len(selected_version.content or "")
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
    chapter.word_count = len(selected_version.content or "")
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
    生成章节正文 - 三层架构流程：
    1. 收集上下文和历史摘要
    2. L2 Director: 生成章节导演脚本（ChapterMission）
    3. 信息可见性过滤：裁剪蓝图，移除未登场角色
    4. L3 Writer: 生成正文（使用 writing_v2 提示词）
    5. 护栏检查：检测并修复违规内容
    """
    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)
    context_builder = WriterContextBuilder()
    guardrails = ChapterGuardrails()

    project = await novel_service.ensure_project_owner(project_id, current_user.id)
    logger.info("用户 %s 开始为项目 %s 生成第 %s 章", current_user.id, project_id, request.chapter_number)
    outline = await novel_service.get_outline(project_id, request.chapter_number)
    if not outline:
        logger.warning("项目 %s 未找到第 %s 章纲要，生成流程终止", project_id, request.chapter_number)
        raise HTTPException(status_code=404, detail="蓝图中未找到对应章节纲要")

    chapter = await novel_service.get_or_create_chapter(project_id, request.chapter_number)
    generation_step_total = 7

    def _format_generation_step(step: str, meta: Optional[Dict[str, object]] = None) -> str:
        """将阶段信息编码到 generation_step，便于前端展示更细粒度执行状态。"""
        if not meta:
            return step
        tokens: List[str] = []
        for key, value in meta.items():
            if value is None:
                continue
            text = str(value).strip()
            if not text:
                continue
            # 避免分隔符污染，保证前端可稳定解析。
            safe_key = str(key).replace("|", "").replace("=", "").strip()
            safe_value = text.replace("|", "").replace("=", "").strip()
            if safe_key and safe_value:
                tokens.append(f"{safe_key}={safe_value}")
        if not tokens:
            return step
        encoded = f"{step}|{'|'.join(tokens)}"
        # generation_step 字段长度上限为 64，超长时兜底截断。
        return encoded[:64]

    async def _update_generation_progress(
        *,
        progress: int,
        step: str,
        step_index: int,
        step_meta: Optional[Dict[str, object]] = None,
        status: Optional[str] = None,
    ) -> None:
        chapter.generation_progress = max(0, min(100, int(progress)))
        chapter.generation_step = _format_generation_step(step, step_meta)
        chapter.generation_step_index = max(0, step_index)
        chapter.generation_step_total = generation_step_total
        if status:
            chapter.status = status
        await session.commit()

    async def _mark_generation_failed() -> None:
        """确保异常后章节状态统一收敛到 failed，避免前端刷新后长期卡在 generating。"""
        try:
            await session.rollback()
        except Exception:
            pass

        try:
            chapter.status = "failed"
            chapter.generation_progress = 0
            chapter.generation_step = "failed"
            chapter.generation_step_index = 0
            chapter.generation_step_total = generation_step_total
            await session.commit()
        except Exception:
            logger.exception(
                "项目 %s 第 %s 章标记 failed 失败",
                project_id,
                request.chapter_number,
            )

    chapter.real_summary = None
    chapter.selected_version_id = None
    chapter.selected_version = None
    chapter.status = "generating"
    chapter.generation_started_at = datetime.now(CN_TIMEZONE)
    chapter.generation_progress = 3
    chapter.generation_step = _format_generation_step("context_prep")
    chapter.generation_step_index = 1
    chapter.generation_step_total = generation_step_total
    await session.commit()

    outlines_map = {item.chapter_number: item for item in project.outlines}

    # ========== 1. 收集历史上下文 ==========
    completed_chapters = []
    completed_summaries = []
    latest_prev_number = -1
    previous_summary_text = ""
    previous_tail_excerpt = ""

    for existing in project.chapters:
        if existing.chapter_number >= request.chapter_number:
            continue
        if existing.selected_version is None or not existing.selected_version.content:
            continue
        if not existing.real_summary:
            try:
                summary = await llm_service.get_summary(
                    existing.selected_version.content,
                    temperature=0.15,
                    user_id=current_user.id,
                    timeout=180.0,
                    stage="summary_memory",
                )
            except HTTPException:
                await _mark_generation_failed()
                raise
            except Exception as exc:
                logger.exception(
                    "项目 %s 第 %s 章生成历史摘要失败: %s",
                    project_id,
                    request.chapter_number,
                    exc,
                )
                await _mark_generation_failed()
                raise HTTPException(status_code=500, detail="生成章节失败：历史摘要阶段异常") from exc
            existing.real_summary = remove_think_tags(summary)
            await session.commit()
        completed_chapters.append({
            "chapter_number": existing.chapter_number,
            "title": outlines_map.get(existing.chapter_number).title if outlines_map.get(existing.chapter_number) else f"第{existing.chapter_number}章",
            "summary": existing.real_summary,
        })
        completed_summaries.append(existing.real_summary or "")
        if existing.chapter_number > latest_prev_number:
            latest_prev_number = existing.chapter_number
            previous_summary_text = existing.real_summary or ""
            previous_tail_excerpt = _extract_tail_excerpt(existing.selected_version.content)

    await _update_generation_progress(progress=15, step="context_prep", step_index=1)

    try:
        # 这里只需要蓝图数据，避免依赖整项目序列化流程导致生成前失败。
        blueprint_schema = novel_service._build_blueprint_schema(project)
        blueprint_dict = blueprint_schema.model_dump()
    except HTTPException:
        await _mark_generation_failed()
        raise
    except Exception as exc:
        logger.exception(
            "项目 %s 第 %s 章构建蓝图上下文失败: %s",
            project_id,
            request.chapter_number,
            exc,
        )
        await _mark_generation_failed()
        raise HTTPException(status_code=500, detail="生成章节失败：加载项目信息异常") from exc

    # 处理关系字段名
    if "relationships" in blueprint_dict and blueprint_dict["relationships"]:
        for relation in blueprint_dict["relationships"]:
            if "character_from" in relation:
                relation["from"] = relation.pop("character_from")
            if "character_to" in relation:
                relation["to"] = relation.pop("character_to")

    outline_title = outline.title or f"第{outline.chapter_number}章"
    outline_summary = outline.summary or "暂无摘要"
    writing_notes = request.writing_notes or "无额外写作指令"

    # 提取所有角色名
    all_characters = [c.get("name") for c in blueprint_dict.get("characters", []) if c.get("name")]

    # ========== 2. L2 Director: 生成章节导演脚本 ==========
    await _update_generation_progress(progress=22, step="director_mission", step_index=2)
    try:
        chapter_mission = await _generate_chapter_mission(
            llm_service=llm_service,
            prompt_service=prompt_service,
            blueprint_dict=blueprint_dict,
            previous_summary=previous_summary_text,
            previous_tail=previous_tail_excerpt,
            outline_title=outline_title,
            outline_summary=outline_summary,
            writing_notes=writing_notes,
            introduced_characters=[],  # 将在下一步填充
            all_characters=all_characters,
            user_id=current_user.id,
        )
    except HTTPException:
        await _mark_generation_failed()
        raise
    except Exception as exc:
        logger.exception(
            "项目 %s 第 %s 章生成导演脚本失败: %s",
            project_id,
            request.chapter_number,
            exc,
        )
        await _mark_generation_failed()
        raise HTTPException(status_code=500, detail="生成章节失败：导演脚本阶段异常") from exc

    # 从导演脚本中提取允许登场的新角色
    allowed_new_characters = []
    if chapter_mission:
        allowed_new_characters = chapter_mission.get("allowed_new_characters", [])

    # ========== 3. 信息可见性过滤 ==========
    try:
        visibility_context = context_builder.build_visibility_context(
            blueprint=blueprint_dict,
            completed_summaries=completed_summaries,
            previous_tail=previous_tail_excerpt,
            outline_title=outline_title,
            outline_summary=outline_summary,
            writing_notes=writing_notes,
            allowed_new_characters=allowed_new_characters,
        )
    except Exception as exc:
        logger.exception(
            "项目 %s 第 %s 章可见性上下文构建失败: %s",
            project_id,
            request.chapter_number,
            exc,
        )
        await _mark_generation_failed()
        raise HTTPException(status_code=500, detail="生成章节失败：上下文构建异常") from exc

    writer_blueprint = visibility_context["writer_blueprint"]
    forbidden_characters = visibility_context["forbidden_characters"]
    introduced_characters = visibility_context["introduced_characters"]

    logger.info(
        "项目 %s 第 %s 章信息可见性: 已登场=%s, 允许新登场=%s, 禁止=%s",
        project_id,
        request.chapter_number,
        len(introduced_characters),
        len(allowed_new_characters),
        len(forbidden_characters),
    )

    # ========== 4. 准备 RAG 上下文 ==========
    await _update_generation_progress(progress=38, step="rag_retrieval", step_index=3)
    vector_store: Optional[VectorStoreService]
    if not settings.vector_store_enabled:
        vector_store = None
    else:
        try:
            vector_store = VectorStoreService()
        except RuntimeError as exc:
            logger.warning("向量库初始化失败，RAG 检索被禁用: %s", exc)
            vector_store = None
    context_service = ChapterContextService(llm_service=llm_service, vector_store=vector_store)

    query_parts = [outline_title, outline_summary]
    if request.writing_notes:
        query_parts.append(request.writing_notes)
    rag_query = "\n".join(part for part in query_parts if part)
    try:
        rag_context = await context_service.retrieve_for_generation(
            project_id=project_id,
            query_text=rag_query or outline.title or outline.summary or "",
            user_id=current_user.id,
        )
    except HTTPException:
        await _mark_generation_failed()
        raise
    except Exception as exc:
        logger.exception(
            "项目 %s 第 %s 章 RAG 检索失败: %s",
            project_id,
            request.chapter_number,
            exc,
        )
        await _mark_generation_failed()
        raise HTTPException(status_code=500, detail="生成章节失败：检索上下文阶段异常") from exc
    await _update_generation_progress(progress=48, step="rag_retrieval", step_index=3)
    rag_chunks_text = "\n\n".join(rag_context.chunk_texts()) if rag_context.chunks else "未检索到章节片段"
    rag_summaries_text = "\n".join(rag_context.summary_lines()) if rag_context.summaries else "未检索到章节摘要"

    # ========== 5. 构建写作提示词 ==========
    # 优先使用 writing_v2，fallback 到 writing
    try:
        writer_prompt = await prompt_service.get_prompt("writing_v2")
        if not writer_prompt:
            writer_prompt = await prompt_service.get_prompt("writing")
    except Exception as exc:
        logger.exception(
            "项目 %s 第 %s 章加载写作提示词失败: %s",
            project_id,
            request.chapter_number,
            exc,
        )
        await _mark_generation_failed()
        raise HTTPException(status_code=500, detail="生成章节失败：加载写作提示词异常") from exc
    if not writer_prompt:
        logger.error("未配置写作提示词，无法生成章节内容")
        chapter.status = "failed"
        chapter.generation_progress = 0
        chapter.generation_step = "failed"
        chapter.generation_step_index = 0
        chapter.generation_step_total = generation_step_total
        await session.commit()
        raise HTTPException(status_code=500, detail="缺少写作提示词，请联系管理员配置")

    # 使用裁剪后的蓝图（移除了 full_synopsis 和未登场角色）
    blueprint_text = json.dumps(writer_blueprint, ensure_ascii=False, indent=2)

    # 构建导演脚本文本
    mission_text = json.dumps(chapter_mission, ensure_ascii=False, indent=2) if chapter_mission else "无导演脚本"

    # 构建禁止角色列表
    forbidden_text = json.dumps(forbidden_characters, ensure_ascii=False) if forbidden_characters else "无"

    target_word_count, minimum_word_count = await resolve_word_count_requirements(
        SystemConfigRepository(session)
    )

    prompt_sections = [
        ("[世界蓝图](JSON，已裁剪)", blueprint_text),
        ("[上一章摘要]", previous_summary_text or "暂无（这是第一章）"),
        ("[上一章结尾]", previous_tail_excerpt or "暂无（这是第一章）"),
        ("[章节导演脚本](JSON)", mission_text),
        ("[检索到的剧情上下文](Markdown)", rag_chunks_text),
        ("[检索到的章节摘要](Markdown)", rag_summaries_text),
        ("[当前章节目标]", f"标题：{outline_title}\n摘要：{outline_summary}\n写作要求：{writing_notes}"),
        (
            "[篇幅与排版要求]",
            build_word_count_requirement_text(target_word_count)
            + "段落清晰，尽量保持自然段首行空两格。",
        ),
        ("[禁止角色](本章不允许提及)", forbidden_text),
    ]
    prompt_input = "\n\n".join(f"{title}\n{content}" for title, content in prompt_sections if content)
    logger.debug("章节写作提示词长度: %s 字符", len(prompt_input))
    await _update_generation_progress(
        progress=55,
        step="draft_generation",
        step_index=4,
        step_meta={"v": "0/?"},
    )

    # ========== 6. L3 Writer: 生成正文 ==========
    async def _generate_single_version(idx: int, version_style_hint: Optional[str] = None) -> Dict:
        """生成单个版本，支持差异化风格提示"""
        try:
            # 如果有版本风格提示，添加到 prompt_input
            final_prompt_input = prompt_input
            if version_style_hint:
                final_prompt_input += f"\n\n[版本风格提示]\n{version_style_hint}"

            response = await llm_service.get_llm_response(
                system_prompt=writer_prompt,
                conversation_history=[{"role": "user", "content": final_prompt_input}],
                temperature=0.9,
                user_id=current_user.id,
                timeout=600.0,
                response_format=None,
                max_tokens=WRITER_GENERATION_MAX_TOKENS,
                stage="chapter_writing",
            )
            cleaned = remove_think_tags(response)
            normalized = unwrap_markdown_json(cleaned)

            # ========== 7. 护栏检查 ==========
            guardrail_result = guardrails.check(
                generated_text=normalized,
                forbidden_characters=forbidden_characters,
                allowed_new_characters=allowed_new_characters,
                pov=chapter_mission.get("pov") if chapter_mission else None,
            )

            final_content = normalized
            guardrail_metadata = {"passed": guardrail_result.passed, "violations": []}

            if not guardrail_result.passed:
                logger.warning(
                    "项目 %s 第 %s 章版本 %s 检测到 %s 个违规",
                    project_id,
                    request.chapter_number,
                    idx + 1,
                    len(guardrail_result.violations),
                )
                guardrail_metadata["violations"] = [
                    {"type": v.type, "severity": v.severity, "description": v.description}
                    for v in guardrail_result.violations
                ]

                # 尝试自动修复
                violations_text = guardrails.format_violations_for_rewrite(guardrail_result)
                final_content = await _rewrite_with_guardrails(
                    llm_service=llm_service,
                    prompt_service=prompt_service,
                    original_text=normalized,
                    chapter_mission=chapter_mission,
                    violations_text=violations_text,
                    user_id=current_user.id,
                )
                if not final_content:
                    logger.warning(
                        "项目 %s 第 %s 章版本 %s 自动修复返回空内容，回退原始正文",
                        project_id,
                        request.chapter_number,
                        idx + 1,
                    )
                    final_content = normalized

            def _extract_text(value: object) -> Optional[str]:
                if not value:
                    return None
                if isinstance(value, str):
                    return value
                if isinstance(value, dict):
                    for key in (
                        "content",
                        "chapter_content",
                        "chapter_text",
                        "text",
                        "body",
                        "story",
                        "chapter",
                        "full_content",
                        "optimized_content",
                    ):
                        if value.get(key):
                            nested = _extract_text(value.get(key))
                            if nested:
                                return nested
                    return None
                if isinstance(value, list):
                    parts: List[str] = []
                    for item in value:
                        nested = _extract_text(item)
                        if nested and nested.strip():
                            parts.append(nested.strip())
                    if parts:
                        return "\n\n".join(parts)
                return None

            parsed_json = None
            extracted_text = None
            try:
                parsed_json = json.loads(final_content)
                extracted_text = _extract_text(parsed_json)
            except Exception:
                parsed_json = None

            resolved_content: Optional[str] = extracted_text
            if not resolved_content and isinstance(final_content, str):
                stripped = final_content.strip()
                if stripped:
                    looks_like_json = (
                        (stripped.startswith("{") and stripped.endswith("}"))
                        or (stripped.startswith("[") and stripped.endswith("]"))
                    )
                    # 若是 JSON 且无法提取正文，视为无效输出；避免把结构化包装写入正文。
                    if not looks_like_json or parsed_json is None:
                        resolved_content = stripped

            if not resolved_content:
                logger.error(
                    "项目 %s 第 %s 章版本 %s 未提取到正文: final_preview=%s",
                    project_id,
                    request.chapter_number,
                    idx + 1,
                    (final_content or "")[:400],
                )

            return {
                "content": resolved_content,
                "parsed_json": parsed_json,
                "guardrail": guardrail_metadata,
                "chapter_mission": chapter_mission,
            }
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception(
                "项目 %s 生成第 %s 章第 %s 个版本时发生异常: %s",
                project_id,
                request.chapter_number,
                idx + 1,
                exc,
            )
            raise HTTPException(
                status_code=500,
                detail=f"生成章节第 {idx + 1} 个版本时失败: {str(exc)[:200]}"
            )

    version_count = await _resolve_version_count(session)
    logger.info(
        "项目 %s 第 %s 章计划生成 %s 个版本",
        project_id,
        request.chapter_number,
        version_count,
    )
    await _update_generation_progress(
        progress=55,
        step="draft_generation",
        step_index=4,
        step_meta={"v": f"0/{version_count}"},
    )

    # 版本差异化风格提示
    version_style_hints = [
        "情绪更细腻，节奏更慢，多写内心戏和感官描写",
        "冲突更强，节奏更快，多写动作和对话",
        "悬念更重，多埋伏笔，结尾钩子更强",
    ]

    raw_versions = []
    total_guardrail_violations = 0
    try:
        for idx in range(version_count):
            style_hint = version_style_hints[idx] if idx < len(version_style_hints) else None
            before_progress = 55 + int((idx / max(version_count, 1)) * 25)
            await _update_generation_progress(
                progress=before_progress,
                step="draft_generation",
                step_index=4,
                step_meta={"v": f"{idx + 1}/{version_count}", "p": "gen"},
            )
            version_payload = await _generate_single_version(idx, style_hint)
            raw_versions.append(version_payload)
            guardrail_count = 0
            if isinstance(version_payload, dict):
                guardrail_meta = version_payload.get("guardrail")
                if isinstance(guardrail_meta, dict):
                    violations = guardrail_meta.get("violations")
                    if isinstance(violations, list):
                        guardrail_count = len(violations)
            total_guardrail_violations += guardrail_count
            after_progress = 55 + int(((idx + 1) / max(version_count, 1)) * 25)
            await _update_generation_progress(
                progress=after_progress,
                step="draft_generation",
                step_index=4,
                step_meta={"v": f"{idx + 1}/{version_count}", "g": guardrail_count},
            )
    except Exception as exc:
        logger.exception("项目 %s 生成第 %s 章时发生异常: %s", project_id, request.chapter_number, exc)
        chapter.status = "failed"
        chapter.generation_progress = 0
        chapter.generation_step = "failed"
        chapter.generation_step_index = 0
        chapter.generation_step_total = generation_step_total
        await session.commit()
        if isinstance(exc, HTTPException):
            raise exc
        raise HTTPException(
            status_code=500,
            detail=f"生成章节失败: {str(exc)[:200]}"
        )

    await _update_generation_progress(
        progress=82,
        step="draft_generation",
        step_index=4,
        step_meta={"v": f"{version_count}/{version_count}", "g": total_guardrail_violations},
    )

    contents: List[str] = []
    metadata: List[Dict] = []
    minimum_acceptable_word_count = int(minimum_word_count * 0.85)
    for version_idx, variant in enumerate(raw_versions, start=1):
        if isinstance(variant, dict):
            candidate = variant.get("content")
            if isinstance(candidate, str):
                candidate = candidate.strip()
            if not candidate and "chapter_content" in variant and variant["chapter_content"]:
                candidate = str(variant["chapter_content"]).strip()
            if not candidate:
                logger.error(
                    "项目 %s 第 %s 章版本 %s 生成结果缺少正文内容，metadata_keys=%s",
                    project_id,
                    request.chapter_number,
                    version_idx,
                    list(variant.keys()),
                )
                chapter.status = "failed"
                chapter.generation_progress = 0
                chapter.generation_step = "failed"
                chapter.generation_step_index = 0
                chapter.generation_step_total = generation_step_total
                await session.commit()
                raise HTTPException(
                    status_code=502,
                    detail=f"生成章节第 {version_idx} 个版本失败：模型未返回有效正文，请重试。",
                )
            candidate = await _expand_chapter_to_minimum_word_count(
                llm_service=llm_service,
                content=candidate,
                minimum_word_count=minimum_word_count,
                target_word_count=target_word_count,
                user_id=current_user.id,
                project_id=project_id,
                chapter_number=request.chapter_number,
                version_index=version_idx,
            )
            candidate = await _compress_chapter_to_word_limit(
                llm_service=llm_service,
                content=candidate,
                target_word_count=target_word_count,
                user_id=current_user.id,
                project_id=project_id,
                chapter_number=request.chapter_number,
                version_index=version_idx,
            )
            candidate_word_count = count_chapter_words(candidate)
            if candidate_word_count < minimum_acceptable_word_count:
                logger.error(
                    "项目 %s 第 %s 章版本 %s 字数严重不足，终止入库: actual=%s minimum=%s acceptable=%s target=%s",
                    project_id,
                    request.chapter_number,
                    version_idx,
                    candidate_word_count,
                    minimum_word_count,
                    minimum_acceptable_word_count,
                    target_word_count,
                )
                chapter.status = "failed"
                chapter.generation_progress = 0
                chapter.generation_step = "failed"
                chapter.generation_step_index = 0
                chapter.generation_step_total = generation_step_total
                await session.commit()
                raise HTTPException(
                    status_code=502,
                    detail=(
                        f"生成章节第 {version_idx} 个版本失败：字数仅 {candidate_word_count}，"
                        f"低于最低要求 {minimum_word_count}（容错阈值 {minimum_acceptable_word_count}）。请重试。"
                    ),
                )
            contents.append(candidate)
            variant["word_limit"] = {
                "target": target_word_count,
                "minimum": minimum_word_count,
                "actual": candidate_word_count,
            }
            metadata.append(variant)
        else:
            text = str(variant).strip()
            if not text:
                chapter.status = "failed"
                chapter.generation_progress = 0
                chapter.generation_step = "failed"
                chapter.generation_step_index = 0
                chapter.generation_step_total = generation_step_total
                await session.commit()
                raise HTTPException(
                    status_code=502,
                    detail=f"生成章节第 {version_idx} 个版本失败：模型返回空内容，请重试。",
                )
            text = await _expand_chapter_to_minimum_word_count(
                llm_service=llm_service,
                content=text,
                minimum_word_count=minimum_word_count,
                target_word_count=target_word_count,
                user_id=current_user.id,
                project_id=project_id,
                chapter_number=request.chapter_number,
                version_index=version_idx,
            )
            text = await _compress_chapter_to_word_limit(
                llm_service=llm_service,
                content=text,
                target_word_count=target_word_count,
                user_id=current_user.id,
                project_id=project_id,
                chapter_number=request.chapter_number,
                version_index=version_idx,
            )
            text_word_count = count_chapter_words(text)
            if text_word_count < minimum_acceptable_word_count:
                logger.error(
                    "项目 %s 第 %s 章版本 %s 字数严重不足，终止入库: actual=%s minimum=%s acceptable=%s target=%s",
                    project_id,
                    request.chapter_number,
                    version_idx,
                    text_word_count,
                    minimum_word_count,
                    minimum_acceptable_word_count,
                    target_word_count,
                )
                chapter.status = "failed"
                chapter.generation_progress = 0
                chapter.generation_step = "failed"
                chapter.generation_step_index = 0
                chapter.generation_step_total = generation_step_total
                await session.commit()
                raise HTTPException(
                    status_code=502,
                    detail=(
                        f"生成章节第 {version_idx} 个版本失败：字数仅 {text_word_count}，"
                        f"低于最低要求 {minimum_word_count}（容错阈值 {minimum_acceptable_word_count}）。请重试。"
                    ),
                )
            contents.append(text)
            metadata.append({
                "raw": variant,
                "word_limit": {
                    "target": target_word_count,
                    "minimum": minimum_word_count,
                    "actual": text_word_count,
                },
            })

    # ========== 8. AI Review: 自动评审多版本 ==========
    await _update_generation_progress(
        progress=86,
        step="quality_review",
        step_index=5,
        step_meta={"v": len(contents)},
    )
    ai_review_result = None
    if len(contents) > 1:
        try:
            ai_review_service = AIReviewService(llm_service, prompt_service)
            ai_review_result = await ai_review_service.review_versions(
                versions=contents,
                chapter_mission=chapter_mission,
                user_id=current_user.id,
            )
            if ai_review_result:
                logger.info(
                    "项目 %s 第 %s 章 AI 评审完成: 推荐版本=%s",
                    project_id,
                    request.chapter_number,
                    ai_review_result.best_version_index,
                )
                # 将评审结果附加到 metadata
                for i, m in enumerate(metadata):
                    m["ai_review"] = {
                        "is_best": i == ai_review_result.best_version_index,
                        "scores": ai_review_result.scores,
                        "evaluation": ai_review_result.overall_evaluation if i == ai_review_result.best_version_index else None,
                        "flaws": ai_review_result.critical_flaws if i == ai_review_result.best_version_index else None,
                        "suggestions": ai_review_result.refinement_suggestions if i == ai_review_result.best_version_index else None,
                    }
        except Exception as exc:
            logger.warning("AI 评审失败，跳过: %s", exc)

    await _update_generation_progress(
        progress=96,
        step="persist_versions",
        step_index=6,
        step_meta={"v": len(contents)},
    )
    try:
        await novel_service.replace_chapter_versions(chapter, contents, metadata)
    except Exception as exc:
        logger.exception("项目 %s 第 %s 章写入版本失败: %s", project_id, request.chapter_number, exc)
        chapter.status = "failed"
        chapter.generation_progress = 0
        chapter.generation_step = "failed"
        chapter.generation_step_index = 0
        chapter.generation_step_total = generation_step_total
        await session.commit()
        raise HTTPException(status_code=500, detail="章节版本写入失败，请重试。")
    logger.info(
        "项目 %s 第 %s 章生成完成，已写入 %s 个版本",
        project_id,
        request.chapter_number,
        len(contents),
    )
    try:
        return await _load_project_schema(novel_service, project_id, current_user.id)
    except HTTPException:
        await _mark_generation_failed()
        raise
    except Exception as exc:
        logger.exception(
            "项目 %s 第 %s 章生成后加载项目状态失败: %s",
            project_id,
            request.chapter_number,
            exc,
        )
        await _mark_generation_failed()
        raise HTTPException(status_code=500, detail="章节已生成，但刷新项目状态失败，请重试") from exc


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


@router.post("/novels/{project_id}/chapters/outline", response_model=NovelProjectSchema)
async def generate_chapters_outline(
    project_id: str,
    request: GenerateOutlineRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> NovelProjectSchema:
    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(project_id, current_user.id)

    # 获取蓝图信息
    project_schema = await novel_service._serialize_project(project)
    blueprint_text = json.dumps(project_schema.blueprint.model_dump(), ensure_ascii=False, indent=2)

    # 获取已有的章节大纲
    existing_outlines = [
        f"第{o.chapter_number}章 - {o.title}: {o.summary}"
        for o in sorted(project.outlines, key=lambda x: x.chapter_number)
    ]
    existing_outlines_text = "\n".join(existing_outlines) if existing_outlines else "暂无"

    outline_prompt = await prompt_service.get_prompt("outline_generation")
    if not outline_prompt:
        raise HTTPException(status_code=500, detail="未配置大纲生成提示词")

    prompt_input = f"""
[世界蓝图]
{blueprint_text}

[已有章节大纲]
{existing_outlines_text}

[生成任务]
请从第 {request.start_chapter} 章开始，续写接下来的 {request.num_chapters} 章的大纲。
要求返回 JSON 格式，包含一个 chapters 数组，每个元素包含 chapter_number, title, summary。
"""

    response = await llm_service.get_llm_response(
        system_prompt=outline_prompt,
        conversation_history=[{"role": "user", "content": prompt_input}],
        temperature=0.7,
        user_id=current_user.id,
        stage="chapter_outline",
    )

    cleaned = remove_think_tags(response)
    normalized = unwrap_markdown_json(cleaned)
    try:
        data = json.loads(normalized)
        new_outlines = data.get("chapters", [])
        for item in new_outlines:
            await novel_service.update_or_create_outline(
                project_id,
                item["chapter_number"],
                item["title"],
                item["summary"]
            )
        await session.commit()
    except Exception as exc:
        logger.exception("生成大纲解析失败: %s", exc)
        raise HTTPException(status_code=500, detail=f"大纲生成失败: {str(exc)}")

    return await _load_project_schema(novel_service, project_id, current_user.id)


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
    chapter.word_count = len(request.content or "")
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
    chapter.word_count = len(request.content or "")
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
