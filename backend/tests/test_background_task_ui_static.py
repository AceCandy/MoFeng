from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FRONTEND_SRC = ROOT / "frontend" / "src"
WRITER_ROUTER = ROOT / "backend" / "app" / "api" / "routers" / "writer.py"


def _source(relative: str) -> str:
    return (FRONTEND_SRC / relative).read_text(encoding="utf-8")


def test_outline_generation_is_submitted_as_background_task():
    writer = WRITER_ROUTER.read_text(encoding="utf-8")
    outline_block = writer.split('"/novels/{project_id}/chapters/outline"', 1)[1].split(
        "\n\n@router.",
        1,
    )[0]
    novel_api = _source("api/novel.ts")
    novel_queries = _source("queries/novel.ts")

    assert "background_tasks: BackgroundTasks" not in outline_block
    assert "BackgroundTaskResponse" in outline_block
    assert "JobService(session).enqueue_job(" in outline_block
    assert 'job_type="chapter_outline"' in outline_block
    assert "background_tasks.add_task(" not in outline_block
    assert "Promise<BackgroundTask>" in novel_api
    assert "tasksQueryKeys" in novel_queries


def test_chapter_edits_submit_one_unified_durable_postprocess_job():
    writer = WRITER_ROUTER.read_text(encoding="utf-8")
    for route in ("chapters/edit\"", "chapters/edit-fast\""):
        block = writer.split(route, 1)[1].split("\n\n@router.", 1)[0]
        assert "background_tasks: BackgroundTasks" not in block
        assert "background_tasks.add_task(" not in block
        assert block.count("ChapterEditService(session).apply_content(") == 1


def test_chapter_generation_and_finalize_are_submitted_to_durable_worker():
    writer = WRITER_ROUTER.read_text(encoding="utf-8")

    assert 'job_type="chapter_generation"' in writer
    assert 'job_type="chapter_finalize"' not in writer
    assert "ChapterFinalizeSubmissionService(session).submit(" in writer
    assert writer.count("response_model=BackgroundTaskResponse") >= 6
    assert writer.count("status_code=202") >= 6
    assert "_confirm_finalize_chapter_sync" not in writer


def test_app_shell_exposes_background_task_log_entry():
    shell = _source("components/shared/AppShell.vue")
    task_panel = _source("components/shared/TaskLogPanel.vue")
    task_api = _source("api/tasks.ts")
    task_queries = _source("queries/tasks.ts")

    assert "useTasksQuery" in shell
    assert "showTaskLogModal" in shell
    assert "TaskLogPanel" in shell
    assert "app-shell__task-button" in shell
    assert ':aria-label="taskButtonLabel"' in shell
    assert "个任务执行中" in shell
    assert "查看任务日志，有任务执行失败" in shell
    assert "查看任务日志，有任务执行完成" in shell
    assert "'9+'" in shell
    assert "任务日志" in task_panel
    assert "getTasks" in task_api
    assert "refetchInterval" in task_queries
