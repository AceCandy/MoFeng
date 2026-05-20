# MoFeng Full-Site Responsive Adaptation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在保持桌面端稳定体验的前提下，实现 MoFeng 全站（作者侧 + 管理侧 + 认证页）在 `Desktop>=1200`、`Tablet 834-1199`、`Mobile<834` 三段断点下的完整可用能力，尤其保证移动端关键流程可操作。

**Architecture:** 采用“分层渐进改造”。先建立统一断点常量与响应式状态基建，再改全局壳层（导航重排 + 内容容器），随后按“认证页 -> 作者主流程 -> 管理后台”落地页面。交互逻辑优先用可测试的纯函数/组合式函数承载，样式规则集中到壳层与页面局部样式，不做跨模块大重构。

**Tech Stack:** Vue 3 + TypeScript + Vue Router + Pinia + @tanstack/vue-query + Naive UI + Vite + Vitest + jsdom

---

## Scope Check

当前 spec 是单一子系统（全站响应式适配），不需要再拆多份计划。实施上按阶段切分为可独立回归的任务批次。

## File Structure Map

### 新增文件
- `frontend/vitest.config.ts`
  - 单元测试运行配置（jsdom、别名、setup 文件）。
- `frontend/src/test/setup.ts`
  - 测试环境通用初始化（matchMedia/ResizeObserver 兜底）。
- `frontend/src/constants/responsive.ts`
  - 三段断点常量与视口分层纯函数。
- `frontend/src/constants/__tests__/responsive.spec.ts`
  - 断点常量与视口层级单测。
- `frontend/src/composables/useResponsiveViewport.ts`
  - 统一响应式视口状态组合式函数。
- `frontend/src/composables/__tests__/useResponsiveViewport.spec.ts`
  - 视口状态与 resize 行为单测。
- `frontend/src/components/shared/shellNavigation.ts`
  - 壳层导航模型（桌面侧栏、移动底部 Tab、抽屉项目）纯函数。
- `frontend/src/components/shared/__tests__/shellNavigation.spec.ts`
  - 导航模型单测。

### 重点修改文件
- `frontend/package.json`
  - 增加 `test:unit` 脚本与测试依赖。
- `frontend/src/assets/main.css`
  - 壳层响应式令牌、底部 Tab、834/1200 断点覆盖。
- `frontend/src/components/shared/AppShell.vue`
  - 导航结构重排、移动端底部 Tab + 抽屉、可访问性属性。
- `frontend/src/views/Login.vue`
- `frontend/src/views/Register.vue`
  - 认证页在 `<834` 下输入与按钮可达性补强。
- `frontend/src/views/NovelWorkspace.vue`
- `frontend/src/views/InspirationMode.vue`
- `frontend/src/views/SettingsView.vue`
- `frontend/src/views/WritingDesk.vue`
- `frontend/src/components/shared/NovelDetailShell.vue`
  - 作者主流程断点统一到 1200/834。
- `frontend/src/views/AdminView.vue`
- `frontend/src/components/admin/SettingsManagement.vue`
- `frontend/src/components/admin/UpdateLogManagement.vue`
- `frontend/src/components/admin/PromptManagement.vue`
- `frontend/src/components/admin/UserManagement.vue`
- `frontend/src/components/admin/NovelManagement.vue`
- `frontend/src/components/admin/Statistics.vue`
  - 管理后台移动端完整可用（表格卡片化、操作区可触达、面板可折叠）。

---

### Task 1: 搭建响应式测试基建与断点常量

**Files:**
- Create: `frontend/vitest.config.ts`
- Create: `frontend/src/test/setup.ts`
- Create: `frontend/src/constants/responsive.ts`
- Create: `frontend/src/constants/__tests__/responsive.spec.ts`
- Modify: `frontend/package.json`

- [ ] **Step 1: 先写失败测试（断点值与视口分层）**

