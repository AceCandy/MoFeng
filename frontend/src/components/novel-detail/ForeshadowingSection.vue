<!-- AIMETA P=伏笔区_伏笔管理展示|R=伏笔列表_回收状态|NR=不含分析逻辑|E=component:ForeshadowingSection|X=ui|A=伏笔组件|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div class="foreshadowing-section">
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div class="flex items-center gap-3">
        <div
          class="w-10 h-10 rounded-full flex items-center justify-center"
          style="background-color: var(--md-warning-container)"
        >
          <svg
            class="w-5 h-5"
            style="color: var(--md-on-warning-container)"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
          >
            <path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
        </div>
        <div>
          <h3 class="md-title-medium" style="color: var(--md-on-surface)">伏笔管理</h3>
          <p class="md-body-small" style="color: var(--md-on-surface-variant)">
            追踪故事线索与回收
          </p>
        </div>
      </div>
      <button @click="refreshData" class="md-icon-btn md-ripple" :disabled="isLoading">
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
      <div
        class="md-card md-card-outlined p-4 text-center"
        style="border-radius: var(--md-radius-md)"
      >
        <p class="md-label-medium" style="color: var(--md-on-surface-variant)">总伏笔</p>
        <p class="md-headline-small" style="color: var(--md-primary)">{{ totalForeshadowings }}</p>
      </div>
      <div
        class="md-card md-card-outlined p-4 text-center"
        style="border-radius: var(--md-radius-md)"
      >
        <p class="md-label-medium" style="color: var(--md-on-surface-variant)">已埋设</p>
        <p class="md-headline-small" style="color: var(--md-google-yellow)">{{ plantedCount }}</p>
      </div>
      <div
        class="md-card md-card-outlined p-4 text-center"
        style="border-radius: var(--md-radius-md)"
      >
        <p class="md-label-medium" style="color: var(--md-on-surface-variant)">已回收</p>
        <p class="md-headline-small" style="color: var(--md-google-green)">{{ paidOffCount }}</p>
      </div>
      <div
        class="md-card md-card-outlined p-4 text-center"
        style="border-radius: var(--md-radius-md)"
      >
        <p class="md-label-medium" style="color: var(--md-on-surface-variant)">待回收</p>
        <p class="md-headline-small" style="color: var(--md-google-red)">{{ overdueCount }}</p>
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
          class="ml-2 px-2 py-0.5 rounded-full md-label-small"
          :style="{ backgroundColor: tab.color + '20', color: tab.color }"
        >
          {{ getCountByStatus(tab.key) }}
        </span>
      </button>
    </div>
    <p
      v-if="isAutoAnalyzing && !isLoading"
      class="mb-4 md-body-small"
      style="color: var(--md-on-surface-variant)"
    >
      正在后台自动识别伏笔，不影响当前页面操作...
    </p>

    <!-- Loading State -->
    <div v-if="isLoading" class="flex flex-col items-center justify-center py-12">
      <div class="md-spinner"></div>
      <p class="mt-4 md-body-medium" style="color: var(--md-on-surface-variant)">
        加载伏笔数据中...
      </p>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="flex flex-col items-center justify-center py-12">
      <div
        class="w-12 h-12 rounded-full flex items-center justify-center mb-4"
        style="background-color: var(--md-error-container)"
      >
        <svg
          class="w-6 h-6"
          style="color: var(--md-error)"
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
      <p class="md-body-medium" style="color: var(--md-error)">{{ error }}</p>
      <button @click="refreshData" class="md-btn md-btn-text md-ripple mt-4">重试</button>
    </div>

    <!-- Empty State -->
    <div
      v-else-if="filteredForeshadowing.length === 0"
      class="flex flex-col items-center justify-center py-12"
    >
      <div
        class="w-16 h-16 rounded-full flex items-center justify-center mb-4"
        style="background-color: var(--md-surface-container)"
      >
        <svg
          class="w-8 h-8"
          style="color: var(--md-on-surface-variant)"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
        >
          <path stroke-linecap="round" stroke-linejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
      </div>
      <p class="md-body-large" style="color: var(--md-on-surface)">
        {{
          activeTab === 'all'
            ? '暂无伏笔记录'
            : `暂无${statusTabs.find((t) => t.key === activeTab)?.label}的伏笔`
        }}
      </p>
      <p class="md-body-medium" style="color: var(--md-on-surface-variant)">
        优先展示已记录伏笔，无记录时自动从章节内容中识别
      </p>
    </div>

    <!-- Foreshadowing List -->
    <div v-else class="space-y-4">
      <div
        v-for="item in filteredForeshadowing"
        :key="item.id"
        class="md-card md-card-outlined p-4 transition-all duration-200 hover:shadow-md"
        style="border-radius: var(--md-radius-md)"
      >
        <div class="flex items-start justify-between">
          <div class="flex-1">
            <!-- Status & Importance -->
            <div class="flex items-center gap-2 mb-2">
              <span
                class="md-chip md-chip-filter selected px-2 py-1"
                :style="{
                  backgroundColor: getStatusColor(item.status) + '20',
                  color: getStatusColor(item.status),
                }"
              >
                {{ getStatusLabel(item.status) }}
              </span>
              <span class="md-chip md-chip-assist px-2 py-1">
                {{ getImportanceLabel(item.importance) }}
              </span>
            </div>

            <!-- Description -->
            <p class="md-body-medium mb-3" style="color: var(--md-on-surface)">
              {{ item.description }}
            </p>

            <!-- Metadata -->
            <div class="flex flex-wrap gap-4">
              <div class="flex items-center gap-1">
                <svg
                  class="w-4 h-4"
                  style="color: var(--md-on-surface-variant)"
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
                <span class="md-body-small" style="color: var(--md-on-surface-variant)">
                  埋设于第{{ item.planted_chapter }}章《{{ item.planted_chapter_title }}》
                </span>
              </div>
              <div v-if="item.expected_payoff_chapter" class="flex items-center gap-1">
                <svg
                  class="w-4 h-4"
                  style="color: var(--md-on-surface-variant)"
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
                <span class="md-body-small" style="color: var(--md-on-surface-variant)">
                  预期回收于第{{ item.expected_payoff_chapter }}章
                </span>
              </div>
              <div v-if="item.actual_payoff_chapter" class="flex items-center gap-1">
                <svg
                  class="w-4 h-4"
                  style="color: var(--md-success)"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                >
                  <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
                </svg>
                <span class="md-body-small" style="color: var(--md-success)">
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
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

