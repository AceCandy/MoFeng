# Admin Domain Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Polish the full `/admin` domain so it matches the Arboris Novel workspace and settings experience at flagship quality.

**Architecture:** Keep the existing Vue 3, Vue Router, Naive UI, and Material-token stack. Replace the nested admin app shell with a product-console layout inside `AppShell.vue`, then normalize admin child panels around shared `--md-*` tokens and existing Naive data controls. Preserve backend contracts and reuse `NovelDetailShell.vue` for admin project detail with an embedded admin-safe layout mode.

**Tech Stack:** Vue 3 SFCs, TypeScript, Vue Router, Naive UI, CSS custom properties in `frontend/src/assets/main.css`, pytest static frontend tests, Vite build.

---

## File Structure

Modify:

- `backend/tests/test_frontend_deep_restructure_static.py`
  - Static regression tests for admin console structure, token usage, emoji removal, and embedded admin detail behavior.
- `frontend/src/views/AdminView.vue`
  - Admin console wrapper, tab navigation, SVG icons, query sync, and active panel rendering.
- `frontend/src/components/admin/Statistics.vue`
  - Tokenized metric tiles and non-emoji statistic icons.
- `frontend/src/components/admin/UserManagement.vue`
  - Shared header/toolbar polish and tokenized title/search styles.
- `frontend/src/components/admin/PromptManagement.vue`
  - Tokenized split list/editor layout and selected/focus states.
- `frontend/src/components/admin/NovelManagement.vue`
  - Tokenized table/mobile card text and header pattern.
- `frontend/src/components/admin/UpdateLogManagement.vue`
  - Tokenized publishing tool and log rows, no decorative gradients.
- `frontend/src/components/admin/SettingsManagement.vue`
  - Tokenized overview, health items, managed rows, code chips, and warning surface.
- `frontend/src/components/admin/PasswordManagement.vue`
  - Tokenized single-column security panel.
- `frontend/src/components/shared/NovelDetailShell.vue`
  - Embedded admin detail mode, admin return target, and read-only context chip.

Do not modify backend API code unless a failing UI verification exposes an API contract defect.

---

## Task 1: Add Admin Polish Static Regression Tests

**Files:**

- Modify: `backend/tests/test_frontend_deep_restructure_static.py`

- [ ] **Step 1: Add failing static tests**

Append these tests after `test_auth_and_admin_surfaces_remove_glass_and_hardcoded_backgrounds`:

```python
def test_admin_console_uses_product_shell_pattern():
    source = _source("views/AdminView.vue")

    for text in [
        "admin-console",
        "admin-console__intro",
        "admin-console__nav",
        "admin-console__content",
        "管理控制台",
        "返回工作台",
        "aria-current",
        "aria-hidden=\"true\"",
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
    ]:
        assert removed not in source


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
```

- [ ] **Step 2: Run the new static tests and verify they fail**

Run:

```bash
pytest backend/tests/test_frontend_deep_restructure_static.py -q
```

Expected:

```text
FAILED backend/tests/test_frontend_deep_restructure_static.py::test_admin_console_uses_product_shell_pattern
FAILED backend/tests/test_frontend_deep_restructure_static.py::test_admin_child_panels_use_tokens_and_remove_decorative_gradients
FAILED backend/tests/test_frontend_deep_restructure_static.py::test_admin_project_detail_uses_embedded_readonly_context
```

If unrelated existing tests fail, stop and inspect before continuing.

- [ ] **Step 3: Commit the failing tests**

Run:

```bash
git add backend/tests/test_frontend_deep_restructure_static.py
git commit -m "test: cover admin domain polish"
```

Expected:

```text
[main <hash>] test: cover admin domain polish
```

---

## Task 2: Replace AdminView Nested Layout With Product Console

**Files:**

- Modify: `frontend/src/views/AdminView.vue`
- Test: `backend/tests/test_frontend_deep_restructure_static.py`

- [ ] **Step 1: Remove nested Naive layout imports**

In `AdminView.vue`, remove these imports from `naive-ui`:

```ts
NLayout,
NLayoutContent,
NLayoutHeader,
NLayoutSider,
NMenu,
NScrollbar,
NSpace,
type MenuOption
```

Keep only `NButton` if the template still uses it.

- [ ] **Step 2: Replace menu metadata with section metadata**

Replace `MenuKey`, `components`, `iconRenderers`, and `menuOptions` with:

