from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.routers.novels import create_novel
from app.models.user import User
from app.services.novel_service import NovelService


ROOT = Path(__file__).resolve().parents[2]
NOVELS_ROUTER = ROOT / "backend/app/api/routers/novels.py"


@pytest.mark.asyncio(loop_scope="session")
async def test_inspiration_project_blocks_new_start_until_blueprint_saved(db_session_factory):
    async with db_session_factory() as session:
        session.add(User(id=1, username="writer", hashed_password="secret"))
        await session.commit()

        service = NovelService(session)
        project = await service.create_project(
            1,
            "未命名灵感",
            "开始灵感模式",
            status=NovelService.INSPIRATION_ACTIVE_STATUS,
        )

        unfinished = await service.find_unfinished_inspiration_project(1)
        assert unfinished is not None
        assert unfinished.id == project.id

        project.status = NovelService.INSPIRATION_BLUEPRINT_GENERATED_STATUS
        await session.commit()
        generated = await service.find_unfinished_inspiration_project(1)
        assert generated is not None
        assert generated.id == project.id

        project.status = NovelService.INSPIRATION_COMPLETE_STATUS
        await session.commit()
        assert await service.find_unfinished_inspiration_project(1) is None


@pytest.mark.asyncio(loop_scope="session")
async def test_legacy_unnamed_inspiration_draft_is_treated_as_unfinished(db_session_factory):
    async with db_session_factory() as session:
        session.add(User(id=1, username="writer", hashed_password="secret"))
        await session.commit()

        service = NovelService(session)
        project = await service.create_project(1, "未命名灵感", "开始灵感模式")

        unfinished = await service.find_unfinished_inspiration_project(1)
        assert unfinished is not None
        assert unfinished.id == project.id


@pytest.mark.asyncio(loop_scope="session")
async def test_create_novel_returns_conflict_with_existing_unfinished_inspiration(db_session_factory):
    async with db_session_factory() as session:
        session.add(User(id=1, username="writer", hashed_password="secret"))
        await session.commit()

        service = NovelService(session)
        project = await service.create_project(
            1,
            "未命名灵感",
            "开始灵感模式",
            status=NovelService.INSPIRATION_ACTIVE_STATUS,
        )

        with pytest.raises(HTTPException) as exc_info:
            await create_novel(
                title="未命名灵感",
                initial_prompt="开始灵感模式",
                session=session,
                current_user=SimpleNamespace(id=1),
            )

        assert exc_info.value.status_code == 409
        assert exc_info.value.detail["code"] == "unfinished_inspiration"
        assert exc_info.value.detail["project_id"] == project.id


def test_generate_blueprint_does_not_rename_unfinished_inspiration_before_save():
    source = NOVELS_ROUTER.read_text(encoding="utf-8")
    generate_block = source.split("async def generate_blueprint", 1)[1].split(
        "\n\n@router.post(\"/{project_id}/blueprint/save\"",
        1,
    )[0]

    assert "if blueprint.title and not is_inspiration_flow:" in generate_block
    assert "project.status = (" in generate_block
    assert "INSPIRATION_BLUEPRINT_GENERATED_STATUS" in generate_block
