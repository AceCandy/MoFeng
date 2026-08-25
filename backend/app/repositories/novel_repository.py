# AIMETA P=小说仓库_小说和章节数据访问|R=小说CRUD_章节CRUD|NR=不含业务逻辑|E=NovelRepository|X=internal|A=仓库类|D=sqlalchemy|S=db|RD=./README.ai
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import selectinload

from ..models import Chapter, ChapterVersion, NovelProject
from .base import BaseRepository


class NovelRepository(BaseRepository[NovelProject]):
    model = NovelProject

    async def get_by_id(
        self,
        project_id: str,
        *,
        include_chapter_details: bool = True,
    ) -> Optional[NovelProject]:
        options = [
            selectinload(NovelProject.blueprint),
            selectinload(NovelProject.characters),
            selectinload(NovelProject.relationships_),
            selectinload(NovelProject.outlines),
            selectinload(NovelProject.conversations),
        ]
        if include_chapter_details:
            options.extend(
                [
                    selectinload(NovelProject.chapters).selectinload(Chapter.versions),
                    selectinload(NovelProject.chapters).selectinload(Chapter.evaluations),
                    selectinload(NovelProject.chapters).selectinload(Chapter.selected_version),
                    selectinload(NovelProject.chapters).selectinload(Chapter.generation_traces),
                ]
            )
        else:
            options.append(selectinload(NovelProject.chapters))

        stmt = (
            select(NovelProject)
            .where(NovelProject.id == project_id)
            # 强制从数据库刷新同一 Session 中已存在的实体，避免返回旧快照。
            .execution_options(populate_existing=True)
            .options(*options)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_by_user(self, user_id: int) -> Iterable[NovelProject]:
        result = await self.session.execute(
            select(NovelProject)
            .where(NovelProject.user_id == user_id)
            .order_by(NovelProject.updated_at.desc())
            .options(
                selectinload(NovelProject.blueprint),
                selectinload(NovelProject.outlines),
                selectinload(NovelProject.chapters).selectinload(Chapter.selected_version),
            )
        )
        return result.scalars().all()

    async def list_all(self) -> Iterable[NovelProject]:
        result = await self.session.execute(
            select(NovelProject)
            .order_by(NovelProject.updated_at.desc())
            .options(
                selectinload(NovelProject.owner),
                selectinload(NovelProject.blueprint),
                selectinload(NovelProject.outlines),
                selectinload(NovelProject.chapters).selectinload(Chapter.selected_version),
            )
        )
        return result.scalars().all()

    async def get_chapter_for_update(
        self,
        *,
        project_id: str,
        chapter_number: int,
    ) -> Optional[Chapter]:
        """锁定章节后加载编辑所需关系，串行化同章正文修改。"""

        stmt = (
            select(Chapter)
            .where(
                Chapter.project_id == project_id,
                Chapter.chapter_number == chapter_number,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
            .options(
                selectinload(Chapter.versions),
                selectinload(Chapter.selected_version),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def ensure_chapter_for_update(
        self,
        *,
        project_id: str,
        chapter_number: int,
    ) -> Chapter:
        """原子确保章节存在并锁行，供 durable workflow start 串行化活动槽。"""

        await self.session.execute(
            pg_insert(Chapter)
            .values(project_id=project_id, chapter_number=chapter_number)
            .on_conflict_do_nothing(index_elements=[Chapter.project_id, Chapter.chapter_number])
        )
        chapter = await self.get_chapter_for_update(
            project_id=project_id,
            chapter_number=chapter_number,
        )
        if chapter is None:
            raise RuntimeError("创建 Chapter 后无法重新锁定")
        return chapter

    async def get_owned_chapter(
        self,
        *,
        project_id: str,
        chapter_number: int,
        user_id: int,
    ) -> Optional[Chapter]:
        """读取属于当前用户的 Chapter identity，不获取行锁。"""

        result = await self.session.execute(
            select(Chapter)
            .join(NovelProject, NovelProject.id == Chapter.project_id)
            .where(
                Chapter.project_id == project_id,
                Chapter.chapter_number == chapter_number,
                NovelProject.user_id == user_id,
            )
        )
        return result.scalars().first()

    async def list_chapter_versions(self, *, chapter_id: int) -> list[ChapterVersion]:
        """按 legacy index 契约的稳定顺序返回章节版本。"""

        result = await self.session.execute(
            select(ChapterVersion)
            .where(ChapterVersion.chapter_id == chapter_id)
            .order_by(ChapterVersion.created_at, ChapterVersion.id)
        )
        return list(result.scalars().all())

    async def get_owned_selected_version(
        self,
        *,
        project_id: str,
        chapter_number: int,
        user_id: int,
        for_update: bool = False,
    ) -> Optional[tuple[Chapter, ChapterVersion]]:
        """读取任务绑定的当前选中版本；提交阶段同时锁定章节和版本。"""

        stmt = (
            select(Chapter, ChapterVersion)
            .join(NovelProject, NovelProject.id == Chapter.project_id)
            .join(ChapterVersion, ChapterVersion.id == Chapter.selected_version_id)
            .where(
                Chapter.project_id == project_id,
                Chapter.chapter_number == chapter_number,
                NovelProject.user_id == user_id,
            )
        )
        if for_update:
            stmt = stmt.with_for_update()
        row = (await self.session.execute(stmt)).first()
        if row is None:
            return None
        return row[0], row[1]
