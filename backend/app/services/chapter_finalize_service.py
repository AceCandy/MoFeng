# AIMETA P=章节定稿提交服务_版本选择与持久任务原子入队|R=鉴权_版本锁定_正文保存_job提交|NR=不执行外部后处理|E=ChapterFinalizeSubmissionService|X=internal|A=service|D=sqlalchemy,job_service|S=db|RD=./README.ai
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.background_task import BackgroundTask
from ..models.novel import Chapter, ChapterVersion
from ..schemas.chapter_context import stable_digest
from ..schemas.novel import ChapterGenerationStatus
from .chapter_word_count_settings import count_chapter_words
from .chapter_projection_service import ChapterProjectionService
from .novel_service import NovelService


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

        if (selected_version_index is None) == (selected_version_id is None):
            raise ValueError("必须且只能指定候选草稿索引或版本 ID")

        await NovelService(self.session).ensure_project_owner(project_id, user_id)
        chapter = (
            await self.session.execute(
                select(Chapter)
                .where(
                    Chapter.project_id == project_id,
                    Chapter.chapter_number == chapter_number,
                )
                .with_for_update()
            )
        ).scalars().first()
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
            ).scalars().all()
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

        try:
            result = await projection_service.create_finalize(
                chapter=chapter,
                selected_version=selected_version,
                source_content=final_content,
                source_hash=source_hash,
                user_id=user_id,
                skip_vector_update=skip_vector_update,
                idempotency_key=idempotency_key,
            )
            return await projection_service.commit_finalize(result)
        except Exception:
            await self.session.rollback()
            raise


__all__ = ["ChapterFinalizeSubmissionService"]
