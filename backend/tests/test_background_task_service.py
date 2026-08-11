import pytest

from app.models import NovelProject
from app.models.user import User
from app.services.background_task_service import BackgroundTaskService


@pytest.mark.asyncio(loop_scope="session")
async def test_background_task_service_delegates_create_and_queries_to_job_service(
    db_session_factory,
):
    async with db_session_factory() as session:
        session.add(User(id=1, username="writer", hashed_password="secret"))
        session.add(
            NovelProject(id="project-1", user_id=1, title="测试项目", initial_prompt="测试")
        )
        await session.commit()

        service = BackgroundTaskService(session)
        task = await service.create_task(
            user_id=1,
            task_type="chapter_outline",
            title="生成后续章节大纲",
            project_id="project-1",
            payload={"start_chapter": 3, "num_chapters": 2},
        )

        assert task.status == "queued"
        assert task.progress == 0
        assert task.log_entries[0]["message"] == "任务已创建，等待后台执行"
        refreshed = await service.get_user_task(task.id, user_id=1)
        listed = await service.list_user_tasks(user_id=1)

        assert refreshed is not None
        assert refreshed.status == "queued"
        assert [item.id for item in listed] == [task.id]
