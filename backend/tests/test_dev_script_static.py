import importlib.util
import socket
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEV_SCRIPT = ROOT / "dev.sh"
DEV_SERVERS = ROOT / "dev_servers.py"


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
