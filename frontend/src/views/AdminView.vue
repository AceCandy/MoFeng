<!-- AIMETA P=管理后台_管理员控制台|R=管理面板_子组件切换|NR=不含普通用户功能|E=route:/admin#component:AdminView|X=ui|A=管理面板|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div class="app-page admin-console" :class="{ 'is-in-modal': props.isModal }">
    <section class="admin-console__tabs">
      <nav class="admin-console__nav" aria-label="管理模块切换" role="tablist">
        <button
          v-for="section in adminSections"
          :key="section.key"
          :ref="(el) => setAdminTabRef(section.key, el)"
          type="button"
          class="admin-console__nav-item"
          :class="{
            'is-active': section.key === activeSection.key,
            'nav-item-statistics': section.key === 'statistics',
            'nav-item-users': section.key === 'users',
            'nav-item-prompts': section.key === 'prompts',
            'nav-item-novels': section.key === 'novels',
            'nav-item-logs': section.key === 'logs',
            'nav-item-settings': section.key === 'settings'
          }"
          :id="`admin-tab-${section.key}`"
          role="tab"
          :aria-selected="section.key === activeSection.key"
          :tabindex="section.key === activeSection.key ? 0 : -1"
          :aria-current="section.key === activeSection.key ? 'page' : undefined"
          aria-controls="admin-panel"
          :title="section.description"
          @click="selectSection(section.key)"
          @keydown="onAdminTabKeydown(section.key, $event)"
        >
          <span class="admin-console__nav-label">{{ section.label }}</span>
        </button>
      </nav>

      <section
        id="admin-panel"
        class="admin-console__content"
        role="tabpanel"
        :aria-labelledby="activeAdminTabId"
      >
        <n-message-provider>
          <keep-alive>
            <component :is="activeComponent" />
          </keep-alive>
        </n-message-provider>
      </section>
    </section>
  </div>
</template>

<script setup lang="ts">
import {
  computed,
  defineAsyncComponent,
  ref,
  watch,
  type Component,
  type ComponentPublicInstance,
} from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NMessageProvider } from 'naive-ui/es/message'

const props = withDefaults(
  defineProps<{
    isModal?: boolean
    initialTab?: string
  }>(),
  {
    isModal: false,
    initialTab: 'statistics',
  }
)

type MenuKey = 'statistics' | 'users' | 'prompts' | 'novels' | 'logs' | 'settings'

interface AdminSection {
  key: MenuKey
  label: string
  description: string
}

type AsyncViewModule = { default: Component }

const createAsyncSection = (loader: () => Promise<AsyncViewModule>) => {
  return defineAsyncComponent({
    loader,
    delay: 120,
    timeout: 15_000,
    // 异步模块偶发加载失败时允许短重试，避免切换 tab 后出现白屏空面板。
    onError: (error, retry, fail, attempts) => {
      const message = error instanceof Error ? error.message : String(error)
      const isLoadIssue = /(fetch|import|chunk)/i.test(message)
      if (isLoadIssue && attempts <= 2) {
        retry()
        return
      }
      fail()
    },
  })
}

const components: Record<MenuKey, ReturnType<typeof defineAsyncComponent>> = {
  statistics: createAsyncSection(() => import('../components/admin/Statistics.vue')),
  users: createAsyncSection(() => import('../components/admin/UserManagement.vue')),
  prompts: createAsyncSection(() => import('../components/admin/PromptManagement.vue')),
  novels: createAsyncSection(() => import('../components/admin/NovelManagement.vue')),
  logs: createAsyncSection(() => import('../components/admin/UpdateLogManagement.vue')),
  settings: createAsyncSection(() => import('../components/admin/SettingsManagement.vue')),
}

const adminSections: AdminSection[] = [
  { key: 'statistics', label: '数据总览', description: '平台规模与请求概况' },
  { key: 'users', label: '用户管理', description: '账号、权限和状态' },
  { key: 'prompts', label: '提示词管理', description: '系统 Prompt 模板' },
  { key: 'novels', label: '小说项目', description: '项目进度与内容巡检' },
  { key: 'logs', label: '更新日志', description: '公告发布与置顶' },
  { key: 'settings', label: '系统配置', description: '托管配置与键值项' },
]

const router = useRouter()
const route = useRoute()

const isMenuKey = (key: string): key is MenuKey => key in components

const resolveMenuKey = (value: unknown): MenuKey => {
  if (typeof value === 'string' && isMenuKey(value)) {
    return value
  }

  return 'statistics'
}