```ts
type MenuKey =
  | 'statistics'
  | 'users'
  | 'prompts'
  | 'novels'
  | 'logs'
  | 'settings'
  | 'password'

interface AdminSection {
  key: MenuKey
  label: string
  description: string
  icon: 'chart' | 'user' | 'prompt' | 'book' | 'log' | 'settings' | 'lock'
}

const components: Record<MenuKey, ReturnType<typeof defineAsyncComponent>> = {
  statistics: defineAsyncComponent(() => import('../components/admin/Statistics.vue')),
  users: defineAsyncComponent(() => import('../components/admin/UserManagement.vue')),
  prompts: defineAsyncComponent(() => import('../components/admin/PromptManagement.vue')),
  novels: defineAsyncComponent(() => import('../components/admin/NovelManagement.vue')),
  logs: defineAsyncComponent(() => import('../components/admin/UpdateLogManagement.vue')),
  settings: defineAsyncComponent(() => import('../components/admin/SettingsManagement.vue')),
  password: defineAsyncComponent(() => import('../components/admin/PasswordManagement.vue')),
}

const adminSections: AdminSection[] = [
  { key: 'statistics', label: '数据总览', description: '平台规模与请求概况', icon: 'chart' },
  { key: 'users', label: '用户管理', description: '账号、权限和状态', icon: 'user' },
  { key: 'prompts', label: '提示词管理', description: '系统 Prompt 模板', icon: 'prompt' },
  { key: 'novels', label: '小说项目', description: '项目进度与内容巡检', icon: 'book' },
  { key: 'logs', label: '更新日志', description: '公告发布与置顶', icon: 'log' },
  { key: 'settings', label: '系统配置', description: '托管配置与键值项', icon: 'settings' },
  { key: 'password', label: '安全中心', description: '管理员密码更新', icon: 'lock' },
]
```

- [ ] **Step 3: Add SVG icon renderer**

Add this helper below `adminSections`:

```ts
const renderIcon = (icon: AdminSection['icon']) => {
  const common = {
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 2,
    'aria-hidden': 'true',
  }

  const paths: Record<AdminSection['icon'], any[]> = {
    chart: [
      h('path', { d: 'M4 19V5' }),
      h('path', { d: 'M4 19h16' }),
      h('path', { d: 'M8 16v-5' }),
      h('path', { d: 'M12 16V8' }),
      h('path', { d: 'M16 16v-3' }),
    ],
    user: [
      h('circle', { cx: 12, cy: 8, r: 4 }),
      h('path', { d: 'M4 20a8 8 0 0116 0' }),
    ],
    prompt: [
      h('path', { d: 'M5 4h14v16H5z' }),
      h('path', { d: 'M8 8h8' }),
      h('path', { d: 'M8 12h8' }),
      h('path', { d: 'M8 16h5' }),
    ],
    book: [
      h('path', { d: 'M4 19.5A2.5 2.5 0 016.5 17H20' }),
      h('path', { d: 'M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z' }),
    ],
    log: [
      h('path', { d: 'M4 5h16' }),
      h('path', { d: 'M4 12h16' }),
      h('path', { d: 'M4 19h10' }),
    ],
    settings: [
      h('circle', { cx: 12, cy: 12, r: 3 }),
      h('path', { d: 'M19.4 15a1.7 1.7 0 00.34 1.87l.06.06a2 2 0 01-2.83 2.83l-.06-.06A1.7 1.7 0 0015 19.4a1.7 1.7 0 00-1 .6 1.7 1.7 0 00-.4 1.1V21a2 2 0 01-4 0v-.09A1.7 1.7 0 009 19.4a1.7 1.7 0 00-1.87.34l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.7 1.7 0 004.6 15a1.7 1.7 0 00-.6-1 1.7 1.7 0 00-1.1-.4H3a2 2 0 010-4h.09A1.7 1.7 0 004.6 9a1.7 1.7 0 00-.34-1.87l-.06-.06a2 2 0 012.83-2.83l.06.06A1.7 1.7 0 009 4.6a1.7 1.7 0 001-.6 1.7 1.7 0 00.4-1.1V3a2 2 0 014 0v.09A1.7 1.7 0 0015 4.6a1.7 1.7 0 001.87-.34l.06-.06a2 2 0 012.83 2.83l-.06.06A1.7 1.7 0 0019.4 9a1.7 1.7 0 00.6 1 1.7 1.7 0 001.1.4H21a2 2 0 010 4h-.09A1.7 1.7 0 0019.4 15z' }),
    ],
    lock: [
      h('rect', { x: 5, y: 11, width: 14, height: 10, rx: 2 }),
      h('path', { d: 'M8 11V8a4 4 0 118 0v3' }),
    ],
  }

  return h('svg', common, paths[icon])
}
```

- [ ] **Step 4: Keep route query sync and active label**

Use these computed values:

```ts
const activeComponent = computed(() => components[activeKey.value])
const activeSection = computed(
  () => adminSections.find((section) => section.key === activeKey.value) || adminSections[0],
)
```

Change `handleMenuSelect` to `selectSection`:

```ts
const selectSection = (key: MenuKey) => {
  activeKey.value = key
  router.replace({ name: 'admin', query: { tab: key } })
}
```

