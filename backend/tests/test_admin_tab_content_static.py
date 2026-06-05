from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FRONTEND_SRC = ROOT / "frontend" / "src"


def _source(relative_path: str) -> str:
    return (FRONTEND_SRC / relative_path).read_text(encoding="utf-8")


def test_admin_overview_shell_has_shared_global_styles():
    source = _source("assets/main.css")

    for selector in [
        ":where(.admin-ops)",
        ":where(.admin-ops__summary)",
        ":where(.admin-ops__metrics)",
        ":where(.admin-ops__metric)",
        ":where(.admin-ops__grid)",
        ":where(.admin-panel-card)",
    ]:
        assert selector in source