const activeKey = ref<MenuKey>('statistics')
const adminTabRefs = ref<Record<MenuKey, HTMLButtonElement | null>>({
  statistics: null,
  users: null,
  prompts: null,
  novels: null,
  logs: null,
  settings: null,
})

watch(
  [() => route.query.tab, () => props.initialTab],
  ([tab, initialTab]) => {
    activeKey.value = props.isModal ? resolveMenuKey(initialTab) : resolveMenuKey(tab)
  },
  { immediate: true },
)

const activeSection = computed(() => {
  return adminSections.find((section) => section.key === activeKey.value) ?? adminSections[0]
})

const activeAdminTabId = computed(() => `admin-tab-${activeSection.value.key}`)

const activeComponent = computed(() => components[activeSection.value.key])

const selectSection = (key: MenuKey) => {
  activeKey.value = key
  if (!props.isModal) {
    router.replace({ name: 'admin', query: { tab: key } })
  }
}

const setAdminTabRef = (
  key: MenuKey,
  element: Element | ComponentPublicInstance | null,
) => {
  const target =
    element instanceof HTMLButtonElement
      ? element
      : element && '$el' in element && element.$el instanceof HTMLButtonElement
        ? element.$el
        : null
  adminTabRefs.value[key] = target
}

const focusAdminTab = (key: MenuKey) => {
  adminTabRefs.value[key]?.focus()
}

// 管理台 tabs 支持方向键快速切换，符合 ARIA Tabs 键盘交互习惯。
const onAdminTabKeydown = (key: MenuKey, event: KeyboardEvent) => {
  const currentIndex = adminSections.findIndex((section) => section.key === key)
  if (currentIndex === -1) return
  const lastIndex = adminSections.length - 1

  let nextIndex: number | null = null
  if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
    nextIndex = currentIndex === lastIndex ? 0 : currentIndex + 1
  } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
    nextIndex = currentIndex === 0 ? lastIndex : currentIndex - 1
  } else if (event.key === 'Home') {
    nextIndex = 0
  } else if (event.key === 'End') {
    nextIndex = lastIndex
  }

  if (nextIndex === null || nextIndex === currentIndex) return
  event.preventDefault()
  const nextKey = adminSections[nextIndex].key
  selectSection(nextKey)
  focusAdminTab(nextKey)
}
</script>

<style scoped>
.admin-console {
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-6);
  min-height: calc(var(--app-viewport-unit) - 112px);
  /* 采用平铺温暖熟宣纸大背景，完美融入墨风系统 */
  background-color: var(--md-background) !important;
  color: var(--md-on-surface);
  font-family: var(--md-font-family);
}

/* 弹窗模式下将导航栏固定在顶部，只让下方内容独立滚动 */
.admin-console.is-in-modal {
  height: 100%;
  min-height: 0;
  gap: var(--md-spacing-4);
}

.admin-console.is-in-modal .admin-console__tabs {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.admin-console.is-in-modal .admin-console__content {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
  padding-right: 4px;
}

.admin-console__tabs {
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-4);
}

.admin-console__nav {
  /* 古典古籍线装双线栏 */
  border: 3px double var(--md-outline) !important;
  border-radius: var(--md-radius-sm) !important; /* 微直角 4px */
  background-color: var(--md-surface) !important; /* 熟宣白 */
  box-shadow: 3px 3px 0px rgba(28, 32, 34, 0.12) !important;
  display: flex; /* 改为 flex 页签左右铺开，更具折页感 */
  flex-wrap: nowrap;
  gap: 0;
  padding: 4px !important;
  overflow-x: auto;
}

.admin-console__nav-item {
  flex: 1;
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  min-height: 52px;
  padding: 0 var(--md-spacing-4) !important;
  border: 1px solid transparent;
  border-radius: var(--md-radius-xs) !important; /* 2px */
  background-color: transparent;
  color: var(--md-on-surface);
  font-family: var(--md-font-serif) !important;
  font-size: var(--md-title-small) !important;
  font-weight: 600;
  line-height: 1;
  cursor: pointer;
  white-space: nowrap;
  position: relative;
  transition:
    background-color 0.3s cubic-bezier(0.22, 1, 0.36, 1),
    border-color 0.3s cubic-bezier(0.22, 1, 0.36, 1),
    color 0.3s cubic-bezier(0.22, 1, 0.36, 1) !important;
}