```ts
// frontend/src/constants/__tests__/responsive.spec.ts
import { describe, expect, it } from 'vitest'
import {
  RESPONSIVE_BREAKPOINTS,
  getViewportTier,
  isDesktopWidth,
  isMobileWidth,
  isTabletWidth,
} from '@/constants/responsive'

describe('responsive constants', () => {
  it('uses agreed breakpoints', () => {
    expect(RESPONSIVE_BREAKPOINTS.desktopMin).toBe(1200)
    expect(RESPONSIVE_BREAKPOINTS.tabletMin).toBe(834)
    expect(RESPONSIVE_BREAKPOINTS.mobileMax).toBe(833)
  })

  it('resolves viewport tier correctly', () => {
    expect(getViewportTier(375)).toBe('mobile')
    expect(getViewportTier(900)).toBe('tablet')
    expect(getViewportTier(1440)).toBe('desktop')
  })

  it('returns boolean guards', () => {
    expect(isMobileWidth(833)).toBe(true)
    expect(isTabletWidth(900)).toBe(true)
    expect(isDesktopWidth(1200)).toBe(true)
  })
})
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd frontend && timeout 60s npm run test:unit -- responsive.spec.ts`
Expected: FAIL，提示 `Missing script: test:unit` 或 `Cannot find module '@/constants/responsive'`。

- [ ] **Step 3: 实现最小可用测试基建 + 断点常量**

```ts
// frontend/vitest.config.ts
import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import vueJsx from '@vitejs/plugin-vue-jsx'

export default defineConfig({
  plugins: [vue(), vueJsx()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.{spec,test}.ts'],
  },
})
```

```ts
// frontend/src/test/setup.ts
import { afterEach, vi } from 'vitest'

if (!window.matchMedia) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }),
  })
}

afterEach(() => {
  vi.restoreAllMocks()
})
```

```ts
// frontend/src/constants/responsive.ts
export const RESPONSIVE_BREAKPOINTS = {
  desktopMin: 1200,
  tabletMin: 834,
  mobileMax: 833,
} as const

export type ViewportTier = 'mobile' | 'tablet' | 'desktop'

export const getViewportTier = (width: number): ViewportTier => {
  if (width >= RESPONSIVE_BREAKPOINTS.desktopMin) return 'desktop'
  if (width >= RESPONSIVE_BREAKPOINTS.tabletMin) return 'tablet'
  return 'mobile'
}

export const isMobileWidth = (width: number) => getViewportTier(width) === 'mobile'
export const isTabletWidth = (width: number) => getViewportTier(width) === 'tablet'
export const isDesktopWidth = (width: number) => getViewportTier(width) === 'desktop'
```

```json
// frontend/package.json (scripts + devDependencies)
{
  "scripts": {
    "test:unit": "vitest run --reporter=verbose",
    "test:unit:watch": "vitest"
  },
  "devDependencies": {
    "jsdom": "^26.1.0",
    "vitest": "^2.1.9"
  }
}
```

- [ ] **Step 4: 重新运行测试，确认通过**

Run: `cd frontend && timeout 60s npm run test:unit -- responsive.spec.ts`
Expected: PASS，`responsive constants` 3 个用例通过。

- [ ] **Step 5: 提交**

```bash
git add frontend/package.json frontend/vitest.config.ts frontend/src/test/setup.ts frontend/src/constants/responsive.ts frontend/src/constants/__tests__/responsive.spec.ts
git commit -m "test: add responsive breakpoint constants and unit test baseline"
```

---

### Task 2: 实现统一视口状态组合式函数

**Files:**
- Create: `frontend/src/composables/useResponsiveViewport.ts`
- Create: `frontend/src/composables/__tests__/useResponsiveViewport.spec.ts`

- [ ] **Step 1: 先写失败测试（初始化 + resize 更新）**

```ts
// frontend/src/composables/__tests__/useResponsiveViewport.spec.ts
import { describe, expect, it } from 'vitest'
import { nextTick } from 'vue'
import { useResponsiveViewport } from '@/composables/useResponsiveViewport'

describe('useResponsiveViewport', () => {
  it('maps initial width to tablet tier', () => {
    window.innerWidth = 900
    const state = useResponsiveViewport()
    expect(state.tier.value).toBe('tablet')
    expect(state.isTablet.value).toBe(true)
  })

  it('updates tier on resize', async () => {
    window.innerWidth = 1280
    const state = useResponsiveViewport()

    window.innerWidth = 390
    window.dispatchEvent(new Event('resize'))
    await nextTick()

    expect(state.tier.value).toBe('mobile')
    expect(state.isMobile.value).toBe(true)
  })
})
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd frontend && timeout 60s npm run test:unit -- useResponsiveViewport.spec.ts`
Expected: FAIL，提示 `Cannot find module '@/composables/useResponsiveViewport'`。

