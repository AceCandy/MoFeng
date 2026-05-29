from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FRONTEND_SRC = ROOT / "frontend" / "src"


def _source(relative_path: str) -> str:
    return (FRONTEND_SRC / relative_path).read_text(encoding="utf-8")


def test_non_statistics_admin_tabs_use_overview_like_content_shell():
    tabs = {
        "components/admin/UserManagement.vue": "用户管理中心",
        "components/admin/PromptManagement.vue": "提示词管理中心",
        "components/admin/NovelManagement.vue": "小说项目中心",
        "components/admin/UpdateLogManagement.vue": "更新日志中心",
        "components/admin/SettingsManagement.vue": "系统配置中心",
    }

    for relative_path, title in tabs.items():
        source = _source(relative_path)
        assert 'class="admin-ops' in source
        assert 'class="admin-ops__summary' in source
        assert 'class="admin-ops__metrics' in source
        assert 'class="admin-ops__grid' in source
        assert title in source


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