.admin-console__nav-item:hover {
  border-color: var(--md-outline-variant) !important;
  background-color: rgba(184, 60, 50, 0.04) !important;
  color: var(--md-secondary) !important;
}

.admin-console__nav-item:focus-visible {
  outline: 2px solid var(--md-primary);
  outline-offset: 2px;
}

.admin-console__nav-item.is-active,
.admin-console__nav-item[aria-selected='true'] {
  border: 1px dashed rgba(184, 60, 50, 0.15) !important;
  border-left: 1.5px solid var(--md-secondary) !important; /* 纤细朱砂竖描起笔，干掉AI粗条 */
  background-color: rgba(184, 60, 50, 0.08) !important; /* 晕染熟宣红 */
  color: var(--md-secondary) !important;
}

/* “盤、籍、令、卷、誌、樞、鑰” 终极金石印章 ::after - 初始悬空隐形，防止布局抖动 */
.admin-console__nav-item::after {
  content: '';
  font-family: var(--md-font-serif) !important;
  font-weight: 900;
  font-size: 13px;
  color: transparent !important;
  background-color: transparent !important;
  border: 1px solid transparent !important;
  border-radius: var(--md-radius-xs) !important;
  width: 22px;
  height: 22px;
  display: grid;
  place-items: center;
  user-select: none;
  flex-shrink: 0;
  margin-left: 8px;
  opacity: 0;
  transform: scale(1.15) translateY(-3px); /* 悬空 */
  transition:
    background-color 0.35s cubic-bezier(0.22, 1, 0.36, 1),
    border-color 0.35s cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 0.35s cubic-bezier(0.22, 1, 0.36, 1),
    color 0.35s cubic-bezier(0.22, 1, 0.36, 1),
    opacity 0.35s cubic-bezier(0.22, 1, 0.36, 1),
    transform 0.35s cubic-bezier(0.22, 1, 0.36, 1) !important;
}

/* 激活时，红泥落地，徐徐印下 */
.admin-console__nav-item.is-active::after,
.admin-console__nav-item[aria-selected='true']::after {
  color: var(--md-secondary) !important;
  background-color: rgba(184, 60, 50, 0.12) !important;
  border: 1px solid var(--md-secondary) !important;
  box-shadow: 1px 1px 0px rgba(184, 60, 50, 0.15) !important;
  opacity: 1;
  transform: scale(1) translateY(0); /* 盖章 */
  animation: ink-seal-press 0.4s cubic-bezier(0.19, 1, 0.22, 1) both;
}

/* 为 7 个 Tab 标签特异性定制汉字印章 */
.admin-console__nav-item.nav-item-statistics::after {
  content: '盤' !important;
}
.admin-console__nav-item.nav-item-users::after {
  content: '籍' !important;
}
.admin-console__nav-item.nav-item-prompts::after {
  content: '令' !important;
}
.admin-console__nav-item.nav-item-novels::after {
  content: '卷' !important;
}
.admin-console__nav-item.nav-item-logs::after {
  content: '誌' !important;
}
.admin-console__nav-item.nav-item-settings::after {
  content: '樞' !important;
}

/* 盖章动效：微重压垂直印痕起伏效果 */
@keyframes ink-seal-press {
  0% {
    opacity: 0;
    transform: scale(1.3) translateY(-4px);
  }
  65% {
    opacity: 0.95;
    transform: scale(0.92) translateY(1.5px); /* 下压 */
  }
  100% {
    opacity: 1;
    transform: scale(1) translateY(0); /* 轻微回弹起笔 */
  }
}

.admin-console__nav-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--md-label-large);
  font-weight: 600;
}

.admin-console__content {
  min-width: 0;
}

@media (max-width: 1199px) {
}

@media (max-width: 833px) {
  .admin-console {
    gap: var(--md-spacing-4);
  }

  .admin-console__nav {
    display: grid !important; /* 窄屏改回网格 */
    grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
    overflow-x: visible;
    border-radius: var(--md-radius-sm) !important;
    padding: var(--md-spacing-2) !important;
  }

  .admin-console__nav-item {
    min-height: 44px;
    padding: 8px var(--md-spacing-3) !important;
    white-space: normal;
    line-height: 1.25;
  }

  .admin-console__nav-item::after {
    display: none !important; /* 窄屏空间狭窄，隐藏印记 */
  }

  .admin-console__nav-label {
    white-space: normal;
    text-overflow: clip;
  }
}

@media (max-width: 480px) {
  .admin-console__nav {
    grid-template-columns: minmax(0, 1fr) !important;
  }
}
</style>
