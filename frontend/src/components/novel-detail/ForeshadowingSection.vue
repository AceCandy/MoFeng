<!-- AIMETA P=伏笔区_伏笔管理展示|R=伏笔列表_回收状态|NR=不含分析逻辑|E=component:ForeshadowingSection|X=ui|A=伏笔组件|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div class="foreshadowing-section blueprint-page">
    <!-- Header -->
    <header class="blueprint-section-header">
      <div class="blueprint-section-header__main">
        <span class="blueprint-section-header__icon" aria-hidden="true">
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
          >
            <path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
        </span>
        <div class="blueprint-section-header__text">
          <p class="blueprint-kicker">线索档案</p>
          <h2 class="blueprint-title">伏笔管理</h2>
          <p class="blueprint-subtitle">追踪故事线索的埋设、回收与逾期状态，减少长篇创作中的遗忘风险。</p>
        </div>
      </div>
      <button
        @click="refreshData"
        class="blueprint-icon-action"
        :disabled="isLoading"
        aria-label="刷新伏笔数据"
        title="刷新伏笔数据"
      >
        <svg
          class="w-5 h-5 foreshadowing-refresh-icon"
          :class="{ 'is-spinning': isLoading }"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
          />
        </svg>
      </button>
    </header>

    <!-- Statistics Cards -->
    <div class="blueprint-metric-grid">
      <div class="blueprint-metric foreshadowing-stat-card">
        <p class="blueprint-metric__label foreshadowing-stat-label">总伏笔</p>
        <p class="blueprint-metric__value foreshadowing-stat-value foreshadowing-stat-value--total">{{ totalForeshadowings }}</p>
      </div>
      <div class="blueprint-metric foreshadowing-stat-card">
        <p class="blueprint-metric__label foreshadowing-stat-label">已埋设</p>
        <p class="blueprint-metric__value foreshadowing-stat-value foreshadowing-stat-value--planted">{{ plantedCount }}</p>
      </div>
      <div class="blueprint-metric foreshadowing-stat-card">
        <p class="blueprint-metric__label foreshadowing-stat-label">已回收</p>
        <p class="blueprint-metric__value foreshadowing-stat-value foreshadowing-stat-value--paid-off">{{ paidOffCount }}</p>
      </div>
      <div class="blueprint-metric foreshadowing-stat-card">
        <p class="blueprint-metric__label foreshadowing-stat-label">待回收</p>
        <p class="blueprint-metric__value foreshadowing-stat-value foreshadowing-stat-value--overdue">{{ overdueCount }}</p>
      </div>
    </div>

    <!-- Status Filter Tabs -->
    <div class="md-tabs foreshadowing-tabs mb-6" role="tablist" aria-label="伏笔状态筛选">
      <button
        v-for="tab in statusTabs"
        :key="tab.key"
        type="button"
        role="tab"
        :id="foreshadowingTabId(tab.key)"
        :aria-selected="activeTab === tab.key"
        :aria-controls="foreshadowingPanelId"
        :tabindex="activeTab === tab.key ? 0 : -1"
        @click="switchStatusTab(tab.key)"
        @keydown="onStatusTabKeydown(tab.key, $event)"
        class="md-tab"
        :class="{ active: activeTab === tab.key }"
      >
        {{ tab.label }}
        <span
          v-if="getCountByStatus(tab.key) > 0"
          class="ml-2 px-2 py-0.5 rounded-xs border border-[var(--md-outline-variant)] md-label-small foreshadowing-tab-badge"
          :class="'foreshadowing-tab-badge--' + tab.key"
        >
          {{ getCountByStatus(tab.key) }}
        </span>
      </button>
    </div>
    <!-- Loading State -->
    <div
      v-if="isLoading"
      class="blueprint-state blueprint-state--loading"
      role="status"
      aria-live="polite"
    >
      <div class="blueprint-state__inner">
        <div class="md-spinner"><span></span></div>
        <p class="blueprint-state__title">加载伏笔数据中</p>
        <p class="blueprint-state__desc">正在整理线索的埋设、回收与逾期状态。</p>
      </div>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="blueprint-state blueprint-state--error" role="alert">
      <div class="blueprint-state__inner">
        <div class="blueprint-state__icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
        </div>
        <p class="blueprint-state__title">伏笔数据加载失败</p>
        <p class="blueprint-state__desc">{{ error }}</p>
        <div class="blueprint-state__actions">
          <button type="button" @click="refreshData" class="md-btn md-btn-outlined">重试</button>
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div
      v-else-if="filteredForeshadowing.length === 0"
      class="blueprint-state blueprint-state--empty"
    >
      <div class="blueprint-state__inner">
        <div class="blueprint-state__icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
        </div>
        <p class="blueprint-state__title">
          {{
            activeTab === 'all'
              ? '暂无伏笔记录'
              : `暂无${statusTabs.find((t) => t.key === activeTab)?.label}的伏笔`
          }}
        </p>
        <p class="blueprint-state__desc">优先展示已记录伏笔，无记录时自动从章节内容中识别。</p>
      </div>
    </div>

    <!-- Foreshadowing List -->
    <div
      v-else
      :id="foreshadowingPanelId"
      class="foreshadowing-list"
      role="tabpanel"
      :aria-labelledby="foreshadowingTabId(activeTab)"
      tabindex="0"
    >
      <div
        v-for="item in filteredForeshadowing"
        :key="item.id"
        class="blueprint-item-card foreshadowing-list-card"
      >
        <div class="flex items-start justify-between">
          <div class="flex-1">
            <!-- Status & Importance -->
            <div class="flex items-center gap-2 mb-2">
              <span
                class="md-chip md-chip-filter selected px-2 py-1 foreshadowing-status-chip"
                :class="'foreshadowing-status-chip--' + item.status"
              >
                {{ getStatusLabel(item.status) }}
              </span>
              <span class="md-chip md-chip-assist px-2 py-1">
                {{ getImportanceLabel(item.importance) }}
              </span>
            </div>

            <!-- Description -->
            <p class="md-body-medium mb-3 foreshadowing-item-desc">
              {{ item.description }}
            </p>

            <!-- Metadata -->
            <div class="flex flex-wrap gap-4">
              <div class="flex items-center gap-1">
                <svg
                  class="w-4 h-4 foreshadowing-meta-icon"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
                  />
                </svg>
                <span class="md-body-small foreshadowing-meta-text">
                  埋设于第{{ item.planted_chapter }}章《{{ item.planted_chapter_title }}》
                </span>
              </div>
              <div v-if="item.expected_payoff_chapter" class="flex items-center gap-1">
                <svg
                  class="w-4 h-4 foreshadowing-meta-icon"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
                <span class="md-body-small foreshadowing-meta-text">
                  预期回收于第{{ item.expected_payoff_chapter }}章
                </span>
              </div>
              <div v-if="item.actual_payoff_chapter" class="flex items-center gap-1">
                <svg
                  class="w-4 h-4 foreshadowing-meta-icon--success"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                >
                  <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
                </svg>
                <span class="md-body-small foreshadowing-meta-text--success">
                  实际回收于第{{ item.actual_payoff_chapter }}章
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useForeshadowingQuery } from '@/queries/novel'

