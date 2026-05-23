<!-- AIMETA P=伏笔区_伏笔管理展示|R=伏笔列表_回收状态|NR=不含分析逻辑|E=component:ForeshadowingSection|X=ui|A=伏笔组件|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div class="foreshadowing-section">
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 rounded-full flex items-center justify-center foreshadowing-header-icon-container">
          <svg
            class="w-5 h-5 foreshadowing-header-icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
          >
            <path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
        </div>
        <div>
          <h3 class="md-title-medium foreshadowing-title">伏笔管理</h3>
          <p class="md-body-small foreshadowing-subtitle">
            追踪故事线索与回收
          </p>
        </div>
      </div>
      <button
        @click="refreshData"
        class="md-icon-btn md-ripple"
        :disabled="isLoading"
        aria-label="刷新伏笔数据"
        title="刷新伏笔数据"
      >
        <svg
          class="w-5 h-5 transition-transform"
          :class="{ 'animate-spin': isLoading }"
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
    </div>

    <!-- Statistics Cards -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
      <div class="md-card md-card-outlined p-4 text-center foreshadowing-stat-card">
        <p class="md-label-medium foreshadowing-stat-label">总伏笔</p>
        <p class="md-headline-small foreshadowing-stat-value foreshadowing-stat-value--total">{{ totalForeshadowings }}</p>
      </div>
      <div class="md-card md-card-outlined p-4 text-center foreshadowing-stat-card">
        <p class="md-label-medium foreshadowing-stat-label">已埋设</p>
        <p class="md-headline-small foreshadowing-stat-value foreshadowing-stat-value--planted">{{ plantedCount }}</p>
      </div>
      <div class="md-card md-card-outlined p-4 text-center foreshadowing-stat-card">
        <p class="md-label-medium foreshadowing-stat-label">已回收</p>
        <p class="md-headline-small foreshadowing-stat-value foreshadowing-stat-value--paid-off">{{ paidOffCount }}</p>
      </div>
      <div class="md-card md-card-outlined p-4 text-center foreshadowing-stat-card">
        <p class="md-label-medium foreshadowing-stat-label">待回收</p>
        <p class="md-headline-small foreshadowing-stat-value foreshadowing-stat-value--overdue">{{ overdueCount }}</p>
      </div>
    </div>

    <!-- Status Filter Tabs -->
    <div class="md-tabs mb-6">
      <button
        v-for="tab in statusTabs"
        :key="tab.key"
        @click="activeTab = tab.key"
        class="md-tab"
        :class="{ active: activeTab === tab.key }"
      >
        {{ tab.label }}
        <span
          v-if="getCountByStatus(tab.key) > 0"
          class="ml-2 px-2 py-0.5 rounded-full md-label-small foreshadowing-tab-badge"
          :class="'foreshadowing-tab-badge--' + tab.key"
        >
          {{ getCountByStatus(tab.key) }}
        </span>
      </button>
    </div>
    <p
      v-if="isAutoAnalyzing && !isLoading"
      class="mb-4 md-body-small foreshadowing-auto-analyze-text"
    >
      正在后台自动识别伏笔，不影响当前页面操作...
    </p>

    <!-- Loading State -->
    <div v-if="isLoading" class="flex flex-col items-center justify-center py-12">
      <div class="md-spinner"></div>
      <p class="mt-4 md-body-medium foreshadowing-loading-text">
        加载伏笔数据中...
      </p>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="flex flex-col items-center justify-center py-12">
      <div
        class="w-12 h-12 rounded-full flex items-center justify-center mb-4 foreshadowing-error-icon-container"
      >
        <svg
          class="w-6 h-6 foreshadowing-error-icon"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
      </div>
      <p class="md-body-medium foreshadowing-error-text">{{ error }}</p>
      <button @click="refreshData" class="md-btn md-btn-text md-ripple mt-4">重试</button>
    </div>

    <!-- Empty State -->
    <div
      v-else-if="filteredForeshadowing.length === 0"
      class="flex flex-col items-center justify-center py-12"
    >
      <div
        class="w-16 h-16 rounded-full flex items-center justify-center mb-4 foreshadowing-empty-icon-container"
      >
        <svg
          class="w-8 h-8 foreshadowing-empty-icon"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
        >
          <path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
      </div>
      <p class="md-body-large foreshadowing-empty-title">
        {{
          activeTab === 'all'
            ? '暂无伏笔记录'
            : `暂无${statusTabs.find((t) => t.key === activeTab)?.label}的伏笔`
        }}
      </p>
      <p class="md-body-medium foreshadowing-empty-desc">
        优先展示已记录伏笔，无记录时自动从章节内容中识别
      </p>
    </div>

    <!-- Foreshadowing List -->
    <div v-else class="space-y-4">
      <div
        v-for="item in filteredForeshadowing"
        :key="item.id"
        class="md-card md-card-outlined p-4 transition-shadow duration-200 hover:shadow-md foreshadowing-list-card"
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
const isAutoAnalyzing = computed(() => false)
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
const activeTab = ref('all')

