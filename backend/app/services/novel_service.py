# AIMETA P=小说服务_小说管理业务逻辑|R=小说CRUD_章节管理|NR=不含内容生成|E=NovelService|X=internal|A=服务类|D=sqlalchemy|S=db|RD=./README.ai
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

from fastapi import HTTPException, status
from sqlalchemy import and_, delete, func, insert, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import (
    BlueprintCharacter,
    BlueprintRelationship,
    Chapter,
    ChapterEvaluation,
    ChapterGenerationTrace,
    ChapterOutline,
    ChapterVersion,
    NovelBlueprint,
    NovelConversation,
    NovelProject,
)
from ..repositories.creation_context_repository import CreationContextRepository
from ..repositories.novel_repository import NovelRepository
from ..schemas.admin import AdminNovelSummary
from ..schemas.novel import (
    Blueprint,
    ChapterGenerationStatus,
    NovelProjectSummary,
    NovelSectionResponse,
    NovelSectionType,
)
from ..schemas.novel import (
    Chapter as ChapterSchema,
)
from ..schemas.novel import (
    ChapterGenerationTrace as ChapterGenerationTraceSchema,
)
from ..schemas.novel import (
    ChapterOutline as ChapterOutlineSchema,
)
from ..schemas.novel import (
    ChapterVersionSelection as ChapterVersionSelectionSchema,
)
from ..schemas.novel import (
    NovelProject as NovelProjectSchema,
)
from .chapter_projection_service import ChapterProjectionService
from .chapter_word_count_settings import count_chapter_words
from .chapter_workflow_activities import ChapterWorkflowReviewOutput
from .event_bus import publish_background_task

_PREFERRED_CONTENT_KEYS: tuple[str, ...] = (
    "content",
    "chapter_content",
    "chapter_text",
    "full_content",
    "text",
    "body",
    "story",
    "chapter",
    "real_summary",
    "summary",
)


def _normalize_chapter_evaluation_feedback(feedback: str) -> str:
    """将已持久化的旧工作流评审包装转换为当前公开展示结构。"""
    try:
        payload = json.loads(feedback)
    except json.JSONDecodeError:
        return feedback
    if not isinstance(payload, dict) or "best_choice" in payload:
        return feedback
    best_ordinal = payload.get("best_ordinal")
    report = payload.get("report")
    if not isinstance(best_ordinal, int) or not isinstance(report, dict):
        return feedback
    try:
        review = ChapterWorkflowReviewOutput(best_ordinal=best_ordinal, report=report)
    except ValueError:
        return feedback
    return json.dumps(review.to_evaluation_payload(), ensure_ascii=False, sort_keys=True)


def _normalize_version_content(raw_content: Any, metadata: Any) -> str:
    # 优先使用原始内容
    text = _coerce_text(raw_content)
    if text:
        return text

    # 如果没有原始内容，尝试从元数据提取（兼容旧逻辑）
    text = _coerce_text(metadata)
    return text or ""


def _coerce_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return _clean_string(value)
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, dict):
        for key in _PREFERRED_CONTENT_KEYS:
            if key in value and value[key]:
                nested = _coerce_text(value[key])
                if nested:
                    return nested
        return _clean_string(json.dumps(value, ensure_ascii=False), parse_json=False)
    if isinstance(value, (list, tuple, set)):
        parts = [text for text in (_coerce_text(item) for item in value) if text]
        if parts:
            return "\n".join(parts)
        return None
    return _clean_string(str(value))


def _clean_string(text: str, parse_json: bool = True) -> str:
    stripped = text.strip()
    if not stripped:
        return stripped
    if parse_json and (
        (stripped.startswith("{") and stripped.endswith("}"))
        or (stripped.startswith("[") and stripped.endswith("]"))
    ):
        try:
            parsed = json.loads(stripped)
            coerced = _coerce_text(parsed)
            if coerced:
                return coerced
        except json.JSONDecodeError:
            pass
    if stripped.startswith('"') and stripped.endswith('"') and len(stripped) >= 2:
        stripped = stripped[1:-1]
    return (
        stripped.replace("\\n", "\n").replace("\\t", "\t").replace('\\"', '"').replace("\\\\", "\\")
    )


logger = logging.getLogger(__name__)