- [ ] **Step 3: 写最小实现**

```ts
// frontend/src/composables/useResponsiveViewport.ts
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { getViewportTier } from '@/constants/responsive'

const getSafeWidth = () => (typeof window === 'undefined' ? 1440 : window.innerWidth)

export const useResponsiveViewport = () => {
  const width = ref(getSafeWidth())

  const syncWidth = () => {
    width.value = getSafeWidth()
  }

  onMounted(() => {
    syncWidth()
    window.addEventListener('resize', syncWidth)
  })

  onBeforeUnmount(() => {
    window.removeEventListener('resize', syncWidth)
  })

  const tier = computed(() => getViewportTier(width.value))
  const isMobile = computed(() => tier.value === 'mobile')
  const isTablet = computed(() => tier.value === 'tablet')
  const isDesktop = computed(() => tier.value === 'desktop')

  return {
    width,
    tier,
    isMobile,
    isTablet,
    isDesktop,
  }
}
```

- [ ] **Step 4: 重新运行测试，确认通过**

Run: `cd frontend && timeout 60s npm run test:unit -- useResponsiveViewport.spec.ts`
Expected: PASS，2 个用例通过。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/composables/useResponsiveViewport.ts frontend/src/composables/__tests__/useResponsiveViewport.spec.ts
git commit -m "feat: add shared responsive viewport composable"
```

---

### Task 3: 抽离壳层导航模型并用单测锁定行为

**Files:**
- Create: `frontend/src/components/shared/shellNavigation.ts`
- Create: `frontend/src/components/shared/__tests__/shellNavigation.spec.ts`

- [ ] **Step 1: 先写失败测试（作者/管理员 + 移动底部 Tab）**

```ts
// frontend/src/components/shared/__tests__/shellNavigation.spec.ts
import { describe, expect, it } from 'vitest'
import { buildShellNavigation } from '@/components/shared/shellNavigation'

describe('buildShellNavigation', () => {
  it('returns 4 mobile tabs for author', () => {
    const nav = buildShellNavigation(false)
    expect(nav.mobileTabs.map((item) => item.key)).toEqual([
      'workspace',
      'inspiration',
      'projects',
      'settings',
    ])
  })

  it('adds admin drawer entry for admin user', () => {
    const nav = buildShellNavigation(true)
    expect(nav.drawerItems.some((item) => item.key === 'admin')).toBe(true)
  })
})
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd frontend && timeout 60s npm run test:unit -- shellNavigation.spec.ts`
Expected: FAIL，提示缺少 `shellNavigation` 模块。

- [ ] **Step 3: 写最小实现**

```ts
// frontend/src/components/shared/shellNavigation.ts
export interface ShellNavItem {
  key: 'workspace' | 'inspiration' | 'projects' | 'settings' | 'admin'
  label: string
  path: string
  mobileTab: boolean
  adminOnly?: boolean
}

const baseItems: ShellNavItem[] = [
  { key: 'workspace', label: '工作台', path: '/workspace', mobileTab: true },
  { key: 'inspiration', label: '灵感', path: '/inspiration', mobileTab: true },
  { key: 'projects', label: '项目', path: '/workspace', mobileTab: true },
  { key: 'settings', label: '设置', path: '/settings', mobileTab: true },
  { key: 'admin', label: '管理', path: '/admin', mobileTab: false, adminOnly: true },
]

export const buildShellNavigation = (isAdmin: boolean) => {
  const available = baseItems.filter((item) => (item.adminOnly ? isAdmin : true))
  return {
    sidebarItems: available.filter((item) => item.key !== 'projects'),
    mobileTabs: available.filter((item) => item.mobileTab),
    drawerItems: available,
  }
}
```

- [ ] **Step 4: 重新运行测试，确认通过**

Run: `cd frontend && timeout 60s npm run test:unit -- shellNavigation.spec.ts`
Expected: PASS，2 个用例通过。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/shared/shellNavigation.ts frontend/src/components/shared/__tests__/shellNavigation.spec.ts
git commit -m "test: lock shell navigation model for desktop and mobile"
```

