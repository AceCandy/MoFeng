"""
预演-正式两阶段生成服务

先生成章节预览（500字），确认方向后再扩写成完整章节。
"""

import json
import logging
from typing import Any, Dict, List

from sqlalchemy.ext.asyncio import AsyncSession

from .llm_service import LLMService
from .model_response_parser import parse_chapter_content_response
from .prompt_service import PromptService

logger = logging.getLogger(__name__)


class PreviewGenerationService:
    """预演-正式两阶段生成服务"""

    def __init__(self, db: AsyncSession, llm_service: LLMService, prompt_service: PromptService):
        self.db = db
        self.llm_service = llm_service
        self.prompt_service = prompt_service

    async def _require_prompt(self, name: str) -> str:
        prompt = await self.prompt_service.get_prompt(name)
        if not prompt:
            raise RuntimeError(f"缺少提示词配置: {name}")
        return prompt

    async def generate_preview(
        self,
        project_id: str,
        chapter_number: int,
        outline: Dict[str, Any],
        blueprint_context: str,
        emotion_context: str,
        memory_context: str,
        style_hint: str = "",
        user_id: int = 0,
    ) -> Dict[str, Any]:
        """
        生成章节预览（500字左右）

        Returns:
            包含预览内容、关键情节点、预期效果的字典
        """
        system_prompt = await self._require_prompt("chapter_preview_generate")
        prompt = json.dumps(
            {
                "project_id": project_id,
                "chapter_number": chapter_number,
                "blueprint_context": blueprint_context[:3000],
                "emotion_context": emotion_context,
                "memory_context": memory_context[:2000],
                "outline": {
                    "title": outline.get("title", ""),
                    "summary": outline.get("summary", ""),
                },
                "style_hint": style_hint or "",
            },
            ensure_ascii=False,
        )

        try:
            response = await self.llm_service.get_llm_response(
                system_prompt=system_prompt,
                conversation_history=[{"role": "user", "content": prompt}],
                temperature=0.7,
                user_id=user_id,
                timeout=120.0,
                stage="chapter_preview",
            )

            content = response
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                result = json.loads(content[json_start:json_end])
                result["status"] = "success"
                return result
        except Exception as e:
            logger.warning(f"生成章节预览失败: {e}")

        return {
            "status": "failed",
            "preview_text": "",
            "key_plot_points": [],
            "error": "生成预览失败",
        }

    async def evaluate_preview(
        self,
        preview: Dict[str, Any],
        outline: Dict[str, Any],
        emotion_context: str,
        user_id: int = 0,
    ) -> Dict[str, Any]:
        """
        评估章节预览的质量

        Returns:
            包含评分、问题、建议的字典
        """
        system_prompt = await self._require_prompt("chapter_preview_evaluate")
        prompt = json.dumps(
            {
                "outline": {
                    "title": outline.get("title", ""),
                    "summary": outline.get("summary", ""),
                },
                "emotion_context": emotion_context,
                "preview_text": preview.get("preview_text", ""),
                "key_plot_points": preview.get("key_plot_points", []),
            },
            ensure_ascii=False,
        )

        try:
            response = await self.llm_service.get_llm_response(
                system_prompt=system_prompt,
                conversation_history=[{"role": "user", "content": prompt}],
                temperature=0.3,
                user_id=user_id,
                timeout=90.0,
                stage="chapter_preview",
            )

            content = response
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                return json.loads(content[json_start:json_end])
        except Exception as e:
            logger.warning(f"评估章节预览失败: {e}")

        return {"overall_score": 70, "approved": True, "revision_needed": False, "issues": []}

    async def expand_preview_to_full_chapter(
        self,
        preview: Dict[str, Any],
        outline: Dict[str, Any],
        blueprint_context: str,
        memory_context: str,
        target_word_count: int = 3000,
        style_hint: str = "",
        user_id: int = 0,
    ) -> str:
        """
        将预览扩写成完整章节

        Args:
            preview: 章节预览
            outline: 章节大纲
            blueprint_context: 蓝图上下文
            memory_context: 记忆层上下文
            target_word_count: 目标字数
            style_hint: 风格提示

        Returns:
            完整的章节正文
        """
        system_prompt = await self._require_prompt("chapter_preview_expand")
        prompt = json.dumps(
            {
                "blueprint_context": blueprint_context[:3000],
                "memory_context": memory_context[:2000],
                "outline": {
                    "title": outline.get("title", ""),
                    "summary": outline.get("summary", ""),
                },
                "preview_text": preview.get("preview_text", ""),
                "key_plot_points": preview.get("key_plot_points", []),
                "opening": preview.get("opening", {}),
                "ending_hook": preview.get("ending_hook", {}),
                "style_hint": style_hint or "",
                "target_word_count": target_word_count,
            },
            ensure_ascii=False,
        )

        try:
            response = await self.llm_service.get_llm_response(
                system_prompt=system_prompt,
                conversation_history=[{"role": "user", "content": prompt}],
                temperature=0.8,
                user_id=user_id,
                timeout=180.0,
                stage="chapter_preview",
            )

            content, _report = parse_chapter_content_response(response)
            return content
        except Exception as e:
            logger.error(f"扩写章节失败: {e}")
            return ""

    async def generate_with_preview(
        self,
        project_id: str,
        chapter_number: int,
        outline: Dict[str, Any],
        blueprint_context: str,
        emotion_context: str,
        memory_context: str,
        target_word_count: int = 3000,
        style_hint: str = "",
        auto_approve: bool = True,
        max_preview_retries: int = 2,
        user_id: int = 0,
    ) -> Dict[str, Any]:
        """
        完整的两阶段生成流程

        Args:
            auto_approve: 是否自动批准预览（True 则不需要人工确认）
            max_preview_retries: 预览不通过时的最大重试次数

        Returns:
            包含预览、评估、正文的完整结果
        """
        result = {
            "preview": None,
            "evaluation": None,
            "full_chapter": "",
            "retries": 0,
            "status": "pending",
        }

        # 阶段 1：生成预览
        for retry in range(max_preview_retries + 1):
            result["retries"] = retry

            # 生成预览
            preview = await self.generate_preview(
                project_id=project_id,
                chapter_number=chapter_number,
                outline=outline,
                blueprint_context=blueprint_context,
                emotion_context=emotion_context,
                memory_context=memory_context,
                style_hint=style_hint,
                user_id=user_id,
            )

            if preview.get("status") != "success":
                continue

            result["preview"] = preview

            # 评估预览
            evaluation = await self.evaluate_preview(
                preview=preview, outline=outline, emotion_context=emotion_context, user_id=user_id
            )

            result["evaluation"] = evaluation

            # 检查是否通过
            if auto_approve or evaluation.get("approved", False):
                break

            # 如果有严重问题且还有重试机会，重新生成
            critical_issues = [
                issue
                for issue in evaluation.get("issues", [])
                if issue.get("severity") == "critical"
            ]

            if not critical_issues or retry >= max_preview_retries:
                break

            # 将修改建议加入风格提示
            suggestions = evaluation.get("revision_suggestions", [])
            if suggestions:
                style_hint = style_hint + "\n注意：" + "；".join(suggestions)

        # 阶段 2：扩写正文
        if result["preview"]:
            full_chapter = await self.expand_preview_to_full_chapter(
                preview=result["preview"],
                outline=outline,
                blueprint_context=blueprint_context,
                memory_context=memory_context,
                target_word_count=target_word_count,
                style_hint=style_hint,
                user_id=user_id,
            )

            result["full_chapter"] = full_chapter
            result["status"] = "success" if full_chapter else "failed"
        else:
            result["status"] = "preview_failed"

        return result

    async def generate_multiple_previews(
        self,
        project_id: str,
        chapter_number: int,
        outline: Dict[str, Any],
        blueprint_context: str,
        emotion_context: str,
        memory_context: str,
        count: int = 3,
        user_id: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        生成多个不同风格的预览供选择

        Args:
            count: 生成预览的数量

        Returns:
            预览列表
        """
        style_hints = [
            "情绪更细腻，节奏更慢，多写内心戏和感官描写",
            "冲突更强，节奏更快，多写动作和对话",
            "悬念更重，多埋伏笔，结尾钩子更强",
            "幽默轻松，多写有趣的对话和互动",
            "紧张刺激，多写危机和转折",
        ]

        previews = []
        for i in range(min(count, len(style_hints))):
            preview = await self.generate_preview(
                project_id=project_id,
                chapter_number=chapter_number,
                outline=outline,
                blueprint_context=blueprint_context,
                emotion_context=emotion_context,
                memory_context=memory_context,
                style_hint=style_hints[i],
                user_id=user_id,
            )

            if preview.get("status") == "success":
                preview["style_hint"] = style_hints[i]
                preview["index"] = i

                # 评估预览
                evaluation = await self.evaluate_preview(
                    preview=preview,
                    outline=outline,
                    emotion_context=emotion_context,
                    user_id=user_id,
                )
                preview["evaluation"] = evaluation

                previews.append(preview)

        # 按评分排序
        previews.sort(key=lambda x: x.get("evaluation", {}).get("overall_score", 0), reverse=True)

        return previews