Keep `syncActiveKeyWithRoute`, `goBack`, and the resize hooks only if used by the new template. Remove `collapsed`, `updateCollapsedByWidth`, and resize listeners when the new template does not need them.

- [ ] **Step 5: Replace the AdminView template**

Replace the full template with:

```vue
<template>
  <div class="app-page admin-console">
    <section class="admin-console__intro" aria-labelledby="admin-console-title">
      <div class="admin-console__intro-copy">
        <p class="admin-console__kicker">Admin</p>
        <h2 id="admin-console-title">管理控制台</h2>
        <p>维护用户、提示词、项目、更新日志和系统配置。</p>
      </div>
      <div class="admin-console__intro-actions">
        <span class="md-chip md-chip-assist">当前：{{ activeSection.label }}</span>
        <span class="md-chip md-chip-assist">管理员访问</span>
        <n-button size="small" secondary type="primary" @click="goBack">
          返回工作台
        </n-button>
      </div>
    </section>

    <nav class="admin-console__nav" aria-label="管理分区">
      <button
        v-for="section in adminSections"
        :key="section.key"
        type="button"
        class="admin-console__nav-item"
        :class="{ 'is-active': activeKey === section.key }"
        :aria-current="activeKey === section.key ? 'page' : undefined"
        @click="selectSection(section.key)"
      >
        <span class="admin-console__nav-icon" aria-hidden="true">
          <component :is="renderIcon(section.icon)" />
        </span>
        <span class="admin-console__nav-copy">
          <strong>{{ section.label }}</strong>
          <small>{{ section.description }}</small>
        </span>
      </button>
    </nav>

    <section class="admin-console__content" :aria-label="activeSection.label">
      <component :is="activeComponent" />
    </section>
  </div>
</template>
```

- [ ] **Step 6: Replace AdminView scoped CSS**

Replace the full `<style scoped>` block with:

```css
.admin-console {
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-5);
}

.admin-console__intro,
.admin-console__content {
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-xl);
  background-color: var(--md-surface);
  box-shadow: var(--md-elevation-1);
}

.admin-console__intro {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--md-spacing-5);
  padding: var(--md-spacing-6);
}

.admin-console__intro-copy {
  min-width: 0;
}

.admin-console__kicker {
  margin: 0 0 var(--md-spacing-1);
  color: var(--md-primary-dark);
  font-size: var(--md-label-medium);
  font-weight: 600;
}

.admin-console__intro h2 {
  margin: 0;
  color: var(--md-on-surface);
  font-size: var(--md-headline-small);
  font-weight: 600;
  line-height: 1.25;
}

.admin-console__intro p:last-child {
  margin: var(--md-spacing-2) 0 0;
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-medium);
}

.admin-console__intro-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: var(--md-spacing-2);
}

.admin-console__nav {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--md-spacing-2);
  padding: var(--md-spacing-2);
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-xl);
  background-color: var(--md-surface-container-low);
}

.admin-console__nav-item {
  min-height: 68px;
  display: flex;
  align-items: center;
  gap: var(--md-spacing-3);
  padding: var(--md-spacing-3);
  border: 1px solid transparent;
  border-radius: var(--md-radius-lg);
  background-color: transparent;
  color: var(--md-on-surface-variant);
  text-align: left;
  cursor: pointer;
  transition:
    background-color var(--md-duration-short) var(--md-easing-standard),
    border-color var(--md-duration-short) var(--md-easing-standard),
    color var(--md-duration-short) var(--md-easing-standard);
}

.admin-console__nav-item:hover {
  border-color: color-mix(in srgb, var(--md-primary) 30%, var(--md-outline-variant));
  background-color: var(--md-surface);
  color: var(--md-primary-dark);
}

.admin-console__nav-item:focus-visible {
  outline: 2px solid var(--md-primary);
  outline-offset: 2px;
}

.admin-console__nav-item.is-active,
.admin-console__nav-item[aria-current='page'] {
  border-color: color-mix(in srgb, var(--md-primary) 42%, var(--md-outline-variant));
  background-color: var(--md-primary-container);
  color: var(--md-on-primary-container);
}

.admin-console__nav-icon {
  width: 40px;
  height: 40px;
  flex: 0 0 40px;
  display: grid;
  place-items: center;
  border-radius: var(--md-radius-md);
  background-color: var(--md-surface);
}

.admin-console__nav-item.is-active .admin-console__nav-icon {
  background-color: color-mix(in srgb, var(--md-primary) 16%, var(--md-surface));
}

.admin-console__nav-icon svg {
  width: 20px;
  height: 20px;
}

.admin-console__nav-copy {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.admin-console__nav-copy strong {
  color: inherit;
  font-size: var(--md-title-small);
  font-weight: 600;
}

.admin-console__nav-copy small {
  color: color-mix(in srgb, currentColor 74%, transparent);
  font-size: var(--md-body-small);
}

.admin-console__content {
  min-width: 0;
  padding: var(--md-spacing-5);
}

@media (max-width: 720px) {
  .admin-console {
    gap: var(--md-spacing-4);
  }

  .admin-console__intro {
    align-items: stretch;
    flex-direction: column;
    padding: var(--md-spacing-4);
  }

  .admin-console__intro-actions {
    justify-content: flex-start;
  }

  .admin-console__nav {
    grid-template-columns: 1fr;
  }

  .admin-console__content {
    padding: var(--md-spacing-4);
    border-radius: var(--md-radius-lg);
  }
}
```

