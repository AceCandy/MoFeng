from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import ChapterOutline, NovelBlueprint, NovelProject
from app.models.user import User
from app.services.novel_service import NovelService


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_chapter_outline_model_declares_structured_story_fields() -> None:
    columns = ChapterOutline.__table__.columns

    assert "goals" in columns
    assert "highlights" in columns
    assert "character_states" in columns


@pytest.mark.asyncio(loop_scope="session")
async def test_update_or_create_outline_persists_structured_story_fields(db_session_factory) -> None:
    async with db_session_factory() as session:
        session.add(User(id=1, username="writer", hashed_password="secret"))
        session.add(NovelProject(id="project-1", user_id=1, title="测试项目", initial_prompt="测试"))
        session.add(NovelBlueprint(project_id="project-1", title="测试项目"))
        await session.commit()

        service = NovelService(session)
        await service.update_or_create_outline(
            "project-1",
            1,
            "第一章",
            "主角发现异常。",
            goals="让主角意识到平静生活被打破。",
            highlights=["猪圈异象", "神秘老者登场"],
            character_states={"李大壮": "困惑但开始相信异象有含义"},
        )
        await session.commit()

        project = (
            await session.execute(
                select(NovelProject)
                .options(
                    selectinload(NovelProject.blueprint),
                    selectinload(NovelProject.characters),
                    selectinload(NovelProject.relationships_),
                    selectinload(NovelProject.outlines),
                )
                .where(NovelProject.id == "project-1")
            )
        ).scalars().one()

        outline = service._build_blueprint_schema(project).chapter_outline[0]

        assert outline.goals == "让主角意识到平静生活被打破。"
        assert outline.highlights == ["猪圈异象", "神秘老者登场"]
        assert outline.character_states == {"李大壮": "困惑但开始相信异象有含义"}


def test_outline_generation_prompt_and_task_require_structured_story_fields() -> None:
    prompt = (BACKEND_ROOT / "prompts" / "outline_generation.md").read_text(encoding="utf-8")
    task_runner = (BACKEND_ROOT / "app" / "services" / "chapter_outline_task_runner.py").read_text(
        encoding="utf-8"
    )

    for field_name in ("goals", "highlights", "character_states"):
        assert field_name in prompt
        assert field_name in task_runner


def test_alembic_baseline_includes_chapter_outline_structured_fields() -> None:
    # schema 改由 alembic baseline 管理（替代 _ensure_schema_updates 过渡态），确认 baseline 含结构化字段列
    baseline = (BACKEND_ROOT / "alembic" / "versions" / "a53385d06521_baseline.py").read_text(encoding="utf-8")

    for field_name in ("goals", "highlights", "character_states"):
        assert f"sa.Column('{field_name}'" in baseline