class NovelService:
    """小说项目服务，基于拆表后的结构提供聚合与业务操作。"""

    STALE_IN_PROGRESS_TIMEOUT = timedelta(minutes=10)
    INSPIRATION_TITLE = "未命名灵感"
    INSPIRATION_INITIAL_PROMPT = "开始灵感模式"
    INSPIRATION_ACTIVE_STATUS = "inspiration_active"
    INSPIRATION_BLUEPRINT_GENERATED_STATUS = "inspiration_blueprint_generated"
    INSPIRATION_COMPLETE_STATUS = "blueprint_ready"
    INSPIRATION_UNFINISHED_STATUSES = (
        INSPIRATION_ACTIVE_STATUS,
        INSPIRATION_BLUEPRINT_GENERATED_STATUS,
    )

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = NovelRepository(session)

    # ------------------------------------------------------------------
    # 项目与摘要
    # ------------------------------------------------------------------
    @classmethod
    def is_inspiration_seed(cls, title: str | None, initial_prompt: str | None) -> bool:
        return (title or "").strip() == cls.INSPIRATION_TITLE and (
            initial_prompt or ""
        ).strip() == cls.INSPIRATION_INITIAL_PROMPT

    @classmethod
    def is_unfinished_inspiration_project(cls, project: NovelProject) -> bool:
        if project.status in cls.INSPIRATION_UNFINISHED_STATUSES:
            return True
        return project.status == "draft" and cls.is_inspiration_seed(
            project.title, project.initial_prompt
        )

    async def create_project(
        self,
        user_id: int,
        title: str,
        initial_prompt: str,
        status: str = "draft",
    ) -> NovelProject:
        project = NovelProject(
            id=str(uuid.uuid4()),
            user_id=user_id,
            title=title,
            initial_prompt=initial_prompt,
            status=status,
        )
        blueprint = NovelBlueprint(project=project)
        self.session.add_all([project, blueprint])
        await self.session.commit()
        await self.session.refresh(project)
        return project

    async def find_unfinished_inspiration_project(self, user_id: int) -> Optional[NovelProject]:
        # 兼容旧数据：早期灵感项目没有专用状态，只能通过固定标题和初始提示识别。
        legacy_inspiration = and_(
            or_(NovelProject.status == "draft", NovelProject.status.is_(None)),
            NovelProject.title == self.INSPIRATION_TITLE,
            NovelProject.initial_prompt == self.INSPIRATION_INITIAL_PROMPT,
        )
        stmt = (
            select(NovelProject)
            .where(
                NovelProject.user_id == user_id,
                or_(
                    NovelProject.status.in_(self.INSPIRATION_UNFINISHED_STATUSES),
                    legacy_inspiration,
                ),
            )
            .order_by(NovelProject.updated_at.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def ensure_project_owner(self, project_id: str, user_id: int) -> NovelProject:
        project = await self.repo.get_by_id(project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
        if project.user_id != user_id:
            # 越权访问统一返回 404，与"项目不存在"同码同文案，避免泄露项目存在性（审计 #14）
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
        return project

    async def get_project_schema(self, project_id: str, user_id: int) -> NovelProjectSchema:
        project = await self.ensure_project_owner(project_id, user_id)
        return await self._serialize_project(project)

    async def get_section_data(
        self,
        project_id: str,
        user_id: int,
        section: NovelSectionType,
    ) -> NovelSectionResponse:
        project = await self.ensure_project_owner(project_id, user_id)
        return self._build_section_response(project, section)

    async def get_chapter_schema(
        self,
        project_id: str,
        user_id: int,
        chapter_number: int,
    ) -> ChapterSchema:
        await self._ensure_project_owner_light(project_id, user_id)

        chapter_stmt = (
            select(Chapter)
            .where(
                Chapter.project_id == project_id,
                Chapter.chapter_number == chapter_number,
            )
            .options(
                selectinload(Chapter.versions),
                selectinload(Chapter.evaluations),
                selectinload(Chapter.selected_version),
                selectinload(Chapter.generation_traces),
            )
        )
        chapter_result = await self.session.execute(chapter_stmt)
        chapter = chapter_result.scalars().first()

        await self._auto_fail_stale_in_progress_chapters(project_id, [chapter] if chapter else [])

        outline_stmt = select(ChapterOutline).where(
            ChapterOutline.project_id == project_id,
            ChapterOutline.chapter_number == chapter_number,
        )
        outline_result = await self.session.execute(outline_stmt)
        outline = outline_result.scalars().first()

        return self._build_chapter_schema_from_entities(
            chapter_number=chapter_number,
            outline=outline,
            chapter=chapter,
            include_content=True,
        )

    async def list_projects_for_user(self, user_id: int) -> List[NovelProjectSummary]:
        projects = await self.repo.list_by_user(user_id)
        summaries: List[NovelProjectSummary] = []
        for project in projects:
            blueprint = project.blueprint
            genre = blueprint.genre if blueprint and blueprint.genre else "未知"
            outlines = project.outlines
            chapters = project.chapters
            total = len(outlines) or len(chapters)
            completed = sum(1 for chapter in chapters if chapter.selected_version_id)
            summaries.append(
                NovelProjectSummary(
                    id=project.id,
                    title=project.title,
                    genre=genre,
                    last_edited=project.updated_at.isoformat() if project.updated_at else "未知",
                    completed_chapters=completed,
                    total_chapters=total,
                )
            )
        return summaries

    async def list_projects_for_admin(self) -> List[AdminNovelSummary]:
        projects = await self.repo.list_all()
        summaries: List[AdminNovelSummary] = []
        for project in projects:
            blueprint = project.blueprint
            genre = blueprint.genre if blueprint and blueprint.genre else "未知"
            outlines = project.outlines
            chapters = project.chapters
            total = len(outlines) or len(chapters)
            completed = sum(1 for chapter in chapters if chapter.selected_version_id)
            owner = project.owner
            summaries.append(
                AdminNovelSummary(
                    id=project.id,
                    title=project.title,
                    owner_id=owner.id if owner else 0,
                    owner_username=owner.username if owner else "未知",
                    genre=genre,
                    last_edited=project.updated_at.isoformat() if project.updated_at else "",
                    completed_chapters=completed,
                    total_chapters=total,
                )
            )
        return summaries

    async def delete_projects(self, project_ids: List[str], user_id: int) -> None:
        for pid in project_ids:
            project = await self.ensure_project_owner(pid, user_id)
            await self.repo.delete(project)
        await self.session.commit()

    async def count_projects(self) -> int:
        result = await self.session.execute(select(func.count(NovelProject.id)))
        return result.scalar_one()

    async def _ensure_project_owner_light(self, project_id: str, user_id: int) -> None:
        result = await self.session.execute(
            select(NovelProject.user_id).where(NovelProject.id == project_id)
        )
        owner_id = result.scalar_one_or_none()
        if owner_id is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
        if owner_id != user_id:
            # 越权访问统一返回 404，与"项目不存在"同码同文案，避免泄露项目存在性（审计 #14）
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")

    # ------------------------------------------------------------------
    # 对话管理
    # ------------------------------------------------------------------
    async def list_conversations(self, project_id: str) -> List[NovelConversation]:
        stmt = (
            select(NovelConversation)
            .where(NovelConversation.project_id == project_id)
            .order_by(NovelConversation.seq.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars())

    async def append_conversation(
        self, project_id: str, role: str, content: str, metadata: Optional[Dict] = None
    ) -> None:
        context_repo = CreationContextRepository(self.session)
        project_user_id = await context_repo.lock_project(project_id)
        if project_user_id is None:
            raise ValueError("项目不存在")
        # 原子 INSERT SELECT MAX(seq)+1，避免读改写并发竞态产生重复 seq
        next_seq = (
            select(func.coalesce(func.max(NovelConversation.seq), 0) + 1)
            .where(NovelConversation.project_id == project_id)
            .scalar_subquery()
        )
        await self.session.execute(
            insert(NovelConversation).values(
                project_id=project_id,
                seq=next_seq,
                role=role,
                content=content,
                metadata_=metadata,
            )
        )
        if role == "assistant":
            turn = await context_repo.get_authoritative_inspiration_turn(project_id)
            await context_repo.advance_inspiration_turn(
                user_id=project_user_id,
                project_id=project_id,
                turn=turn,
            )
        await self.session.commit()
        await self._touch_project(project_id)

    # ------------------------------------------------------------------
    # 蓝图管理
    # ------------------------------------------------------------------
    async def replace_blueprint(self, project_id: str, blueprint: Blueprint) -> None:
        record = await self.session.get(NovelBlueprint, project_id)
        if not record:
            record = NovelBlueprint(project_id=project_id)
            self.session.add(record)
        record.title = blueprint.title
        record.target_audience = blueprint.target_audience
        record.genre = blueprint.genre
        record.style = blueprint.style
        record.tone = blueprint.tone
        record.one_sentence_summary = blueprint.one_sentence_summary
        record.full_synopsis = blueprint.full_synopsis
        record.world_setting = blueprint.world_setting

        await self.session.execute(
            delete(BlueprintCharacter).where(BlueprintCharacter.project_id == project_id)
        )
        for index, data in enumerate(blueprint.characters):
            self.session.add(
                BlueprintCharacter(
                    project_id=project_id,
                    name=data.get("name", ""),
                    identity=data.get("identity"),
                    personality=data.get("personality"),
                    goals=data.get("goals"),
                    abilities=data.get("abilities"),
                    relationship_to_protagonist=data.get("relationship_to_protagonist"),
                    extra={
                        k: v
                        for k, v in data.items()
                        if k
                        not in {
                            "name",
                            "identity",
                            "personality",
                            "goals",
                            "abilities",
                            "relationship_to_protagonist",
                        }
                    },
                    position=index,
                )
            )

        await self.session.execute(
            delete(BlueprintRelationship).where(BlueprintRelationship.project_id == project_id)
        )
        for index, relation in enumerate(blueprint.relationships):
            self.session.add(
                BlueprintRelationship(
                    project_id=project_id,
                    character_from=relation.character_from,
                    character_to=relation.character_to,
                    description=relation.description,
                    position=index,
                )
            )

        await self.session.execute(
            delete(ChapterOutline).where(ChapterOutline.project_id == project_id)
        )
        for outline in blueprint.chapter_outline:
            self.session.add(
                ChapterOutline(
                    project_id=project_id,
                    chapter_number=outline.chapter_number,
                    title=outline.title,
                    summary=outline.summary,
                    goals=outline.goals,
                    highlights=outline.highlights,
                    character_states=outline.character_states,
                )
            )

        await self.session.commit()
        await self._touch_project(project_id)

    async def patch_blueprint(self, project_id: str, patch: Dict) -> None:
        blueprint = await self.session.get(NovelBlueprint, project_id)
        if not blueprint:
            blueprint = NovelBlueprint(project_id=project_id)
            self.session.add(blueprint)

        if "one_sentence_summary" in patch:
            blueprint.one_sentence_summary = patch["one_sentence_summary"]
        if "full_synopsis" in patch:
            blueprint.full_synopsis = patch["full_synopsis"]
        if "world_setting" in patch and patch["world_setting"] is not None:
            # 创建新字典对象以触发 SQLAlchemy 的变更检测
            existing = blueprint.world_setting or {}
            blueprint.world_setting = {**existing, **patch["world_setting"]}
        if "characters" in patch and patch["characters"] is not None:
            await self.session.execute(
                delete(BlueprintCharacter).where(BlueprintCharacter.project_id == project_id)
            )
            for index, data in enumerate(patch["characters"]):
                self.session.add(
                    BlueprintCharacter(
                        project_id=project_id,
                        name=data.get("name", ""),
                        identity=data.get("identity"),
                        personality=data.get("personality"),
                        goals=data.get("goals"),
                        abilities=data.get("abilities"),
                        relationship_to_protagonist=data.get("relationship_to_protagonist"),
                        extra={
                            k: v
                            for k, v in data.items()
                            if k
                            not in {
                                "name",
                                "identity",
                                "personality",
                                "goals",
                                "abilities",
                                "relationship_to_protagonist",
                            }
                        },
                        position=index,
                    )
                )
        if "relationships" in patch and patch["relationships"] is not None:
            await self.session.execute(
                delete(BlueprintRelationship).where(BlueprintRelationship.project_id == project_id)
            )
            for index, relation in enumerate(patch["relationships"]):
                self.session.add(
                    BlueprintRelationship(
                        project_id=project_id,
                        character_from=relation.get("character_from"),
                        character_to=relation.get("character_to"),
                        description=relation.get("description"),
                        position=index,
                    )
                )
        if "chapter_outline" in patch and patch["chapter_outline"] is not None:
            await self.session.execute(
                delete(ChapterOutline).where(ChapterOutline.project_id == project_id)
            )
            for outline in patch["chapter_outline"]:
                self.session.add(
                    ChapterOutline(
                        project_id=project_id,
                        chapter_number=outline.get("chapter_number"),
                        title=outline.get("title", ""),
                        summary=outline.get("summary"),
                        goals=outline.get("goals", ""),
                        highlights=outline.get("highlights") or [],
                        character_states=outline.get("character_states") or {},
                    )
                )
        await self.session.commit()
        await self._touch_project(project_id)

    # ------------------------------------------------------------------
    # 章节与版本
    # ------------------------------------------------------------------
    async def get_outline(self, project_id: str, chapter_number: int) -> Optional[ChapterOutline]:
        stmt = select(ChapterOutline).where(
            ChapterOutline.project_id == project_id,
            ChapterOutline.chapter_number == chapter_number,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def update_or_create_outline(
        self,
        project_id: str,
        chapter_number: int,
        title: str,
        summary: str,
        goals: str = "",
        highlights: Optional[List[str]] = None,
        character_states: Optional[Dict[str, str]] = None,
        metadata: Optional[dict] = None,
    ) -> ChapterOutline:
        """更新或创建章节大纲，写入概要、目标、看点和角色瞬时状态。"""
        stmt = select(ChapterOutline).where(
            ChapterOutline.project_id == project_id,
            ChapterOutline.chapter_number == chapter_number,
        )
        result = await self.session.execute(stmt)
        outline = result.scalars().first()
        resolved_highlights = highlights or []
        resolved_character_states = character_states or {}
        if outline:
            outline.title = title
            outline.summary = summary
            outline.goals = goals
            outline.highlights = resolved_highlights
            outline.character_states = resolved_character_states
            if metadata is not None:
                outline.metadata = metadata
        else:
            outline = ChapterOutline(
                project_id=project_id,
                chapter_number=chapter_number,
                title=title,
                summary=summary,
                goals=goals,
                highlights=resolved_highlights,
                character_states=resolved_character_states,
                metadata=metadata,
            )
            self.session.add(outline)
        await self.session.flush()
        return outline

    async def get_or_create_chapter(self, project_id: str, chapter_number: int) -> Chapter:
        stmt = (
            select(Chapter)
            .options(selectinload(Chapter.selected_version))
            .where(
                Chapter.project_id == project_id,
                Chapter.chapter_number == chapter_number,
            )
        )
        result = await self.session.execute(stmt)
        chapter = result.scalars().first()
        if chapter:
            return chapter
        chapter = Chapter(project_id=project_id, chapter_number=chapter_number)
        self.session.add(chapter)
        try:
            await self.session.commit()
        except IntegrityError:
            # 并发场景：另一请求已创建同 (project_id, chapter_number)，回退后重读
            await self.session.rollback()
            result = await self.session.execute(stmt)
            chapter = result.scalars().first()
            if chapter:
                return chapter
            raise
        await self.session.refresh(chapter)
        return chapter

    async def replace_chapter_versions(
        self,
        chapter: Chapter,
        contents: List[str],
        metadata: Optional[List[Dict]] = None,
        evaluation_feedback: Optional[str] = None,
    ) -> List[ChapterVersion]:
        # 生成完成只保存候选草稿；真实正文、章节梳理和选中版本必须等用户确认定稿后写入。
        # 调用方可能持有 finalize 提交前的 ORM 快照；必须先锁定并覆盖为数据库当前值。
        with self.session.no_autoflush:
            locked_chapter = (
                (
                    await self.session.execute(
                        select(Chapter)
                        .where(Chapter.id == chapter.id)
                        .with_for_update()
                        .execution_options(populate_existing=True)
                    )
                )
                .scalars()
                .first()
            )
        if locked_chapter is None:
            raise ValueError("章节不存在")
        chapter = locked_chapter
        supersede_job = None
        if chapter.selected_version_id is not None and (
            int(chapter.current_revision or 0) > 0 or chapter.projection_generation is not None
        ):
            owner_id = await self.session.scalar(
                select(NovelProject.user_id).where(NovelProject.id == chapter.project_id)
            )
            if owner_id is None:
                raise ValueError("章节所属项目不存在")
            supersede_job = await ChapterProjectionService(self.session).create_tombstone_job(
                chapter=chapter,
                user_id=owner_id,
                reason="chapter_regenerated",
                event_type="ChapterRevisionSuperseded",
            )
        chapter.selected_version_id = None
        chapter.selected_version = None
        chapter.real_summary = None
        chapter.word_count = 0
        chapter.projection_generation = None
        await self.session.flush()
        await self.session.execute(
            delete(ChapterEvaluation).where(ChapterEvaluation.chapter_id == chapter.id)
        )
        await self.session.execute(
            delete(ChapterVersion).where(ChapterVersion.chapter_id == chapter.id)
        )
        versions: List[ChapterVersion] = []
        for index, content in enumerate(contents):
            extra = metadata[index] if metadata and index < len(metadata) else None
            text_content = _normalize_version_content(content, extra)
            version = ChapterVersion(
                chapter_id=chapter.id,
                content=text_content,
                metadata=extra,  # ✅ 落盘 metadata
                version_label=f"v{index + 1}",
            )
            self.session.add(version)
            versions.append(version)
        await self.session.flush()
        if evaluation_feedback and evaluation_feedback.strip() and versions:
            review_version = versions[0]
            self.session.add(
                ChapterEvaluation(
                    chapter_id=chapter.id,
                    version_id=review_version.id,
                    feedback=evaluation_feedback.strip(),
                    decision="ai_review",
                )
            )
        chapter.status = ChapterGenerationStatus.WAITING_FOR_CONFIRM.value
        chapter.generation_step = f"waiting_for_confirm|v={len(versions)}"
        chapter.generation_progress = 100
        chapter.generation_step_index = 7
        chapter.generation_step_total = 7
        await self.session.commit()
        await self.session.refresh(chapter)
        if supersede_job is not None:
            await publish_background_task(supersede_job.user_id)
        await self._touch_project(chapter.project_id)
        return versions

    async def select_chapter_version(self, chapter: Chapter, version_index: int) -> ChapterVersion:
        stmt = (
            select(ChapterVersion)
            .where(ChapterVersion.chapter_id == chapter.id)
            .order_by(ChapterVersion.created_at)
        )
        result = await self.session.execute(stmt)
        versions = result.scalars().all()

        if not versions or version_index < 0 or version_index >= len(versions):
            raise HTTPException(status_code=400, detail="版本索引无效")
        selected = versions[version_index]

        # 校验内容是否为空
        if not selected.content or len(selected.content.strip()) == 0:
            raise HTTPException(status_code=400, detail="选中的版本内容为空，无法确认为最终版")

        chapter.selected_version_id = selected.id
        # 同步关系对象，避免同一请求事务中 selected_version 仍为旧缓存。
        chapter.selected_version = selected
        chapter.status = ChapterGenerationStatus.SUCCESSFUL.value
        chapter.generation_progress = 100
        chapter.generation_step = "completed"
        chapter.generation_step_index = 7
        chapter.generation_step_total = 7
        chapter.word_count = count_chapter_words(selected.content or "")
        await self.session.commit()
        await self.session.refresh(chapter)
        await self._touch_project(chapter.project_id)
        return selected

    async def add_chapter_evaluation(
        self,
        chapter: Chapter,
        version: Optional[ChapterVersion],
        feedback: str,
        decision: Optional[str] = None,
    ) -> None:
        evaluation = ChapterEvaluation(
            chapter_id=chapter.id,
            version_id=version.id if version else None,
            feedback=feedback,
            decision=decision,
        )
        self.session.add(evaluation)
        chapter.status = ChapterGenerationStatus.WAITING_FOR_CONFIRM.value
        chapter.generation_progress = 100
        chapter.generation_step = "evaluation_done"
        chapter.generation_step_index = 3
        chapter.generation_step_total = 3
        await self.session.commit()
        await self.session.refresh(chapter)
        await self._touch_project(chapter.project_id)

    async def reset_chapter_without_workflow(
        self,
        project_id: str,
        chapter_number: int,
    ) -> None:
        """清理没有 durable run 的未定稿章节，同时保留章节大纲。"""

        outline = await self.get_outline(project_id, chapter_number)
        if outline is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="章节大纲不存在")
        chapter = await self.repo.get_chapter_for_update(
            project_id=project_id,
            chapter_number=chapter_number,
        )
        if chapter is None:
            await self.session.rollback()
            return
        if chapter.selected_version_id is not None or int(chapter.current_revision or 0) > 0:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="已完成章节不能重置，请使用删除章节",
            )

        try:
            await self.session.execute(
                delete(ChapterEvaluation).where(ChapterEvaluation.chapter_id == chapter.id)
            )
            await self.session.execute(
                delete(ChapterVersion).where(ChapterVersion.chapter_id == chapter.id)
            )
            await self.session.execute(
                delete(ChapterGenerationTrace).where(
                    ChapterGenerationTrace.chapter_id == chapter.id
                )
            )
            chapter.status = ChapterGenerationStatus.NOT_GENERATED.value
            chapter.generation_progress = 0
            chapter.generation_step = None
            chapter.generation_step_index = 0
            chapter.generation_step_total = 0
            chapter.generation_started_at = None
            chapter.real_summary = None
            chapter.word_count = 0
            chapter.source_hash = None
            chapter.required_projection_snapshot = []
            chapter.projection_generation = None
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        await self._touch_project(project_id)

    async def delete_chapters(
        self,
        project_id: str,
        chapter_numbers: Iterable[int],
        *,
        delete_artifacts_confirmed: bool = False,
        confirmation_text: Optional[str] = None,
    ) -> None:
        numbers = sorted({int(number) for number in chapter_numbers if int(number) > 0})
        if not numbers:
            return

        outlines_result = await self.session.execute(
            select(ChapterOutline)
            .where(ChapterOutline.project_id == project_id)
            .order_by(ChapterOutline.chapter_number.asc())
        )
        outlines = list(outlines_result.scalars())
        outline_numbers = {outline.chapter_number for outline in outlines}
        missing_numbers = [number for number in numbers if number not in outline_numbers]
        if missing_numbers:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"章节大纲不存在: {', '.join(map(str, missing_numbers))}",
            )

        project = await self.repo.get_by_id(project_id)
        if project is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
        chapters_result = await self.session.execute(
            select(Chapter).where(Chapter.project_id == project_id).with_for_update()
        )
        chapters_by_number = {
            chapter.chapter_number: chapter for chapter in chapters_result.scalars()
        }
        completed_numbers = sorted(
            number
            for number, chapter in chapters_by_number.items()
            if chapter.status == ChapterGenerationStatus.SUCCESSFUL.value
        )
        latest_completed_number = completed_numbers[-1] if completed_numbers else None
        completed_to_delete: List[int] = []
        draft_numbers: List[int] = []

        for number in numbers:
            chapter = chapters_by_number.get(number)
            if chapter and chapter.status == ChapterGenerationStatus.SUCCESSFUL.value:
                if number != latest_completed_number:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="只能删除最近一个已完成章节",
                    )
                completed_to_delete.append(number)
                continue

            if chapter and chapter.status != ChapterGenerationStatus.NOT_GENERATED.value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="只能删除未生成大纲章节或最近一个已完成章节",
                )
            draft_numbers.append(number)

        if completed_to_delete:
            completed_number = completed_to_delete[0]
            if not delete_artifacts_confirmed:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="删除最近已完成章节必须二次确认删除章节及全部产物",
                )

            later_outline_numbers = sorted(
                number for number in outline_numbers if number > completed_number
            )
            missing_later_numbers = [
                number for number in later_outline_numbers if number not in draft_numbers
            ]
            if missing_later_numbers:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="删除最近已完成章节时必须同时删除其后的未生成章节大纲",
                )

        if draft_numbers:
            first_draft_number = min(draft_numbers)
            expected_tail_numbers = sorted(
                number for number in outline_numbers if number >= first_draft_number
            )
            if sorted(draft_numbers) != expected_tail_numbers:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="只能删除尾部连续未生成章节大纲",
                )

        completed_chapter_ids = [
            chapters_by_number[number].id
            for number in completed_to_delete
            if number in chapters_by_number
        ]
        tombstone_jobs = []

        try:
            if completed_chapter_ids:
                projection_service = ChapterProjectionService(self.session)
                for number in completed_to_delete:
                    tombstone_jobs.append(
                        await projection_service.create_tombstone_job(
                            chapter=chapters_by_number[number],
                            user_id=project.user_id,
                            reason="chapter_deleted",
                        )
                    )
                await self.session.execute(
                    delete(ChapterEvaluation).where(
                        ChapterEvaluation.chapter_id.in_(completed_chapter_ids)
                    )
                )
                await self.session.execute(
                    delete(ChapterVersion).where(
                        ChapterVersion.chapter_id.in_(completed_chapter_ids)
                    )
                )
                await self.session.execute(
                    delete(ChapterGenerationTrace).where(
                        ChapterGenerationTrace.chapter_id.in_(completed_chapter_ids)
                    )
                )
                await self.session.execute(
                    delete(Chapter).where(
                        Chapter.project_id == project_id,
                        Chapter.chapter_number.in_(completed_to_delete),
                    )
                )

            if draft_numbers:
                draft_chapter_ids = [
                    chapters_by_number[number].id
                    for number in draft_numbers
                    if number in chapters_by_number
                ]
                if draft_chapter_ids:
                    await self.session.execute(
                        delete(ChapterGenerationTrace).where(
                            ChapterGenerationTrace.chapter_id.in_(draft_chapter_ids)
                        )
                    )
                    await self.session.execute(
                        delete(Chapter).where(
                            Chapter.project_id == project_id,
                            Chapter.chapter_number.in_(draft_numbers),
                        )
                    )

            await self.session.execute(
                delete(ChapterOutline).where(
                    ChapterOutline.project_id == project_id,
                    ChapterOutline.chapter_number.in_(numbers),
                )
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        for job in tombstone_jobs:
            await publish_background_task(job.user_id)
        await self._touch_project(project_id)

    # ------------------------------------------------------------------
    # 序列化辅助
    # ------------------------------------------------------------------
    async def get_project_schema_for_admin(self, project_id: str) -> NovelProjectSchema:
        project = await self.repo.get_by_id(project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
        return await self._serialize_project(project)

    async def get_section_data_for_admin(
        self,
        project_id: str,
        section: NovelSectionType,
    ) -> NovelSectionResponse:
        project = await self.repo.get_by_id(project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
        return self._build_section_response(project, section)

    async def get_chapter_schema_for_admin(
        self,
        project_id: str,
        chapter_number: int,
    ) -> ChapterSchema:
        project = await self.repo.get_by_id(project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
        return self._build_chapter_schema(project, chapter_number)

    async def _serialize_project(self, project: NovelProject) -> NovelProjectSchema:
        await self._auto_fail_stale_in_progress_chapters(project.id, list(project.chapters))

        conversations = [
            {"role": convo.role, "content": convo.content}
            for convo in sorted(project.conversations, key=lambda c: c.seq)
        ]

        blueprint_schema = self._build_blueprint_schema(project)

        outlines_map = {outline.chapter_number: outline for outline in project.outlines}
        chapters_map = {chapter.chapter_number: chapter for chapter in project.chapters}
        chapter_numbers = sorted(set(outlines_map.keys()) | set(chapters_map.keys()))
        chapters_schema: List[ChapterSchema] = [
            self._build_chapter_schema(
                project,
                number,
                outlines_map=outlines_map,
                chapters_map=chapters_map,
            )
            for number in chapter_numbers
        ]

        return NovelProjectSchema(
            id=project.id,
            user_id=project.user_id,
            title=project.title,
            initial_prompt=project.initial_prompt or "",
            conversation_history=conversations,
            blueprint=blueprint_schema,
            chapters=chapters_schema,
        )

    @staticmethod
    def _to_utc_if_possible(value: Optional[datetime]) -> Optional[datetime]:
        if value is None:
            return None
        if value.tzinfo is None:
            # 兼容 naive 时间（默认按 UTC 写入），补 UTC 时区。
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    async def _auto_fail_stale_in_progress_chapters(
        self, project_id: str, chapters: List[Chapter]
    ) -> None:
        if not chapters:
            return

        now_utc = datetime.now(timezone.utc)
        changed = False

        for chapter in chapters:
            if chapter is None:
                continue
            if chapter.status not in (
                ChapterGenerationStatus.GENERATING.value,
                ChapterGenerationStatus.EVALUATING.value,
                ChapterGenerationStatus.SELECTING.value,
            ):
                continue

            updated_at_utc = self._to_utc_if_possible(chapter.updated_at)
            started_at_utc = self._to_utc_if_possible(chapter.generation_started_at)
            reference_ts = updated_at_utc or started_at_utc
            if reference_ts is None:
                continue

            if now_utc - reference_ts <= self.STALE_IN_PROGRESS_TIMEOUT:
                continue

            prev_status = chapter.status
            chapter.status = ChapterGenerationStatus.FAILED.value
            chapter.generation_progress = 0
            chapter.generation_step = "failed"
            chapter.generation_step_index = 0
            # 仅在缺省时兜底，避免覆盖已有流程总步数
            chapter.generation_step_total = chapter.generation_step_total or 0
            changed = True
            self.session.add(chapter)
            logger.warning(
                f"检测到章节生成状态超时，自动标记失败: project_id={project_id} "
                f"chapter_number={chapter.chapter_number} prev_status={prev_status}"
            )

        if changed:
            await self.session.commit()

    async def _touch_project(self, project_id: str) -> None:
        await self.session.execute(
            update(NovelProject)
            .where(NovelProject.id == project_id)
            .values(updated_at=datetime.now(timezone.utc))
        )
        await self.session.commit()

    def _build_blueprint_schema(self, project: NovelProject) -> Blueprint:
        blueprint_obj = project.blueprint
        if blueprint_obj:
            return Blueprint(
                title=blueprint_obj.title or "",
                target_audience=blueprint_obj.target_audience or "",
                genre=blueprint_obj.genre or "",
                style=blueprint_obj.style or "",
                tone=blueprint_obj.tone or "",
                one_sentence_summary=blueprint_obj.one_sentence_summary or "",
                full_synopsis=blueprint_obj.full_synopsis or "",
                world_setting=blueprint_obj.world_setting or {},
                characters=[
                    {
                        "name": character.name,
                        "identity": character.identity,
                        "personality": character.personality,
                        "goals": character.goals,
                        "abilities": character.abilities,
                        "relationship_to_protagonist": character.relationship_to_protagonist,
                        **(character.extra or {}),
                    }
                    for character in sorted(project.characters, key=lambda c: c.position)
                ],
                relationships=[
                    {
                        "character_from": relation.character_from,
                        "character_to": relation.character_to,
                        "description": relation.description or "",
                        "relationship_type": getattr(relation, "relationship_type", None),
                    }
                    for relation in sorted(project.relationships_, key=lambda r: r.position)
                ],
                chapter_outline=[
                    ChapterOutlineSchema(
                        chapter_number=outline.chapter_number,
                        title=outline.title,
                        summary=outline.summary or "",
                        goals=outline.goals or "",
                        highlights=outline.highlights or [],
                        character_states=outline.character_states or {},
                    )
                    for outline in sorted(project.outlines, key=lambda o: o.chapter_number)
                ],
            )
        return Blueprint(
            title="",
            target_audience="",
            genre="",
            style="",
            tone="",
            one_sentence_summary="",
            full_synopsis="",
            world_setting={},
            characters=[],
            relationships=[],
            chapter_outline=[],
        )

    def _build_section_response(
        self,
        project: NovelProject,
        section: NovelSectionType,
    ) -> NovelSectionResponse:
        blueprint = self._build_blueprint_schema(project)

        if section == NovelSectionType.OVERVIEW:
            data = {
                "title": project.title,
                "initial_prompt": project.initial_prompt or "",
                "status": project.status,
                "one_sentence_summary": blueprint.one_sentence_summary,
                "target_audience": blueprint.target_audience,
                "genre": blueprint.genre,
                "style": blueprint.style,
                "tone": blueprint.tone,
                "full_synopsis": blueprint.full_synopsis,
                "updated_at": project.updated_at.isoformat() if project.updated_at else None,
            }
        elif section == NovelSectionType.WORLD_SETTING:
            data = {
                "world_setting": blueprint.world_setting or {},
            }
        elif section == NovelSectionType.CHARACTERS:
            data = {
                "characters": blueprint.characters,
            }
        elif section == NovelSectionType.RELATIONSHIPS:
            data = {
                "relationships": blueprint.relationships,
            }
        elif section == NovelSectionType.CHAPTER_OUTLINE:
            data = {
                "chapter_outline": [outline.model_dump() for outline in blueprint.chapter_outline],
            }
        elif section == NovelSectionType.CHAPTERS:
            outlines_map = {outline.chapter_number: outline for outline in project.outlines}
            chapters_map = {chapter.chapter_number: chapter for chapter in project.chapters}
            chapter_numbers = sorted(set(outlines_map.keys()) | set(chapters_map.keys()))
            # 章节列表只返回元数据，不包含完整内容
            chapters = [
                self._build_chapter_schema(
                    project,
                    number,
                    outlines_map=outlines_map,
                    chapters_map=chapters_map,
                    include_content=False,
                ).model_dump()
                for number in chapter_numbers
            ]
            data = {
                "chapters": chapters,
                "total": len(chapters),
            }
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="未知的章节类型")

        return NovelSectionResponse(section=section, data=data)

    def _build_chapter_schema(
        self,
        project: NovelProject,
        chapter_number: int,
        *,
        outlines_map: Optional[Dict[int, ChapterOutline]] = None,
        chapters_map: Optional[Dict[int, Chapter]] = None,
        include_content: bool = True,
    ) -> ChapterSchema:
        outlines = outlines_map or {outline.chapter_number: outline for outline in project.outlines}
        chapters = chapters_map or {chapter.chapter_number: chapter for chapter in project.chapters}
        outline = outlines.get(chapter_number)
        chapter = chapters.get(chapter_number)

        return self._build_chapter_schema_from_entities(
            chapter_number=chapter_number,
            outline=outline,
            chapter=chapter,
            include_content=include_content,
        )

    def _build_chapter_schema_from_entities(
        self,
        *,
        chapter_number: int,
        outline: Optional[ChapterOutline],
        chapter: Optional[Chapter],
        include_content: bool = True,
    ) -> ChapterSchema:
        if not outline and not chapter:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="章节不存在")

        title = outline.title if outline else f"第{chapter_number}章"
        summary = outline.summary if outline else ""
        goals = outline.goals if outline else ""
        highlights = outline.highlights if outline else []
        character_states = outline.character_states if outline else {}
        real_summary = chapter.real_summary if chapter else None
        content = None
        versions: Optional[List[str]] = None
        version_selections: Optional[List[ChapterVersionSelectionSchema]] = None
        evaluation_text: Optional[str] = None
        status_value = ChapterGenerationStatus.NOT_GENERATED.value
        word_count = 0
        generation_traces: List[ChapterGenerationTraceSchema] = []

        if chapter:
            status_value = chapter.status or ChapterGenerationStatus.NOT_GENERATED.value
            word_count = chapter.word_count or 0
            loaded_versions = chapter.__dict__.get("versions") or []
            loaded_evaluations = chapter.__dict__.get("evaluations") or []
            loaded_selected_version = chapter.__dict__.get("selected_version")
            if "generation_traces" in chapter.__dict__ and chapter.generation_traces:
                generation_traces = [
                    ChapterGenerationTraceSchema(
                        id=trace.id,
                        node_key=trace.node_key,
                        node_label=trace.node_label,
                        stage=trace.stage,
                        status=trace.status,
                        uses_llm=self._trace_uses_llm(trace),
                        system_prompt=trace.system_prompt,
                        user_prompt=trace.user_prompt,
                        raw_response=trace.raw_response,
                        cleaned_output=trace.cleaned_output,
                        error=trace.error,
                        metadata=trace.metadata,
                        duration_ms=self._trace_duration_ms(trace),
                        started_at=trace.started_at,
                        ended_at=trace.ended_at,
                        created_at=trace.created_at,
                    )
                    for trace in sorted(
                        chapter.generation_traces,
                        key=lambda item: (item.created_at, item.id),
                    )
                ]

            # 只有在 include_content=True 时才包含完整内容
            if include_content:
                selected_version = None
                if chapter.selected_version_id and loaded_versions:
                    selected_version = next(
                        (v for v in loaded_versions if v.id == chapter.selected_version_id),
                        None,
                    )
                if (
                    selected_version is None
                    and loaded_selected_version
                    and (
                        chapter.selected_version_id is None
                        or loaded_selected_version.id == chapter.selected_version_id
                    )
                ):
                    selected_version = loaded_selected_version
                if selected_version:
                    content = selected_version.content
                if loaded_versions:
                    ordered_versions = sorted(
                        loaded_versions,
                        key=lambda item: (item.created_at, item.id),
                    )
                    versions = [version.content for version in ordered_versions]
                    confirmation_versions = ordered_versions
                    if status_value == ChapterGenerationStatus.WAITING_FOR_CONFIRM.value:
                        best_versions = [
                            version
                            for version in ordered_versions
                            if isinstance(version.metadata, dict)
                            and isinstance(version.metadata.get("ai_review"), dict)
                            and version.metadata["ai_review"].get("is_best") is True
                        ]
                        if len(best_versions) == 1:
                            confirmation_versions = best_versions
                    version_selections = [
                        ChapterVersionSelectionSchema(
                            id=version.id,
                            content=version.content,
                            version_label=version.version_label,
                            workflow_run_id=self._version_workflow_run_id(version),
                        )
                        for version in confirmation_versions
                    ]
                if loaded_evaluations:
                    latest = sorted(loaded_evaluations, key=lambda item: item.created_at)[-1]
                    evaluation_text = (
                        _normalize_chapter_evaluation_feedback(latest.feedback)
                        if latest.feedback
                        else latest.decision
                    )

        return ChapterSchema(
            chapter_number=chapter_number,
            title=title,
            summary=summary,
            goals=goals or "",
            highlights=highlights or [],
            character_states=character_states or {},
            real_summary=real_summary,
            content=content,
            versions=versions,
            version_selections=version_selections,
            evaluation=evaluation_text,
            generation_status=ChapterGenerationStatus(status_value),
            generation_progress=chapter.generation_progress if chapter else 0,
            generation_step=chapter.generation_step if chapter else None,
            generation_step_index=chapter.generation_step_index if chapter else 0,
            generation_step_total=chapter.generation_step_total if chapter else 0,
            generation_started_at=(
                chapter.__dict__.get("generation_started_at") if chapter else None
            ),
            # updated_at 可能因 DB 侧 onupdate 在 commit 后被标记为 expired；
            # 序列化阶段只读取已加载值，避免触发异步懒加载导致 MissingGreenlet。
            status_updated_at=chapter.__dict__.get("updated_at") if chapter else None,
            word_count=word_count,
            generation_traces=generation_traces,
        )

    @staticmethod
    def _version_workflow_run_id(version: ChapterVersion) -> Optional[str]:
        metadata = version.metadata if isinstance(version.metadata, dict) else {}
        workflow = metadata.get("_chapter_workflow")
        if not isinstance(workflow, dict):
            return None
        run_id = workflow.get("run_id")
        return run_id if isinstance(run_id, str) and len(run_id) == 36 else None

    @staticmethod
    def _trace_uses_llm(trace: Any) -> bool:
        """兼容旧 trace：优先读显式标记，缺失时再按调用材料推断。"""
        metadata = trace.metadata if isinstance(trace.metadata, dict) else {}
        explicit = metadata.get("uses_llm")
        if isinstance(explicit, bool):
            return explicit
        model_calls = metadata.get("model_calls")
        if isinstance(model_calls, list):
            return len(model_calls) > 0
        return any(
            bool((value or "").strip())
            for value in (trace.system_prompt, trace.user_prompt, trace.raw_response)
        )

    @staticmethod
    def _trace_duration_ms(trace: Any) -> Optional[int]:
        """返回节点系统耗时，兼容未写 duration_ms 的旧 trace。"""
        metadata = trace.metadata if isinstance(trace.metadata, dict) else {}
        duration_ms = metadata.get("duration_ms")
        if isinstance(duration_ms, (int, float)) and duration_ms >= 0:
            return int(duration_ms)
        started_at = getattr(trace, "started_at", None)
        ended_at = getattr(trace, "ended_at", None)
        if not started_at or not ended_at:
            return None
        return max(0, int((ended_at - started_at).total_seconds() * 1000))
