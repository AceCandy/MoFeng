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

    for text in ["工作台", "模型设置", "管理", "isMobileNavOpen"]:
        assert text in source

    assert "灵感" not in source
    assert "path: '/inspiration'" not in source
    assert 'aria-label="打开导航"' in source
    assert 'aria-label="关闭导航"' in source
    assert "app-shell__mobile-backdrop" in source


def test_workspace_prioritizes_continue_writing_and_new_actions():
    source = _source("views/NovelWorkspace.vue")

    for text in [
        "继续写作",
        "最近项目",
        "sortedProjects",
        "continueProject",
        "workspace-panel__actions",
    ]:
        assert text in source

    assert "router.push(`/projects/${project.id}/write`)" in source
    assert "router.push(`/projects/${projectId}`)" in source
    assert "router.push(`/projects/${response.id}/write`)" in source
    assert 'to="/admin"' not in source
    assert "查看平台与项目管理入口" not in source


def test_workspace_polish_preserves_primary_flow_and_responsive_states():
    workspace = _source("views/NovelWorkspace.vue")
    project_card = _source("components/ProjectCard.vue")
    shell = _source("components/shared/AppShell.vue")
    styles = _source("assets/main.css")

    for text in [
        "continueProgress",
        "workspace-continue__progress",
        "aria-label=\"最近项目进度\"",
        "workspace-panel__action:focus-visible",
        "@media (max-width: 520px)",
    ]:
        assert text in workspace

    for text in [
        "@click.stop=\"$emit('detail', project.id)\"",
        "line-clamp",
        "touch-action: manipulation",
    ]:
        assert text in project_card

    assert '@click="$emit(\'click\', project.id)"' not in project_card
    assert "(e: 'click'" not in project_card

    for text in [
        'id="app-primary-navigation"',
        ':aria-expanded="isMobileNavOpen"',
        'aria-controls="app-primary-navigation"',
        "isMobileShell",
        "window.matchMedia",
        "(max-width: 1023px)",
        ':aria-hidden="isMobileShell && !isMobileNavOpen ? \'true\' : undefined"',
        ':inert="isMobileShell && !isMobileNavOpen"',
    ]:
        assert text in shell

    for text in [
        "app-shell__workspace-context",
        "app-shell__topbar::after",
        "color-mix(in srgb, var(--md-surface-dim)",
    ]:
        assert text in styles


def test_distill_removes_redundant_workspace_card_chrome():
    workspace = _source("views/NovelWorkspace.vue")
    project_card = _source("components/ProjectCard.vue")

    for removed in [
        "workspace-actions",
        "workspace-action__icon",
        "<small>从对话开始整理故事蓝图</small>",
        "<small>上传 .txt 并进入写作台</small>",
    ]:
        assert removed not in workspace

    for removed in [
        "project-card__mark",
        "project-card__chips",
        "查看",
    ]:
        assert removed not in project_card

    assert "project-card__actions--compact" in project_card


def test_project_context_collapses_global_shell_to_icon_rail():
    shell = _source("components/shared/AppShell.vue")
    styles = _source("assets/main.css")

    for text in [
        "isProjectContext",
        "app-shell--project-context",
        "app-shell__brand-copy",
        "app-shell__nav-text",
        "app-shell__account-copy",
        "app-shell__logout",
        "'project-detail'",
        "'project-write'",
        "'admin-project-detail'",
    ]:
        assert text in shell

    for text in [
        ".app-shell--project-context",
        "grid-template-columns: 72px minmax(0, 1fr)",
        ".app-shell--project-context .app-shell__topbar",
        "display: none",
        ".app-shell--project-context .app-shell__content",
        "padding: 0",
    ]:
        assert text in styles

    rail_nav_block = _css_block(styles, ".app-shell--project-context .app-shell__nav-item")
    assert "width: 48px" in rail_nav_block
    assert "height: 48px" in rail_nav_block
    assert "justify-content: center" in rail_nav_block

    mobile_context_block = _css_block(styles, ".app-shell--project-context")
    assert "grid-template-columns: 72px minmax(0, 1fr)" in mobile_context_block


def test_writing_desk_uses_shared_surface_instead_of_local_shell_theme():
    source = _source("views/WritingDesk.vue")

    assert 'class="writing-desk-page flex flex-col overflow-hidden"' in source
    assert "router.push(`/projects/${project.value.id}`)" in source
    assert "onUnmounted" not in source
    assert ":global(body.m3-novel)" not in source
    assert ".m3-shell" not in source
    assert "radial-gradient" not in source
    assert "--md-primary:" not in source