---

### Task 4: 改造 AppShell + 全局样式，完成导航重排

**Files:**
- Modify: `frontend/src/components/shared/AppShell.vue`
- Modify: `frontend/src/assets/main.css`
- Modify: `frontend/src/constants/responsive.ts`

- [ ] **Step 1: 写失败测试（壳层导航模型集成）**

```ts
// frontend/src/components/shared/__tests__/shellNavigation.spec.ts (新增断言)
it('keeps inspiration entry in sidebar', () => {
  const nav = buildShellNavigation(false)
  expect(nav.sidebarItems.some((item) => item.key === 'inspiration')).toBe(true)
})
```

- [ ] **Step 2: 运行测试，确认当前逻辑未覆盖壳层消费**

Run: `cd frontend && timeout 60s npm run test:unit -- shellNavigation.spec.ts`
Expected: PASS，随后在 Step 3 完成 `AppShell.vue` 对导航模型的真实消费改造。

- [ ] **Step 3: 实现壳层重排（脚本与模板）**

```ts
// AppShell.vue <script setup> 关键改动
import { buildShellNavigation } from '@/components/shared/shellNavigation'
import { RESPONSIVE_BREAKPOINTS } from '@/constants/responsive'

const navModel = computed(() => buildShellNavigation(Boolean(authStore.user?.is_admin)))

onMounted(() => {
  mobileMediaQuery = window.matchMedia(`(max-width: ${RESPONSIVE_BREAKPOINTS.mobileMax}px)`)
  syncMobileShell()
  mobileMediaQuery.addEventListener('change', syncMobileShell)
})
```

```vue
<!-- AppShell.vue <template> 关键新增：移动底部 Tab -->
<nav v-if="isMobileShell" class="app-shell__bottom-tabs" aria-label="移动主导航">
  <RouterLink
    v-for="item in navModel.mobileTabs"
    :key="item.key"
    :to="item.path"
    class="app-shell__bottom-tab"
    :class="{ 'is-active': item.path === '/workspace' ? route.path.startsWith('/projects/') || route.path === '/workspace' : route.path.startsWith(item.path) }"
  >
    <span>{{ item.label }}</span>
  </RouterLink>
</nav>
```

```css
/* main.css 关键新增：移动底部导航与 1200/834 断点 */
:root {
  --app-breakpoint-desktop: 1200px;
  --app-breakpoint-tablet: 834px;
  --app-mobile-tab-height: 64px;
}

@media (max-width: 1199px) {
  .app-shell__topbar {
    min-height: 72px;
  }
}

@media (max-width: 833px) {
  .app-shell__content {
    padding-bottom: calc(var(--app-mobile-tab-height) + max(var(--md-spacing-3), env(safe-area-inset-bottom)));
  }

  .app-shell__bottom-tabs {
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 55;
    height: var(--app-mobile-tab-height);
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    border-top: 1px solid var(--md-outline-variant);
    background-color: color-mix(in oklch, var(--md-surface) 96%, var(--md-tint-cool));
    padding-bottom: env(safe-area-inset-bottom);
  }
}
```

- [ ] **Step 4: 运行测试与类型检查**

Run: `cd frontend && timeout 60s npm run test:unit -- shellNavigation.spec.ts && timeout 60s npm run type-check`
Expected: PASS，导航模型测试通过，类型检查无错误。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/shared/AppShell.vue frontend/src/assets/main.css frontend/src/constants/responsive.ts
git commit -m "feat: rework app shell navigation for desktop tablet mobile"
```

---

### Task 5: 认证页适配（Login/Register）

**Files:**
- Modify: `frontend/src/views/Login.vue`
- Modify: `frontend/src/views/Register.vue`

- [ ] **Step 1: 先写样式回归测试（静态断言断点存在）**

```ts
// frontend/src/constants/__tests__/responsive.spec.ts 新增一条静态策略断言
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

