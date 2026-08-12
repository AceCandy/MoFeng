import importlib.util
import json
import os
import shutil
import socket
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
DEV_SCRIPT = ROOT / "dev.sh"
DEV_SERVERS = ROOT / "dev_servers.py"
VITE_CONFIG = ROOT / "frontend" / "vite.config.ts"
DEPLOY_ENV_EXAMPLE = ROOT / "deploy" / ".env.example"
DEPLOY_COMPOSE = ROOT / "deploy" / "docker-compose.yml"
DEPLOY_NGINX = ROOT / "deploy" / "nginx.conf"
DEPLOY_SUPERVISOR = ROOT / "deploy" / "supervisord.conf"
DEPLOY_DOCKERFILE = ROOT / "deploy" / "Dockerfile"
DEPLOY_SCRIPT = ROOT / "deploy" / "scripts" / "deploy_docker.sh"
RELEASE_SMOKE_SCRIPT = ROOT / "deploy" / "scripts" / "smoke_release_image.sh"
QUICK_DEPLOY_SCRIPT = ROOT / "deploy" / "scripts" / "quick_deploy.sh"
SERVER_DEPLOY_SCRIPT = ROOT / "deploy" / "scripts" / "server_deploy.sh"
TRANSPORT_CI = ROOT / ".github" / "workflows" / "transport-contract-ci.yml"


def _load_dev_servers_module():
    spec = importlib.util.spec_from_file_location("dev_servers", DEV_SERVERS)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dev_script_disables_node_webstorage_for_vite_devtools():
    source = DEV_SCRIPT.read_text(encoding="utf-8")

    assert "--no-experimental-webstorage" in source
    assert "NODE_OPTIONS" in source
    assert "npm run dev" in source


def test_dev_script_prepares_database_before_starting_runtime():
    source = DEV_SCRIPT.read_text(encoding="utf-8")

    migration = source.index("app.db.cli db-migrate")
    bootstrap = source.index("app.db.cli db-bootstrap")
    runtime = source.index("app.main:app")
    assert migration < bootstrap < runtime


def test_dev_script_port_probe_does_not_allow_reusing_occupied_ports():
    source = DEV_SCRIPT.read_text(encoding="utf-8")
    port_probe = source.split("is_port_available()", 1)[1].split("find_available_port()", 1)[0]

    assert "setsockopt" not in port_probe


def test_local_dev_default_ports_are_consistent():
    dev_script = DEV_SCRIPT.read_text(encoding="utf-8")
    dev_servers = DEV_SERVERS.read_text(encoding="utf-8")
    vite_config = VITE_CONFIG.read_text(encoding="utf-8")

    assert "BACKEND_DEFAULT_PORT=6101" in dev_script
    assert "FRONTEND_DEFAULT_PORT=6100" in dev_script
    assert "BACKEND_DEFAULT_PORT = 6101" in dev_servers
    assert "FRONTEND_DEFAULT_PORT = 6100" in dev_servers
    assert "process.env.BACKEND_PORT || '6101'" in vite_config
    assert "process.env.FRONTEND_PORT || '6100'" in vite_config


def test_deploy_default_ports_are_consistent():
    env_example = DEPLOY_ENV_EXAMPLE.read_text(encoding="utf-8")
    compose = DEPLOY_COMPOSE.read_text(encoding="utf-8")
    nginx = DEPLOY_NGINX.read_text(encoding="utf-8")
    supervisor = DEPLOY_SUPERVISOR.read_text(encoding="utf-8")

    assert "APP_PORT=6100" in env_example
    assert '"${APP_PORT:-6100}:6100"' in compose
    assert "http://127.0.0.1:6101/api/ready" in compose
    assert "listen 6100;" in nginx
    assert "listen [::]:6100;" in nginx
    assert "proxy_pass http://127.0.0.1:6101;" in nginx
    assert "--port 6101" in supervisor


def test_supervisor_sets_appuser_home_for_database_ssl_defaults():
    supervisor = DEPLOY_SUPERVISOR.read_text(encoding="utf-8")

    assert "user=appuser" in supervisor
    assert 'environment=HOME="/home/appuser"' in supervisor


