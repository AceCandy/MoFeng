import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT.parent / "frontend/src"
SETTINGS_VIEW = "views/SettingsView.vue"
PERSONAL_MODEL_ROUTING = "components/llm-settings/PersonalModelRouting.vue"
MAIN_TS = "main.ts"


def _source(path: str) -> str:
    return (FRONTEND / path).read_text(encoding="utf-8")


def _assert_pattern(path: str, label: str, pattern: str) -> None:
    source = _source(path)
    assert re.search(pattern, source, re.DOTALL), (
        f"{path}: 缺少 {label}; pattern={pattern}"
    )


def _assert_missing(path: str, label: str, pattern: str) -> None:
    source = _source(path)
    assert not re.search(pattern, source, re.DOTALL), (
        f"{path}: 不应再出现 {label}; pattern={pattern}"
    )


def _component_tags(path: str, component: str) -> list[str]:
    source = _source(path)
    return re.findall(rf"<{component}\b[^>]*>", source, re.DOTALL)


def _css_block(source: str, selector: str) -> str:
    matches = re.findall(rf"{re.escape(selector)}\s*\{{([^}}]+)\}}", source, re.DOTALL)
    assert matches, f"缺少 CSS 选择器: {selector}"
    return "\n".join(matches)


def test_settings_view_only_declares_current_model_sections():
    source = _source(SETTINGS_VIEW)

    for section in ["llm", "embedding", "routes"]:
        assert re.search(rf"id\s*:\s*['\"]{section}['\"]", source)

    for removed in ["overview", "providers", "models", "basic"]:
        assert not re.search(rf"id\s*:\s*['\"]{removed}['\"]", source)

    for label in ["LLM 模型", "向量模型", "AI 阶段路由"]:
        assert label in source

    assert "activeSettingsSection" in source
    assert "settings-console__nav" in source
    assert "settings-console__mobile-tabs" in source
    assert "aria-current" in source


def test_settings_view_routes_sections_without_legacy_basic_config():
    for section in ["llm", "embedding", "routes"]:
        _assert_pattern(
            SETTINGS_VIEW,
            f"PersonalModelRouting {section} 分区",
            rf"<PersonalModelRouting\b[^>]+active-section\s*=\s*['\"]{section}['\"]",
        )

    assert _component_tags(SETTINGS_VIEW, "LLMSettings") == []
    _assert_missing(SETTINGS_VIEW, "基础 LLM 配置", "基础 LLM 配置")
    _assert_missing(SETTINGS_VIEW, "概览分区", "settings-overview-panel")


def test_personal_model_routing_has_llm_vector_and_routes_sections():
    _assert_pattern(
        PERSONAL_MODEL_ROUTING,
        "RoutingSection 联合类型",
        r"type\s+RoutingSection\s*=\s*['\"]llm['\"]\s*\|\s*['\"]embedding['\"]\s*\|\s*['\"]routes['\"]",
    )
    _assert_pattern(
        PERSONAL_MODEL_ROUTING,
        "activeSection prop",
        r"defineProps<\{[^}]*activeSection\??\s*:\s*RoutingSection",
    )

    for label in ["新增供应商", "拉取模型", "主模型", "当前使用"]:
        assert label in _source(PERSONAL_MODEL_ROUTING)

    for removed in ["个人模型路由", "默认 Chat", "默认 Embedding"]:
        assert removed not in _source(PERSONAL_MODEL_ROUTING)


def test_personal_model_routing_separates_chat_and_embedding_models():
    source = _source(PERSONAL_MODEL_ROUTING)

    assert "chatModelsByProvider" in source
    assert "embeddingModelsByProvider" in source
    assert "setPrimaryChatModel" in source
    assert "selectEmbeddingModel" in source
    assert "getProviderModels" in source
    assert "capabilities: { chat: true, embedding: false }" in source
    assert "capabilities: { chat: false, embedding: true }" in source


def test_personal_model_routing_keeps_fetched_models_per_capability():
    source = _source(PERSONAL_MODEL_ROUTING)

    assert "modelsByCapability" in source
    assert "modelsByCapability: { chat: [], embedding: [] }" in source
    assert "modelsByCapability[capability]" in source
    assert "state.models = await getProviderModels" not in source