const route = useRoute()
const projectId = route.params.id as string

const foreshadowingQuery = useForeshadowingQuery(() => projectId)
const isLoading = computed(
  () => foreshadowingQuery.isLoading.value || foreshadowingQuery.isFetching.value,
)
const error = computed(() => {
  const queryError = foreshadowingQuery.error.value
  return queryError instanceof Error ? queryError.message : queryError ? String(queryError) : null
})
const foreshadowingData = computed(() => foreshadowingQuery.data.value ?? null)
const foreshadowingList = computed(() => foreshadowingData.value?.foreshadowings ?? [])
const totalForeshadowings = computed(() => foreshadowingData.value?.total_foreshadowings ?? 0)
const plantedCount = computed(() => foreshadowingData.value?.planted_count ?? 0)
const paidOffCount = computed(() => foreshadowingData.value?.paid_off_count ?? 0)
const overdueCount = computed(() => foreshadowingData.value?.overdue_count ?? 0)
const statusTabs = [
  { key: 'all', label: '全部' },
  { key: 'planted', label: '已埋设' },
  { key: 'paid_off', label: '已回收' },
  { key: 'overdue', label: '待回收' },
] as const

type StatusTabKey = (typeof statusTabs)[number]['key']

const activeTab = ref<StatusTabKey>('all')
const foreshadowingPanelId = 'foreshadowing-status-panel'

const foreshadowingTabId = (key: StatusTabKey) => `foreshadowing-tab-${key}`

const switchStatusTab = (key: StatusTabKey) => {
  activeTab.value = key
}