- [ ] **Step 7: Run static tests for AdminView**

Run:

```bash
pytest backend/tests/test_frontend_deep_restructure_static.py::test_admin_console_uses_product_shell_pattern -q
```

Expected:

```text
1 passed
```

- [ ] **Step 8: Commit AdminView polish**

Run:

```bash
git add frontend/src/views/AdminView.vue
git commit -m "style: align admin console shell"
```

Expected:

```text
[main <hash>] style: align admin console shell
```

---

## Task 3: Tokenize Statistics, Users, Novels, and Password Panels

**Files:**

- Modify: `frontend/src/components/admin/Statistics.vue`
- Modify: `frontend/src/components/admin/UserManagement.vue`
- Modify: `frontend/src/components/admin/NovelManagement.vue`
- Modify: `frontend/src/components/admin/PasswordManagement.vue`
- Test: `backend/tests/test_frontend_deep_restructure_static.py`

- [ ] **Step 1: Replace statistic emoji markup with SVG metric icons**

In `Statistics.vue`, replace each statistic card icon block:

```vue
<div class="stat-icon">📚</div>
```

with this pattern, using the matching SVG per tile:

```vue
<div class="stat-icon" aria-hidden="true">
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <path stroke-linecap="round" stroke-linejoin="round" d="M4 19.5A2.5 2.5 0 016.5 17H20" />
    <path stroke-linecap="round" stroke-linejoin="round" d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z" />
  </svg>
</div>
```

Use this SVG for `用户总数`:

```vue
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
  <circle cx="12" cy="8" r="4" />
  <path stroke-linecap="round" stroke-linejoin="round" d="M4 20a8 8 0 0116 0" />
</svg>
```

Use this SVG for `API 请求总数`:

```vue
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
  <path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
</svg>
```

- [ ] **Step 2: Tokenize Statistics styles**

Replace the `Statistics.vue` scoped CSS with:

```css
.admin-card {
  width: 100%;
  box-sizing: border-box;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--md-spacing-3);
  flex-wrap: wrap;
}

.card-title {
  color: var(--md-on-surface);
  font-size: var(--md-title-large);
  font-weight: 600;
}

.stat-card {
  min-height: 132px;
  display: flex;
  align-items: center;
  gap: var(--md-spacing-4);
  padding: var(--md-spacing-5);
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-lg);
  background-color: var(--md-surface-container-low);
}

.stat-icon {
  width: 44px;
  height: 44px;
  flex: 0 0 44px;
  display: grid;
  place-items: center;
  border-radius: var(--md-radius-md);
  background-color: var(--md-primary-container);
  color: var(--md-on-primary-container);
}

.stat-icon svg {
  width: 22px;
  height: 22px;
}

@media (max-width: 767px) {
  .card-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .card-title {
    font-size: var(--md-title-medium);
  }

  .stat-card {
    padding: var(--md-spacing-4);
  }
}
```

- [ ] **Step 3: Tokenize UserManagement styles**

Replace `UserManagement.vue` scoped CSS with:

```css
.admin-card {
  width: 100%;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--md-spacing-4);
  flex-wrap: wrap;
}

.card-title {
  color: var(--md-on-surface);
  font-size: var(--md-title-large);
  font-weight: 600;
}

.search-input {
  width: min(240px, 60vw);
}

.user-table {
  width: 100%;
}

@media (max-width: 767px) {
  .card-header {
    flex-direction: column;
    align-items: stretch;
  }

  .card-title {
    font-size: var(--md-title-medium);
  }

  .search-input {
    width: 100%;
  }
}
```

- [ ] **Step 4: Tokenize NovelManagement styles**

In `NovelManagement.vue`, replace hard-coded color styles in the scoped CSS:

```css
.card-title {
  color: var(--md-on-surface);
  font-size: var(--md-title-large);
  font-weight: 600;
}

.table-title {
  color: var(--md-on-surface);
  font-weight: 600;
}

.table-subtitle {
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
  word-break: break-all;
}

.table-owner,
.table-progress,
.table-date {
  color: var(--md-on-surface);
}

.novel-card {
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-lg);
  background-color: var(--md-surface);
}

.mobile-card-title {
  color: var(--md-on-surface);
  font-size: var(--md-title-small);
  font-weight: 600;
}

.mobile-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--md-spacing-3);
  margin-top: var(--md-spacing-3);
  color: var(--md-on-surface);
  font-size: var(--md-body-medium);
  word-break: break-word;
}

.mobile-label {
  color: var(--md-on-surface-variant);
}

.mobile-value {
  color: var(--md-on-surface);
  font-weight: 500;
  text-align: right;
}
```

