from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEV_SCRIPT = ROOT / "dev.sh"


def test_dev_script_disables_node_webstorage_for_vite_devtools():
    source = DEV_SCRIPT.read_text(encoding="utf-8")

    assert "--no-experimental-webstorage" in source
    assert "NODE_OPTIONS" in source
    assert "npm run dev" in source
