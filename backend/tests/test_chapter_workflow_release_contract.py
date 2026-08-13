# AIMETA P=章节工作流单轨发布契约|R=常开入口_无旧job与切流配置|NR=不启动容器或执行provider|E=test_*|X=internal|A=contract_test|D=pytest|S=test|RD=./README.ai
from pathlib import Path

from app.core.config import Settings

ROOT = Path(__file__).resolve().parents[2]


def test_chapter_workflow_is_the_only_generation_runtime() -> None:
    writer = (ROOT / "backend/app/api/routers/writer.py").read_text(encoding="utf-8")
    handlers = (ROOT / "backend/app/services/job_handlers.py").read_text(encoding="utf-8")

    assert "chapter_workflow_start_enabled" not in Settings.model_fields
    assert 'job_type="chapter_generation"' not in writer
    assert 'job_type="chapter_generation"' not in handlers
    assert 'job_type="chapter_workflow"' in handlers
    assert not (ROOT / "backend/app/services/pipeline_orchestrator.py").exists()
    assert not (ROOT / "backend/app/services/chapter_generation_task_runner.py").exists()


def test_release_configuration_has_no_workflow_start_gate() -> None:
    paths = (
        "backend/env.example",
        "deploy/.env.example",
        "deploy/docker-compose.yml",
        "deploy/scripts/deploy_docker.sh",
        "deploy/scripts/server_deploy.sh",
        "deploy/scripts/smoke_release_image.sh",
    )

    for relative_path in paths:
        source = (ROOT / relative_path).read_text(encoding="utf-8")
        assert "CHAPTER_WORKFLOW_START_ENABLED" not in source