Keep the existing layout selectors that do not contain hard-coded colors.

- [ ] **Step 5: Tokenize PasswordManagement styles**

Replace `PasswordManagement.vue` scoped CSS with:

```css
.password-container {
  width: min(100%, 560px);
  margin: 0 auto;
}

.password-card {
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-lg);
  background-color: var(--md-surface);
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-title {
  color: var(--md-on-surface);
  font-size: var(--md-title-large);
  font-weight: 600;
}

.password-form {
  max-width: 440px;
}

.mb-4 {
  margin-bottom: var(--md-spacing-4);
}
```

- [ ] **Step 6: Run static tests for tokenized child panels**

Run:

```bash
pytest backend/tests/test_frontend_deep_restructure_static.py::test_admin_child_panels_use_tokens_and_remove_decorative_gradients -q
```

Expected at this stage:

```text
FAILED backend/tests/test_frontend_deep_restructure_static.py::test_admin_child_panels_use_tokens_and_remove_decorative_gradients
```

The test should now fail only on `PromptManagement.vue`, `UpdateLogManagement.vue`, or `SettingsManagement.vue`, because those are handled in Task 4.

- [ ] **Step 7: Commit these panel changes**

Run:

```bash
git add frontend/src/components/admin/Statistics.vue frontend/src/components/admin/UserManagement.vue frontend/src/components/admin/NovelManagement.vue frontend/src/components/admin/PasswordManagement.vue
git commit -m "style: tokenize core admin panels"
```

Expected:

```text
[main <hash>] style: tokenize core admin panels
```

---

## Task 4: Tokenize Prompt, Update Log, and System Settings Panels

**Files:**

- Modify: `frontend/src/components/admin/PromptManagement.vue`
- Modify: `frontend/src/components/admin/UpdateLogManagement.vue`
- Modify: `frontend/src/components/admin/SettingsManagement.vue`
- Test: `backend/tests/test_frontend_deep_restructure_static.py`

- [ ] **Step 1: Tokenize PromptManagement CSS**

In `PromptManagement.vue`, replace the scoped CSS from `.admin-card` through `.prompt-list-item:focus-visible` with:

```css
.admin-card {
  width: 100%;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: var(--md-spacing-4);
}

.card-title {
  color: var(--md-on-surface);
  font-size: var(--md-title-large);
  font-weight: 600;
}

.prompt-layout {
  display: flex;
  align-items: stretch;
  gap: var(--md-spacing-5);
  min-height: 420px;
}

.prompt-layout.mobile {
  flex-direction: column;
}

.prompt-sidebar {
  width: 300px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  padding: var(--md-spacing-3);
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-lg);
  background-color: var(--md-surface-container-low);
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--md-spacing-3);
  padding: 0 var(--md-spacing-1);
}

.sidebar-title {
  color: var(--md-on-surface);
  font-size: var(--md-label-large);
  font-weight: 600;
}

.prompt-layout.mobile .prompt-sidebar {
  width: 100%;
  max-height: 260px;
}

.prompt-scroll {
  max-height: 520px;
  padding-right: var(--md-spacing-1);
}

.prompt-layout.mobile .prompt-scroll {
  max-height: 210px;
}

.prompt-list {
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-2);
}

.prompt-list-item {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--md-spacing-3);
  padding: var(--md-spacing-3);
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-md);
  background-color: var(--md-surface);
  color: var(--md-on-surface);
  text-align: left;
  cursor: pointer;
  transition:
    background-color var(--md-duration-short) var(--md-easing-standard),
    border-color var(--md-duration-short) var(--md-easing-standard),
    color var(--md-duration-short) var(--md-easing-standard);
}

.prompt-list-item:hover {
  border-color: color-mix(in srgb, var(--md-primary) 32%, var(--md-outline-variant));
  background-color: var(--md-surface-container-low);
}

.prompt-list-item.active {
  border-color: color-mix(in srgb, var(--md-primary) 42%, var(--md-outline-variant));
  background-color: var(--md-primary-container);
  color: var(--md-on-primary-container);
}

.prompt-item-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.prompt-item-title {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  color: inherit;
  font-size: var(--md-body-medium);
  font-weight: 600;
}

.prompt-item-key {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  color: color-mix(in srgb, currentColor 70%, transparent);
  font-size: var(--md-body-small);
}

.prompt-item-meta {
  flex-shrink: 0;
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
}

.prompt-list-item:focus-visible {
  outline: 2px solid var(--md-primary);
  outline-offset: 2px;
}
```

Keep the remaining editor, modal, and mobile styles if they already use no banned hard-coded colors.

