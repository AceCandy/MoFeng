# AIMETA P=章节正文编辑服务_持久后处理投递|R=串行化正文修改_原子创建后处理任务|NR=不执行摘要向量伏笔计算|E=ChapterEditService|X=internal|A=服务类|D=sqlalchemy,job_service|S=db|RD=./README.ai
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.background_task import BackgroundTask
from ..models.novel import Chapter, ChapterVersion
from ..repositories.novel_repository import NovelRepository
from ..schemas.chapter_context import stable_digest
from .chapter_word_count_settings import count_chapter_words
from .job_service import JobService
from .novel_service import NovelService


@dataclass(frozen=True)
class ChapterEditResult:
    """正文更新及其 durable 后处理任务。"""

    chapter: Chapter
    selected_version: ChapterVersion
    job: BackgroundTask


class ChapterEditService:
    """统一 edit、edit-fast 与 optimizer 的正文提交边界。"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.novel_service = NovelService(session)
        self.novel_repo = NovelRepository(session)

    async def apply_content(
        self,
        *,
        project_id: str,
        chapter_number: int,
        content: str,
        user_id: int,
        version_label: str,
    ) -> ChapterEditResult:
        """锁定章节并让正文更新与 durable job 在同一事务提交。"""

        await self.novel_service.ensure_project_owner(project_id, user_id)
        await self.novel_service.get_or_create_chapter(project_id, chapter_number)
        chapter = await self.novel_repo.get_chapter_for_update(
            project_id=project_id,
            chapter_number=chapter_number,
        )
        if chapter is None:
            raise ValueError("章节不存在")

        target_version = chapter.selected_version
        if target_version is None and chapter.versions:
            target_version = max(chapter.versions, key=lambda item: item.created_at)

        if target_version is None:
            target_version = ChapterVersion(
                chapter_id=chapter.id,
                content=content,
                version_label=version_label,
            )
            self.session.add(target_version)
            await self.session.flush()
        else:
            target_version.content = content

        chapter.selected_version_id = target_version.id
        chapter.selected_version = target_version
        chapter.status = "successful"
        chapter.generation_progress = 100
        chapter.generation_step = "completed"
        chapter.generation_step_index = 7
        chapter.generation_step_total = 7
        chapter.word_count = count_chapter_words(content or "")

        job = await JobService(self.session).enqueue_job(
            user_id=user_id,
            project_id=project_id,
            job_type="chapter_edit_postprocess",
            title=f"更新第 {chapter_number} 章摘要、索引与伏笔",
            payload={
                "project_id": project_id,
                "chapter_number": chapter_number,
                "selected_version_id": target_version.id,
                "content_hash": stable_digest(content),
            },
            payload_version=1,
        )
        return ChapterEditResult(
            chapter=chapter,
            selected_version=target_version,
            job=job,
        )


__all__ = ["ChapterEditResult", "ChapterEditService"]