def test_personal_model_routing_can_delete_saved_models_only():
    source = _source(PERSONAL_MODEL_ROUTING)

    assert "deleteUserModel" in source
    assert "deleteModelForActiveSection" in source
    assert "savedModelForActiveSection(provider.id, modelName)" in source
    assert "删除模型" in source
    assert "主模型不能直接删除" in source
    assert "当前向量模型不能直接删除" in source


def test_personal_model_routing_has_provider_card_enable_and_delete_actions():
    source = _source(PERSONAL_MODEL_ROUTING)

    assert "deleteProvider" in source
    assert "toggleProviderEnabled" in source
    assert "deleteProviderFromCard" in source
    assert "删除供应商" in source
    assert "确定删除供应商" in source
    assert "关联模型和阶段路由也会一起删除" in source


def test_personal_model_routing_filters_providers_by_active_section():
    source = _source(PERSONAL_MODEL_ROUTING)

    assert "activeProviders" in source
    assert 'v-for="provider in activeProviders"' in source
    assert "providerCapabilities(provider)[activeModelCapability()]" in source
    assert "capabilities: createProviderCapabilities()" in source
    assert 'v-if="activeProviders.length === 0"' in source


def test_personal_model_routing_uses_floating_model_picker_and_chips():
    source = _source(PERSONAL_MODEL_ROUTING)

    assert "model-routing__model-picker" in source
    assert "isModelPickerOpen(provider.id)" in source
    assert "filteredModelNamesForProvider(provider.id)" in source
    assert "selectedModelChipsForProvider(provider.id)" in source
    assert 'v-for="chip in selectedModelChipsForProvider(provider.id)"' in source
    assert "model-routing__selected-chip" in source
    assert "setPrimaryChatModelById" in source
    assert 'name="primary-chat-model"' not in source
    assert "handleModelRowClick" not in source


def test_settings_panel_allows_model_picker_to_escape_card_clip():
    source = _source(SETTINGS_VIEW)
    panel_block = _css_block(source, ".settings-panel")

    assert "overflow: visible" in panel_block


def test_settings_console_uses_touch_sized_controls():
    source = _source(PERSONAL_MODEL_ROUTING)
    settings_source = _source(SETTINGS_VIEW)

    for selector in [
        ".model-routing__picker-row",
        ".model-routing__delete-btn",
        ".model-routing__status",
        ".model-routing__provider-delete",
    ]:
        block = _css_block(source, selector)
        assert "min-height: 44px" in block

    assert "min-width: 44px" in source
    mobile_tab_block = _css_block(settings_source, ".settings-console__mobile-tab")
    assert "min-height: 44px" in mobile_tab_block


def test_settings_console_has_accessible_destructive_model_labels():
    source = _source(PERSONAL_MODEL_ROUTING)

    assert ':aria-label="`删除模型 ${chip.display_name || chip.model_name}`"' in source
    assert ':title="`删除模型 ${chip.display_name || chip.model_name}`"' in source
    assert 'aria-label="删除模型"' not in source
    assert 'title="删除模型"' not in source


def test_settings_console_avoids_low_contrast_action_colors():
    source = _source(PERSONAL_MODEL_ROUTING)
    global_source = _source("assets/main.css")

    assert "color: var(--md-primary-dark)" in global_source
    assert "color: var(--md-error-strong)" in source
    assert "color: var(--md-error);" not in source
    assert "rgba(66, 133, 244" not in global_source


def test_settings_console_removes_decorative_background_gradient():
    source = _source(SETTINGS_VIEW)
    settings_page_block = source.split(".settings-page", 1)[1].split("}", 1)[0]

    assert "radial-gradient" not in settings_page_block
    assert "background-color: var(--md-surface-dim)" in settings_page_block


def test_app_loads_only_necessary_noto_sans_weights():
    source = _source(MAIN_TS)

    assert "@fontsource/noto-sans-sc/400.css" in source
    assert "@fontsource/noto-sans-sc/500.css" in source
    assert "@fontsource/noto-sans-sc/300.css" not in source
    assert "@fontsource/noto-sans-sc/700.css" not in source
