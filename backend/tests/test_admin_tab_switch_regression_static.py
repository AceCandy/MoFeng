from pathlib import Path


FRONTEND_SRC = Path(__file__).resolve().parents[2] / "frontend" / "src"


def _source(relative_path: str) -> str:
    return (FRONTEND_SRC / relative_path).read_text(encoding="utf-8")


def test_admin_tab_switch_regression_keeps_panel_renderable():
    source = _source("views/AdminView.vue")

    # 切换 tab 后保留已加载组件实例，避免异步组件反复重建导致空白面板。
    assert "<keep-alive>" in source
    assert "</keep-alive>" in source

    # 移除 hover/focus 预取，避免在频繁切换时提前触发动态导入失败并污染模块状态。
    for removed in [
        "@mouseenter=\"prefetchSection(",
        "@focus=\"prefetchSection(",
        "@touchstart.passive=\"prefetchSection(",
        "const componentLoaders:",
        "const prefetchedSections",
        "const prefetchInFlight",
        "const prefetchSection =",
        "prefetchSection(activeKey.value)",
        "prefetchSection(key)",
    ]:
        assert removed not in source
