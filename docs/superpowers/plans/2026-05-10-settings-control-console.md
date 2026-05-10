# Settings Control Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn `/settings` into a control-console layout with section navigation and focused detail panels.

**Architecture:** Keep all existing backend contracts and save logic unchanged. `SettingsView.vue` owns route-level shell and active section state, `PersonalModelRouting.vue` renders provider/model/route subsections based on a simple prop, and `LLMSettings.vue` renders the legacy basic config section on demand.

**Tech Stack:** Vue 3 SFC, `<script setup lang="ts">`, scoped CSS, existing Material 3 CSS classes, Vite build, pytest static checks.

---

## File Structure

- Modify `frontend/src/views/SettingsView.vue`
  - Add section navigation state.
  - Render left desktop navigation and mobile horizontal navigation.
  - Render overview, routing subsections, and basic config panel.
  - Keep version check and inspiration redirect behavior.

- Modify `frontend/src/components/LLMSettings.vue`
  - Add optional presentation props so it can render only the basic config form without the old outer card/header/routing block.
  - Keep existing form state, load/save/delete logic, model-list fetching, and emitted `saved` event.

- Modify `frontend/src/components/llm-settings/PersonalModelRouting.vue`
  - Add `activeSection` prop with values `providers`, `models`, and `routes`.
  - Render only the requested logical panel while preserving shared bundle loading and save behavior.
  - Keep provider/model/stage route API calls unchanged.

- Create `backend/tests/test_settings_console_static.py`
  - Static guard for the new section keys and component props.
  - Static guard that backend API contracts remain out of the UI-only change.

---

### Task 1: Add Static Guard For Settings Console Structure

**Files:**
- Create: `backend/tests/test_settings_console_static.py`

- [ ] **Step 1: Write the failing static tests**

Create `backend/tests/test_settings_console_static.py`:

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT.parent / "frontend/src"


def _source(path: str) -> str:
    return (FRONTEND / path).read_text(encoding="utf-8")


def test_settings_view_declares_console_sections():
    source = _source("views/SettingsView.vue")

    for section in [
        "overview",
        "providers",
        "models",
        "routes",
        "basic",
    ]:
        assert f"id: '{section}'" in source

    assert "activeSettingsSection" in source
    assert "settings-console__nav" in source
    assert "settings-console__mobile-tabs" in source
    assert "aria-current" in source


def test_settings_view_routes_sections_to_existing_components():
    source = _source("views/SettingsView.vue")

    assert 'active-section="providers"' in source
    assert 'active-section="models"' in source
    assert 'active-section="routes"' in source
    assert "<LLMSettings" in source
    assert ":show-routing=\"false\"" in source
    assert ":embedded=\"true\"" in source
    assert '@saved="handleLLMConfigSaved"' in source


def test_personal_model_routing_supports_section_prop():
    source = _source("components/llm-settings/PersonalModelRouting.vue")

    assert "type RoutingSection = 'providers' | 'models' | 'routes'" in source
    assert "activeSection" in source
    assert "v-if=\"activeSection === 'providers'\"" in source
    assert "v-if=\"activeSection === 'models'\"" in source
    assert "v-if=\"activeSection === 'routes'\"" in source


def test_llm_settings_can_render_basic_config_only():
    source = _source("components/LLMSettings.vue")

    assert "showRouting" in source
    assert "embedded" in source
    assert "v-if=\"props.showRouting\"" in source
    assert "llm-settings--embedded" in source
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run:

```bash
pytest backend/tests/test_settings_console_static.py -q
```

Expected result:

```text
FAILED backend/tests/test_settings_console_static.py::test_settings_view_declares_console_sections
FAILED backend/tests/test_settings_console_static.py::test_settings_view_routes_sections_to_existing_components
FAILED backend/tests/test_settings_console_static.py::test_personal_model_routing_supports_section_prop
FAILED backend/tests/test_settings_console_static.py::test_llm_settings_can_render_basic_config_only
```

- [ ] **Step 3: Commit the failing test**

Run:

```bash
git add backend/tests/test_settings_console_static.py
git commit -m "test: guard settings console layout"
```

---

### Task 2: Make PersonalModelRouting Render One Section At A Time

**Files:**
- Modify: `frontend/src/components/llm-settings/PersonalModelRouting.vue`

- [ ] **Step 1: Add the section prop**

In `PersonalModelRouting.vue`, add this type and props near the existing `defineEmits` call:

```ts
type RoutingSection = 'providers' | 'models' | 'routes';

const props = withDefaults(defineProps<{
  activeSection?: RoutingSection;
}>(), {
  activeSection: 'providers',
});
```

Keep the existing `defineEmits` block unchanged.

- [ ] **Step 2: Gate the provider, model, and route panels in the template**