it('login/register include mobile breakpoint at 833px', () => {
  const loginSfc = readFileSync(resolve(process.cwd(), 'src/views/Login.vue'), 'utf-8')
  const registerSfc = readFileSync(resolve(process.cwd(), 'src/views/Register.vue'), 'utf-8')
  expect(loginSfc.includes('@media (max-width: 833px)')).toBe(true)
  expect(registerSfc.includes('@media (max-width: 833px)')).toBe(true)
})
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd frontend && timeout 60s npm run test:unit -- responsive.spec.ts`
Expected: FAIL，当前是 `520px` 断点。

- [ ] **Step 3: 实现认证页断点升级与输入区可达性**

```css
/* Login.vue / Register.vue 关键改动模式 */
@media (max-width: 833px) {
  .login-page,
  .register-page {
    justify-content: flex-start;
    gap: var(--md-spacing-4);
    padding-top: max(var(--md-spacing-5), env(safe-area-inset-top));
  }

  .login-card,
  .register-card {
    width: 100%;
    max-width: 100%;
    padding: var(--md-spacing-4);
    border-radius: var(--md-radius-lg);
  }
}
```

- [ ] **Step 4: 重新运行测试与构建检查**

Run: `cd frontend && timeout 60s npm run test:unit -- responsive.spec.ts && timeout 60s npm run build`
Expected: PASS，静态断点断言通过，构建通过。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/views/Login.vue frontend/src/views/Register.vue frontend/src/constants/__tests__/responsive.spec.ts
git commit -m "feat: adapt auth pages for mobile-first usability"
```

---

### Task 6: 作者主流程适配（工作台/灵感/详情/写作台/设置）

**Files:**
- Modify: `frontend/src/views/NovelWorkspace.vue`
- Modify: `frontend/src/views/InspirationMode.vue`
- Modify: `frontend/src/views/SettingsView.vue`
- Modify: `frontend/src/views/WritingDesk.vue`
- Modify: `frontend/src/components/shared/NovelDetailShell.vue`

- [ ] **Step 1: 写失败测试（Settings 断点与 WritingDesk 断点统一）**

```ts
// frontend/src/constants/__tests__/responsive.spec.ts 新增断言
it('author pages use 1199/833 breakpoints', () => {
  const files = [
    'src/views/NovelWorkspace.vue',
    'src/views/InspirationMode.vue',
    'src/views/SettingsView.vue',
    'src/views/WritingDesk.vue',
    'src/components/shared/NovelDetailShell.vue',
  ]

  for (const file of files) {
    const content = readFileSync(resolve(process.cwd(), file), 'utf-8')
    expect(content.includes('max-width: 1199px') || content.includes('desktopMin')).toBe(true)
    expect(content.includes('max-width: 833px') || content.includes('mobileMax')).toBe(true)
  }
})
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd frontend && timeout 60s npm run test:unit -- responsive.spec.ts`
Expected: FAIL，部分页面仍使用 `1120/900/768/640/1023`。

- [ ] **Step 3: 按页面实施改造**

```ts
// WritingDesk.vue 关键逻辑：用统一断点常量替换硬编码
import { RESPONSIVE_BREAKPOINTS } from '@/constants/responsive'

const SIDEBAR_DRAWER_BREAKPOINT = RESPONSIVE_BREAKPOINTS.mobileMax
const ASSISTANT_DRAWER_BREAKPOINT = RESPONSIVE_BREAKPOINTS.desktopMin - 1
```

```css
/* SettingsView.vue 关键样式断点升级 */
@media (max-width: 1199px) {
  .settings-center {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 833px) {
  .settings-center__nav {
    grid-template-columns: minmax(0, 1fr);
  }
  .settings-center__panel {
    padding: var(--md-spacing-4);
  }
}
```

```css
/* NovelWorkspace.vue */
@media (max-width: 1199px) {
  .workspace-hero {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 833px) {
  .workspace-canvas {
    grid-template-columns: minmax(0, 1fr);
  }
  .workspace-module--tools {
    grid-column: span 1;
  }
}
```

```css
/* InspirationMode.vue */
@media (max-width: 1199px) {
  .inspiration-chat {
    height: calc(
      var(--app-viewport-unit) - max(var(--md-spacing-6), env(safe-area-inset-top)) -
        max(var(--md-spacing-6), env(safe-area-inset-bottom))
    );
  }
}

@media (max-width: 833px) {
  .inspiration-page {
    padding:
      max(var(--md-spacing-2), env(safe-area-inset-top))
      max(var(--md-spacing-2), env(safe-area-inset-right))
      max(var(--md-spacing-2), env(safe-area-inset-bottom))
      max(var(--md-spacing-2), env(safe-area-inset-left));
  }
}
```