// 伏笔状态筛选遵循 ARIA Tabs 键盘交互，减少长列表页面里的重复 Tab 扫描。
const onStatusTabKeydown = (key: StatusTabKey, event: KeyboardEvent) => {
  const keys = statusTabs.map((tab) => tab.key)
  const currentIndex = keys.indexOf(key)
  let nextIndex: number | null = null

  if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
    nextIndex = (currentIndex + 1) % keys.length
  } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
    nextIndex = (currentIndex - 1 + keys.length) % keys.length
  } else if (event.key === 'Home') {
    nextIndex = 0
  } else if (event.key === 'End') {
    nextIndex = keys.length - 1
  }

  if (nextIndex === null) return
  event.preventDefault()
  const nextKey = keys[nextIndex]
  switchStatusTab(nextKey)
  document.getElementById(foreshadowingTabId(nextKey))?.focus()
}

const filteredForeshadowing = computed(() => {
  if (activeTab.value === 'all') {
    return foreshadowingList.value
  }
  return foreshadowingList.value.filter((item) => item.status === activeTab.value)
})

const getCountByStatus = (status: StatusTabKey) => {
  if (status === 'all') return totalForeshadowings.value
  if (status === 'planted') return plantedCount.value
  if (status === 'paid_off') return paidOffCount.value
  if (status === 'overdue') return overdueCount.value
  return 0
}

const getStatusLabel = (status: string) => {
  const labels: Record<string, string> = {
    planted: '已埋设',
    paid_off: '已回收',
    overdue: '待回收',
  }
  return labels[status] || status
}

const getImportanceLabel = (importance: string) => {
  const labels: Record<string, string> = {
    short: '短期伏笔',
    medium: '中期伏笔',
    long: '长期伏笔',
  }
  return labels[importance] || importance
}

const refreshData = () => {
  foreshadowingQuery.refetch()
}
</script>

<style scoped>
.foreshadowing-stat-card {
  text-align: left;
}

.foreshadowing-stat-label {
  color: var(--md-on-surface-variant);
}

.foreshadowing-stat-value {
  font-weight: 700;
}

.foreshadowing-stat-value--total {
  color: var(--md-primary);
}

.foreshadowing-stat-value--planted {
  color: var(--md-warning-text);
}

.foreshadowing-stat-value--paid-off {
  color: var(--md-success-text);
}

.foreshadowing-stat-value--overdue {
  color: var(--md-error-text);
}

.foreshadowing-tab-badge--all {
  background-color: color-mix(in srgb, var(--md-on-surface-variant) 12%, transparent);
  color: var(--md-on-surface-variant);
}

.foreshadowing-tab-badge--planted {
  background-color: color-mix(in srgb, var(--md-warning) 12%, transparent);
  color: var(--md-warning-text);
}

.foreshadowing-tab-badge--paid_off {
  background-color: color-mix(in srgb, var(--md-success) 12%, transparent);
  color: var(--md-success-text);
}

.foreshadowing-tab-badge--overdue {
  background-color: color-mix(in srgb, var(--md-error) 12%, transparent);
  color: var(--md-error-text);
}

.foreshadowing-list-card {
  border-radius: var(--md-radius-sm) !important;
}

.foreshadowing-refresh-icon {
  transition: transform var(--md-duration-short) var(--md-easing-standard);
}

.foreshadowing-refresh-icon.is-spinning {
  animation: md-spin 1s linear infinite;
}

.foreshadowing-list {
  display: grid;
  gap: var(--md-spacing-4);
}

.foreshadowing-tabs {
  min-width: 0;
}

.foreshadowing-status-chip--planted {
  background-color: color-mix(in srgb, var(--md-warning) 12%, transparent) !important;
  color: var(--md-warning-text) !important;
}

.foreshadowing-status-chip--paid_off {
  background-color: color-mix(in srgb, var(--md-success) 12%, transparent) !important;
  color: var(--md-success-text) !important;
}

.foreshadowing-status-chip--overdue {
  background-color: color-mix(in srgb, var(--md-error) 12%, transparent) !important;
  color: var(--md-error-text) !important;
}

.foreshadowing-item-desc {
  color: var(--md-on-surface);
}

.foreshadowing-meta-icon {
  color: var(--md-on-surface-variant);
}

.foreshadowing-meta-text {
  color: var(--md-on-surface-variant);
}

.foreshadowing-meta-icon--success {
  color: var(--md-success-text);
}

.foreshadowing-meta-text--success {
  color: var(--md-success-text);
}

@media (prefers-reduced-motion: reduce) {
  .foreshadowing-refresh-icon.is-spinning {
    animation: none;
  }
}

@media (max-width: 640px) {
  .foreshadowing-tabs {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    overflow-x: visible;
    gap: var(--md-spacing-2);
  }

  .foreshadowing-tabs .md-tab {
    width: 100%;
    min-width: 0;
    flex: initial;
    justify-content: center;
  }
}
</style>