- [ ] **Step 2: Tokenize UpdateLogManagement CSS**

Replace `UpdateLogManagement.vue` scoped CSS with:

```css
.admin-card {
  width: 100%;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--md-spacing-4);
  flex-wrap: wrap;
}

.card-title {
  color: var(--md-on-surface);
  font-size: var(--md-title-large);
  font-weight: 600;
}

.form-card {
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-lg);
  background-color: var(--md-surface-container-low);
}

.log-card {
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-lg);
  background-color: var(--md-surface);
}

.log-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: var(--md-spacing-3);
  margin-bottom: var(--md-spacing-3);
}

.log-date {
  color: var(--md-on-surface);
  font-size: var(--md-body-small);
}

.log-author {
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
}

.log-content {
  color: var(--md-on-surface);
  font-size: var(--md-body-medium);
  line-height: 1.7;
  white-space: pre-wrap;
}
```

- [ ] **Step 3: Tokenize SettingsManagement CSS**

In `SettingsManagement.vue`, replace the scoped CSS from `.admin-settings` through the end of the file with:

```css
.admin-settings {
  width: 100%;
}

.overview-card,
.meta-card,
.top-settings-card {
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-lg);
  background-color: var(--md-surface);
}

.overview-card {
  background-color: var(--md-surface-container-low);
}

.overview-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--md-spacing-4);
  flex-wrap: wrap;
}

.overview-copy {
  max-width: 720px;
}

.overview-title {
  margin: 0;
  color: var(--md-on-surface);
  font-size: var(--md-title-large);
  font-weight: 600;
}

.overview-subtitle {
  margin: var(--md-spacing-2) 0 0;
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-medium);
  line-height: 1.6;
}

.meta-grid {
  display: grid;
  gap: var(--md-spacing-4);
  grid-template-columns: 1fr;
}

.meta-card {
  height: 100%;
  min-width: 0;
  overflow: hidden;
}

.health-grid {
  display: grid;
  gap: var(--md-spacing-3);
  min-width: 0;
}

.health-item {
  min-width: 0;
  overflow: hidden;
  padding: var(--md-spacing-3);
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-md);
  background-color: var(--md-surface-container-low);
}

.health-label {
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
}

.health-value {
  min-width: 0;
  margin: var(--md-spacing-1) 0 var(--md-spacing-2);
  color: var(--md-on-surface);
  font-size: var(--md-body-medium);
  font-weight: 600;
}

.health-value-url {
  display: block;
  max-width: 100%;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.top-settings-grid {
  display: grid;
  gap: var(--md-spacing-4);
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.top-settings-card {
  height: 100%;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--md-spacing-4);
  flex-wrap: wrap;
}

.card-title {
  color: var(--md-on-surface);
  font-size: var(--md-title-large);
  font-weight: 600;
}

.card-subtitle {
  margin: var(--md-spacing-1) 0 0;
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
  line-height: 1.5;
}

.version-form {
  max-width: 540px;
}

.form-hint {
  margin: var(--md-spacing-1) 0 var(--md-spacing-3);
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
}

.version-compare-panel {
  margin: var(--md-spacing-1) 0 var(--md-spacing-3);
  padding: var(--md-spacing-3);
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-md);
  background-color: var(--md-surface-container-low);
}

.compare-row {
  display: flex;
  align-items: center;
  gap: var(--md-spacing-2);
  color: var(--md-on-surface);
  font-size: var(--md-body-small);
  line-height: 1.6;
}

.compare-empty,
.compare-meta {
  color: var(--md-on-surface-variant);
}

.compare-meta {
  margin-top: var(--md-spacing-1);
  font-size: var(--md-body-small);
}

.compare-result {
  margin-top: var(--md-spacing-2);
  font-size: var(--md-body-small);
  font-weight: 600;
}

.compare-new {
  color: var(--md-on-warning-container);
}

.compare-same {
  color: var(--md-on-success-container);
}

.compare-error {
  color: var(--md-error-strong);
}

.table-toolbar {
  margin-bottom: var(--md-spacing-4);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--md-spacing-3);
  flex-wrap: wrap;
}

.risk-alert {
  margin-bottom: var(--md-spacing-3);
}

.toolbar-search {
  min-width: 280px;
  flex: 1;
}

.key-code {
  display: inline-block;
  padding: 2px var(--md-spacing-2);
  border-radius: var(--md-radius-sm);
  background-color: var(--md-primary-container);
  color: var(--md-on-primary-container);
  font-size: var(--md-body-small);
  word-break: break-all;
}

.value-text {
  display: block;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: min(52vw, 560px);
}

.config-table :deep(.row-managed td) {
  background-color: color-mix(in srgb, var(--md-primary) 7%, var(--md-surface));
}

.config-modal {
  max-width: min(640px, 92vw);
}

@media (max-width: 767px) {
  .top-settings-grid {
    grid-template-columns: 1fr;
  }

  .card-title,
  .overview-title {
    font-size: var(--md-title-medium);
  }

  .toolbar-search {
    min-width: 100%;
  }

  .table-toolbar {
    align-items: stretch;
    flex-direction: column;
  }
}
```

