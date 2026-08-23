<!-- AIMETA P=统计面板_系统使用统计|R=统计图表|NR=不含数据修改|E=component:Statistics|X=ui|A=统计组件|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <section class="admin-panel statistics-panel">
    <div class="admin-panel__body">
      <n-alert v-if="error" type="error" closable @close="error = null" style="margin-bottom: var(--md-spacing-4);">
        {{ error }}
      </n-alert>

      <n-spin :show="loading">
        <div class="admin-ops">
          <header class="admin-ops__summary">
            <div class="admin-ops__copy">
              <h2>系统运行总览</h2>
              <p>集中查看调用、用户、项目与近期变更，先确认平台状态，再进入对应治理模块。</p>
            </div>
            <div class="admin-ops__toolbar">
              <n-button quaternary size="small" @click="fetchStats" :loading="loading" class="admin-ops__refresh-btn">
                刷新
              </n-button>
            </div>
          </header>

          <div class="admin-ops__metrics">
            <article class="admin-ops__metric">
              <p>AI 调用总量</p>
              <strong>{{ statisticsPending ? '—' : (stats?.api_request_count ?? 0) }}</strong>
              <span>累计请求次数</span>
            </article>
            <article class="admin-ops__metric">
              <p>活跃项目</p>
              <strong>{{ novelsPending ? '—' : activeProjects.length }}</strong>
              <span>最近 7 天有编辑</span>
            </article>
            <article class="admin-ops__metric">
              <p>平台用户</p>
              <strong>{{ statisticsPending ? '—' : (stats?.user_count ?? 0) }}</strong>
              <span>当前注册用户数</span>
            </article>
            <article class="admin-ops__metric">
              <p>项目总量</p>
              <strong>{{ statisticsPending ? '—' : (stats?.novel_count ?? 0) }}</strong>
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
        </div>
      </n-spin>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { NAlert } from 'naive-ui/es/alert'
import { NButton } from 'naive-ui/es/button'
import { NSpin } from 'naive-ui/es/spin'
import {
  useAdminNovelsQuery,
  useAdminStatisticsQuery,
  useAdminUpdateLogsQuery,
} from '@/queries/admin'

const statisticsQuery = useAdminStatisticsQuery()
const novelQuery = useAdminNovelsQuery()
const updateLogsQuery = useAdminUpdateLogsQuery()

const stats = computed(() => statisticsQuery.data.value ?? null)
const statisticsPending = computed(() => statisticsQuery.isPending.value)
const novelsPending = computed(() => novelQuery.isPending.value)

const loading = computed(
  () =>
    statisticsQuery.isLoading.value ||
    statisticsQuery.isFetching.value ||
    novelQuery.isLoading.value ||
    novelQuery.isFetching.value ||
    updateLogsQuery.isLoading.value ||
    updateLogsQuery.isFetching.value
)

const isErrorDismissed = ref(false)
const error = computed({
  get: () => {
    if (isErrorDismissed.value) {
      return null
    }
    const queryError =
      statisticsQuery.error.value || novelQuery.error.value || updateLogsQuery.error.value
    return queryError instanceof Error ? queryError.message : queryError ? String(queryError) : null
  },
  set: () => {
    isErrorDismissed.value = true
  },
})

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

const fetchStats = () => {
  statisticsQuery.refetch()
  novelQuery.refetch()
  updateLogsQuery.refetch()
}

watch(
  [
    () => statisticsQuery.error.value,
    () => novelQuery.error.value,
    () => updateLogsQuery.error.value,
  ],
  () => {
    isErrorDismissed.value = false
  }
)
</script>

<style scoped>
.admin-ops__refresh-btn {
  flex-shrink: 0;
}

/* 日志/项目清单与空态提示样式已统一下沉至 admin-panels.css */

.admin-panel-card--trend {
  display: flex;
  flex-direction: column;
}

.admin-trend {
  margin-top: var(--md-spacing-4);
  padding: var(--md-spacing-3);
  height: 176px;
  border-radius: var(--md-radius-xs); /* 微直角 2px */
  border: 1px solid var(--md-outline);
  background-color: var(--md-surface-container-low); /* 竹纸暖黄 */
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  align-items: end;
  gap: var(--md-spacing-2);
}

.admin-trend__bar {
  position: relative;
  border-radius: var(--md-radius-xs) var(--md-radius-xs) 0 0; /* 微直角，底部贴合轴线 */
  background-color: var(--md-primary); /* 焦墨单色实条 */
  min-height: 22px;
}

.admin-trend__bar span {
  position: absolute;
  top: -18px;
  left: 50%;
  transform: translateX(-50%);
  font-size: 11px;
  color: var(--md-on-surface-variant);
  font-family: var(--md-font-mono);
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
  font-family: var(--md-font-mono);
}

/* 仅在中等宽度切两列；≤833px 时由 admin-panels.css 统一塌为单列，避免 span 2 撑出隐式列 */
@media (min-width: 834px) and (max-width: 960px) {
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
</style>
