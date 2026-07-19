import pytest

from app.models import NovelProject
from app.models.user import User
from app.services.background_task_service import BackgroundTaskService


@pytest.mark.asyncio(loop_scope="session")
async def test_background_task_service_records_status_progress_and_logs(db_session_factory):
    async with db_session_factory() as session:
        session.add(User(id=1, username="writer", hashed_password="secret"))
        session.add(NovelProject(id="project-1", user_id=1, title="测试项目", initial_prompt="测试"))
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

        await service.mark_running(task.id, "开始生成章节大纲")
        await service.append_log(task.id, "AI 已返回大纲结果", progress=80)
        await service.mark_succeeded(task.id, result={"outline_count": 2})

        refreshed = await service.get_user_task(task.id, user_id=1)

        assert refreshed is not None
        assert refreshed.status == "succeeded"
        assert refreshed.progress == 100
        assert refreshed.result == {"outline_count": 2}
        assert [entry["message"] for entry in refreshed.log_entries] == [
            "任务已创建，等待后台执行",
            "开始生成章节大纲",
            "AI 已返回大纲结果",
            "任务执行完成",
        ]
