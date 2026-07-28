# AIMETA P=章节伏笔同步服务_规则与模型判定|R=候选计算_状态判定_事务应用|NR=不持有HTTP或任务状态|E=ForeshadowingSyncService|X=internal|A=服务类|D=sqlalchemy,llm|S=db,net|RD=./README.ai
from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import re
from typing import Awaitable, Callable, Dict, List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import AsyncSessionLocal
from ..models.foreshadowing import Foreshadowing, ForeshadowingStatusHistory
from ..models.novel import Chapter
from ..utils.json_utils import remove_think_tags, unwrap_markdown_json
from .llm_service import LLMService
from .prompt_service import PromptService

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


@dataclass(frozen=True)
class ActiveForeshadowingSnapshot:
    """模型判定时使用的历史伏笔不可变快照。"""

    id: int
    status: str
    content: str
    keywords: List[str]


@dataclass(frozen=True)
class ForeshadowingComputeContext:
    """短事务读取后可脱离数据库会话的伏笔计算输入。"""

    chapter_number: int
    content: str
    rule_candidates: List[dict]
    active: List[ActiveForeshadowingSnapshot]
    candidate_prompt: Optional[str]
    status_prompt: Optional[str]


@dataclass(frozen=True)
class ForeshadowingLLMRequest:
    """一次伏笔模型调用的纯数据请求。"""

    activity_key: str
    system_prompt: str
    user_prompt: str
    max_tokens: int = 1200


@dataclass(frozen=True)
class ForeshadowingPlan:
    """等待在数据库事务中应用的伏笔变更计划。"""

    candidates: List[dict]
    active: List[ActiveForeshadowingSnapshot]
    status_decisions: Dict[int, str]


ForeshadowingLLMCall = Callable[[ForeshadowingLLMRequest], Awaitable[str]]


def serialize_foreshadowing_plan(plan: ForeshadowingPlan) -> dict:
    """把不可变计算结果保存到 typed projection run。"""

    return {
        "candidates": list(plan.candidates),
        "active": [
            {
                "id": item.id,
                "status": item.status,
                "content": item.content,
                "keywords": list(item.keywords),
            }
            for item in plan.active
        ],
        "status_decisions": {
            str(item_id): decision for item_id, decision in plan.status_decisions.items()
        },
    }


def serialize_foreshadowing_context(context: ForeshadowingComputeContext) -> dict:
    """冻结 projection 计算基线，避免 legacy owner 先提交导致输入漂移。"""

    return {
        "chapter_number": context.chapter_number,
        "content": context.content,
        "rule_candidates": list(context.rule_candidates),
        "active": [
            {
                "id": item.id,
                "status": item.status,
                "content": item.content,
                "keywords": list(item.keywords),
            }
            for item in context.active
        ],
        "candidate_prompt": context.candidate_prompt,
        "status_prompt": context.status_prompt,
    }


def deserialize_foreshadowing_context(payload: dict) -> ForeshadowingComputeContext:
    """恢复 canonical revision 中保存的伏笔计算基线。"""

    return ForeshadowingComputeContext(
        chapter_number=int(payload["chapter_number"]),
        content=str(payload.get("content") or ""),
        rule_candidates=list(payload.get("rule_candidates") or []),
        active=[
            ActiveForeshadowingSnapshot(
                id=int(item["id"]),
                status=str(item["status"]),
                content=str(item.get("content") or ""),
                keywords=list(item.get("keywords") or []),
            )
            for item in payload.get("active", [])
            if isinstance(item, dict) and item.get("id") is not None
        ],
        candidate_prompt=payload.get("candidate_prompt"),
        status_prompt=payload.get("status_prompt"),
    )


def deserialize_foreshadowing_plan(payload: dict) -> ForeshadowingPlan:
    """恢复已持久化的伏笔计划，供 cutover 原子提升。"""

    active = [
        ActiveForeshadowingSnapshot(
            id=int(item["id"]),
            status=str(item["status"]),
            content=str(item.get("content") or ""),
            keywords=list(item.get("keywords") or []),
        )
        for item in payload.get("active", [])
        if isinstance(item, dict) and item.get("id") is not None
    ]
    return ForeshadowingPlan(
        candidates=list(payload.get("candidates") or []),
        active=active,
        status_decisions={
            int(item_id): str(decision)
            for item_id, decision in dict(payload.get("status_decisions") or {}).items()
        },
    )