- [ ] **Step 4: Run full admin child panel static test**

Run:

```bash
pytest backend/tests/test_frontend_deep_restructure_static.py::test_admin_child_panels_use_tokens_and_remove_decorative_gradients -q
```

Expected:

```text
1 passed
```

- [ ] **Step 5: Commit remaining admin panel tokenization**

Run:

```bash
git add frontend/src/components/admin/PromptManagement.vue frontend/src/components/admin/UpdateLogManagement.vue frontend/src/components/admin/SettingsManagement.vue
git commit -m "style: remove decorative admin panel drift"
```

Expected:

```text
[main <hash>] style: remove decorative admin panel drift
```

---

## Task 5: Embed Admin Project Detail in Product Shell

**Files:**

- Modify: `frontend/src/components/shared/NovelDetailShell.vue`
- Test: `backend/tests/test_frontend_deep_restructure_static.py`

- [ ] **Step 1: Replace root wrapper classes**

In `NovelDetailShell.vue`, replace the root wrapper:

```vue
<div class="h-screen flex flex-col overflow-hidden md-surface">
```

with:

```vue
<div class="detail-shell" :class="{ 'detail-shell--embedded': isAdmin }">
```

- [ ] **Step 2: Add admin read-only chip in the top bar**

Inside the title block, after the updated-at paragraph, add:

```vue
<span v-if="isAdmin" class="detail-shell__mode-chip">管理只读</span>
```

- [ ] **Step 3: Replace top app bar layout classes**

Change:

```vue
<header class="md-top-app-bar sticky top-0 z-40">
```

to:

```vue
<header class="md-top-app-bar detail-shell__topbar">
```

Change the inner wrapper:

```vue
<div class="max-w-[1800px] mx-auto w-full flex items-center px-4 h-16">
```

to:

```vue
<div class="detail-shell__topbar-inner">
```

- [ ] **Step 4: Replace main layout classes**

Change:

```vue
<div class="flex max-w-[1800px] mx-auto w-full flex-1 min-h-0 overflow-hidden">
```

to:

```vue
<div class="detail-shell__body">
```

Change the drawer aside class:

```vue
class="fixed left-0 top-16 bottom-0 z-30 w-80 md-surface transform transition-transform duration-300 lg:translate-x-0"
```

to:

```vue
class="detail-shell__drawer md-surface"
```

Keep the existing `:class="isSidebarOpen ? 'translate-x-0' : '-translate-x-full'"` only if mobile drawer transform is still controlled by CSS. If the class conflicts with the new CSS, replace it with:

```vue
:class="{ 'is-open': isSidebarOpen }"
```

Change the main content wrapper:

```vue
<div class="flex-1 lg:ml-80 min-h-0 flex flex-col h-full">
```

to:

```vue
<div class="detail-shell__main">
```

Change the padded content wrapper:

```vue
<div
  class="flex-1 min-h-0 h-full p-4 sm:p-6 lg:p-8 flex flex-col overflow-hidden box-border"
>
```

to:

```vue
<div class="detail-shell__content-wrap">
```

- [ ] **Step 5: Update admin return target**

Replace:

```ts
const goBack = () => router.push(props.isAdmin ? '/admin' : '/workspace')
```

with:

```ts
const goBack = () => {
  if (props.isAdmin) {
    router.push({ name: 'admin', query: { tab: 'novels' } })
    return
  }
  router.push('/workspace')
}
```

- [ ] **Step 6: Replace NovelDetailShell scoped CSS**

At the top of the scoped CSS, add these classes before the transition classes:

```css
.detail-shell {
  width: 100%;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background-color: var(--md-surface);
}

.detail-shell--embedded {
  min-height: calc(100vh - 176px);
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-xl);
  background-color: var(--md-surface);
  box-shadow: var(--md-elevation-1);
}

.detail-shell__topbar {
  position: sticky;
  top: 0;
  z-index: 20;
  flex-shrink: 0;
}

.detail-shell__topbar-inner {
  width: 100%;
  max-width: 1800px;
  height: 64px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  padding: 0 var(--md-spacing-4);
}

.detail-shell__mode-chip {
  display: inline-flex;
  width: fit-content;
  margin-top: var(--md-spacing-1);
  padding: 2px var(--md-spacing-2);
  border-radius: var(--md-radius-full);
  background-color: var(--md-primary-container);
  color: var(--md-on-primary-container);
  font-size: var(--md-label-small);
  font-weight: 600;
}

.detail-shell__body {
  width: 100%;
  max-width: 1800px;
  margin: 0 auto;
  flex: 1;
  min-height: 0;
  display: flex;
  overflow: hidden;
}

.detail-shell__drawer {
  width: 320px;
  flex: 0 0 320px;
  border-right: 1px solid var(--md-outline-variant);
}

.detail-shell__main {
  flex: 1;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.detail-shell__content-wrap {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: var(--md-spacing-6);
  box-sizing: border-box;
}

@media (max-width: 1023px) {
  .detail-shell__drawer {
    position: fixed;
    left: 0;
    top: 64px;
    bottom: 0;
    z-index: 30;
    transform: translateX(-100%);
    transition: transform var(--md-duration-medium) var(--md-easing-emphasized);
  }

  .detail-shell__drawer.is-open {
    transform: translateX(0);
  }

  .detail-shell__content-wrap {
    padding: var(--md-spacing-4);
  }
}

@media (max-width: 640px) {
  .detail-shell--embedded {
    border-radius: var(--md-radius-lg);
  }
}
```