def test_deploy_examples_and_operator_commands_resolve_database_config():
    env_example = DEPLOY_ENV_EXAMPLE.read_text(encoding="utf-8")
    deploy_script = DEPLOY_SCRIPT.read_text(encoding="utf-8")
    quick_deploy = QUICK_DEPLOY_SCRIPT.read_text(encoding="utf-8")
    server_deploy = SERVER_DEPLOY_SCRIPT.read_text(encoding="utf-8")

    assert "host.docker.internal" not in env_example
    assert '--env-file "$DEPLOY_ENV_FILE"' in deploy_script
    assert 'if [ -z "${DATABASE_URL:-}" ]; then' in deploy_script
    assert "REQUIRED_VARS+=(POSTGRES_PASSWORD)" in deploy_script
    assert 'if [ -n "${DATABASE_URL:-}" ]; then' in deploy_script
    assert "docker compose --env-file .env -f deploy/docker-compose.yml" in quick_deploy
    assert "docker compose --env-file .env -f deploy/docker-compose.yml" in server_deploy
    assert "/root/MoFeng/docs/DEPLOYMENT.md" in server_deploy


def test_deploy_defines_and_gates_independent_durable_worker():
    env_example = DEPLOY_ENV_EXAMPLE.read_text(encoding="utf-8")
    compose = DEPLOY_COMPOSE.read_text(encoding="utf-8")
    deploy_script = DEPLOY_SCRIPT.read_text(encoding="utf-8")

    assert "  worker:" in compose
    assert 'command: ["python", "-m", "app.worker", "run"]' in compose
    assert "restart: unless-stopped" in compose
    assert "stop_grace_period: 15m" in compose
    assert 'test: ["CMD", "python", "-m", "app.worker", "health"]' in compose
    assert "JOB_WORKER_NAME: ${JOB_WORKER_NAME:-mofeng-worker}" in compose

    for key in (
        "JOB_WORKER_GENERATION",
        "JOB_LEASE_SECONDS",
        "JOB_HEARTBEAT_INTERVAL_SECONDS",
        "JOB_WORKER_HEARTBEAT_INTERVAL_SECONDS",
        "JOB_WORKER_POLL_INTERVAL_SECONDS",
        "JOB_WORKER_HEALTH_STALE_SECONDS",
        "JOB_EVENT_RETENTION_DAYS",
        "JOB_EVENT_CLEANUP_INTERVAL_SECONDS",
    ):
        assert f"{key}=" in env_example
        assert f"{key}:" in compose

    assert "exec -T worker python -m app.worker health" in deploy_script
    assert "durable worker 健康检查失败" in deploy_script
    assert "logs --tail=80 worker" in deploy_script


def test_python_dependency_install_requires_hash_locks():
    dockerfile = DEPLOY_DOCKERFILE.read_text(encoding="utf-8")
    transport_ci = TRANSPORT_CI.read_text(encoding="utf-8")

    assert dockerfile.count("FROM python:3.11-alpine") == 2
    assert "FROM python:3.11-slim" not in dockerfile
    assert "apk add --no-cache" in dockerfile
    assert "pip install --no-cache-dir --upgrade pip" not in dockerfile
    assert "pip install --no-cache-dir --no-compile --require-hashes" in dockerfile
    assert dockerfile.count("pip uninstall -y pip setuptools wheel") == 2
    assert "python -m pip install --require-hashes -r requirements-dev.txt" in transport_ci
    assert "backend/requirements.in" in transport_ci
    assert "backend/requirements-dev.in" in transport_ci