def test_writing_desk_keeps_chapter_sidebar_persistent_and_removes_redundant_header_actions():
    page = _source("views/WritingDesk.vue")
    header = _source("components/writing-desk/WDHeader.vue")
    sidebar = _source("components/writing-desk/WDSidebar.vue")

    for text in [
        "writing-desk-layout",
        "@open-project-detail=\"viewProjectDetail\"",
    ]:
        assert text in page

    for removed in [
        "项目详情",
        "退出登录",
        "收起目录",
        "chapterSidebarOpen",
        "toggleSidebar",
        "handleLogout",
        "useAuthStore",
        "writing-desk-header__sidebar-toggle",
    ]:
        assert removed not in header

    assert "lg:hidden" not in header

    for text in [
        'id="writing-desk-chapter-sidebar"',
        "@click=\"emit('openProjectDetail')\"",
        "writing-sidebar",
    ]:
        assert text in sidebar

    assert "writing-sidebar--closed" not in sidebar
    assert "sidebarOpen" not in sidebar
    assert "lg:translate-x-0" not in sidebar

    for removed in [
        "openProjectSection",
        "writing-sidebar__summary-link",
        "writing-sidebar__metric-link",
        "characterCount",
        "relationshipCount",
    ]:
        assert removed not in sidebar


def test_distill_simplifies_archive_nav_and_global_shell_copy():
    shell = _source("components/shared/AppShell.vue")
    detail = _source("components/shared/NovelDetailShell.vue")

    for removed in [
        "app-shell__brand-subtitle",
        "app-shell__nav-label",
        "app-shell__eyebrow",
        "pageDescription",
        "当前区域",
    ]:
        assert removed not in shell

    for removed in [
        "section.description",
        "detail-shell__nav-copy",
        "detail-shell__drawer-toggle-text",
        "Drawer Header",
        "蓝图导航</span>",
    ]:
        assert removed not in detail


def test_novel_detail_accepts_section_query_for_writing_desk_deep_links():
    source = _source("components/shared/NovelDetailShell.vue")

    for text in [
        "const sectionKeys = sections.map((section) => section.key)",
        "const initialSection = resolveInitialSection()",
        "const activeSection = ref<SectionKey>(initialSection)",
        "const resolveInitialSection = (): SectionKey => {",
        "route.query.section",
        "useNovelSectionQuery",
        "activeNovelSection",
    ]:
        assert text in source


def test_chapters_detail_uses_bounded_scroll_container():
    shell = _source("components/shared/NovelDetailShell.vue")
    chapters = _source("components/novel-detail/ChaptersSection.vue")

    for text in [
        "'detail-shell__content-surface--fill overflow-hidden'",
        ".detail-shell__content-surface--fill",
        "height: calc(100vh - 6rem)",
        "max-height: calc(100vh - 6rem)",
        "height: calc(100vh - 7.5rem)",
        "max-height: calc(100vh - 7.5rem)",
        "min-height: 0",
    ]:
        assert text in shell

    assert 'class="flex-1 overflow-y-auto min-h-0 overscroll-contain"' in chapters
    assert 'class="flex-1 h-full overflow-y-auto min-h-0 overscroll-contain"' not in chapters


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


def test_admin_console_uses_product_shell_pattern():
    source = _source("views/AdminView.vue")

    for text in [
        "admin-console",
        "admin-console__nav",
        "admin-console__content",
        "aria-current",
    ]:
        assert text in source

    for removed in [
        "NLayoutSider",
        "NLayoutHeader",
        "NLayoutContent",
        "NMenu",
        "📊",
        "👤",
        "🗒️",
        "📚",
        "📝",
        "⚙️",
        "🔒",
        "admin-console__intro",
        "admin-console__workspace",
        "admin-console__nav-panel",
        "admin-console__content-header",
        "返回工作台",
        "admin-console__nav-icon",
        "renderIcon",
    ]:
        assert removed not in source