```css
/* NovelDetailShell.vue */
@media (min-width: 1200px) {
  .detail-shell__drawer {
    position: sticky;
    top: 72px;
  }
}

@media (max-width: 833px) {
  .detail-shell__overview-strip {
    grid-template-columns: minmax(0, 1fr);
  }
  .detail-shell__drawer {
    width: min(320px, calc(100vw - 40px));
  }
}
```

- [ ] **Step 4: 运行单测 + 类型检查**

Run: `cd frontend && timeout 60s npm run test:unit -- responsive.spec.ts && timeout 60s npm run type-check`
Expected: PASS，断点断言通过，类型检查通过。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/views/NovelWorkspace.vue frontend/src/views/InspirationMode.vue frontend/src/views/SettingsView.vue frontend/src/views/WritingDesk.vue frontend/src/components/shared/NovelDetailShell.vue frontend/src/constants/__tests__/responsive.spec.ts
git commit -m "feat: align author workflow pages to 1200 834 responsive system"
```

---

### Task 7: 管理后台全量适配（完整可用）

**Files:**
- Modify: `frontend/src/views/AdminView.vue`
- Modify: `frontend/src/components/admin/SettingsManagement.vue`
- Modify: `frontend/src/components/admin/UpdateLogManagement.vue`
- Modify: `frontend/src/components/admin/PromptManagement.vue`
- Modify: `frontend/src/components/admin/UserManagement.vue`
- Modify: `frontend/src/components/admin/NovelManagement.vue`
- Modify: `frontend/src/components/admin/Statistics.vue`

- [ ] **Step 1: 先写失败测试（Admin 断点和移动卡片态）**

```ts
// frontend/src/constants/__tests__/responsive.spec.ts 新增断言
it('admin pages expose mobile-friendly patterns', () => {
  const adminView = readFileSync(resolve(process.cwd(), 'src/views/AdminView.vue'), 'utf-8')
  const settingsMgmt = readFileSync(resolve(process.cwd(), 'src/components/admin/SettingsManagement.vue'), 'utf-8')

  expect(adminView.includes('max-width: 833px')).toBe(true)
  expect(settingsMgmt.includes('isMobile')).toBe(true)
})
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd frontend && timeout 60s npm run test:unit -- responsive.spec.ts`
Expected: FAIL，`AdminView` 仍是 `740/480`，`SettingsManagement` 无统一 mobile 卡片逻辑。

- [ ] **Step 3: 实现管理后台移动端完整可操作**

```ts
// SettingsManagement.vue 关键新增
const isMobile = ref(false)

const updateLayout = () => {
  isMobile.value = window.innerWidth <= RESPONSIVE_BREAKPOINTS.mobileMax
}

onMounted(() => {
  updateLayout()
  window.addEventListener('resize', updateLayout)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', updateLayout)
})
```

```vue
<!-- SettingsManagement.vue 关键模板分支 -->
<div v-if="isMobile" class="settings-mobile-list">
  <article v-for="item in filteredConfigs" :key="item.key" class="settings-mobile-card">
    <header>
      <strong>{{ item.key }}</strong>
      <n-tag :bordered="false" size="small">{{ isManagedConfigKey(item.key) ? '托管项' : '普通项' }}</n-tag>
    </header>
    <p>{{ item.description || '无描述' }}</p>
    <n-space justify="end">
      <n-button size="small" @click="openEditModal(item)">编辑</n-button>
      <n-button size="small" type="error" quaternary @click="deleteConfig(item.key)">删除</n-button>
    </n-space>
  </article>
</div>
<n-data-table
  v-else
  :columns="columns"
  :data="filteredConfigs"
  :loading="configLoading"
  :bordered="false"
  :row-key="rowKey"
  :row-class-name="tableRowClassName"
  class="config-table"
