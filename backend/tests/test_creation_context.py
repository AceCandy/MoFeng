# AIMETA P=创作上下文测试_跨设备恢复合同|R=字段PATCH_轮次保护_隔离_并发|NR=不执行前端恢复|E=test_*|X=internal|A=integration_test|D=pytest|S=test|RD=./README.ai
import asyncio
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError
from sqlalchemy import delete, select

from app.models import NovelProject, UserCreationContext
from app.models.user import User
from app.schemas.creation_context import CreationContextPatch
from app.services.creation_context_service import CreationContextService
from app.services.novel_service import NovelService


async def _seed_project(session, *, user_id: int, project_id: str) -> None:
    session.add(User(id=user_id, username=f"context-{user_id}", hashed_password="secret"))
    session.add(
        NovelProject(
            id=project_id,
            user_id=user_id,
            title="创作上下文测试",
            initial_prompt="测试",
        )
    )
    await session.commit()


def test_creation_context_patch_requires_fields_and_draft_turn_pair() -> None:
    with pytest.raises(ValidationError, match="至少需要更新"):
        CreationContextPatch()
    with pytest.raises(ValidationError, match="必须同时提交"):
        CreationContextPatch(inspiration_draft="未发送")
    with pytest.raises(ValidationError, match="必须同时提交"):
        CreationContextPatch(inspiration_turn=0)


@pytest.mark.asyncio(loop_scope="session")
async def test_patch_updates_only_supplied_fields_and_same_turn_last_write_wins(
    db_session_factory,
) -> None:
    async with db_session_factory() as session:
        await _seed_project(session, user_id=5101, project_id="context-fields")
        service = CreationContextService(session)

        await service.patch_context(
            user_id=5101,
            project_id="context-fields",
            patch=CreationContextPatch(
                surface="writing",
                chapter_number=2,
                inspiration_draft="第一份草稿",
                inspiration_turn=0,
            ),
        )
        await service.patch_context(
            user_id=5101,
            project_id="context-fields",
            patch=CreationContextPatch(desk_section="versions"),
        )
        context = await service.patch_context(
            user_id=5101,
            project_id="context-fields",
            patch=CreationContextPatch(
                inspiration_draft="后写入草稿",
                inspiration_turn=0,
            ),
        )

        assert context.surface == "writing"
        assert context.chapter_number == 2
        assert context.desk_section == "versions"
        assert context.inspiration_draft == "后写入草稿"
        assert context.inspiration_turn == 0


@pytest.mark.asyncio(loop_scope="session")
async def test_assistant_turn_clears_draft_and_stale_patch_keeps_other_fields(
    db_session_factory,
) -> None:
    async with db_session_factory() as session:
        await _seed_project(session, user_id=5102, project_id="context-stale")
        session.add(User(id=5103, username="context-5103", hashed_password="secret"))
        await session.commit()
        session.add(
            UserCreationContext(
                user_id=5103,
                project_id="context-stale",
                inspiration_draft="其他用户草稿",
                inspiration_turn=0,
            )
        )
        await session.commit()

        service = CreationContextService(session)
        await service.patch_context(
            user_id=5102,
            project_id="context-stale",
            patch=CreationContextPatch(
                inspiration_draft="即将过期",
                inspiration_turn=0,
            ),
        )
        await NovelService(session).append_conversation(
            "context-stale",
            "assistant",
            "下一轮问题",
        )
        context = await service.patch_context(
            user_id=5102,
            project_id="context-stale",
            patch=CreationContextPatch(
                surface="archive",
                inspiration_draft="旧轮次迟到草稿",
                inspiration_turn=0,
            ),
        )
        other_context = await session.get(
            UserCreationContext,
            (5103, "context-stale"),
        )

        assert context.surface == "archive"
        assert context.inspiration_draft is None
        assert context.inspiration_turn == 1
        assert other_context is not None
        assert other_context.inspiration_draft == "其他用户草稿"
        assert other_context.inspiration_turn == 0