interface Foreshadowing {
  id: string
  description: string
  planted_chapter: number
  planted_chapter_title: string
  expected_payoff_chapter?: number
  actual_payoff_chapter?: number
  status: 'planted' | 'paid_off' | 'overdue'
  importance: 'short' | 'medium' | 'long'
}

interface ForeshadowingResponse {
  project_id: string
  project_title: string
  total_foreshadowings: number
  planted_count: number
  paid_off_count: number
  overdue_count: number
  foreshadowings: Foreshadowing[]
}

interface ForeshadowingDbItem {
  id: number | string
  chapter_number: number
  content?: string
  type?: string
  status?: string
  resolved_chapter_number?: number | null
  author_note?: string | null
}

interface ForeshadowingDbListResponse {
  total: number
  data: ForeshadowingDbItem[]
}

const route = useRoute()
const authStore = useAuthStore()
const projectId = route.params.id as string

const isLoading = ref(false)
const isAutoAnalyzing = ref(false)
const error = ref<string | null>(null)
const foreshadowingList = ref<Foreshadowing[]>([])
const totalForeshadowings = ref(0)
const plantedCount = ref(0)
const paidOffCount = ref(0)
const overdueCount = ref(0)
const activeTab = ref('all')

const statusTabs = [
  { key: 'all', label: '全部', color: '#5F6368' },
  { key: 'planted', label: '已埋设', color: '#FBBC04' },
  { key: 'paid_off', label: '已回收', color: '#34A853' },
  { key: 'overdue', label: '待回收', color: '#EA4335' },
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
    planted: '#FBBC04',
    paid_off: '#34A853',
    overdue: '#EA4335',
  }
  return colors[status] || '#5F6368'
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

const setForeshadowingState = (list: Foreshadowing[]) => {
  foreshadowingList.value = list
  totalForeshadowings.value = list.length
  plantedCount.value = list.filter((item) => item.status === 'planted').length
  paidOffCount.value = list.filter((item) => item.status === 'paid_off').length
  overdueCount.value = list.filter((item) => item.status === 'overdue').length
}

const mapDbStatusToUiStatus = (
  status?: string,
  resolvedChapter?: number | null,
): Foreshadowing['status'] => {
  if (status === 'resolved' || !!resolvedChapter) return 'paid_off'
  if (status === 'abandoned' || status === 'overdue') return 'overdue'
  return 'planted'
}

const mapDbTypeToImportance = (type?: string): Foreshadowing['importance'] => {
  const normalizedType = (type || '').toLowerCase()
  if (['long', 'long_term', 'core', 'major'].includes(normalizedType)) {
    return 'long'
  }
  if (['short', 'short_term', 'hint', 'minor'].includes(normalizedType)) {
    return 'short'
  }
  return 'medium'
}

