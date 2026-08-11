import pytest
from sqlalchemy import select

from app.models import (
    BlueprintCharacter,
    ChapterBlueprint,
    ChapterSnapshot,
    CharacterState,
    NovelProject,
    ProjectMemory,
)
from app.models.user import User
from app.services.finalize_service import FinalizeService


class FakeLLMService:
    async def generate(self, prompt: str, **_: object) -> str:
        if "剧情线追踪" in prompt:
            return '{"unresolved_hooks": [], "main_conflicts": [], "character_arcs": []}'
        if "章节标题" in prompt:
            return "本章摘要"
        if "角色状态" in prompt:
            return "主角：状态稳定"
        return "更新后的全局摘要"


@pytest.mark.asyncio(loop_scope="session")
async def test_finalize_chapter_uses_async_session_without_missing_greenlet(
    db_session_factory,
) -> None:
    async with db_session_factory() as session:
        session.add(User(id=1, username="writer", hashed_password="secret"))
        session.add(
            NovelProject(id="project-1", user_id=1, title="测试项目", initial_prompt="测试")
        )
        await session.commit()
        session.add(BlueprintCharacter(project_id="project-1", name="主角", position=1))
        session.add(ChapterBlueprint(project_id="project-1", chapter_number=1))
        await session.commit()

        service = FinalizeService(session, FakeLLMService())
        result = await service.finalize_chapter(
            project_id="project-1",
            chapter_number=1,
            chapter_text="第一章正文内容。",
            user_id=1,
            skip_vector_update=True,
        )

        assert result["success"] is True
        assert result["updates"] == {
            "global_summary": "updated",
            "character_state": "updated",
            "plot_arcs": "updated",
            "snapshot": "created",
        }

        memory = (
            (
                await session.execute(
                    select(ProjectMemory).where(ProjectMemory.project_id == "project-1")
                )
            )
            .scalars()
            .one()
        )
        blueprint = (
            (
                await session.execute(
                    select(ChapterBlueprint).where(
                        ChapterBlueprint.project_id == "project-1",
                        ChapterBlueprint.chapter_number == 1,
                    )
                )
            )
            .scalars()
            .one()
        )
        snapshots = (
            (
                await session.execute(
                    select(ChapterSnapshot).where(ChapterSnapshot.project_id == "project-1")
                )
            )
            .scalars()
            .all()
        )
        states = (
            (
                await session.execute(
                    select(CharacterState).where(CharacterState.project_id == "project-1")
                )
            )
            .scalars()
            .all()
        )

        assert memory.global_summary == "更新后的全局摘要"
        assert memory.last_updated_chapter == 1
        assert memory.version == 2
        assert blueprint.is_finalized is True
        assert len(snapshots) == 1
        assert snapshots[0].chapter_summary == "本章摘要"
        assert len(states) == 1
        assert states[0].character_id is not None
        assert states[0].character_name == "主角"
        assert states[0].extra == {"raw_state_text": "主角：状态稳定"}


@pytest.mark.asyncio(loop_scope="session")
async def test_finalize_chapter_skips_character_state_without_blueprint_character(
    db_session_factory,
) -> None:
    async with db_session_factory() as session:
        session.add(User(id=1, username="writer", hashed_password="secret"))
        session.add(
            NovelProject(id="project-1", user_id=1, title="测试项目", initial_prompt="测试")
        )
        await session.commit()
        session.add(ChapterBlueprint(project_id="project-1", chapter_number=1))
        await session.commit()

        service = FinalizeService(session, FakeLLMService())
        result = await service.finalize_chapter(
            project_id="project-1",
            chapter_number=1,
            chapter_text="第一章正文内容。",
            user_id=1,
            skip_vector_update=True,
        )

        assert result["success"] is True
        assert result["updates"]["character_state"] == "updated"

        states = (
            (
                await session.execute(
                    select(CharacterState).where(CharacterState.project_id == "project-1")
                )
            )
            .scalars()
            .all()
        )
        snapshots = (
            (
                await session.execute(
                    select(ChapterSnapshot).where(ChapterSnapshot.project_id == "project-1")
                )
            )
            .scalars()
            .all()
        )

        # 没有蓝图角色时不能写 character_id=0，否则 MySQL 外键会在定稿时回滚整笔事务。
        assert states == []
        assert snapshots[0].character_states_snapshot == {"raw_text": "主角：状态稳定"}


class FailingLLMService:
    """所有 LLM 调用均抛异常，用于验证全失败不再静默报 success=True（H4）。"""

    async def generate(self, prompt: str, **_: object) -> str:
        raise RuntimeError("LLM 503")


class PartialFailingLLMService:
    """仅剧情线调用抛异常，用于验证部分失败返回 partial_success（H4）。"""

    async def generate(self, prompt: str, **_: object) -> str:
        if "剧情线追踪" in prompt:
            raise RuntimeError("plot_arcs 503")
        if "章节标题" in prompt:
            return "本章摘要"
        if "角色状态" in prompt:
            return "主角：状态稳定"
        return "更新后的全局摘要"