def test_admin_console_uses_compact_top_tabs_without_redundant_headers():
    source = _source("views/AdminView.vue")

    for text in [
        "admin-console__nav",
        "admin-console__nav-item",
        "admin-console__nav-label",
        "admin-console__content",
        "grid-template-columns: repeat(7, minmax(104px, 1fr))",
        "border-radius: var(--md-radius-full)",
    ]:
        assert text in source

    for removed in [
        "admin-console__intro",
        "admin-console__workspace",
        "admin-console__nav-panel",
        "admin-console__nav-heading",
        "admin-console__content-shell",
        "admin-console__content-header",
        "admin-section-title",
        "模块导航",
        "当前模块",
        "admin-console__section-index",
        "activeSectionIndex",
        "goBack",
    ]:
        assert removed not in source

    assert "admin-console__nav-item::before" not in source
    assert "border-left" not in source


def test_admin_console_content_does_not_wrap_child_panels_in_extra_card():
    source = _source("views/AdminView.vue")
    content_block = _css_block(source, ".admin-console__content")

    assert "min-width: 0" in content_block
    assert "border:" not in content_block
    assert "border-radius:" not in content_block
    assert "box-shadow:" not in content_block
    assert "padding:" not in content_block


def test_admin_child_panels_use_tokens_and_remove_decorative_gradients():
    admin_files = [
        "components/admin/Statistics.vue",
        "components/admin/UserManagement.vue",
        "components/admin/PromptManagement.vue",
        "components/admin/NovelManagement.vue",
        "components/admin/UpdateLogManagement.vue",
        "components/admin/SettingsManagement.vue",
        "components/admin/PasswordManagement.vue",
    ]

    for path in admin_files:
        source = _source(path)
        assert "var(--md-" in source, f"{path}: admin polish should use Material tokens"

        for removed in [
            "linear-gradient",
            "#1f2937",
            "#111827",
            "#6b7280",
            "#4b5563",
            "#374151",
            "#0f172a",
            "#475569",
            "#e5e7eb",
            "#f9fafb",
            "#fbfdff",
            "rgba(79, 70, 229",
            "rgba(15, 118, 110",
        ]:
            assert removed not in source, f"{path}: remove one-off style {removed!r}"

    statistics = _source("components/admin/Statistics.vue")
    assert "stat-icon" in statistics
    for emoji in ["📚", "👥", "⚡"]:
        assert emoji not in statistics

    users = _source("components/admin/UserManagement.vue")
    for text in [
        "isMobile",
        "user-mobile-list",
        "user-mobile-card",
        "window.innerWidth < 768",
    ]:
        assert text in users


def test_admin_list_tabs_use_flat_panels_instead_of_outer_cards():
    list_pages = [
        "components/admin/UserManagement.vue",
        "components/admin/NovelManagement.vue",
        "components/admin/PromptManagement.vue",
        "components/admin/UpdateLogManagement.vue",
        "components/admin/SettingsManagement.vue",
    ]

    for path in list_pages:
        source = _source(path)
        assert "class=\"admin-panel" in source, f"{path}: 管理列表页应使用扁平 admin-panel"
        assert "class=\"admin-table-shell" in source, f"{path}: 列表内容应收敛到单层表格区域"
        assert "class=\"admin-card\"" not in source, f"{path}: 不应再用外层 n-card 包页面"
        assert "class=\"novel-management-card\"" not in source, f"{path}: 不应再用外层 n-card 包页面"


def test_admin_domain_panels_share_global_flat_treatment():
    source = _source("assets/main.css")

    for text in [
        "Admin Domain Panels",
        ".admin-panel",
        ".admin-panel__header",
        ".admin-panel__header--toolbar",
        ".admin-table-shell",
        ".n-data-table",
        "var(--md-radius-lg)",
    ]:
        assert text in source

    for removed in [
        ".admin-card",
        ".novel-management-card",
        ".password-card",
    ]:
        assert removed not in source


def test_admin_tabs_do_not_repeat_selected_tab_as_content_title():
    repeated_titles = {
        "components/admin/Statistics.vue": "数据总览",
        "components/admin/UserManagement.vue": "用户管理",
        "components/admin/PromptManagement.vue": "提示词管理",
        "components/admin/NovelManagement.vue": "小说管理",
        "components/admin/UpdateLogManagement.vue": "更新日志管理",
        "components/admin/PasswordManagement.vue": "管理员密码修改",
    }

    for path, title in repeated_titles.items():
        source = _source(path)
        assert f'class="admin-panel__title">{title}' not in source
        assert "aria-labelledby=" not in source


