# AIMETA P=章节定稿提交服务_版本选择与持久任务原子入队|R=鉴权_版本锁定_正文保存_job提交|NR=不执行外部后处理|E=ChapterFinalizeSubmissionService|X=internal|A=service|D=sqlalchemy,job_service|S=db|RD=./README.ai
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.background_task import BackgroundTask
from ..models.novel import Chapter, ChapterVersion
from ..schemas.chapter_context import stable_digest
from ..schemas.novel import ChapterGenerationStatus
from .chapter_projection_service import CanonicalFinalizeResult, ChapterProjectionService
from .chapter_word_count_settings import count_chapter_words
from .novel_service import NovelService


@dataclass(frozen=True)
class PreparedChapterFinalize:
    """同一事务内已锁定并校验的 canonical finalize 输入。"""

    chapter: Chapter
    selected_version: ChapterVersion
    source_content: str
    source_hash: str
    user_id: int
    skip_vector_update: bool
    idempotency_key: Optional[str]


class ChapterFinalizeSubmissionService:
    """在一个事务内锁定最终正文，并创建后续 durable job。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def submit(
        self,
        *,
        project_id: str,
        chapter_number: int,
        user_id: int,
        selected_version_index: Optional[int] = None,
        selected_version_id: Optional[int] = None,
        edited_content: Optional[str] = None,
        skip_vector_update: bool = False,
        idempotency_key: Optional[str] = None,
    ) -> BackgroundTask:
        """校验候选版本并把正文选择与 job.queued 原子提交。"""

        try:
            prepared = await self.prepare(
                project_id=project_id,
                chapter_number=chapter_number,
                user_id=user_id,
                selected_version_index=selected_version_index,
                selected_version_id=selected_version_id,
                edited_content=edited_content,
                skip_vector_update=skip_vector_update,
                idempotency_key=idempotency_key,
            )
            if isinstance(prepared, BackgroundTask):
                return prepared
            result = await self.apply(prepared)
            return await ChapterProjectionService(self.session).commit_finalize(result)
        except Exception:
            await self.session.rollback()
            raise

    async def prepare(
        self,
        *,
        project_id: str,
        chapter_number: int,
        user_id: int,
        selected_version_index: Optional[int] = None,
        selected_version_id: Optional[int] = None,
        edited_content: Optional[str] = None,
        skip_vector_update: bool = False,
        idempotency_key: Optional[str] = None,
    ) -> PreparedChapterFinalize | BackgroundTask:
        """锁定 Chapter/版本并构造不提交事务的 finalize 输入。"""

        if (selected_version_index is None) == (selected_version_id is None):
            raise ValueError("必须且只能指定候选草稿索引或版本 ID")

        await NovelService(self.session).ensure_project_owner(project_id, user_id)
        chapter = (
            (
                await self.session.execute(
                    select(Chapter)
                    .where(
                        Chapter.project_id == project_id,
                        Chapter.chapter_number == chapter_number,
                    )
                    .with_for_update()
                )
            )
            .scalars()
            .first()
        )
        if chapter is None:
            raise ValueError("章节不存在")

        versions = list(
            (
                await self.session.execute(
                    select(ChapterVersion)
                    .where(ChapterVersion.chapter_id == chapter.id)
                    .order_by(ChapterVersion.created_at, ChapterVersion.id)
                    .with_for_update()
                )
            )
            .scalars()
            .all()
        )
        if selected_version_index is not None:
            if selected_version_index < 0 or selected_version_index >= len(versions):
                raise ValueError("候选草稿索引无效")
            selected_version = versions[selected_version_index]
        else:
            selected_version = next(
                (version for version in versions if version.id == selected_version_id),
                None,
            )
            if selected_version is None:
                raise ValueError("选中的版本不存在或内容为空")

        final_content = edited_content if edited_content is not None else selected_version.content
        final_content = (final_content or "").strip()
        if not final_content:
            raise ValueError("最终正文为空，无法定稿")

        source_hash = stable_digest(final_content)
        projection_service = ChapterProjectionService(self.session)
        existing = await projection_service.find_existing_finalize_job(
            user_id=user_id,
            project_id=project_id,
            selected_version_id=selected_version.id,
            source_hash=source_hash,
            skip_vector_update=skip_vector_update,
            idempotency_key=idempotency_key,
        )
        if existing is not None:
            return existing

        selected_version.content = final_content
        chapter.status = ChapterGenerationStatus.FINALIZING.value
        chapter.generation_progress = 0
        chapter.generation_step = "confirm_finalize"
        chapter.generation_step_index = 1
        chapter.generation_step_total = 4
        chapter.selected_version_id = selected_version.id
        chapter.selected_version = selected_version
        chapter.word_count = count_chapter_words(final_content)
        return PreparedChapterFinalize(
            chapter=chapter,
            selected_version=selected_version,
            source_content=final_content,
            source_hash=source_hash,
            user_id=user_id,
            skip_vector_update=skip_vector_update,
            idempotency_key=idempotency_key,
        )

    async def apply(
        self,
        prepared: PreparedChapterFinalize,
        *,
        workflow_stream_id: Optional[str] = None,
    ) -> CanonicalFinalizeResult:
        """在 prepare 的同一事务内追加 revision/outbox/job，但不提交。"""

        return await ChapterProjectionService(self.session).create_finalize(
            chapter=prepared.chapter,
            selected_version=prepared.selected_version,
            source_content=prepared.source_content,
            source_hash=prepared.source_hash,
            user_id=prepared.user_id,
            skip_vector_update=prepared.skip_vector_update,
            idempotency_key=prepared.idempotency_key,
            workflow_stream_id=workflow_stream_id,
        )


__all__ = ["ChapterFinalizeSubmissionService", "PreparedChapterFinalize"]
