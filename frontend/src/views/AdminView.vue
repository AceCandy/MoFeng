<!-- AIMETA P=管理后台_管理员控制台|R=管理面板_子组件切换|NR=不含普通用户功能|E=route:/admin#component:AdminView|X=ui|A=管理面板|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div class="app-page admin-console">
    <section class="admin-ops" aria-label="系统运营控制台">
      <div class="admin-ops__hero">
        <div>
          <p class="admin-eyebrow">系统运营控制台</p>
          <h2>平台运行概览</h2>
          <p>
            统一查看平台规模、项目活跃度与日志流，快速定位当前需要处理的运营动作。
          </p>
        </div>
      </div>

      <div class="admin-ops__metrics">
        <article class="admin-ops__metric">
          <p>AI 调用总量</p>
          <strong>{{ stats?.api_request_count ?? 0 }}</strong>
          <span>累计请求次数</span>
        </article>
        <article class="admin-ops__metric">
          <p>活跃项目</p>
          <strong>{{ activeProjects.length }}</strong>
          <span>最近 7 天有编辑</span>
        </article>
        <article class="admin-ops__metric">
          <p>平台用户</p>
          <strong>{{ stats?.user_count ?? 0 }}</strong>
          <span>当前注册用户数</span>
        </article>
        <article class="admin-ops__metric">
          <p>项目总量</p>
          <strong>{{ stats?.novel_count ?? 0 }}</strong>
          <span>累计小说项目</span>
        </article>
      </div>

      <div class="admin-ops__grid">
        <article class="admin-panel-card">
          <header>
            <h3>最近日志</h3>
            <p>最近发布与置顶变更</p>
          </header>
          <ul v-if="recentLogs.length > 0" class="admin-log-list">
            <li v-for="log in recentLogs" :key="log.id">
              <p>{{ log.content }}</p>
              <span>{{ formatDate(log.created_at) }}</span>
            </li>
          </ul>
          <p v-else class="admin-empty-hint">暂无日志记录</p>
        </article>

        <article class="admin-panel-card">
          <header>
            <h3>活跃项目</h3>
            <p>最近更新频率最高的小说</p>
          </header>
          <ul v-if="activeProjectList.length > 0" class="admin-project-list">
            <li v-for="project in activeProjectList" :key="project.id">
              <div>
                <strong>{{ project.title }}</strong>
                <span>{{ project.owner_username }} · {{ project.genre || '未分类' }}</span>
              </div>
              <em>{{ formatDate(project.last_edited) }}</em>
            </li>
          </ul>
          <p v-else class="admin-empty-hint">暂无活跃项目</p>
        </article>

        <article class="admin-panel-card admin-panel-card--trend">
          <header>
            <h3>调用热度趋势</h3>
            <p>近 7 日项目编辑热度（可作为调用压力参考）</p>
          </header>
          <div class="admin-trend" role="img" aria-label="近7日调用热度趋势图">
            <div
              v-for="point in activityTrend"
              :key="point.day"
              class="admin-trend__bar"
              :style="{ height: `${point.height}%` }"
              :title="`${point.label}：${point.count} 次活跃`"
            >
              <span>{{ point.count }}</span>
            </div>
          </div>
          <div class="admin-trend__labels">
            <span v-for="point in activityTrend" :key="`${point.day}-label`">{{ point.day }}</span>
          </div>
        </article>
      </div>
    </section>

    <section class="admin-console__tabs">
      <nav class="admin-console__nav" aria-label="管理模块切换" role="tablist">
        <button
          v-for="section in adminSections"
          :key="section.key"
          :ref="(el) => setAdminTabRef(section.key, el)"
          type="button"
          class="admin-console__nav-item"
          :class="{ 'is-active': section.key === activeSection.key }"
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
import {
  useAdminNovelsQuery,
  useAdminStatisticsQuery,
  useAdminUpdateLogsQuery,
} from '@/queries/admin'

const props = withDefaults(
  defineProps<{
    isModal?: boolean
  }>(),
  {
    isModal: false,
  }
)

type MenuKey = 'statistics' | 'users' | 'prompts' | 'novels' | 'logs' | 'settings' | 'password'

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
  password: createAsyncSection(() => import('../components/admin/PasswordManagement.vue')),
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

