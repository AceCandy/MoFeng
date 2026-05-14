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
        <span class="admin-console__nav-label">{{ section.label }}</span>
      </button>
    </nav>

    <section class="admin-console__content">
      <component :is="activeComponent" />
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

type MenuKey = 'statistics' | 'users' | 'prompts' | 'novels' | 'logs' | 'settings' | 'password'

interface AdminSection {
  key: MenuKey
  label: string
  description: string
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
  { key: 'statistics', label: '数据总览', description: '平台规模与请求概况' },
  { key: 'users', label: '用户管理', description: '账号、权限和状态' },
  { key: 'prompts', label: '提示词管理', description: '系统 Prompt 模板' },
  { key: 'novels', label: '小说项目', description: '项目进度与内容巡检' },
  { key: 'logs', label: '更新日志', description: '公告发布与置顶' },
  { key: 'settings', label: '系统配置', description: '托管配置与键值项' },
  { key: 'password', label: '安全中心', description: '管理员密码更新' },
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