@pytest.mark.asyncio(loop_scope="session")
async def test_finalize_chapter_all_llm_fail_returns_success_false(db_session_factory) -> None:
    """所有 LLM 调用失败时 success=False 且记录全部失败项，不再静默误报成功；不写快照避免与上层回滚不一致（H4）。"""
    async with db_session_factory() as session:
        session.add(User(id=1, username="writer", hashed_password="secret"))
        session.add(
            NovelProject(id="project-1", user_id=1, title="测试项目", initial_prompt="测试")
        )
        await session.commit()
        session.add(ChapterBlueprint(project_id="project-1", chapter_number=1))
        await session.commit()

        service = FinalizeService(session, FailingLLMService())
        result = await service.finalize_chapter(
            project_id="project-1",
            chapter_number=1,
            chapter_text="第一章正文内容。",
            user_id=1,
            skip_vector_update=True,
        )

        assert result["success"] is False
        assert "partial_success" not in result
        assert len(result["errors"]) == 4
        # 全失败不写快照，避免章节回滚后残留无效快照
        snapshots = (
            (
                await session.execute(
                    select(ChapterSnapshot).where(ChapterSnapshot.project_id == "project-1")
                )
            )
            .scalars()
            .all()
        )
        assert snapshots == []


@pytest.mark.asyncio(loop_scope="session")
async def test_finalize_chapter_partial_llm_fail_returns_partial_success(
    db_session_factory,
) -> None:
    """部分 LLM 调用失败时 success=True 且 partial_success=True，失败项记录到 errors（H4）。"""
    async with db_session_factory() as session:
        session.add(User(id=1, username="writer", hashed_password="secret"))
        session.add(
            NovelProject(id="project-1", user_id=1, title="测试项目", initial_prompt="测试")
        )
        await session.commit()
        session.add(ChapterBlueprint(project_id="project-1", chapter_number=1))
        await session.commit()

        service = FinalizeService(session, PartialFailingLLMService())
        result = await service.finalize_chapter(
            project_id="project-1",
            chapter_number=1,
            chapter_text="第一章正文内容。",
            user_id=1,
            skip_vector_update=True,
        )

        assert result["success"] is True
        assert result["partial_success"] is True
        assert len(result["errors"]) == 1
        assert result["errors"][0]["field"] == "plot_arcs"
        assert "plot_arcs" not in result["updates"]
        assert result["updates"]["global_summary"] == "updated"
        assert result["updates"]["character_state"] == "updated"
        assert result["updates"]["snapshot"] == "created"


class ConcurrentModifyLLMService:
    """模拟 LLM 调用期间另一事务改了 memory.version（乐观锁冲突）。

    在第一次 generate 时用独立 session 自增 version 并改 global_summary，
    使得 finalize 写回时 WHERE version=old 不匹配。
    """

    def __init__(self, db_session_factory, project_id: str):
        self._factory = db_session_factory
        self._project_id = project_id
        self._modified = False

    async def generate(self, prompt: str, **_: object) -> str:
        if not self._modified:
            async with self._factory() as other:
                memory = (
                    (
                        await other.execute(
                            select(ProjectMemory).where(
                                ProjectMemory.project_id == self._project_id
                            )
                        )
                    )
                    .scalars()
                    .one()
                )
                memory.version += 1
                memory.global_summary = "并发用户编辑"
                await other.commit()
            self._modified = True
        if "剧情线追踪" in prompt:
            return '{"unresolved_hooks": [], "main_conflicts": [], "character_arcs": []}'
        if "章节标题" in prompt:
            return "本章摘要"
        if "角色状态" in prompt:
            return "主角：状态稳定"
        return "LLM 生成的摘要"


@pytest.mark.asyncio(loop_scope="session")
async def test_finalize_chapter_conflict_keeps_concurrent_edit(db_session_factory) -> None:
    """乐观锁冲突：LLM 期间 memory.version 被并发改，写回不覆盖，result.conflict=True，LLM 结果仍入 snapshot。"""
    async with db_session_factory() as session:
        session.add(User(id=1, username="writer", hashed_password="secret"))
        session.add(
            NovelProject(id="project-1", user_id=1, title="测试项目", initial_prompt="测试")
        )
        await session.commit()
        session.add(BlueprintCharacter(project_id="project-1", name="主角", position=1))
        session.add(ChapterBlueprint(project_id="project-1", chapter_number=1))
        await session.commit()

        llm = ConcurrentModifyLLMService(db_session_factory, "project-1")
        service = FinalizeService(session, llm)
        result = await service.finalize_chapter(
            project_id="project-1",
            chapter_number=1,
            chapter_text="第一章正文内容。",
            user_id=1,
            skip_vector_update=True,
        )

        assert result["success"] is True
        assert result["conflict"] is True
        # 冲突时 global_summary/plot_arcs 未写入 memory，不标记 updated
        assert "global_summary" not in result["updates"]
        assert "plot_arcs" not in result["updates"]

    # 用独立 session 验证 memory 保留并发修改、snapshot 仍有 LLM 结果
    async with db_session_factory() as verify:
        memory = (
            (
                await verify.execute(
                    select(ProjectMemory).where(ProjectMemory.project_id == "project-1")
                )
            )
            .scalars()
            .one()
        )
        assert memory.global_summary == "并发用户编辑"
        assert memory.version == 2
        snapshots = (
            (
                await verify.execute(
                    select(ChapterSnapshot).where(ChapterSnapshot.project_id == "project-1")
                )
            )
            .scalars()
            .all()
        )
        assert len(snapshots) == 1
        assert snapshots[0].global_summary_snapshot == "LLM 生成的摘要"
