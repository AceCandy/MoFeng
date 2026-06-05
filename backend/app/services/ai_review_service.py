# AIMETA P=AI评审服务_多版本对比选优|R=版本评分_最佳选择_改进建议|NR=不含数据存储|E=none|X=internal|A=评审_对比|D=openai|S=net|RD=./README.ai
"""
AIReviewService: AI 评审服务

核心职责：
1. 对多个生成版本进行对比评审
2. 基于当前作品上下文完成章节评审
3. 选出最佳版本并返回结构化结果
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..services.llm_service import LLMService
from ..services.prompt_service import PromptService
from ..utils.json_utils import remove_think_tags, unwrap_markdown_json

logger = logging.getLogger(__name__)


@dataclass
class VersionReview:
    """单个版本的评审结果"""

    version_number: int
    pros: List[str] = field(default_factory=list)
    cons: List[str] = field(default_factory=list)
    overall_review: str = ""
    scores: Dict[str, int] = field(default_factory=dict)


@dataclass
class ReviewResult:
    """评审结果"""

    best_version_index: int
    scores: Dict[str, int]
    overall_evaluation: str
    critical_flaws: List[str]
    refinement_suggestions: str
    final_recommendation: str
    version_reviews: List[VersionReview] = field(default_factory=list)
    raw_response: Optional[str] = None

    def to_evaluation_payload(self) -> Dict[str, Any]:
        """转换为前端兼容的章节评审结构。"""
        evaluation: Dict[str, Any] = {}
        for review in sorted(self.version_reviews, key=lambda item: item.version_number):
            evaluation[f"version{review.version_number}"] = {
                "pros": review.pros,
                "cons": review.cons,
                "overall_review": review.overall_review,
                "scores": review.scores,
            }

        return {
            "best_choice": self.best_version_index + 1,
            "reason_for_choice": self.final_recommendation or self.overall_evaluation,
            "evaluation": evaluation,
        }


class AIReviewService:
    """
    AI 评审服务。

    使用 editor_review / evaluation 提示词，基于当前作品上下文完成章节评审。
    """

    def __init__(self, llm_service: LLMService, prompt_service: PromptService):
        self.llm_service = llm_service
        self.prompt_service = prompt_service

    async def review_versions(
        self,
        versions: List[str],
        chapter_mission: Optional[dict] = None,
        user_id: int = 0,
        review_context: Optional[Dict[str, Any]] = None,
        strict: bool = False,
    ) -> Optional[ReviewResult]:
        """对多个版本进行评审，返回评审结果。"""
        if not versions:
            logger.warning("没有版本可供评审")
            if strict:
                raise RuntimeError("没有版本可供评审")
            return None

        if len(versions) == 1:
            logger.info("只有一个版本，跳过对比评审")
            version_review = VersionReview(
                version_number=1,
                pros=["唯一候选版本"],
                cons=[],
                overall_review="单版本，无需对比",
                scores={},
            )
            return ReviewResult(
                best_version_index=0,
                scores={},
                overall_evaluation="单版本，无需对比",
                critical_flaws=[],
                refinement_suggestions="",
                final_recommendation="采用唯一版本",
                version_reviews=[version_review],
            )

        review_prompt = await self.prompt_service.get_prompt("editor_review")
        if not review_prompt:
            logger.warning("未配置 editor_review 提示词，跳过 AI 评审")
            if strict:
                raise RuntimeError("缺少 editor_review 提示词，无法进行多版本评审")
            return None

        review_input = self._build_review_input(versions, chapter_mission, review_context)

        try:
            response = await self.llm_service.get_llm_response(
                system_prompt=review_prompt,
                conversation_history=[{"role": "user", "content": review_input}],
                temperature=0.3,
                user_id=user_id,
                timeout=180.0,
                stage="version_review",
            )
            cleaned = remove_think_tags(response)
            normalized = unwrap_markdown_json(cleaned)

            result = self._parse_review_response(normalized, versions)
            result.raw_response = cleaned

            logger.info("AI 评审完成: 最佳版本=%s", result.best_version_index)
            return result
        except Exception:
            logger.exception("AI 评审失败")
            if strict:
                raise
            return None

    async def review_single_version(
        self,
        version_content: str,
        user_id: int = 0,
        review_context: Optional[Dict[str, Any]] = None,
        strict: bool = False,
    ) -> Optional[str]:
        """对单个版本进行上下文化评审。"""
        if not version_content or not version_content.strip():
            logger.warning("单版本评审内容为空")
            if strict:
                raise RuntimeError("单版本评审内容为空")
            return None

        eval_prompt = await self.prompt_service.get_prompt("evaluation")
        if not eval_prompt:
            logger.warning("未配置 evaluation 提示词，跳过单版本 AI 评审")
            if strict:
                raise RuntimeError("缺少 evaluation 提示词，无法进行单版本评审")
            return None

        review_input = self._build_single_review_input(version_content, review_context)

        try:
            response = await self.llm_service.get_llm_response(
                system_prompt=eval_prompt,
                conversation_history=[{"role": "user", "content": review_input}],
                temperature=0.3,
                user_id=user_id,
                timeout=180.0,
                stage="version_review",
            )
            return remove_think_tags(response)
        except Exception:
            logger.exception("单版本 AI 评审失败")
            if strict:
                raise
            return None

    def _build_review_input(
        self,
        versions: List[str],
        chapter_mission: Optional[dict],
        review_context: Optional[Dict[str, Any]],
    ) -> str:
        """构建多版本评审输入文本。"""
        payload = self._build_base_context_payload(review_context)
        payload["chapter_mission"] = chapter_mission or payload.get("chapter_mission") or {}
        payload["candidate_versions"] = [
            {
                "version_number": index + 1,
                "content": self._truncate_text(content, limit=6000),
                "original_length": len(content or ""),
            }
            for index, content in enumerate(versions)
        ]
        payload["review_requirements"] = {
            "pick_exactly_one_best_version": True,
            "version_number_starts_at": 1,
            "return_version_local_analysis": True,
            "avoid_fabricated_fields": True,
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def _build_single_review_input(
        self,
        version_content: str,
        review_context: Optional[Dict[str, Any]],
    ) -> str:
        """构建单版本评审输入文本。"""
        payload = self._build_base_context_payload(review_context)
        payload["content_to_evaluate"] = {
            "version_number": 1,
            "content": self._truncate_text(version_content, limit=8000),
            "original_length": len(version_content or ""),
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    def _build_base_context_payload(self, review_context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        context = review_context or {}
        return {
            "novel_blueprint": context.get("novel_blueprint") or {},
            "chapter_outline": context.get("chapter_outline") or {},
            "chapter_blueprint": context.get("chapter_blueprint") or {},
            "chapter_mission": context.get("chapter_mission") or {},
            "project_memory": context.get("project_memory") or {},
            "constitution": context.get("constitution") or "",
            "writer_persona": context.get("writer_persona") or "",
            "previous_chapter": context.get("previous_chapter") or {},
            "completed_chapters": context.get("completed_chapters") or [],
            "pending_foreshadows": context.get("pending_foreshadows") or [],
            "related_chapters": context.get("related_chapters") or [],
            "active_plot_threads": context.get("active_plot_threads") or [],
        }

    def _parse_review_response(self, response: str, versions: List[str]) -> ReviewResult:
        """解析评审响应。"""
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            logger.warning("评审响应不是有效 JSON，使用默认结果")
            return self._build_fallback_result(response, versions)

        best_version_index = self._normalize_best_version_index(
            data.get("best_version_index"),
            data.get("best_version_number"),
            len(versions),
        )
        version_reviews = self._parse_version_reviews(data, len(versions))

        if not version_reviews:
            version_reviews = self._build_default_version_reviews(len(versions), best_version_index, data)

        aggregate_scores = self._extract_scores(data.get("scores"))
        if not aggregate_scores:
            best_review = next(
                (review for review in version_reviews if review.version_number == best_version_index + 1),
                None,
            )
            aggregate_scores = best_review.scores if best_review else {}

        critical_flaws = data.get("critical_flaws")
        if not isinstance(critical_flaws, list):
            critical_flaws = []

        return ReviewResult(
            best_version_index=best_version_index,
            scores=aggregate_scores,
            overall_evaluation=self._coerce_text(data.get("overall_evaluation")),
            critical_flaws=[self._coerce_text(item) for item in critical_flaws if self._coerce_text(item)],
            refinement_suggestions=self._coerce_text(data.get("refinement_suggestions")),
            final_recommendation=self._coerce_text(data.get("final_recommendation")),
            version_reviews=version_reviews,
        )

    def _build_fallback_result(self, response: str, versions: List[str]) -> ReviewResult:
        version_reviews = [
            VersionReview(
                version_number=index + 1,
                pros=[],
                cons=[],
                overall_review="AI 返回非结构化结果，建议人工复核",
                scores={},
            )
            for index in range(len(versions))
        ]
        return ReviewResult(
            best_version_index=0,
            scores={},
            overall_evaluation=response[:500] if response else "",
            critical_flaws=[],
            refinement_suggestions="",
            final_recommendation="解析失败，建议人工审核",
            version_reviews=version_reviews,
        )

    def _parse_version_reviews(self, data: Dict[str, Any], version_count: int) -> List[VersionReview]:
        raw_reviews = data.get("version_reviews")
        if not isinstance(raw_reviews, list):
            return []

        parsed_reviews: List[VersionReview] = []
        for item in raw_reviews:
            if not isinstance(item, dict):
                continue
            version_number = self._parse_version_number(item)
            if version_number is None or version_number < 1 or version_number > version_count:
                continue
            parsed_reviews.append(
                VersionReview(
                    version_number=version_number,
                    pros=self._normalize_string_list(item.get("pros")),
                    cons=self._normalize_string_list(item.get("cons")),
                    overall_review=self._coerce_text(item.get("overall_review")),
                    scores=self._extract_scores(item.get("scores")),
                )
            )

        parsed_reviews.sort(key=lambda item: item.version_number)
        seen = set()
        deduped: List[VersionReview] = []
        for review in parsed_reviews:
            if review.version_number in seen:
                continue
            seen.add(review.version_number)
            deduped.append(review)
        return deduped

    def _build_default_version_reviews(
        self,
        version_count: int,
        best_version_index: int,
        data: Dict[str, Any],
    ) -> List[VersionReview]:
        overall = self._coerce_text(data.get("overall_evaluation")) or "已参与多版本对比评审"
        recommendation = self._coerce_text(data.get("final_recommendation"))
        flaws = self._normalize_string_list(data.get("critical_flaws"))
        suggestions = self._coerce_text(data.get("refinement_suggestions"))
        reviews: List[VersionReview] = []
        for index in range(version_count):
            is_best = index == best_version_index
            cons = list(flaws) if is_best else []
            if is_best and suggestions:
                cons.append(suggestions)
            if not is_best and recommendation:
                cons.append(recommendation)
            reviews.append(
                VersionReview(
                    version_number=index + 1,
                    pros=[overall] if is_best and overall else [],
                    cons=cons,
                    overall_review=overall if is_best else "已参与多版本对比评审",
                    scores={},
                )
            )
        return reviews

    @staticmethod
    def _normalize_best_version_index(
        best_version_index: Any,
        best_version_number: Any,
        version_count: int,
    ) -> int:
        if isinstance(best_version_number, int) and 1 <= best_version_number <= version_count:
            return best_version_number - 1
        if isinstance(best_version_index, int):
            if 0 <= best_version_index < version_count:
                return best_version_index
            if 1 <= best_version_index <= version_count:
                return best_version_index - 1
        return 0

    def _parse_version_number(self, item: Dict[str, Any]) -> Optional[int]:
        candidates = [item.get("version_number"), item.get("version_index"), item.get("version")]
        for value in candidates:
            if isinstance(value, int):
                if value >= 1:
                    return value
                return value + 1
            if isinstance(value, str) and value.isdigit():
                number = int(value)
                if number >= 1:
                    return number
        return None

    @staticmethod
    def _extract_scores(raw_scores: Any) -> Dict[str, int]:
        if not isinstance(raw_scores, dict):
            return {}
        normalized: Dict[str, int] = {}
        for key, value in raw_scores.items():
            if isinstance(value, (int, float)):
                normalized[str(key)] = int(value)
        return normalized

    def _normalize_string_list(self, value: Any) -> List[str]:
        if not isinstance(value, list):
            return []
        results = []
        for item in value:
            text = self._coerce_text(item)
            if text:
                results.append(text)
        return results

    @staticmethod
    def _coerce_text(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, (int, float, bool)):
            return str(value)
        if isinstance(value, (dict, list)):
            try:
                return json.dumps(value, ensure_ascii=False)
            except TypeError:
                return ""
        return ""

    @staticmethod
    def _truncate_text(content: str, limit: int) -> str:
        if len(content) <= limit:
            return content
        return f"{content[:limit]}\n\n...(已截断，原文共 {len(content)} 字)"

    async def auto_select_best_version(
        self,
        versions: List[str],
        chapter_mission: Optional[dict] = None,
        user_id: int = 0,
        review_context: Optional[Dict[str, Any]] = None,
    ) -> int:
        """自动选择最佳版本的索引。"""
        result = await self.review_versions(
            versions,
            chapter_mission=chapter_mission,
            user_id=user_id,
            review_context=review_context,
        )
        if result:
            return result.best_version_index
        return 0