const parseErrorMessage = async (response: Response, fallback: string): Promise<string> => {
  let errorMessage = fallback
  try {
    const errorData = await response.json()
    if (response.status === 422 && errorData.detail) {
      if (Array.isArray(errorData.detail)) {
        const errors = errorData.detail
          .map((err: any) => `${err.loc?.join('.')} - ${err.msg}`)
          .join('; ')
        errorMessage = `参数校验失败: ${errors}`
      } else if (typeof errorData.detail === 'string') {
        errorMessage = errorData.detail
      }
    } else {
      errorMessage = errorData.detail || errorData.message || JSON.stringify(errorData)
    }
  } catch {
    errorMessage = `HTTP ${response.status}: ${response.statusText}`
  }
  return errorMessage
}

const fetchFromForeshadowingStore = async (): Promise<Foreshadowing[]> => {
  const response = await fetch(`/api/novels/${projectId}/foreshadowings?limit=500`, {
    headers: {
      Authorization: `Bearer ${authStore.token}`,
      'Content-Type': 'application/json',
    },
  })

  if (!response.ok) {
    throw new Error(await parseErrorMessage(response, '获取伏笔库数据失败'))
  }

  const data: ForeshadowingDbListResponse = await response.json()
  const dbItems = Array.isArray(data.data) ? data.data : []

  return dbItems.map((item) => {
    const chapterNumber = Number(item.chapter_number || 0)
    return {
      id: String(item.id),
      description: item.content || item.author_note || '未命名伏笔',
      planted_chapter: chapterNumber,
      planted_chapter_title: `第${chapterNumber}章`,
      expected_payoff_chapter: undefined,
      actual_payoff_chapter: item.resolved_chapter_number ?? undefined,
      status: mapDbStatusToUiStatus(item.status, item.resolved_chapter_number),
      importance: mapDbTypeToImportance(item.type),
    }
  })
}

const fetchFromAnalytics = async (): Promise<ForeshadowingResponse> => {
  const response = await fetch(`/api/analytics/${projectId}/foreshadowing`, {
    headers: {
      Authorization: `Bearer ${authStore.token}`,
      'Content-Type': 'application/json',
    },
  })

  if (!response.ok) {
    throw new Error(await parseErrorMessage(response, '获取自动识别伏笔数据失败'))
  }

  return (await response.json()) as ForeshadowingResponse
}

const fetchAnalyticsFallbackInBackground = async () => {
  isAutoAnalyzing.value = true
  try {
    const analyticsData = await fetchFromAnalytics()
    const nextList = analyticsData.foreshadowings || []
    // 仅在当前仍为空时回填，避免覆盖用户刚刚拿到的伏笔库结果
    if (foreshadowingList.value.length === 0 && nextList.length > 0) {
      setForeshadowingState(nextList)
    }
  } catch {
    // 后台回填失败不阻断详情页，主错误状态由 fetchData 统一处理。
  } finally {
    isAutoAnalyzing.value = false
  }
}

const fetchData = async (mode: 'full' | 'quick' = 'full') => {
  isLoading.value = true
  error.value = null

  try {
    let storeForeshadowings: Foreshadowing[] | null = null
    let storeError: string | null = null

    try {
      storeForeshadowings = await fetchFromForeshadowingStore()
    } catch (storeErr: any) {
      storeError = storeErr instanceof Error ? storeErr.message : String(storeErr)
    }

    if (storeForeshadowings && storeForeshadowings.length > 0) {
      setForeshadowingState(storeForeshadowings)
      return
    }

    // 快速刷新模式：不阻塞等待自动识别，先立即返回空态，再后台回填
    if (mode === 'quick') {
      setForeshadowingState([])
      void fetchAnalyticsFallbackInBackground()
      return
    }

    try {
      const analyticsData = await fetchFromAnalytics()
      setForeshadowingState(analyticsData.foreshadowings || [])
      return
    } catch (analyticsErr: any) {
      // 伏笔库请求成功但为空时，自动识别失败不视为页面错误，直接展示空态
      if (storeForeshadowings) {
        setForeshadowingState([])
        return
      }

      const analyticsMessage =
        analyticsErr instanceof Error ? analyticsErr.message : String(analyticsErr)
      if (storeError) {
        throw new Error(`${storeError}；自动识别接口也失败：${analyticsMessage}`)
      }
      throw analyticsErr
    }
  } catch (e: any) {
    console.error('伏笔管理加载错误:', e)
    if (e instanceof Error) {
      error.value = e.message
    } else if (typeof e === 'string') {
      error.value = e
    } else {
      error.value = '加载失败，请稍后重试'
    }
  } finally {
    isLoading.value = false
  }
}

const refreshData = () => {
  fetchData('quick')
}

onMounted(() => {
  fetchData('full')
})
</script>