/>
```

```css
/* AdminView.vue 断点统一 */
@media (max-width: 1199px) {
  .admin-ops__metrics,
  .admin-ops__grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 833px) {
  .admin-console__nav {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
```

- [ ] **Step 4: 运行单测 + 类型检查 + 构建**

Run: `cd frontend && timeout 60s npm run test:unit -- responsive.spec.ts && timeout 60s npm run type-check && timeout 60s npm run build`
Expected: PASS，断言通过，类型检查和构建通过。

- [ ] **Step 5: 提交**

```bash
git add frontend/src/views/AdminView.vue frontend/src/components/admin/SettingsManagement.vue frontend/src/components/admin/UpdateLogManagement.vue frontend/src/components/admin/PromptManagement.vue frontend/src/components/admin/UserManagement.vue frontend/src/components/admin/NovelManagement.vue frontend/src/components/admin/Statistics.vue frontend/src/constants/__tests__/responsive.spec.ts
git commit -m "feat: make admin console fully operable on mobile"
```

---

### Task 8: 全站回归验证与交付说明

**Files:**
- Modify: `docs/superpowers/specs/2026-05-20-responsive-fullsite-adapt-design.md`（可选：补充实施状态）
- Create: `docs/superpowers/plans/2026-05-20-responsive-fullsite-adapt-verification.md`

- [ ] **Step 1: 写失败验证记录模板（先定义必须项）**

```md
# Responsive Verification Checklist

- [ ] 375x812: /workspace /inspiration /projects/:id /projects/:id/write /settings /admin /admin/novels/:id /login /register
- [ ] 834x1112: /workspace /inspiration /projects/:id /projects/:id/write /settings /admin /admin/novels/:id /login /register
- [ ] 1280x800: /workspace /inspiration /projects/:id /projects/:id/write /settings /admin /admin/novels/:id /login /register
- [ ] 1440x900: /workspace /inspiration /projects/:id /projects/:id/write /settings /admin /admin/novels/:id /login /register
- [ ] 移动端关键操作可达：登录、项目进入、章节相关操作、设置保存、管理常用操作
```

- [ ] **Step 2: 运行完整命令链**

Run:
1. `cd frontend && timeout 60s npm run test:unit`
2. `cd frontend && timeout 60s npm run type-check`
3. `cd frontend && timeout 60s npm run build`
4. `cd frontend && timeout 60s npm run dev -- --host 0.0.0.0 --port 5173`

Expected:
- 单元测试全绿。
- 类型检查通过。
- 构建成功。
- 本地手工 smoke 通过断点与路由清单。

- [ ] **Step 3: 记录验收证据**

```md
# docs/superpowers/plans/2026-05-20-responsive-fullsite-adapt-verification.md

## Command Evidence
- `npm run test:unit`: pass
- `npm run type-check`: pass
- `npm run build`: pass

## Route and Viewport Evidence
- 375x812: `pass|fail`，附页面列表与截图文件名
- 834x1112: `pass|fail`，附页面列表与截图文件名
- 1280x800: `pass|fail`，附页面列表与截图文件名
- 1440x900: `pass|fail`，附页面列表与截图文件名

## Known Risks
- `none` 或具体阻塞项（文件、路由、重现步骤）
```

- [ ] **Step 4: 最终提交**

```bash
git add docs/superpowers/plans/2026-05-20-responsive-fullsite-adapt-verification.md
git commit -m "docs: add responsive adaptation verification evidence"
```

- [ ] **Step 5: 交付摘要**

输出变更文件清单、验证命令结果、已知风险（若有）。

---

## Spec Coverage Self-Review

1. 全站覆盖：Task 4 + Task 6 + Task 7 覆盖作者侧、管理侧、认证页。
2. 断点标准（1200/834）：Task 1 提供常量，Task 4/6/7 实际替换页面断点。
3. 导航重排（移动底部 Tab + 抽屉）：Task 3 + Task 4。
4. 移动端完整可用：Task 6/7 的操作区、表格卡片化、弹层可达性。
5. 验收标准：Task 8 固化视口、路由、命令与证据记录。

无未覆盖需求。

## Placeholder Scan

已检查计划中无 `TODO/TBD/implement later` 占位语句。

## Type/Name Consistency

统一命名：`RESPONSIVE_BREAKPOINTS`、`useResponsiveViewport`、`buildShellNavigation` 在任务中保持一致。
