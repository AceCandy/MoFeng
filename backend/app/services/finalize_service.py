# AIMETA P=旧定稿记忆服务_兼容入口与记忆辅助|R=摘要_角色状态_剧情线_章节快照|NR=不写入RAG或拥有durable任务事务|E=FinalizeService|X=internal|A=compat_service|D=llm_service,sqlalchemy|S=db,net|RD=./README.ai
"""
定稿服务 (FinalizeService)

融合自 上游融合仓库 的 finalization.py 设计理念，提供章节定稿后的一系列处理：
1. 更新全局摘要 (global_summary)
2. 更新角色状态 (character_state)
3. 更新剧情线追踪 (plot_arcs)
4. 创建章节快照 (chapter_snapshot)

这是"生成后闭环"的核心服务，确保长程一致性。
"""

import logging
import re
from typing import Optional, Dict, Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.project_memory import ProjectMemory, ChapterSnapshot
from ..models.memory_layer import CharacterState
from ..models.novel import BlueprintCharacter
from ..models.chapter_blueprint import ChapterBlueprint
from .chapter_word_count_settings import count_chapter_words
from .llm_service import LLMService

logger = logging.getLogger(__name__)


# ==================== 提示词模板 ====================

UPDATE_GLOBAL_SUMMARY_PROMPT = """\
以下是新完成的章节文本：
{chapter_text}

这是当前的前文摘要（可为空）：
{global_summary}

请根据本章新增内容，更新前文摘要。
要求：
- 保留既有重要信息，同时融入新剧情要点
- 以简洁、连贯的语言描述全书进展
- 客观描绘，不展开联想或解释
- 突出关键转折、人物关系变化、伏笔进展
- 总字数控制在2000字以内

仅返回前文摘要文本，不要解释任何内容。
"""

UPDATE_CHARACTER_STATE_PROMPT = """\
以下是新完成的章节文本：
{chapter_text}

这是当前的角色状态文档：
{old_state}

请更新主要角色状态，内容格式：
角色名：
├──物品:
│  ├──物品名：描述
│  └──...
├──能力:
│  ├──技能名：描述
│  └──...
├──状态:
│  ├──身体状态：描述
│  └──心理状态：描述
├──主要角色间关系网:
│  ├──角色A：关系描述
│  └──...
├──触发或加深的事件:
│  ├──事件1：描述
│  └──...

要求：
- 请直接在已有文档基础上进行增删
- 不改变原有结构，语言尽量简洁、有条理
- 新出场角色简要描述即可，淡出视线的角色可删除

仅返回更新后的角色状态文本，不要解释任何内容。
"""

UPDATE_PLOT_ARCS_PROMPT = """\
以下是新完成的章节文本：
{chapter_text}

当前章节号：第{chapter_number}章

这是当前的剧情线追踪（JSON格式）：
{plot_arcs}

请分析本章内容，更新剧情线追踪：

1. 未回收伏笔 (unresolved_hooks):
   - 检查是否有新埋设的伏笔
   - 检查是否有伏笔被回收（标记为resolved）
   - 检查是否有伏笔被强化

2. 主线矛盾 (main_conflicts):
   - 检查是否有新的主线矛盾出现
   - 检查现有矛盾的进展状态

3. 角色弧线 (character_arcs):
   - 检查角色的成长/变化阶段
   - 更新下一个里程碑

请以JSON格式返回更新后的剧情线追踪，结构如下：
{{
  "unresolved_hooks": [
    {{"id": "hook_1", "description": "描述", "planted_chapter": 1, "expected_payoff": 10, "status": "active/reinforced/resolved"}}
  ],
  "main_conflicts": [
    {{"id": "conflict_1", "description": "描述", "status": "active/escalating/resolved"}}
  ],
  "character_arcs": [
    {{"character": "角色名", "current_stage": "当前阶段", "next_milestone": "下一里程碑"}}
  ]
}}

仅返回JSON，不要解释任何内容。
"""

GENERATE_CHAPTER_SUMMARY_PROMPT = """\
请为以下章节内容生成一个简洁的摘要（100-200字）：

章节标题：第{chapter_number}章
章节内容：
{chapter_text}

要求：
- 概括本章的主要事件和关键转折
- 突出人物行动和情感变化
- 保持客观，不做评价

仅返回摘要文本，不要解释任何内容。
"""


