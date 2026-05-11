import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT.parent / "frontend/src"
VITE_CONFIG = ROOT.parent / "frontend/vite.config.ts"


def _source(path: str) -> str:
    return (FRONTEND / path).read_text(encoding="utf-8")


def _vite_config_source() -> str:
    return VITE_CONFIG.read_text(encoding="utf-8")


def _assert_contains(path: str, text: str) -> None:
    source = _source(path)
    assert text in source, f"{path}: 缺少 {text!r}"


def _assert_missing(path: str, text: str) -> None:
    source = _source(path)
    assert text not in source, f"{path}: 不应再出现 {text!r}"


def _css_block(source: str, selector: str) -> str:
    matches = re.findall(rf"{re.escape(selector)}\s*\{{([^}}]+)\}}", source, re.DOTALL)
    assert matches, f"缺少 CSS 选择器: {selector}"
    return "\n".join(matches)


def test_router_declares_app_layout_and_canonical_project_routes():
    source = _source("router/index.ts")

    for path in ["/projects/:id", "/projects/:id/write", "/admin/novels/:id"]:
        assert f"path: '{path}'" in source

    for label in ["工作台", "灵感", "小说档案", "写作台", "模型设置", "管理"]:
        assert f"label: '{label}'" in source

    assert "layout: 'app'" in source
    assert "layout: 'auth'" in source
    assert "name: 'project-detail'" in source
    assert "name: 'project-write'" in source
    assert "name: 'admin-project-detail'" in source


def test_router_keeps_legacy_paths_as_redirects_only():
    source = _source("router/index.ts")

    assert "path: '/detail/:id'" in source
    assert "path: '/novel/:id'" in source
    assert "path: '/admin/novel/:id'" in source
    assert "`/projects/${to.params.id}`" in source
    assert "`/projects/${to.params.id}/write`" in source
    assert "`/admin/novels/${to.params.id}`" in source
    assert "name: 'novel-detail'" not in source
    assert "name: 'writing-desk'" not in source
    assert "name: 'admin-novel-detail'" not in source


def test_app_uses_shared_shell_layouts():
    source = _source("App.vue")

    for text in ["AppShell", "AuthLayout", 'RouterView v-slot="{ Component }"', ':is="layoutComponent"']:
        assert text in source

    _assert_contains("components/shared/AppShell.vue", "app-shell")
    _assert_contains("components/shared/AuthLayout.vue", "auth-layout")


def test_app_shell_contains_primary_navigation_and_mobile_behavior():
    source = _source("components/shared/AppShell.vue")

    for text in ["工作台", "灵感", "模型设置", "管理", "isMobileNavOpen"]:
        assert text in source

    assert 'aria-label="打开导航"' in source
    assert 'aria-label="关闭导航"' in source
    assert "app-shell__mobile-backdrop" in source


def test_workspace_prioritizes_continue_writing_and_new_actions():
    source = _source("views/NovelWorkspace.vue")

    for text in ["继续写作", "最近项目", "sortedProjects", "continueProject", "workspace-actions"]:
        assert text in source

    assert "router.push(`/projects/${project.id}/write`)" in source
    assert "router.push(`/projects/${projectId}`)" in source
    assert "router.push(`/projects/${response.id}/write`)" in source


def test_writing_desk_uses_shared_surface_instead_of_local_shell_theme():
    source = _source("views/WritingDesk.vue")

    assert 'class="writing-desk-page flex flex-col overflow-hidden"' in source
    assert "router.push(`/projects/${project.value.id}`)" in source
    assert "onUnmounted" not in source
    assert ":global(body.m3-novel)" not in source
    assert ".m3-shell" not in source
    assert "radial-gradient" not in source
    assert "--md-primary:" not in source


def test_auth_and_admin_surfaces_remove_glass_and_hardcoded_backgrounds():
    register = _source("views/Register.vue")
    admin = _source("views/AdminView.vue")

    assert "backdrop-blur" not in register
    assert "bg-white/70" not in register
    assert "md-text-field" in register
    assert "md-btn md-btn-filled" in register

    assert "backdrop-filter" not in admin
    assert "rgba(255, 255, 255" not in admin
    assert "#f5f5f7" not in admin
    assert "var(--md-surface)" in admin
    assert "var(--md-surface-dim)" in admin


def test_global_shell_css_and_antipatterns_are_normalized():
    source = _source("assets/main.css")

    for selector in [".app-shell", ".app-shell__sidebar", ".app-shell__topbar", ".app-page", ".auth-layout"]:
        _css_block(source, selector)

    for path in ["views/WorkspaceEntry.vue", "components/ProjectCard.vue"]:
        _assert_missing(path, "hover:scale")

    for banned in ["from-indigo", "to-purple", "backdrop-blur-xl"]:
        assert banned not in _source("views/Register.vue")


def test_vite_dev_server_allows_configured_public_domain():
    source = _vite_config_source()

    assert "FRONTEND_ALLOWED_HOSTS" in source
    assert "test.acecandy.cn" in source
    assert "frontendAllowedHosts" in source
    assert "allowedHosts: frontendAllowedHosts" in source