Keep existing transition and scrollbar CSS below this block.

- [ ] **Step 7: Run admin detail static test**

Run:

```bash
pytest backend/tests/test_frontend_deep_restructure_static.py::test_admin_project_detail_uses_embedded_readonly_context -q
```

Expected:

```text
1 passed
```

- [ ] **Step 8: Commit admin detail polish**

Run:

```bash
git add frontend/src/components/shared/NovelDetailShell.vue
git commit -m "style: embed admin project detail"
```

Expected:

```text
[main <hash>] style: embed admin project detail
```

---

## Task 6: Final Verification and Browser Smoke

**Files:**

- Verify only unless a preceding check fails.

- [ ] **Step 1: Run full static frontend restructure tests**

Run:

```bash
pytest backend/tests/test_frontend_deep_restructure_static.py -q
```

Expected:

```text
10 passed
```

If the number differs because the file has additional tests, expected output is all tests in this file passing.

- [ ] **Step 2: Run frontend build**

Run:

```bash
cd frontend && npm run build
```

Expected:

```text
vue-tsc --build
vite build
✓ built
```

- [ ] **Step 3: Start the dev server for browser smoke**

Run:

```bash
./dev.sh
```

Expected output includes:

```text
本机访问前端: http://127.0.0.1:<port>
```

Keep this process running for browser checks. If port `5173` is occupied, use the actual printed port.

- [ ] **Step 4: Browser smoke all admin tabs**

Open these routes in a logged-in admin session:

```text
/admin?tab=statistics
/admin?tab=users
/admin?tab=prompts
/admin?tab=novels
/admin?tab=logs
/admin?tab=settings
/admin?tab=password
```

For each route, verify:

```text
No console error.
No horizontal page scroll at desktop width.
The active nav item is visibly selected.
The URL keeps the expected tab query.
Main action and refresh/search controls are reachable by keyboard focus.
```

- [ ] **Step 5: Browser smoke admin project detail**

From `/admin?tab=novels`, open one project detail.

Verify:

```text
Route is /admin/novels/<id>.
The detail surface appears inside the app shell, not as a second nested full-screen app.
The top area shows 管理只读.
返回列表 returns to /admin?tab=novels.
```

- [ ] **Step 6: Responsive smoke**

Check these viewport widths:

```text
1440px desktop
900px tablet
390px mobile
```

Verify:

```text
Admin nav does not overlap text.
Toolbar rows wrap cleanly.
Prompt list stacks above editor on mobile.
Touch targets remain at least 44px tall.
No page-level horizontal scroll.
```

- [ ] **Step 7: Commit verification-only fixes if any**

If browser or build verification required fixes, commit them:

```bash
git add frontend/src backend/tests
git commit -m "fix: polish admin responsive states"
```

If no fixes were needed, do not create an empty commit.

- [ ] **Step 8: Report final evidence**

Final report should include:

```text
pytest backend/tests/test_frontend_deep_restructure_static.py -q -> passed
cd frontend && npm run build -> passed
Browser smoke routes checked: /admin tabs and /admin/novels/:id
Any remaining risk: authentication/data availability for admin detail if no project exists
```

---

## Self-Review

Spec coverage:

- `/admin` control console: Task 2.
- Seven admin tabs: Tasks 3 and 4.
- `/admin/novels/:id` detail: Task 5.
- Design token alignment and emoji removal: Tasks 1, 3, 4.
- Query sync and admin return behavior: Tasks 2 and 5.
- Static/build/browser verification: Task 6.

Placeholder scan:

- No placeholder tokens, deferred-implementation wording, or open-ended steps.
- Each code-changing task names exact files and includes concrete snippets or selectors.

Type consistency:

- The active admin key remains `MenuKey`.
- `selectSection(section.key)` uses `MenuKey`.
- `renderIcon(section.icon)` uses `AdminSection['icon']`.
- Admin project return uses the existing router route name `admin`.