def _normalize_snippet(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip()
    return normalized.strip("，。！？!?；;：:、 ")


def _extract_keyword_anchors(text: str, max_count: int = 8) -> List[str]:
    anchors: List[str] = []
    seen = set()
    for token in re.findall(r"[\u4e00-\u9fff]{2,6}", text):
        if token in _KEYWORD_STOPWORDS or token in seen:
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
    raw_sentences = re.findall(r"[^。！？!?;\n]{6,120}[。！？!?;]?", text)
    sentences: List[str] = []
    for raw in raw_sentences:
        sentence = re.sub(r"\s+", " ", raw).strip()
        if 10 <= len(sentence) <= 90:
            sentences.append(sentence)
    return sentences


def extract_foreshadowing_candidates(content: str) -> List[dict]:
    """按精度优先规则抽取单章自动伏笔候选。"""

    normalized_content = re.sub(r"\s+", " ", content or "").strip()
    if not normalized_content:
        return []

    candidates: List[dict] = []
    seen_snippets = set()
    type_counter = {key: 0 for key in _TYPE_LIMITS}

    def add_candidate(
        snippet: str,
        foreshadowing_type: str,
        confidence: float,
        importance: str,
        keywords: List[str],
    ) -> None:
        if type_counter.get(foreshadowing_type, 0) >= _TYPE_LIMITS.get(foreshadowing_type, 1):
            return
        normalized_snippet = _normalize_snippet(snippet)
        if len(normalized_snippet) < 10:
            return
        dedupe_key = normalized_snippet[:120]
        if dedupe_key in seen_snippets:
            return
        seen_snippets.add(dedupe_key)
        merged_keywords = keywords[:] or _extract_keyword_anchors(normalized_snippet, max_count=6)
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

    sentences = _split_candidate_sentences(normalized_content)
    for sentence in sentences:
        cue_hits = [keyword for keyword in _QUESTION_CUES if keyword in sentence]
        if ("？" in sentence or "?" in sentence) and cue_hits:
            add_candidate(sentence, "question", 0.74, "major", cue_hits[:3])
        if len(candidates) >= LLM_FORESHADOWING_REVIEW_LIMIT:
            return candidates[:LLM_FORESHADOWING_REVIEW_LIMIT]

    for sentence in sentences:
        for rule in _FORESHADOWING_RULES:
            if rule["type"] == "question":
                continue
            matched = [keyword for keyword in rule["keywords"] if keyword in sentence]
            if not matched:
                continue
            if rule["type"] == "mystery":
                strong = [keyword for keyword in matched if keyword in _MYSTERY_STRONG_CUES]
                question = ("？" in sentence or "?" in sentence) and any(
                    cue in sentence for cue in _QUESTION_CUES
                )
                if not ((strong and len(matched) >= 2) or (question and strong)):
                    continue
            if rule["type"] in {"clue", "setup"}:
                strong_markers = {"线索", "伏笔", "悬念"}
                if len(matched) < 2 and not any(marker in matched for marker in strong_markers):
                    continue
            add_candidate(
                sentence,
                rule["type"],
                rule["confidence"],
                rule["importance"],
                matched[:4],
            )
            if len(candidates) >= LLM_FORESHADOWING_REVIEW_LIMIT:
                return candidates[:LLM_FORESHADOWING_REVIEW_LIMIT]
    return candidates[:LLM_FORESHADOWING_REVIEW_LIMIT]


def _contains_any(text: str, needles: List[str]) -> bool:
    return any(needle and needle in text for needle in needles)


def _rule_status(content: str, item: ActiveForeshadowingSnapshot) -> str:
    anchors = [keyword for keyword in item.keywords if isinstance(keyword, str) and len(keyword) >= 2]
    if not anchors:
        anchors = _extract_keyword_anchors(item.content, max_count=6)
    if _contains_any(content, _PAYOFF_MARKERS) and anchors and _contains_any(content, anchors):
        return "revealed"
    if item.status == "planted" and (
        (anchors and _contains_any(content, anchors)) or _contains_any(content, _REINFORCE_MARKERS)
    ):
        return "developing"
    return "unchanged"


class ForeshadowingSyncService:
    """把伏笔计算与最终事务写入分开，供 HTTP 与 durable job 共用。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def load_compute_context(
        self,
        *,
        project_id: str,
        chapter_number: int,
        content: str,
    ) -> ForeshadowingComputeContext:
        normalized = (content or "").strip()
        candidates = extract_foreshadowing_candidates(normalized) if normalized else []
        active: List[ActiveForeshadowingSnapshot] = []
        if normalized:
            rows = (
                await self.session.execute(
                    select(Foreshadowing).where(
                        Foreshadowing.project_id == project_id,
                        Foreshadowing.chapter_number < chapter_number,
                        Foreshadowing.is_active.is_(True),
                        Foreshadowing.status.in_(["planted", "developing", "partial"]),
                    )
                )
            ).scalars().all()
            active = [
                ActiveForeshadowingSnapshot(
                    id=item.id,
                    status=item.status,
                    content=item.content,
                    keywords=list(item.keywords or []),
                )
                for item in rows[:LLM_FORESHADOWING_ACTIVE_LIMIT]
            ]

        prompt_service = PromptService(self.session)
        candidate_prompt = (
            await prompt_service.get_prompt("foreshadowing_candidate_review")
            if candidates
            else None
        )
        status_prompt = (
            await prompt_service.get_prompt("foreshadowing_status_judge")
            if active
            else None
        )
        return ForeshadowingComputeContext(
            chapter_number=chapter_number,
            content=normalized,
            rule_candidates=candidates,
            active=active,
            candidate_prompt=candidate_prompt,
            status_prompt=status_prompt,
        )

    @classmethod
    async def compute_plan(
        cls,
        context: ForeshadowingComputeContext,
        *,
        llm_call: ForeshadowingLLMCall,
        tolerate_llm_errors: bool,
    ) -> ForeshadowingPlan:
        candidates = context.rule_candidates[:MAX_AUTO_FORESHADOWINGS_PER_CHAPTER]
        if context.rule_candidates and context.candidate_prompt:
            request = cls._candidate_request(context)
            try:
                response = await llm_call(request)
            except Exception as exc:
                if not tolerate_llm_errors:
                    raise
                logger.warning("LLM 伏笔候选精筛失败，使用规则候选: %s", exc)
            else:
                candidates = cls._parse_candidate_response(response, context.rule_candidates)

        model_decisions: Dict[int, str] = {}
        if context.active and context.status_prompt:
            request = cls._status_request(context)
            try:
                response = await llm_call(request)
            except Exception as exc:
                if not tolerate_llm_errors:
                    raise
                logger.warning("LLM 伏笔状态判定失败，使用规则状态: %s", exc)
            else:
                model_decisions = cls._parse_status_response(response, context.active)

        decisions = {
            item.id: model_decisions.get(item.id) or _rule_status(context.content, item)
            for item in context.active
        }
        return ForeshadowingPlan(
            candidates=candidates,
            active=context.active,
            status_decisions=decisions,
        )

    async def apply_plan(
        self,
        *,
        project_id: str,
        chapter: Chapter,
        plan: ForeshadowingPlan,
        chapter_revision: int = 0,
        artifact_generation: str = "legacy",
        projection_run_id: Optional[str] = None,
        activate: bool = True,
    ) -> dict:
        """写入计划；shadow 只落 inactive candidate，不触碰 active owner。"""

        if activate:
            await self.session.execute(
                update(Foreshadowing)
                .where(
                    Foreshadowing.project_id == project_id,
                    Foreshadowing.chapter_id == chapter.id,
                    Foreshadowing.is_manual.is_(False),
                    Foreshadowing.is_active.is_(True),
                )
                .values(is_active=False)
            )
        reveal_offset = {"major": 8, "minor": 4, "subtle": 12}
        for candidate in plan.candidates:
            self.session.add(
                Foreshadowing(
                    project_id=project_id,
                    chapter_id=chapter.id,
                    chapter_number=chapter.chapter_number,
                    chapter_revision=chapter_revision,
                    artifact_generation=artifact_generation,
                    projection_run_id=projection_run_id,
                    is_active=activate,
                    content=candidate["content"],
                    type=candidate["type"],
                    keywords=candidate["keywords"],
                    status="planted",
                    target_reveal_chapter=chapter.chapter_number
                    + reveal_offset.get(candidate["importance"], 6),
                    name=_build_auto_foreshadowing_name(candidate["content"], candidate["type"]),
                    importance=candidate["importance"],
                    is_manual=False,
                    ai_confidence=candidate["confidence"],
                )
            )

        revealed_count = 0
        developing_count = 0
        if activate:
            revealed_count, developing_count = await self._apply_status_decisions(
                project_id=project_id,
                chapter=chapter,
                plan=plan,
                chapter_revision=chapter_revision,
                artifact_generation=artifact_generation,
                projection_run_id=projection_run_id,
            )

        return {
            "created": len(plan.candidates),
            "revealed": revealed_count,
            "developing": developing_count,
        }

    async def promote_staged_plan(
        self,
        *,
        project_id: str,
        chapter: Chapter,
        plan_payload: dict,
        chapter_revision: int,
        artifact_generation: str,
        projection_run_id: str,
    ) -> dict:
        """在 cutover 事务内提升已写入的 candidate，并应用延迟状态变更。"""

        plan = deserialize_foreshadowing_plan(plan_payload)
        await self.session.execute(
            update(Foreshadowing)
            .where(
                Foreshadowing.project_id == project_id,
                Foreshadowing.chapter_id == chapter.id,
                Foreshadowing.is_manual.is_(False),
                Foreshadowing.is_active.is_(True),
            )
            .values(is_active=False)
        )
        staged = list(
            (
                await self.session.execute(
                    select(Foreshadowing)
                    .where(
                        Foreshadowing.project_id == project_id,
                        Foreshadowing.chapter_id == chapter.id,
                        Foreshadowing.chapter_revision == chapter_revision,
                        Foreshadowing.artifact_generation == artifact_generation,
                        Foreshadowing.projection_run_id == projection_run_id,
                        Foreshadowing.is_active.is_(False),
                    )
                    .with_for_update()
                )
            ).scalars().all()
        )
        for item in staged:
            item.is_active = True
        revealed_count, developing_count = await self._apply_status_decisions(
            project_id=project_id,
            chapter=chapter,
            plan=plan,
            chapter_revision=chapter_revision,
            artifact_generation=artifact_generation,
            projection_run_id=projection_run_id,
        )
        return {
            "created": len(staged),
            "revealed": revealed_count,
            "developing": developing_count,
        }

    async def _apply_status_decisions(
        self,
        *,
        project_id: str,
        chapter: Chapter,
        plan: ForeshadowingPlan,
        chapter_revision: int,
        artifact_generation: str,
        projection_run_id: Optional[str],
    ) -> tuple[int, int]:
        active_ids = [item.id for item in plan.active]
        if not active_ids:
            return 0, 0
        rows = (
            await self.session.execute(
                select(Foreshadowing)
                .where(
                    Foreshadowing.project_id == project_id,
                    Foreshadowing.id.in_(active_ids),
                    Foreshadowing.is_active.is_(True),
                )
                .with_for_update()
            )
        ).scalars().all()
        active_by_id = {item.id: item for item in rows}

        revealed_count = 0
        developing_count = 0
        for source in plan.active:
            current = active_by_id.get(source.id)
            if current is None or current.status != source.status:
                continue
            decision = plan.status_decisions.get(source.id, "unchanged")
            if decision == "revealed":
                current.status = "revealed"
                current.resolved_chapter_id = chapter.id
                current.resolved_chapter_number = chapter.chapter_number
                self.session.add(
                    ForeshadowingStatusHistory(
                        foreshadowing_id=current.id,
                        old_status=source.status,
                        new_status="revealed",
                        chapter_number=chapter.chapter_number,
                        chapter_revision=chapter_revision,
                        artifact_generation=artifact_generation,
                        projection_run_id=projection_run_id,
                        reason="语义判定本章已回收该伏笔",
                    )
                )
                revealed_count += 1
            elif source.status == "planted" and decision == "developing":
                current.status = "developing"
                self.session.add(
                    ForeshadowingStatusHistory(
                        foreshadowing_id=current.id,
                        old_status="planted",
                        new_status="developing",
                        chapter_number=chapter.chapter_number,
                        chapter_revision=chapter_revision,
                        artifact_generation=artifact_generation,
                        projection_run_id=projection_run_id,
                        reason="语义判定本章继续推进该伏笔",
                    )
                )
                developing_count += 1
        return revealed_count, developing_count

    async def sync_chapter(
        self,
        *,
        project_id: str,
        chapter: Chapter,
        content: str,
        user_id: Optional[int],
        session_factory=AsyncSessionLocal,
    ) -> dict:
        """兼容同步调用方；模型等待期间不持有数据库事务。"""

        context = await self.load_compute_context(
            project_id=project_id,
            chapter_number=chapter.chapter_number,
            content=content,
        )
        await self.session.commit()

        async def call_model(request: ForeshadowingLLMRequest) -> str:
            return await LLMService.get_llm_response_detached(
                system_prompt=request.system_prompt,
                conversation_history=[{"role": "user", "content": request.user_prompt}],
                session_factory=session_factory,
                temperature=0.1,
                user_id=user_id,
                timeout=90.0,
                response_format="json_object",
                max_tokens=request.max_tokens,
                stage="foreshadowing",
            )

        plan = await self.compute_plan(
            context,
            llm_call=call_model,
            tolerate_llm_errors=True,
        )
        stats = await self.apply_plan(project_id=project_id, chapter=chapter, plan=plan)
        await self.session.commit()
        return stats

    @staticmethod
    def _candidate_request(context: ForeshadowingComputeContext) -> ForeshadowingLLMRequest:
        payload = [
            {
                "id": index,
                "content": item["content"],
                "type": item["type"],
                "keywords": item.get("keywords") or [],
                "importance": item.get("importance") or "minor",
                "confidence": item.get("confidence") or 0.5,
            }
            for index, item in enumerate(context.rule_candidates[:LLM_FORESHADOWING_REVIEW_LIMIT])
        ]
        return ForeshadowingLLMRequest(
            activity_key="foreshadowing_candidate_review",
            system_prompt=context.candidate_prompt or "",
            user_prompt=json.dumps(
                {
                    "chapter_number": context.chapter_number,
                    "max_items": MAX_AUTO_FORESHADOWINGS_PER_CHAPTER,
                    "candidates": payload,
                    "content_excerpt": context.content[:4000],
                },
                ensure_ascii=False,
            ),
        )

    @staticmethod
    def _status_request(context: ForeshadowingComputeContext) -> ForeshadowingLLMRequest:
        return ForeshadowingLLMRequest(
            activity_key="foreshadowing_status_judge",
            system_prompt=context.status_prompt or "",
            user_prompt=json.dumps(
                {
                    "chapter_number": context.chapter_number,
                    "content_excerpt": context.content[:5000],
                    "foreshadowings": [
                        {
                            "id": item.id,
                            "status": item.status,
                            "content": item.content,
                            "keywords": item.keywords,
                        }
                        for item in context.active
                    ],
                },
                ensure_ascii=False,
            ),
        )

    @staticmethod
    def _parse_candidate_response(response: str, candidates: List[dict]) -> List[dict]:
        try:
            data = json.loads(unwrap_markdown_json(remove_think_tags(response)))
        except (TypeError, ValueError, json.JSONDecodeError):
            return candidates[:MAX_AUTO_FORESHADOWINGS_PER_CHAPTER]
        raw_items = data.get("items") if isinstance(data, dict) else None
        if not isinstance(raw_items, list):
            return candidates[:MAX_AUTO_FORESHADOWINGS_PER_CHAPTER]

        limited = candidates[:LLM_FORESHADOWING_REVIEW_LIMIT]
        refined: List[dict] = []
        seen_ids = set()
        for item in raw_items:
            if not isinstance(item, dict) or not item.get("keep"):
                continue
            item_id = item.get("id")
            if not isinstance(item_id, int) or item_id in seen_ids or not 0 <= item_id < len(limited):
                continue
            seen_ids.add(item_id)
            source = limited[item_id]
            keywords = [
                keyword.strip()
                for keyword in item.get("keywords", [])
                if isinstance(keyword, str) and 2 <= len(keyword.strip()) <= 8
            ][:5]
            confidence = item.get("confidence")
            if not isinstance(confidence, (int, float)):
                confidence = source.get("confidence") or 0.5
            refined.append(
                {
                    "content": source["content"],
                    "type": item.get("type")
                    if item.get("type") in {"mystery", "question", "clue", "setup"}
                    else source["type"],
                    "keywords": keywords
                    or source.get("keywords")
                    or _extract_keyword_anchors(source["content"], max_count=5),
                    "importance": item.get("importance")
                    if item.get("importance") in {"major", "minor", "subtle"}
                    else source.get("importance", "minor"),
                    "confidence": max(0.0, min(1.0, float(confidence))),
                }
            )
            if len(refined) >= MAX_AUTO_FORESHADOWINGS_PER_CHAPTER:
                break
        return refined

    @staticmethod
    def _parse_status_response(
        response: str,
        active: List[ActiveForeshadowingSnapshot],
    ) -> Dict[int, str]:
        try:
            data = json.loads(unwrap_markdown_json(remove_think_tags(response)))
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        raw_items = data.get("items") if isinstance(data, dict) else None
        if not isinstance(raw_items, list):
            return {}
        valid_ids = {item.id for item in active}
        decisions: Dict[int, str] = {}
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            item_id = item.get("id")
            status = item.get("status")
            if isinstance(item_id, int) and item_id in valid_ids and status in {
                "revealed",
                "developing",
                "unchanged",
            }:
                decisions[item_id] = status
        return decisions


__all__ = [
    "ForeshadowingComputeContext",
    "ForeshadowingLLMRequest",
    "ForeshadowingPlan",
    "ForeshadowingSyncService",
    "deserialize_foreshadowing_context",
    "deserialize_foreshadowing_plan",
    "extract_foreshadowing_candidates",
    "serialize_foreshadowing_context",
    "serialize_foreshadowing_plan",
]