Change the template section rendering so the provider panel is wrapped like this:

```vue
<section v-if="activeSection === 'providers'" class="model-routing__panel">
```

Change the model panel wrapper to:

```vue
<section v-if="activeSection === 'models'" class="model-routing__panel">
```

Change the route panel wrapper to:

```vue
<section v-if="activeSection === 'routes'" class="model-routing__panel model-routing__stages">
```

Remove the surrounding `model-routing__grid` wrapper if it only exists to hold both provider and model panels together. Keep the inner provider/model/stage form markup unchanged.

- [ ] **Step 3: Update the header copy for section mode**

Keep the `个人模型路由` header, but make the subtitle describe the current section through a computed value:

```ts
const sectionSubtitle = computed(() => {
  if (props.activeSection === 'providers') {
    return '维护供应商地址、类型与 API Key。';
  }
  if (props.activeSection === 'models') {
    return '维护可用模型、能力标签和默认模型。';
  }
  return '为不同 AI 阶段指定默认模型。';
});
```

Then update the subtitle binding:

```vue
<p class="md-body-medium model-routing__subtitle">
  {{ sectionSubtitle }}
</p>
```

- [ ] **Step 4: Run the section prop static test**

Run:

```bash
pytest backend/tests/test_settings_console_static.py::test_personal_model_routing_supports_section_prop -q
```

Expected result:

```text
1 passed
```

- [ ] **Step 5: Commit the routing section change**

Run:

```bash
git add frontend/src/components/llm-settings/PersonalModelRouting.vue
git commit -m "feat: split model routing settings sections"
```

---

### Task 3: Let LLMSettings Render As Embedded Basic Config

**Files:**
- Modify: `frontend/src/components/LLMSettings.vue`

- [ ] **Step 1: Add presentation props**

Add this props block near the existing `defineEmits` call:

```ts
const props = withDefaults(defineProps<{
  embedded?: boolean;
  showRouting?: boolean;
}>(), {
  embedded: false,
  showRouting: true,
});
```

- [ ] **Step 2: Make the outer class and header conditional**

Change the root section class to:

```vue
<section
  class="md-card md-card-elevated llm-settings"
  :class="{ 'llm-settings--embedded': props.embedded }"
>
```

Change the header wrapper to:

```vue
<header v-if="!props.embedded" class="llm-settings__header">
```

- [ ] **Step 3: Gate PersonalModelRouting inside LLMSettings**

Change:

```vue
<PersonalModelRouting @saved="emit('saved')" />
```

to:

```vue
<PersonalModelRouting v-if="props.showRouting" @saved="emit('saved')" />
```

Keep the import because default usage still supports the full old component behavior.

- [ ] **Step 4: Add embedded styling**

Add these styles inside the existing scoped style block:

```css
.llm-settings--embedded {
  box-shadow: none;
  padding: 0;
  border-radius: 0;
  background: transparent;
}
```

- [ ] **Step 5: Run the LLMSettings static test**

Run:

```bash
pytest backend/tests/test_settings_console_static.py::test_llm_settings_can_render_basic_config_only -q
```

Expected result:

```text
1 passed
```

- [ ] **Step 6: Commit the embedded LLM settings change**

Run:

```bash
git add frontend/src/components/LLMSettings.vue
git commit -m "feat: support embedded basic llm settings"
```

---

### Task 4: Build The Settings Console Shell

**Files:**
- Modify: `frontend/src/views/SettingsView.vue`

- [ ] **Step 1: Add console section types and state**

Add these definitions after the version debug constants:

```ts
type SettingsSectionId = 'overview' | 'providers' | 'models' | 'routes' | 'basic';

interface SettingsSection {
  id: SettingsSectionId;
  label: string;
  description: string;
}

const settingsSections: SettingsSection[] = [
  { id: 'overview', label: '概览', description: '查看版本状态与配置入口' },
  { id: 'providers', label: '供应商与 API Key', description: '维护模型供应商、地址和认证信息' },
  { id: 'models', label: '可用模型', description: '维护模型名称、能力和默认模型' },
  { id: 'routes', label: 'AI 阶段路由', description: '为不同 AI 流程指定默认模型' },
  { id: 'basic', label: '基础 LLM 配置', description: '兼容旧版主模型与向量模型配置' },
];

const activeSettingsSection = ref<SettingsSectionId>('overview');

const activeSectionMeta = computed(() => (
  settingsSections.find(section => section.id === activeSettingsSection.value) || settingsSections[0]
));

const selectSettingsSection = (sectionId: SettingsSectionId) => {
  activeSettingsSection.value = sectionId;
};
```

- [ ] **Step 2: Replace the stacked content template with console layout**

