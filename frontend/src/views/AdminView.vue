<!-- AIMETA P=管理后台_管理员控制台|R=管理面板_子组件切换|NR=不含普通用户功能|E=route:/admin#component:AdminView|X=ui|A=管理面板|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div class="app-page admin-console">
    <nav class="admin-console__nav" aria-label="管理模块切换">
      <button
        v-for="section in adminSections"
        :key="section.key"
        type="button"
        class="admin-console__nav-item"
        :class="{ 'is-active': section.key === activeSection.key }"
        :aria-current="section.key === activeSection.key ? 'page' : undefined"
        :title="section.description"
        @click="selectSection(section.key)"
      >
        <span class="admin-console__nav-icon" aria-hidden="true">
          <component :is="() => renderIcon(section.icon)" />
        </span>
        <span class="admin-console__nav-label">{{ section.label }}</span>
      </button>
    </nav>

    <section class="admin-console__content">
      <component :is="activeComponent" />
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, h, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

type MenuKey = 'statistics' | 'users' | 'prompts' | 'novels' | 'logs' | 'settings' | 'password'

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

const paths: Record<AdminSection['icon'], ReturnType<typeof h>[]> = {
  chart: [
    h('path', { d: 'M4 19h16' }),
    h('path', { d: 'M7 16V9' }),
    h('path', { d: 'M12 16V6' }),
    h('path', { d: 'M17 16v-5' }),
  ],
  user: [
    h('circle', { cx: '12', cy: '8', r: '3.2' }),
    h('path', { d: 'M5.5 19c1.7-3 4-4.5 6.5-4.5s4.8 1.5 6.5 4.5' }),
  ],
  prompt: [
    h('path', { d: 'M6.5 5.5h11v9h-6l-4 4v-4h-1z' }),
    h('path', { d: 'M9 8h6' }),
    h('path', { d: 'M9 11h4' }),
  ],
  book: [
    h('path', { d: 'M6 4.5h9.5A2.5 2.5 0 0 1 18 7v12H8.5A2.5 2.5 0 0 0 6 21.5z' }),
    h('path', { d: 'M8 7h7' }),
    h('path', { d: 'M8 10h7' }),
  ],
  log: [
    h('path', { d: 'M7 6h10' }),
    h('path', { d: 'M7 11h10' }),
    h('path', { d: 'M7 16h6' }),
    h('path', { d: 'M18 16h.01' }),
  ],
  settings: [
    h('circle', { cx: '12', cy: '12', r: '2.5' }),
    h('path', {
      d: 'M19 12a7.2 7.2 0 0 0-.05-.9l2-1.5-2-3.5-2.4.8a7.1 7.1 0 0 0-1.6-.9L14.5 4h-5l-.4 2a7.1 7.1 0 0 0-1.6.9l-2.4-.8-2 3.5 2 1.5A7.2 7.2 0 0 0 5 12c0 .3 0 .6.05.9l-2 1.5 2 3.5 2.4-.8c.5.4 1 .7 1.6.9l.4 2h5l.4-2c.6-.2 1.1-.5 1.6-.9l2.4.8 2-3.5-2-1.5c.03-.3.05-.6.05-.9z',
    }),
  ],
  lock: [
    h('rect', { x: '6.5', y: '11', width: '11', height: '8', rx: '2' }),
    h('path', { d: 'M9 11V8.8A3 3 0 0 1 12 6a3 3 0 0 1 3 2.8V11' }),
    h('circle', { cx: '12', cy: '15', r: '1.2' }),
  ],
}

const common = {
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  'stroke-width': 1.8,
  'stroke-linecap': 'round',
  'stroke-linejoin': 'round',
  width: '1em',
  height: '1em',
  'aria-hidden': 'true',
}

const renderIcon = (icon: AdminSection['icon']) => h('svg', common, paths[icon])

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

watch(
  () => route.query.tab,
  (tab) => {
    activeKey.value = resolveMenuKey(tab)
  },
  { immediate: true },
)

const activeSection = computed(() => {
  return adminSections.find((section) => section.key === activeKey.value) ?? adminSections[0]
})

const activeComponent = computed(() => components[activeSection.value.key])

const selectSection = (key: MenuKey) => {
  activeKey.value = key
  router.replace({ name: 'admin', query: { tab: key } })
}
</script>

<style scoped>
.admin-console {
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-6);
  min-height: calc(100vh - 112px);
  background-color: var(--md-surface-dim);
  color: var(--md-on-surface);
}

.admin-console__nav {
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-xl);
  background-color: var(--md-surface);
}

.admin-console__nav {
  display: grid;
  grid-template-columns: repeat(7, minmax(104px, 1fr));
  gap: var(--md-spacing-1);
  padding: var(--md-spacing-1);
  border-radius: var(--md-radius-full);
  background-color: var(--md-surface-container-low);
  overflow-x: auto;
}

.admin-console__nav-item {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--md-spacing-2);
  width: 100%;
  min-height: 40px;
  padding: 0 var(--md-spacing-3);
  border: none;
  border-radius: var(--md-radius-full);
  background-color: transparent;
  color: var(--md-on-surface);
  font-size: var(--md-label-large);
  font-weight: 600;
  line-height: 1;
  cursor: pointer;
  white-space: nowrap;
  transition:
    background-color var(--md-duration-short) var(--md-easing-standard),
    color var(--md-duration-short) var(--md-easing-standard);
}

.admin-console__nav-item:hover {
  background-color: var(--md-surface-container);
}

.admin-console__nav-item:focus-visible {
  outline: 2px solid var(--md-primary);
  outline-offset: 2px;
}

.admin-console__nav-item.is-active,
.admin-console__nav-item[aria-current='page'] {
  background-color: var(--md-primary-container);
  color: var(--md-on-primary-container);
}

.admin-console__nav-icon {
  display: inline-grid;
  place-items: center;
  width: 1.125rem;
  height: 1.125rem;
  flex: 0 0 auto;
}

.admin-console__nav-icon :deep(svg) {
  width: 1rem;
  height: 1rem;
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

@media (max-width: 520px) {
  .admin-console {
    gap: var(--md-spacing-4);
  }

  .admin-console__nav {
    border-radius: var(--md-radius-lg);
  }

  .admin-console__nav-item {
    min-height: 44px;
    padding: 0 var(--md-spacing-3);
  }
}
</style>
