import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT.parent / "frontend/src"
SETTINGS_VIEW = "views/SettingsView.vue"
PERSONAL_MODEL_ROUTING = "components/llm-settings/PersonalModelRouting.vue"
LLM_SETTINGS = "components/LLMSettings.vue"


def _source(path: str) -> str:
    return (FRONTEND / path).read_text(encoding="utf-8")


def _assert_pattern(path: str, label: str, pattern: str) -> None:
    source = _source(path)
    assert re.search(pattern, source, re.DOTALL), (
        f"{path}: 缺少 {label}; pattern={pattern}"
    )


def _component_tags(path: str, component: str) -> list[str]:
    source = _source(path)
    return re.findall(rf"<{component}\b[^>]*>", source, re.DOTALL)


def _aria_current_bindings(path: str) -> list[str]:
    source = _source(path)
    return re.findall(r":aria-current\s*=\s*(['\"])(.*?)\1", source, re.DOTALL)


def test_settings_view_declares_console_sections():
    for section in [
        "overview",
        "providers",
        "models",
        "routes",
        "basic",
    ]:
        _assert_pattern(
            SETTINGS_VIEW,
            f"设置分区 {section}",
            rf"id\s*:\s*['\"]{section}['\"]",
        )

    _assert_pattern(
        SETTINGS_VIEW,
        "activeSettingsSection 响应式状态",
        r"const\s+activeSettingsSection\s*=\s*ref<SettingsSectionId>\s*\(",
    )
    _assert_pattern(
        SETTINGS_VIEW,
        "桌面设置导航",
        r"<nav[^>]+class\s*=\s*['\"]settings-console__nav['\"]",
    )
    _assert_pattern(
        SETTINGS_VIEW,
        "移动设置 tabs",
        r"class\s*=\s*['\"]settings-console__mobile-tabs['\"]",
    )
    active_aria_bindings = [
        binding
        for _, binding in _aria_current_bindings(SETTINGS_VIEW)
        if re.search(r"activeSettingsSection\s*===\s*\w+\.id", binding)
    ]
    assert len(active_aria_bindings) >= 2, (
        f"{SETTINGS_VIEW}: 桌面导航和移动 tabs 都需要绑定 active aria-current，"
        f"实际命中={active_aria_bindings}"
    )


def test_settings_view_routes_sections_to_existing_components():
    for section in ["providers", "models", "routes"]:
        _assert_pattern(
            SETTINGS_VIEW,
            f"PersonalModelRouting {section} 分区",
            rf"<PersonalModelRouting\b[^>]+active-section\s*=\s*['\"]{section}['\"]",
        )

    llm_settings_tags = _component_tags(SETTINGS_VIEW, "LLMSettings")
    assert len(llm_settings_tags) == 1, (
        f"{SETTINGS_VIEW}: LLMSettings 应只在 basic 分区渲染一次，"
        f"实际数量={len(llm_settings_tags)}"
    )
    llm_settings_tag = llm_settings_tags[0]
    for label, pattern in [
        (
            "basic 分区条件",
            (
                r"(?:v-else(?!-)|"
                r"v-else-if\s*=\s*['\"][^'\"]*activeSettingsSection\s*===\s*['\"]basic['\"])"
            ),
        ),
        ("embedded=true", r":embedded\s*=\s*['\"]true['\"]"),
        ("show-routing=false", r":show-routing\s*=\s*['\"]false['\"]"),
        ("saved handler", r"@saved\s*=\s*['\"]handleLLMConfigSaved['\"]"),
    ]:
        assert re.search(pattern, llm_settings_tag), (
            f"{SETTINGS_VIEW}: LLMSettings 缺少 {label}; tag={llm_settings_tag}"
        )


def test_personal_model_routing_supports_section_prop():
    _assert_pattern(
        PERSONAL_MODEL_ROUTING,
        "RoutingSection 联合类型",
        r"type\s+RoutingSection\s*=\s*['\"]providers['\"]\s*\|\s*['\"]models['\"]\s*\|\s*['\"]routes['\"]",
    )
    _assert_pattern(
        PERSONAL_MODEL_ROUTING,
        "activeSection prop",
        r"defineProps<\{[^}]*activeSection\??\s*:\s*RoutingSection",
    )
    _assert_pattern(
        PERSONAL_MODEL_ROUTING,
        "activeSection fallback 渲染",
        r"const\s+shouldRenderSection\s*=\s*\([^)]*section\s*:\s*RoutingSection[^)]*\)\s*:\s*boolean\s*=>\s*\([^)]*props\.activeSection\s*===\s*undefined[^)]*props\.activeSection\s*===\s*section[^)]*\)",
    )
    _assert_pattern(
        PERSONAL_MODEL_ROUTING,
        "providers 分区 v-if",
        r"v-if\s*=\s*['\"]shouldRenderSection\(['\"]providers['\"]\)['\"]",
    )
    _assert_pattern(
        PERSONAL_MODEL_ROUTING,
        "models 分区 v-if",
        r"v-if\s*=\s*['\"]shouldRenderSection\(['\"]models['\"]\)['\"]",
    )
    _assert_pattern(
        PERSONAL_MODEL_ROUTING,
        "routes 分区 v-if",
        r"v-if\s*=\s*['\"]shouldRenderSection\(['\"]routes['\"]\)['\"]",
    )


def test_llm_settings_can_render_basic_config_only():
    _assert_pattern(
        LLM_SETTINGS,
        "embedded/showRouting props",
        (
            r"defineProps<\{"
            r"(?=[^}]*embedded\??\s*:\s*boolean)"
            r"(?=[^}]*showRouting\??\s*:\s*boolean)[^}]*\}"
        ),
    )
    _assert_pattern(
        LLM_SETTINGS,
        "showRouting 控制路由组件",
        r"<PersonalModelRouting\b[^>]+v-if\s*=\s*(['\"])(?:props\.)?showRouting\1",
    )
    _assert_pattern(
        LLM_SETTINGS,
        "embedded class binding",
        r":class\s*=\s*['\"][^'\"]*llm-settings--embedded",
    )
    _assert_pattern(
        LLM_SETTINGS,
        "embedded 样式",
        r"\.llm-settings--embedded\s*\{",
    )