const statisticsQuery = useAdminStatisticsQuery()
const novelQuery = useAdminNovelsQuery()
const updateLogsQuery = useAdminUpdateLogsQuery()

const stats = computed(() => statisticsQuery.data.value ?? null)

const recentLogs = computed(() => {
  const logs = updateLogsQuery.data.value ?? []
  return [...logs]
    .sort((left, right) => {
      return new Date(right.created_at).getTime() - new Date(left.created_at).getTime()
    })
    .slice(0, 5)
})

const activeProjectList = computed(() => {
  const novels = novelQuery.data.value ?? []
  return [...novels]
    .sort((left, right) => {
      return new Date(right.last_edited).getTime() - new Date(left.last_edited).getTime()
    })
    .slice(0, 6)
})

const activeProjects = computed(() => {
  const novels = novelQuery.data.value ?? []
  const now = Date.now()
  const sevenDaysMs = 7 * 24 * 60 * 60 * 1000
  return novels.filter((novel) => now - new Date(novel.last_edited).getTime() <= sevenDaysMs)
})

const activityTrend = computed(() => {
  const novels = novelQuery.data.value ?? []
  const map = new Map<string, number>()
  const keys: Array<{ dateKey: string; day: string }> = []

  for (let offset = 6; offset >= 0; offset -= 1) {
    const date = new Date()
    date.setHours(0, 0, 0, 0)
    date.setDate(date.getDate() - offset)
    const dateKey = date.toISOString().slice(0, 10)
    const day = `${date.getMonth() + 1}/${date.getDate()}`
    keys.push({ dateKey, day })
    map.set(dateKey, 0)
  }

  novels.forEach((novel) => {
    const edited = new Date(novel.last_edited)
    edited.setHours(0, 0, 0, 0)
    const key = edited.toISOString().slice(0, 10)
    if (map.has(key)) {
      map.set(key, (map.get(key) || 0) + 1)
    }
  })

  const maxValue = Math.max(...Array.from(map.values()), 1)

  return keys.map(({ dateKey, day }) => {
    const count = map.get(dateKey) || 0
    const height = Math.max(18, Math.round((count / maxValue) * 100))
    return {
      day,
      label: dateKey,
      count,
      height,
    }
  })
})

const formatDate = (value: string) => {
  if (!value) return '--'
  return new Date(value).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

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
  password: null,
})

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
  background-color: var(--md-surface-dim);
  color: var(--md-on-surface);
}

.admin-ops {
  padding: clamp(var(--md-spacing-5), 4vw, var(--md-spacing-8));
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-xl);
  background:
    linear-gradient(
      140deg,
      color-mix(in srgb, var(--md-surface) 94%, transparent),
      color-mix(in srgb, var(--md-secondary-container) 34%, var(--md-surface-container-low))
    );
  box-shadow: var(--md-elevation-1);
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-5);
}

.admin-eyebrow {
  margin: 0;
  color: var(--md-primary-dark);
  font-size: var(--md-label-medium);
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.admin-ops h2 {
  margin: 10px 0 0;
  font-size: clamp(1.4rem, 2vw, 1.95rem);
  color: var(--md-on-surface);
}

.admin-ops p {
  margin: var(--md-spacing-3) 0 0;
  color: var(--md-on-surface-variant);
  line-height: 1.7;
  max-width: 72ch;
}

.admin-ops__metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--md-spacing-4);
}

.admin-ops__metric {
  padding: var(--md-spacing-4);
  border-radius: var(--md-radius-lg);
  border: 1px solid var(--md-outline-variant);
  background-color: color-mix(in srgb, var(--md-surface) 95%, transparent);
}

.admin-ops__metric p,
.admin-ops__metric span {
  margin: 0;
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
}

.admin-ops__metric strong {
  margin: var(--md-spacing-2) 0 5px;
  display: block;
  color: var(--md-on-surface);
  font-size: var(--md-title-large);
}

.admin-ops__grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--md-spacing-4);
}

.admin-panel-card {
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-lg);
  background-color: color-mix(in srgb, var(--md-surface) 95%, transparent);
  padding: var(--md-spacing-4);
}

.admin-panel-card h3 {
  margin: 0;
  color: var(--md-on-surface);
  font-size: var(--md-title-large);
}

.admin-panel-card header p {
  margin: 8px 0 0;
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
}