Keep the outer page div and inspiration notice logic. Replace the main content after the notice with this structure:

```vue
<section class="settings-console">
  <nav class="settings-console__nav" aria-label="设置分区">
    <button
      v-for="section in settingsSections"
      :key="section.id"
      type="button"
      class="settings-console__nav-item"
      :class="{ active: activeSettingsSection === section.id }"
      :aria-current="activeSettingsSection === section.id ? 'page' : undefined"
      @click="selectSettingsSection(section.id)"
    >
      <span>{{ section.label }}</span>
      <small>{{ section.description }}</small>
    </button>
  </nav>

  <div class="settings-console__content">
    <div class="settings-console__mobile-tabs" role="tablist" aria-label="设置分区">
      <button
        v-for="section in settingsSections"
        :key="section.id"
        type="button"
        class="settings-console__tab"
        :class="{ active: activeSettingsSection === section.id }"
        :aria-current="activeSettingsSection === section.id ? 'page' : undefined"
        @click="selectSettingsSection(section.id)"
      >
        {{ section.label }}
      </button>
    </div>

    <section class="md-card md-card-elevated settings-panel">
      <header class="settings-panel__header">
        <div>
          <p class="md-label-medium settings-panel__eyebrow">Settings</p>
          <h2 class="md-headline-small settings-panel__title">{{ activeSectionMeta.label }}</h2>
          <p class="md-body-medium settings-panel__subtitle">{{ activeSectionMeta.description }}</p>
        </div>
      </header>

      <div v-if="activeSettingsSection === 'overview'" class="settings-overview-panel">
        <div class="settings-summary-grid">
          <article
            v-for="section in settingsSections.filter(item => item.id !== 'overview')"
            :key="section.id"
            class="settings-summary-card"
          >
            <h3 class="md-title-medium">{{ section.label }}</h3>
            <p class="md-body-small">{{ section.description }}</p>
            <button
              type="button"
              class="md-btn md-btn-text md-ripple settings-summary-card__action"
              @click="selectSettingsSection(section.id)"
            >
              打开
            </button>
          </article>
        </div>
      </div>

      <PersonalModelRouting
        v-else-if="activeSettingsSection === 'providers'"
        active-section="providers"
        @saved="handleLLMConfigSaved"
      />

      <PersonalModelRouting
        v-else-if="activeSettingsSection === 'models'"
        active-section="models"
        @saved="handleLLMConfigSaved"
      />

      <PersonalModelRouting
        v-else-if="activeSettingsSection === 'routes'"
        active-section="routes"
        @saved="handleLLMConfigSaved"
      />

      <LLMSettings
        v-else
        :embedded="true"
        :show-routing="false"
        @saved="handleLLMConfigSaved"
      />
    </section>
  </div>
</section>
```

Also import `PersonalModelRouting`:

```ts
import PersonalModelRouting from '@/components/llm-settings/PersonalModelRouting.vue';
```

- [ ] **Step 3: Add console layout CSS**

Append these styles to the scoped style block:

```css
.settings-console {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  gap: var(--md-spacing-5);
  align-items: start;
}

.settings-console__nav {
  position: sticky;
  top: var(--md-spacing-6);
  display: grid;
  gap: var(--md-spacing-2);
}

.settings-console__nav-item {
  width: 100%;
  border: 1px solid transparent;
  border-radius: var(--md-radius-lg);
  background: transparent;
  color: var(--md-on-surface-variant);
  display: grid;
  gap: 2px;
  padding: var(--md-spacing-3);
  text-align: left;
  cursor: pointer;
  transition:
    background-color var(--md-duration-short) var(--md-easing-standard),
    border-color var(--md-duration-short) var(--md-easing-standard),
    color var(--md-duration-short) var(--md-easing-standard);
}

.settings-console__nav-item span {
  font-size: var(--md-body-medium);
  font-weight: 700;
}

.settings-console__nav-item small {
  font-size: var(--md-body-small);
}

.settings-console__nav-item:hover,
.settings-console__nav-item.active {
  border-color: var(--md-primary);
  background: var(--md-primary-container);
  color: var(--md-on-primary-container);
}

.settings-console__nav-item:focus-visible,
.settings-console__tab:focus-visible {
  outline: 2px solid var(--md-primary);
  outline-offset: 2px;
}

.settings-console__content {
  min-width: 0;
  display: grid;
  gap: var(--md-spacing-3);
}

.settings-console__mobile-tabs {
  display: none;
}

.settings-panel {
  border-radius: var(--md-radius-xl);
  padding: var(--md-spacing-6);
}

.settings-panel__header {
  margin-bottom: var(--md-spacing-5);
}

.settings-panel__eyebrow {
  margin: 0 0 var(--md-spacing-1);
  color: var(--md-primary);
}

.settings-panel__title {
  margin: 0;
  color: var(--md-on-surface);
}

.settings-panel__subtitle {
  margin: var(--md-spacing-1) 0 0;
  color: var(--md-on-surface-variant);
}

.settings-summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--md-spacing-3);
}

.settings-summary-card {
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-lg);
  padding: var(--md-spacing-4);
  background: var(--md-surface-container-low);
}

.settings-summary-card h3,
.settings-summary-card p {
  margin: 0;
}

.settings-summary-card p {
  margin-top: var(--md-spacing-1);
  color: var(--md-on-surface-variant);
}

.settings-summary-card__action {
  margin-top: var(--md-spacing-3);
  padding-inline: var(--md-spacing-2);
}

@media (max-width: 960px) {
  .settings-console {
    grid-template-columns: minmax(0, 1fr);
  }

  .settings-console__nav {
    display: none;
  }

  .settings-console__mobile-tabs {
    display: flex;
    gap: var(--md-spacing-2);
    overflow-x: auto;
    padding-bottom: var(--md-spacing-1);
  }

  .settings-console__tab {
    border: 1px solid var(--md-outline-variant);
    border-radius: var(--md-radius-full);
    background: var(--md-surface);
    color: var(--md-on-surface-variant);
    flex: 0 0 auto;
    min-height: 38px;
    padding: 0 var(--md-spacing-3);
    font-weight: 700;
  }

  .settings-console__tab.active {
    border-color: var(--md-primary);
    background: var(--md-primary-container);
    color: var(--md-on-primary-container);
  }

  .settings-panel {
    padding: var(--md-spacing-4);
  }

  .settings-summary-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
```