def test_admin_novel_genre_column_wraps_long_multi_genres_without_overlap():
    source = _source("components/admin/NovelManagement.vue")

    for text in [
        "genreSegments",
        "visibleGenreSegments",
        "overflowGenreCount",
        "table-genre-list",
        "table-genre-chip",
        "table-genre-more",
    ]:
        assert text in source

    genre_list_block = _css_block(source, ":deep(.table-genre-list)")
    assert "max-width: 100%" in genre_list_block
    assert "flex-wrap: wrap" in genre_list_block
    assert "overflow: hidden" in genre_list_block

    genre_chip_block = _css_block(source, ":deep(.table-genre-chip)")
    assert "max-width:" in genre_chip_block
    assert "overflow: hidden" in genre_chip_block
    assert "text-overflow: ellipsis" in genre_chip_block
    assert "white-space: nowrap" in genre_chip_block


def test_admin_project_detail_uses_embedded_readonly_context():
    source = _source("components/shared/NovelDetailShell.vue")

    for text in [
        "detail-shell",
        "detail-shell--embedded",
        "isAdmin",
        "管理只读",
        "router.push({ name: 'admin', query: { tab: 'novels' } })",
    ]:
        assert text in source

    assert "h-screen flex flex-col overflow-hidden md-surface" not in source
    assert "top-16 bottom-0" not in source


def test_novel_archive_area_uses_flat_shell_and_tokenized_overview():
    shell = _source("components/shared/NovelDetailShell.vue")
    overview = _source("components/novel-detail/OverviewSection.vue")

    for text in [
        ":aria-label=\"isSidebarOpen ? '收起蓝图导航' : '展开蓝图导航'\"",
        'aria-label="小说档案分区"',
        ":aria-current=\"activeSection === section.key ? 'page' : undefined\"",
        "detail-shell__nav-item",
        "detail-shell__nav-icon",
        "detail-shell__content-surface",
        "position: sticky",
    ]:
        assert text in shell

    for removed in [
        "md-card md-card-elevated",
        "detail-shell__drawer md-surface",
        "margin-left: 20rem",
    ]:
        assert removed not in shell

    for text in [
        "archive-overview",
        "archive-overview__summary",
        "archive-overview__metadata",
        "archive-overview__synopsis",
        "aria-label=\"编辑核心摘要\"",
        "color: var(--md-primary-dark)",
        "background-color: var(--md-surface)",
        "grid-template-columns: repeat(auto-fit, minmax(240px, 1fr))",
        "overflow-wrap: normal",
    ]:
        assert text in overview

    for removed in [
        "bg-white/95",
        "text-indigo",
        "text-slate",
        "text-gray",
        "shadow-sm",
        "rounded-2xl",
    ]:
        assert removed not in overview


def test_novel_archive_drawer_toggle_and_scroll_are_operable():
    source = _source("components/shared/NovelDetailShell.vue")

    for text in [
        "detail-shell--drawer-collapsed",
        "detail-shell__drawer-toggle",
        "蓝图导航",
        "detail-shell__content-frame",
        'id="novel-detail-blueprint-nav"',
        'aria-controls="novel-detail-blueprint-nav"',
        ':aria-expanded="isSidebarOpen"',
        ":aria-label=\"isSidebarOpen ? '收起蓝图导航' : '展开蓝图导航'\"",
        "const isDesktopViewport = ref",
        "const closeSidebar = () => {",
    ]:
        assert text in source

    for removed in [
        "document.body.style.overflow = 'hidden'",
        "originalBodyOverflow",
        "lg:hidden",
    ]:
        assert removed not in source

    body_block = _css_block(source, ".detail-shell__body")
    assert "flex: 1 0 auto" in body_block
    assert "min-height: calc(100vh - 4rem)" in body_block
    assert "overflow: visible" in body_block
    assert "overflow: hidden" not in body_block

    content_wrap_block = _css_block(source, ".detail-shell__content-wrap")
    assert "align-items: flex-start" in content_wrap_block
    assert "overflow: visible" in content_wrap_block
    assert "overflow: hidden" not in content_wrap_block

    collapsed_drawer_block = _css_block(
        source, ".detail-shell--drawer-collapsed .detail-shell__drawer"
    )
    for text in ["flex-basis: 0", "width: 0", "pointer-events: none"]:
        assert text in collapsed_drawer_block


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