@pytest.mark.asyncio(loop_scope="session")
async def test_future_inspiration_turn_is_rejected(db_session_factory) -> None:
    async with db_session_factory() as session:
        await _seed_project(session, user_id=5104, project_id="context-future")

        with pytest.raises(ValueError, match="灵感轮次无效"):
            await CreationContextService(session).patch_context(
                user_id=5104,
                project_id="context-future",
                patch=CreationContextPatch(
                    inspiration_draft="超前草稿",
                    inspiration_turn=1,
                ),
            )

        assert await session.get(UserCreationContext, (5104, "context-future")) is None


@pytest.mark.asyncio(loop_scope="session")
async def test_context_list_is_user_scoped_and_stable_on_equal_timestamps(
    db_session_factory,
) -> None:
    async with db_session_factory() as session:
        shared_time = datetime(2026, 8, 24, tzinfo=timezone.utc)
        session.add_all(
            [
                User(id=5105, username="context-5105", hashed_password="secret"),
                User(id=5106, username="context-5106", hashed_password="secret"),
            ]
        )
        await session.commit()
        session.add_all(
            [
                NovelProject(
                    id="context-order-b",
                    user_id=5105,
                    title="B",
                    initial_prompt="测试",
                ),
                NovelProject(
                    id="context-order-a",
                    user_id=5105,
                    title="A",
                    initial_prompt="测试",
                ),
                NovelProject(
                    id="context-other-user",
                    user_id=5106,
                    title="其他用户",
                    initial_prompt="测试",
                ),
            ]
        )
        await session.commit()
        session.add_all(
            [
                UserCreationContext(
                    user_id=5105,
                    project_id="context-order-b",
                    updated_at=shared_time,
                ),
                UserCreationContext(
                    user_id=5105,
                    project_id="context-order-a",
                    updated_at=shared_time,
                ),
                UserCreationContext(
                    user_id=5106,
                    project_id="context-other-user",
                    updated_at=shared_time,
                ),
            ]
        )
        await session.commit()

        contexts = await CreationContextService(session).list_contexts(user_id=5105)

        assert [context.project_id for context in contexts] == [
            "context-order-a",
            "context-order-b",
        ]


@pytest.mark.asyncio(loop_scope="session")
async def test_context_cascades_when_project_or_user_is_deleted(db_session_factory) -> None:
    async with db_session_factory() as session:
        await _seed_project(session, user_id=5107, project_id="context-delete-project")
        await _seed_project(session, user_id=5108, project_id="context-delete-user")
        session.add_all(
            [
                UserCreationContext(user_id=5107, project_id="context-delete-project"),
                UserCreationContext(user_id=5108, project_id="context-delete-user"),
            ]
        )
        await session.commit()

        await session.execute(
            delete(NovelProject).where(NovelProject.id == "context-delete-project")
        )
        await session.execute(delete(User).where(User.id == 5108))
        await session.commit()

        contexts = list((await session.scalars(select(UserCreationContext))).all())
        assert contexts == []


@pytest.mark.asyncio(loop_scope="session")
async def test_concurrent_first_patches_preserve_both_fields(isolated_pg) -> None:
    session_factory = isolated_pg.session_factory
    async with session_factory() as session:
        await _seed_project(session, user_id=5109, project_id="context-concurrent")

    async def patch_context(patch: CreationContextPatch) -> None:
        async with session_factory() as session:
            await CreationContextService(session).patch_context(
                user_id=5109,
                project_id="context-concurrent",
                patch=patch,
            )

    await asyncio.gather(
        patch_context(CreationContextPatch(surface="writing")),
        patch_context(CreationContextPatch(chapter_number=3)),
    )

    async with session_factory() as session:
        context = await session.get(UserCreationContext, (5109, "context-concurrent"))

    assert context is not None
    assert context.surface == "writing"
    assert context.chapter_number == 3