class FinalizeService:
    """
    定稿服务

    兼容旧调用并提供记忆投影复用的持久化辅助方法。
    """

    def __init__(
        self,
        db: AsyncSession,
        llm_service: LLMService,
    ):
        self.db = db
        self.llm_service = llm_service

    async def finalize_chapter(
        self,
        project_id: str,
        chapter_number: int,
        chapter_text: str,
        user_id: int,
        skip_vector_update: bool = False,
    ) -> Dict[str, Any]:
        """
        对指定章节执行定稿处理

        Args:
            project_id: 项目ID
            chapter_number: 章节号
            chapter_text: 章节正文
            user_id: 用户ID
            skip_vector_update: 兼容旧调用；RAG 已由章节投影链路统一处理

        Returns:
            包含更新结果的字典。success 严格反映核心记忆字段是否至少有一个有效写入；
            部分失败时 success=True 且 partial_success=True；全部失败 success=False（H4）。
        """
        logger.info(f"开始定稿处理: project={project_id}, chapter={chapter_number}")

        result: Dict[str, Any] = {
            "success": False,
            "chapter_number": chapter_number,
            "updates": {},
            "errors": [],
        }

        try:
            # 1. 短事务读取项目记忆与当前状态后立即 commit，释放 DB 连接；
            #    后续 LLM 调用不独占连接池（H4：解耦 LLM 与 DB 事务）。
            project_memory = await self._get_or_create_project_memory(project_id)
            old_summary = project_memory.global_summary or ""
            old_plot_arcs = project_memory.plot_arcs or {}
            # 记下读时的 id 与 version，供写回时乐观锁守卫（commit 后对象 expire）
            memory_id = project_memory.id
            memory_version = project_memory.version
            old_state = await self._get_character_state_text(project_id)
            await self.db.commit()

            # 2-4. LLM 调用（事务外）：每个独立捕获，失败记录到 errors 但不静默吞没（H4）。
            new_summary = await self._safe_llm_call(
                self._update_global_summary(
                    chapter_text=chapter_text,
                    old_summary=old_summary,
                    user_id=user_id,
                ),
                "global_summary",
                result,
            )
            new_state = await self._safe_llm_call(
                self._update_character_state(
                    chapter_text=chapter_text,
                    old_state=old_state,
                    user_id=user_id,
                ),
                "character_state",
                result,
            )
            new_plot_arcs = await self._safe_llm_call(
                self._update_plot_arcs(
                    chapter_text=chapter_text,
                    chapter_number=chapter_number,
                    old_plot_arcs=old_plot_arcs,
                    user_id=user_id,
                ),
                "plot_arcs",
                result,
            )
            chapter_summary = await self._safe_llm_call(
                self._generate_chapter_summary(
                    chapter_text=chapter_text,
                    chapter_number=chapter_number,
                    user_id=user_id,
                ),
                "chapter_summary",
                result,
            )

            # success 严格语义：核心字段至少一个有效值才写快照 + success=True；
            # 全失败跳过快照写入，避免与上层回滚后章节状态不一致（H4）。
            core_fields = [new_summary, new_state, new_plot_arcs, chapter_summary]
            valid_count = sum(1 for field in core_fields if field)
            if valid_count == 0:
                result["success"] = False
                result["error"] = "所有记忆更新 LLM 调用均失败"
                logger.warning(
                    f"定稿全部 LLM 调用失败，跳过快照写入: project={project_id}, chapter={chapter_number}"
                )
                return result

            # 5-7. 写快照（新短事务）：仅写入有效结果。
            if new_state:
                await self._save_character_state(project_id, chapter_number, new_state)
                result["updates"]["character_state"] = "updated"
            await self._create_chapter_snapshot(
                project_id=project_id,
                chapter_number=chapter_number,
                global_summary=new_summary or old_summary,
                character_states=new_state,
                plot_arcs=new_plot_arcs or old_plot_arcs,
                chapter_summary=chapter_summary,
                word_count=count_chapter_words(chapter_text),
            )
            result["updates"]["snapshot"] = "created"
            # 乐观锁写回：守卫读时 version，冲突则不覆盖 memory（保留并发修改），LLM 结果已在 snapshot。
            memory_update_values: Dict[str, Any] = {
                "last_updated_chapter": chapter_number,
                "version": ProjectMemory.version + 1,
            }
            if new_summary:
                memory_update_values["global_summary"] = new_summary
            if new_plot_arcs:
                memory_update_values["plot_arcs"] = new_plot_arcs
            memory_stmt = (
                update(ProjectMemory)
                .where(ProjectMemory.id == memory_id, ProjectMemory.version == memory_version)
                .values(**memory_update_values)
            )
            memory_update_result = await self.db.execute(memory_stmt)
            if memory_update_result.rowcount > 0:
                if new_summary:
                    result["updates"]["global_summary"] = "updated"
                if new_plot_arcs:
                    result["updates"]["plot_arcs"] = "updated"
            else:
                # 并发修改冲突：保留对方修改不覆盖 memory，LLM 结果已在 snapshot 供参考。
                result["conflict"] = True
            await self._update_blueprint_status(project_id, chapter_number)
            await self.db.commit()

            result["success"] = True
            if valid_count < len(core_fields):
                result["partial_success"] = True

            logger.info(
                f"定稿处理完成: project={project_id}, chapter={chapter_number}, "
                f"success={result['success']}, partial={result.get('partial_success', False)}"
            )

        except Exception as e:
            logger.error(f"定稿处理失败: {e}")
            await self.db.rollback()
            result["success"] = False
            result["error"] = str(e)

        return result

    async def _safe_llm_call(
        self,
        coro: Any,
        field_name: str,
        result: Dict[str, Any],
    ) -> Any:
        """包装 LLM 调用：捕获异常并记录到 result['errors']，不静默吞没（H4）。"""
        try:
            return await coro
        except Exception as e:
            logger.error(f"{field_name} LLM 调用失败: {e}")
            result.setdefault("errors", []).append({"field": field_name, "error": str(e)})
            return None

    async def _get_or_create_project_memory(self, project_id: str) -> ProjectMemory:
        """获取或创建项目记忆"""
        memory = (
            (
                await self.db.execute(
                    select(ProjectMemory).where(ProjectMemory.project_id == project_id)
                )
            )
            .scalars()
            .first()
        )

        if not memory:
            memory = ProjectMemory(
                project_id=project_id,
                global_summary="",
                plot_arcs={"unresolved_hooks": [], "main_conflicts": [], "character_arcs": []},
            )
            self.db.add(memory)
            await self.db.flush()

        return memory

    async def _update_global_summary(
        self, chapter_text: str, old_summary: str, user_id: int
    ) -> Optional[str]:
        """更新全局摘要（异常向上传播，由 _safe_llm_call 统一记录，H4）"""
        prompt = UPDATE_GLOBAL_SUMMARY_PROMPT.format(
            chapter_text=chapter_text, global_summary=old_summary
        )

        response = await self.llm_service.generate(
            prompt=prompt, user_id=user_id, max_tokens=3000, temperature=0.3
        )
        return response.strip() if response else None

    async def _get_character_state_text(self, project_id: str) -> str:
        """获取角色状态文本"""
        # 获取最新的角色状态记录
        states = (
            (
                await self.db.execute(
                    select(CharacterState)
                    .where(
                        CharacterState.project_id == project_id,
                        CharacterState.is_active.is_(True),
                    )
                    .order_by(
                        CharacterState.chapter_number.desc(),
                        CharacterState.chapter_revision.desc(),
                        CharacterState.id.desc(),
                    )
                )
            )
            .scalars()
            .all()
        )

        if not states:
            return ""

        # 按角色分组，取每个角色的最新状态
        latest_states = {}
        for state in states:
            if state.character_name not in latest_states:
                latest_states[state.character_name] = state

        # 格式化为文本
        text_parts = []
        for name, state in latest_states.items():
            parts = [f"{name}："]
            if state.inventory:
                parts.append(f"├──物品: {state.inventory}")
            if state.power_level:
                parts.append(f"├──能力: {state.power_level}")
            parts.append(f"├──状态:")
            parts.append(f"│  ├──身体状态: {state.health_status or '正常'}")
            parts.append(f"│  └──心理状态: {state.emotion or '平静'}")
            if state.relationship_changes:
                parts.append(f"├──关系网: {state.relationship_changes}")
            if state.new_knowledge:
                parts.append(f"├──触发事件: {state.new_knowledge}")
            text_parts.append("\n".join(parts))

        return "\n\n".join(text_parts)

    async def _update_character_state(
        self, chapter_text: str, old_state: str, user_id: int
    ) -> Optional[str]:
        """更新角色状态（异常向上传播，由 _safe_llm_call 统一记录，H4）"""
        prompt = UPDATE_CHARACTER_STATE_PROMPT.format(
            chapter_text=chapter_text, old_state=old_state or "（暂无角色状态记录）"
        )

        response = await self.llm_service.generate(
            prompt=prompt, user_id=user_id, max_tokens=4000, temperature=0.3
        )
        return response.strip() if response else None

    async def _save_character_state(
        self,
        project_id: str,
        chapter_number: int,
        state_text: str,
        *,
        chapter_revision: int = 0,
        artifact_generation: str = "legacy",
        projection_run_id: Optional[str] = None,
        is_active: bool = True,
    ):
        """保存角色状态到数据库"""
        characters = await self._get_blueprint_characters(project_id)
        if not characters:
            logger.warning("项目 %s 未配置蓝图角色，跳过角色状态外键表写入", project_id)
            return

        state_blocks = self._split_character_state_text(state_text)
        matched_states: list[tuple[BlueprintCharacter, str]] = []
        for character in characters:
            block = self._match_character_state_block(character.name, state_blocks, state_text)
            if block:
                matched_states.append((character, block))

        if not matched_states:
            logger.warning("项目 %s 角色状态未匹配到蓝图角色，跳过角色状态外键表写入", project_id)
            return

        for character, block in matched_states:
            state_kwargs = {}

            # character_states.character_id 有外键约束，只能写入真实蓝图角色，原始文本仍保留在 extra 中。
            state = CharacterState(
                project_id=project_id,
                character_id=character.id,
                character_name=character.name,
                chapter_number=chapter_number,
                chapter_revision=chapter_revision,
                artifact_generation=artifact_generation,
                projection_run_id=projection_run_id,
                is_active=is_active,
                extra={"raw_state_text": block},
                **state_kwargs,
            )
            self.db.add(state)

    async def _get_blueprint_characters(self, project_id: str) -> list[BlueprintCharacter]:
        """读取项目蓝图角色，用于给角色状态表提供合法外键。"""
        result = await self.db.execute(
            select(BlueprintCharacter)
            .where(BlueprintCharacter.project_id == project_id)
            .order_by(BlueprintCharacter.position, BlueprintCharacter.id)
        )
        return list(result.scalars().all())

    @staticmethod
    def _split_character_state_text(state_text: str) -> dict[str, str]:
        """按“角色名：”标题粗略切分 AI 返回的角色状态文档。"""
        blocks: dict[str, list[str]] = {}
        current_name: Optional[str] = None

        heading_pattern = re.compile(r"^\s*(?![├│└#\-*])([^：:\n]{1,80})\s*[：:]\s*(.*)$")
        for raw_line in state_text.splitlines():
            line = raw_line.strip()
            match = heading_pattern.match(line)
            if match:
                current_name = match.group(1).strip()
                first_value = match.group(2).strip()
                blocks.setdefault(current_name, [])
                heading = f"{current_name}：{first_value}" if first_value else f"{current_name}："
                blocks[current_name].append(heading)
                continue

            if current_name:
                blocks[current_name].append(raw_line)

        return {
            name: "\n".join(part for part in parts if part.strip()).strip()
            for name, parts in blocks.items()
        }

    @staticmethod
    def _match_character_state_block(
        character_name: str,
        state_blocks: dict[str, str],
        fallback_text: str,
    ) -> Optional[str]:
        """优先按标题精确匹配；标题解析失败时退回到全文包含匹配。"""
        for state_name, block in state_blocks.items():
            if state_name == character_name or character_name in state_name:
                return block or fallback_text

        if not state_blocks and character_name in fallback_text:
            return fallback_text

        return None

    async def _update_plot_arcs(
        self, chapter_text: str, chapter_number: int, old_plot_arcs: Dict, user_id: int
    ) -> Optional[Dict]:
        """更新剧情线追踪（异常向上传播，由 _safe_llm_call 统一记录，H4）"""
        import json

        prompt = UPDATE_PLOT_ARCS_PROMPT.format(
            chapter_text=chapter_text,
            chapter_number=chapter_number,
            plot_arcs=json.dumps(old_plot_arcs, ensure_ascii=False, indent=2),
        )

        response = await self.llm_service.generate(
            prompt=prompt, user_id=user_id, max_tokens=2000, temperature=0.3
        )
        if not response:
            return None
        # 尝试解析JSON
        response = response.strip()
        if response.startswith("```"):
            response = response.split("```")[1]
            if response.startswith("json"):
                response = response[4:]
        return json.loads(response)

    async def _generate_chapter_summary(
        self, chapter_text: str, chapter_number: int, user_id: int
    ) -> Optional[str]:
        """生成章节摘要（异常向上传播，由 _safe_llm_call 统一记录，H4）"""
        prompt = GENERATE_CHAPTER_SUMMARY_PROMPT.format(
            chapter_text=chapter_text[:5000], chapter_number=chapter_number  # 限制长度
        )

        response = await self.llm_service.generate(
            prompt=prompt, user_id=user_id, max_tokens=500, temperature=0.3
        )
        return response.strip() if response else None

    async def _create_chapter_snapshot(
        self,
        project_id: str,
        chapter_number: int,
        global_summary: Optional[str],
        character_states: Optional[str],
        plot_arcs: Optional[Dict],
        chapter_summary: Optional[str],
        word_count: int,
        *,
        chapter_revision: int = 0,
        artifact_generation: str = "legacy",
        projection_run_id: Optional[str] = None,
        is_active: bool = True,
    ):
        """创建章节快照"""
        snapshot = ChapterSnapshot(
            project_id=project_id,
            chapter_number=chapter_number,
            global_summary_snapshot=global_summary,
            character_states_snapshot={"raw_text": character_states} if character_states else None,
            plot_arcs_snapshot=plot_arcs,
            chapter_summary=chapter_summary,
            word_count=word_count,
            chapter_revision=chapter_revision,
            artifact_generation=artifact_generation,
            projection_run_id=projection_run_id,
            is_active=is_active,
        )
        self.db.add(snapshot)

    async def _update_blueprint_status(self, project_id: str, chapter_number: int):
        """更新章节蓝图状态"""
        blueprint = (
            (
                await self.db.execute(
                    select(ChapterBlueprint).where(
                        ChapterBlueprint.project_id == project_id,
                        ChapterBlueprint.chapter_number == chapter_number,
                    )
                )
            )
            .scalars()
            .first()
        )

        if blueprint:
            blueprint.is_finalized = True

    async def get_finalize_context(self, project_id: str, chapter_number: int) -> Dict[str, Any]:
        """
        获取定稿上下文信息

        用于在生成章节时提供上下文参考。
        """
        memory = (
            (
                await self.db.execute(
                    select(ProjectMemory).where(ProjectMemory.project_id == project_id)
                )
            )
            .scalars()
            .first()
        )

        # 获取最近的章节快照
        recent_snapshots = (
            (
                await self.db.execute(
                    select(ChapterSnapshot)
                    .where(
                        ChapterSnapshot.project_id == project_id,
                        ChapterSnapshot.chapter_number < chapter_number,
                        ChapterSnapshot.is_active.is_(True),
                    )
                    .order_by(
                        ChapterSnapshot.chapter_number.desc(),
                        ChapterSnapshot.chapter_revision.desc(),
                        ChapterSnapshot.id.desc(),
                    )
                    .limit(3)
                )
            )
            .scalars()
            .all()
        )

        return {
            "global_summary": memory.global_summary if memory else None,
            "plot_arcs": memory.plot_arcs if memory else None,
            "recent_snapshots": [
                {"chapter_number": s.chapter_number, "summary": s.chapter_summary}
                for s in recent_snapshots
            ],
        }