const statusTabs = [
  { key: 'all', label: '全部', color: 'var(--md-on-surface-variant)' },
  { key: 'planted', label: '已埋设', color: 'var(--md-warning)' },
  { key: 'paid_off', label: '已回收', color: 'var(--md-success)' },
  { key: 'overdue', label: '待回收', color: 'var(--md-error)' },
]

const filteredForeshadowing = computed(() => {
  if (activeTab.value === 'all') {
    return foreshadowingList.value
  }
  return foreshadowingList.value.filter((item) => item.status === activeTab.value)
})

const getCountByStatus = (status: string) => {
  if (status === 'all') return totalForeshadowings.value
  if (status === 'planted') return plantedCount.value
  if (status === 'paid_off') return paidOffCount.value
  if (status === 'overdue') return overdueCount.value
  return 0
}

const getStatusColor = (status: string) => {
  const colors: Record<string, string> = {
    planted: 'var(--md-warning)',
    paid_off: 'var(--md-success)',
    overdue: 'var(--md-error)',
  }
  return colors[status] || 'var(--md-on-surface-variant)'
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
.foreshadowing-header-icon-container {
  background-color: var(--md-warning-container);
}

.foreshadowing-header-icon {
  color: var(--md-on-warning-container);
}

.foreshadowing-title {
  color: var(--md-on-surface);
}

.foreshadowing-subtitle {
  color: var(--md-on-surface-variant);
}

.foreshadowing-stat-card {
  border-radius: var(--md-radius-sm) !important;
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
  color: var(--md-warning);
}

.foreshadowing-stat-value--paid-off {
  color: var(--md-success);
}

.foreshadowing-stat-value--overdue {
  color: var(--md-error);
}

.foreshadowing-tab-badge--all {
  background-color: color-mix(in srgb, var(--md-on-surface-variant) 12%, transparent);
  color: var(--md-on-surface-variant);
}

.foreshadowing-tab-badge--planted {
  background-color: color-mix(in srgb, var(--md-warning) 12%, transparent);
  color: var(--md-warning);
}

.foreshadowing-tab-badge--paid_off {
  background-color: color-mix(in srgb, var(--md-success) 12%, transparent);
  color: var(--md-success);
}

.foreshadowing-tab-badge--overdue {
  background-color: color-mix(in srgb, var(--md-error) 12%, transparent);
  color: var(--md-error);
}

.foreshadowing-auto-analyze-text {
  color: var(--md-on-surface-variant);
}

.foreshadowing-loading-text {
  color: var(--md-on-surface-variant);
}

.foreshadowing-error-icon-container {
  background-color: var(--md-error-container);
}

.foreshadowing-error-icon {
  color: var(--md-error);
}

.foreshadowing-error-text {
  color: var(--md-error);
}

.foreshadowing-empty-icon-container {
  background-color: var(--md-surface-container);
}

.foreshadowing-empty-icon {
  color: var(--md-on-surface-variant);
}

.foreshadowing-empty-title {
  color: var(--md-on-surface);
}

.foreshadowing-empty-desc {
  color: var(--md-on-surface-variant);
}

.foreshadowing-list-card {
  border-radius: var(--md-radius-sm) !important;
}

.foreshadowing-status-chip--planted {
  background-color: color-mix(in srgb, var(--md-warning) 12%, transparent) !important;
  color: var(--md-warning) !important;
}

.foreshadowing-status-chip--paid_off {
  background-color: color-mix(in srgb, var(--md-success) 12%, transparent) !important;
  color: var(--md-success) !important;
}

.foreshadowing-status-chip--overdue {
  background-color: color-mix(in srgb, var(--md-error) 12%, transparent) !important;
  color: var(--md-error) !important;
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
  color: var(--md-success);
}

.foreshadowing-meta-text--success {
  color: var(--md-success);
}
</style>