.admin-log-list,
.admin-project-list {
  margin: var(--md-spacing-4) 0 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-2);
}

.admin-log-list li,
.admin-project-list li {
  padding: var(--md-spacing-3);
  border-radius: var(--md-radius-md);
  border: 1px solid var(--md-outline-variant);
  background-color: var(--md-surface-container-low);
}

.admin-log-list p {
  margin: 0;
  color: var(--md-on-surface);
  font-size: var(--md-body-small);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.admin-log-list span,
.admin-project-list em,
.admin-project-list span {
  margin-top: 6px;
  display: block;
  color: var(--md-on-surface-variant);
  font-size: var(--md-label-small);
  font-style: normal;
}

.admin-project-list strong {
  color: var(--md-on-surface);
  font-size: var(--md-label-large);
}

.admin-empty-hint {
  margin: var(--md-spacing-5) 0 0;
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
}

.admin-panel-card--trend {
  display: flex;
  flex-direction: column;
}

.admin-trend {
  margin-top: var(--md-spacing-4);
  padding: var(--md-spacing-3);
  height: 176px;
  border-radius: var(--md-radius-md);
  border: 1px solid var(--md-outline-variant);
  background-color: var(--md-surface-container-low);
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  align-items: end;
  gap: var(--md-spacing-2);
}

.admin-trend__bar {
  position: relative;
  border-radius: 8px 8px 4px 4px;
  background: linear-gradient(
    180deg,
    color-mix(in srgb, var(--md-primary-light) 85%, transparent),
    color-mix(in srgb, var(--md-primary) 82%, transparent)
  );
  min-height: 22px;
}

.admin-trend__bar span {
  position: absolute;
  top: -18px;
  left: 50%;
  transform: translateX(-50%);
  font-size: 11px;
  color: var(--md-on-surface-variant);
}

.admin-trend__labels {
  margin-top: var(--md-spacing-2);
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: var(--md-spacing-2);
}

.admin-trend__labels span {
  text-align: center;
  color: var(--md-on-surface-variant);
  font-size: 11px;
}

.admin-console__tabs {
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-4);
}

.admin-console__nav {
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-xl);
  background-color: color-mix(in srgb, var(--md-surface) 96%, transparent);
  box-shadow: var(--md-elevation-1);
}

.admin-console__nav {
  display: grid;
  grid-template-columns: repeat(7, minmax(104px, 1fr));
  gap: var(--md-spacing-1);
  padding: var(--md-spacing-1);
  border-radius: var(--md-radius-full);
  background-color: color-mix(in srgb, var(--md-surface-container-low) 94%, transparent);
  overflow-x: auto;
}

.admin-console__nav-item {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  min-height: 44px;
  padding: 0 var(--md-spacing-3);
  border: 1px solid transparent;
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
    border-color var(--md-duration-short) var(--md-easing-standard),
    color var(--md-duration-short) var(--md-easing-standard);
}

.admin-console__nav-item:hover {
  border-color: var(--md-outline-variant);
  background-color: var(--md-surface-container);
}

.admin-console__nav-item:focus-visible {
  outline: 2px solid var(--md-primary);
  outline-offset: 2px;
}

.admin-console__nav-item.is-active,
.admin-console__nav-item[aria-selected='true'] {
  border-color: color-mix(in srgb, var(--md-primary) 28%, var(--md-outline-variant));
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

@media (max-width: 1199px) {
  .admin-ops__metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .admin-ops__grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .admin-panel-card--trend {
    grid-column: span 2;
  }
}

@media (max-width: 833px) {
  .admin-console {
    gap: var(--md-spacing-4);
  }

  .admin-ops {
    padding: var(--md-spacing-4);
    border-radius: var(--md-radius-lg);
  }

  .admin-ops__metrics,
  .admin-ops__grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .admin-panel-card--trend {
    grid-column: span 1;
  }

  .admin-console__nav {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    overflow-x: visible;
    border-radius: var(--md-radius-lg);
    padding: var(--md-spacing-2);
  }

  .admin-console__nav-item {
    min-height: 44px;
    padding: 8px var(--md-spacing-3);
    white-space: normal;
    line-height: 1.25;
  }

  .admin-console__nav-label {
    white-space: normal;
    text-overflow: clip;
  }

}

@media (max-width: 480px) {
  .admin-console__nav {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
