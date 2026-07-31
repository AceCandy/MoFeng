# AIMETA P=章节工作流发布配置契约测试|R=默认关闭_Compose显式gate_发布示例|NR=不启动容器或执行workflow|E=test_*|X=internal|A=contract_test|D=pytest,docker-compose|S=test|RD=./README.ai
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from app.core.config import Settings

ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = ROOT / "deploy" / "docker-compose.yml"


def test_workflow_start_gate_defaults_closed_and_release_files_are_explicit():
    assert Settings.model_fields["chapter_workflow_start_enabled"].default is False

    compose = COMPOSE_FILE.read_text(encoding="utf-8")
    backend_example = (ROOT / "backend" / "env.example").read_text(encoding="utf-8")
    deploy_example = (ROOT / "deploy" / ".env.example").read_text(encoding="utf-8")
    deploy_script = (ROOT / "deploy" / "scripts" / "deploy_docker.sh").read_text(encoding="utf-8")
    server_script = (ROOT / "deploy" / "scripts" / "server_deploy.sh").read_text(encoding="utf-8")

    assert "${CHAPTER_WORKFLOW_START_ENABLED:?" in compose
    assert "CHAPTER_WORKFLOW_START_ENABLED=true" in backend_example
    assert "CHAPTER_WORKFLOW_START_ENABLED=true" in deploy_example
    assert "REQUIRED_VARS=(SECRET_KEY CHAPTER_WORKFLOW_START_ENABLED)" in deploy_script
    assert "CHAPTER_WORKFLOW_START_ENABLED=true" in server_script


def test_compose_fails_closed_without_gate_and_resolves_explicit_true(tmp_path):
    docker = shutil.which("docker")
    if docker is None:
        pytest.skip("docker compose CLI 不可用")

    env_file = tmp_path / "release.env"
    env_file.write_text(
        "SECRET_KEY=test-only-secret-key-at-least-32-characters\n"
        "POSTGRES_PASSWORD=test-only-password\n"
        "BOOTSTRAP_CREATE_DEFAULT_ADMIN=false\n",
        encoding="utf-8",
    )
    command = [
        docker,
        "compose",
        "--env-file",
        str(env_file),
        "-f",
        str(COMPOSE_FILE),
        "config",
        "--format",
        "json",
    ]

    missing = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert missing.returncode != 0
    assert "CHAPTER_WORKFLOW_START_ENABLED" in missing.stderr

    env_file.write_text(
        env_file.read_text(encoding="utf-8") + "CHAPTER_WORKFLOW_START_ENABLED=true\n",
        encoding="utf-8",
    )
    enabled = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert enabled.returncode == 0, enabled.stderr
    config = json.loads(enabled.stdout)
    assert config["services"]["app"]["environment"]["CHAPTER_WORKFLOW_START_ENABLED"] == ("true")