def test_release_smoke_uses_digest_and_cleans_isolated_resources():
    compose = DEPLOY_COMPOSE.read_text(encoding="utf-8")
    smoke = RELEASE_SMOKE_SCRIPT.read_text(encoding="utf-8")

    for service in ("migrate", "bootstrap", "app", "worker", "pg"):
        assert f"container_name: ${{COMPOSE_PROJECT_NAME:-mofeng}}-{service}" in compose

    assert "@sha256:[0-9a-f]{64}" in smoke
    assert 'docker pull "$image_ref"' in smoke
    assert 'docker tag "$image_ref" "$local_image"' in smoke
    assert '--project-name "$project_name"' in smoke
    assert "--profile postgres" in smoke
    assert "ENVIRONMENT=development" in smoke
    assert "LINUXDO_REDIRECT_URI=http://127.0.0.1/" in smoke
    assert "python -m app.db.cli db-migrate" in smoke
    assert "python -m app.db.cli db-bootstrap" in smoke
    assert "python -m app.db.cli db-check" in smoke
    assert "/api/ready" in smoke
    assert "python -m app.worker health" in smoke
    assert "python -m app.worker metrics" in smoke
    assert "down --volumes --remove-orphans" in smoke
    assert "--timeout 10" in smoke
    assert 'docker image rm "$local_image"' in smoke
    assert "trap cleanup EXIT" in smoke


@pytest.mark.parametrize(
    "image_ref",
    (
        "acecandy/mofeng:latest",
        "acecandy/mofeng@sha256:short",
        f"acecandy/mofeng@sha256:{'A' * 64}",
    ),
)
def test_release_smoke_rejects_non_digest_references_before_using_docker(image_ref):
    result = subprocess.run(
        ["bash", str(RELEASE_SMOKE_SCRIPT), image_ref],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "<repository@sha256:digest>" in result.stderr


def test_deploy_compose_resolves_durable_worker_structure(tmp_path):
    docker = shutil.which("docker")
    if docker is None:
        pytest.skip("docker compose CLI 不可用")

    env_file = tmp_path / "compose.env"
    env_file.write_text(
        "SECRET_KEY=test-only-secret-key-at-least-32-characters\n"
        "POSTGRES_PASSWORD=test-only-password\n"
        "BOOTSTRAP_CREATE_DEFAULT_ADMIN=false\n"
        "CHAPTER_WORKFLOW_START_ENABLED=true\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            docker,
            "compose",
            "--env-file",
            str(env_file),
            "-f",
            str(DEPLOY_COMPOSE),
            "--profile",
            "postgres",
            "config",
            "--format",
            "json",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "COMPOSE_PROJECT_NAME": "mofeng-smoke-contract"},
    )
    assert result.returncode == 0, result.stderr

    config = json.loads(result.stdout)
    assert config["name"] == "mofeng-smoke-contract"
    for service in ("migrate", "bootstrap", "app", "worker", "pg"):
        assert config["services"][service]["container_name"] == (f"mofeng-smoke-contract-{service}")

    worker = config["services"]["worker"]
    assert worker["command"] == ["python", "-m", "app.worker", "run"]
    assert worker["restart"] == "unless-stopped"
    assert worker["stop_grace_period"] == "15m0s"
    assert worker["healthcheck"]["test"] == [
        "CMD",
        "python",
        "-m",
        "app.worker",
        "health",
    ]
    assert worker["depends_on"]["bootstrap"]["condition"] == ("service_completed_successfully")
    assert worker["environment"]["JOB_WORKER_NAME"] == "mofeng-worker"


def test_deploy_compose_accepts_database_url_without_postgres_password(tmp_path):
    docker = shutil.which("docker")
    if docker is None:
        pytest.skip("docker compose CLI 不可用")

    env_file = tmp_path / "external-database.env"
    env_file.write_text(
        "SECRET_KEY=test-only-secret-key-at-least-32-characters\n"
        "DATABASE_URL=postgresql+asyncpg://test:test@database.example/mofeng\n"
        "BOOTSTRAP_CREATE_DEFAULT_ADMIN=false\n"
        "CHAPTER_WORKFLOW_START_ENABLED=true\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            docker,
            "compose",
            "--env-file",
            str(env_file),
            "-f",
            str(DEPLOY_COMPOSE),
            "config",
            "--format",
            "json",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    config = json.loads(result.stdout)
    assert "pg" not in config["services"]
    assert config["services"]["app"]["environment"]["DATABASE_URL"].startswith(
        "postgresql+asyncpg://"
    )


def test_dev_server_port_probe_treats_loopback_listener_as_busy_for_wildcard_host():
    dev_servers = _load_dev_servers_module()

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]

    try:
        assert not dev_servers._is_port_available("0.0.0.0", port)
    finally:
        listener.close()
