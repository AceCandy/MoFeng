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

    assert "background_tasks: BackgroundTasks" in outline_block
    assert "BackgroundTaskResponse" in outline_block
    assert "create_task(" in outline_block
    assert "background_tasks.add_task(" in outline_block
    assert "run_generate_chapters_outline_task" in outline_block
    assert "Promise<BackgroundTask>" in novel_api
    assert "tasksQueryKeys" in novel_queries


def test_app_shell_exposes_background_task_log_entry():
    shell = _source("components/shared/AppShell.vue")
    task_panel = _source("components/shared/TaskLogPanel.vue")
    task_api = _source("api/tasks.ts")
    task_queries = _source("queries/tasks.ts")

    assert "useTasksQuery" in shell
    assert "showTaskLogModal" in shell
    assert "TaskLogPanel" in shell
    assert "app-shell__task-button" in shell
    assert "当前正在执行的任务日志" in shell
    assert "任务日志" in task_panel
    assert "getTasks" in task_api
    assert "refetchInterval" in task_queries