- [ ] **Step 4: Run SettingsView static tests**

Run:

```bash
pytest backend/tests/test_settings_console_static.py::test_settings_view_declares_console_sections backend/tests/test_settings_console_static.py::test_settings_view_routes_sections_to_existing_components -q
```

Expected result:

```text
2 passed
```

- [ ] **Step 5: Commit the console shell change**

Run:

```bash
git add frontend/src/views/SettingsView.vue
git commit -m "feat: add settings console shell"
```

---

### Task 5: Verify Build And Browser Layout

**Files:**
- No source changes expected unless verification finds a defect.

- [ ] **Step 1: Run all static settings tests**

Run:

```bash
pytest backend/tests/test_settings_console_static.py -q
```

Expected result:

```text
4 passed
```

- [ ] **Step 2: Run frontend build**

Run:

```bash
cd frontend
npm run build
```

Expected result:

```text
vue-tsc --build
vite build
```

The command must exit with status `0`.

- [ ] **Step 3: Start the frontend dev server**

Run from `frontend/`:

```bash
npm run dev -- --host 0.0.0.0
```

Expected result includes a LAN URL or local URL similar to:

```text
Local:   http://localhost:5173/
Network: http://192.168.1.205:5173/
```

- [ ] **Step 4: Browser smoke test desktop layout**

Open `/settings` in a browser at desktop width.

Check:

```text
左侧有 5 个导航项
右侧只显示当前 active panel
点击“供应商与 API Key”只显示供应商面板
点击“可用模型”只显示模型面板
点击“AI 阶段路由”只显示阶段路由面板
点击“基础 LLM 配置”只显示主模型/向量模型表单
版本状态仍在顶部显示
```

- [ ] **Step 5: Browser smoke test mobile layout**

Open `/settings` at mobile width.

Check:

```text
左侧导航隐藏
顶部横向 tabs 出现
tabs 不换成多行
点击各 tab 能切换对应 panel
表单字段没有横向溢出
```

- [ ] **Step 6: Final commit only if verification required fixes**

If verification required source fixes, commit them:

```bash
git add frontend/src/views/SettingsView.vue frontend/src/components/LLMSettings.vue frontend/src/components/llm-settings/PersonalModelRouting.vue backend/tests/test_settings_console_static.py
git commit -m "fix: polish settings console layout"
```

If no source fixes were needed, do not create an empty commit.

---

## Self-Review Notes

- Spec coverage:
  - Desktop left navigation plus right detail panel: Task 4.
  - Mobile top navigation plus single-column detail: Task 4 and Task 5.
  - No backend contract changes: tasks only touch frontend components and a static test.
  - Existing save/delete behavior preserved: Task 2 and Task 3 keep existing methods and API calls.
  - Browser smoke verification: Task 5.

- Placeholder scan:
  - No placeholder markers or unspecified implementation steps.

- Type consistency:
  - `SettingsSectionId` uses `overview | providers | models | routes | basic`.
  - `RoutingSection` uses `providers | models | routes`.
  - Template prop uses kebab-case `active-section`, matching Vue prop casing.
