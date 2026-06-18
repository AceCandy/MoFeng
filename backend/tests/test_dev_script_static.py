import importlib.util
import socket
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEV_SCRIPT = ROOT / "dev.sh"
DEV_SERVERS = ROOT / "dev_servers.py"
VITE_CONFIG = ROOT / "frontend" / "vite.config.ts"
DEPLOY_ENV_EXAMPLE = ROOT / "deploy" / ".env.example"
DEPLOY_COMPOSE = ROOT / "deploy" / "docker-compose.yml"
DEPLOY_NGINX = ROOT / "deploy" / "nginx.conf"
DEPLOY_SUPERVISOR = ROOT / "deploy" / "supervisord.conf"


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
    assert "http://127.0.0.1:6101/api/health" in compose
    assert "listen 6100;" in nginx
    assert "listen [::]:6100;" in nginx
    assert "proxy_pass http://127.0.0.1:6101;" in nginx
    assert "--port 6101" in supervisor


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
