from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONTEND_SRC = ROOT / "frontend" / "src"


def _source(relative_path: str) -> str:
    return (FRONTEND_SRC / relative_path).read_text(encoding="utf-8")


def _global_css() -> str:
    """main.css 入口 + 所有 partial 拼接（#28 拆分后全局 CSS 分散在 styles/ partial）。"""
    parts = [_source("assets/main.css")]
    for css_file in sorted((FRONTEND_SRC / "assets" / "styles").rglob("*.css")):
        parts.append(css_file.read_text(encoding="utf-8"))
    return "\n".join(parts)


def test_admin_overview_shell_has_shared_global_styles():
    source = _global_css()

    for selector in [
        ":where(.admin-ops)",
        ":where(.admin-ops__summary)",
        ":where(.admin-ops__metrics)",
        ":where(.admin-ops__metric)",
        ":where(.admin-ops__grid)",
        ":where(.admin-panel-card)",
    ]:
        assert selector in source
