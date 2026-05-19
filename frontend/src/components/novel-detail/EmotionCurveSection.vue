<template>
  <div class="emotion-curve-section">
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div class="flex items-center gap-3">
        <div
          class="w-10 h-10 rounded-full flex items-center justify-center"
          style="background-color: var(--md-primary-container)"
        >
          <svg
            class="w-5 h-5"
            style="color: var(--md-on-primary-container)"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z"
            />
          </svg>
        </div>
        <div>
          <h3 class="md-title-medium" style="color: var(--md-on-surface)">情感曲线</h3>
          <p class="md-body-small" style="color: var(--md-on-surface-variant)">追踪章节情感变化</p>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <button @click="useAIAnalysis" class="md-btn md-btn-tonal md-ripple" :disabled="isLoading">
          <svg
            class="w-5 h-5"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
            />
          </svg>
          AI深度分析
        </button>
        <button
          @click="refreshData"
          class="md-btn md-btn-text md-ripple refresh-btn"
          :disabled="isLoading"
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
          刷新
        </button>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="isLoading" class="flex flex-col items-center justify-center py-12">
      <div class="md-spinner"></div>
      <p class="mt-4 md-body-medium" style="color: var(--md-on-surface-variant)">
        分析情感数据中...
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
      v-else-if="!emotionPoints || emotionPoints.length === 0"
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
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
          />
        </svg>
      </div>
      <p class="md-body-large" style="color: var(--md-on-surface)">暂无情感数据</p>
      <p class="md-body-medium" style="color: var(--md-on-surface-variant)">
        生成章节内容后将自动分析情感曲线
      </p>
    </div>

    <!-- Chart Container -->
    <div v-else>
      <!-- Statistics Cards -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div
          class="md-card md-card-outlined p-4 text-center"
          style="border-radius: var(--md-radius-md)"
        >
          <p class="md-label-medium" style="color: var(--md-on-surface-variant)">总章节</p>
          <p class="md-headline-small" style="color: var(--md-primary)">{{ totalChapters }}</p>
        </div>
        <div
          class="md-card md-card-outlined p-4 text-center"
          style="border-radius: var(--md-radius-md)"
        >
          <p class="md-label-medium" style="color: var(--md-on-surface-variant)">平均强度</p>
          <p class="md-headline-small" style="color: var(--md-primary)">{{ averageIntensity }}</p>
        </div>
        <div
          class="md-card md-card-outlined p-4 text-center"
          style="border-radius: var(--md-radius-md)"
        >
          <p class="md-label-medium" style="color: var(--md-on-surface-variant)">主导情感</p>
          <p class="md-headline-small" style="color: var(--md-primary)">{{ dominantEmotion }}</p>
        </div>
        <div
          class="md-card md-card-outlined p-4 text-center"
          style="border-radius: var(--md-radius-md)"
        >
          <p class="md-label-medium" style="color: var(--md-on-surface-variant)">情感类型</p>
          <p class="md-headline-small" style="color: var(--md-primary)">{{ emotionTypeCount }}</p>
        </div>
      </div>

      <!-- Emotion Type Filter Chips -->
      <div class="flex flex-wrap gap-2 mb-6">
        <button
          v-for="emotion in emotionTypes"
          :key="emotion.key"
          @click="toggleEmotion(emotion.key)"
          class="md-chip md-chip-filter md-ripple"
          :class="{ selected: selectedEmotions.includes(emotion.key) }"
          :style="
            selectedEmotions.includes(emotion.key)
              ? {
                  backgroundColor: emotion.color + '20',
                  color: emotion.color,
                  borderColor: emotion.color,
                }
              : {}
          "
        >
          <span class="w-2 h-2 rounded-full" :style="{ backgroundColor: emotion.color }"></span>
          {{ emotion.label }}
          <span v-if="emotionDistribution[emotion.label]" class="ml-1 opacity-70"
            >({{ emotionDistribution[emotion.label] }})</span
          >
        </button>
      </div>

      <!-- Chart -->
      <div class="md-card md-card-outlined p-4" style="border-radius: var(--md-radius-md)">
        <canvas ref="chartCanvas" height="300"></canvas>
      </div>

      <!-- Chapter Details List -->
      <div class="mt-6 space-y-3">
        <h4 class="md-title-small" style="color: var(--md-on-surface)">章节情感详情</h4>
        <div
          v-for="point in emotionPoints"
          :key="point.chapter_number"
          class="md-card md-card-outlined p-4 flex items-center gap-4"
          style="border-radius: var(--md-radius-md)"
        >
          <div
            class="w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0"
            :style="{ backgroundColor: getEmotionColor(point.emotion_type) + '20' }"
          >
            <span class="md-label-large" :style="{ color: getEmotionColor(point.emotion_type) }">{{
              point.chapter_number
            }}</span>
          </div>
          <div class="flex-1 min-w-0">
            <p class="md-body-medium truncate" style="color: var(--md-on-surface)">
              {{ point.title }}
            </p>
            <p class="md-body-small" style="color: var(--md-on-surface-variant)">
              {{ point.description }}
            </p>
          </div>
          <div class="flex items-center gap-2 flex-shrink-0">
            <span
              class="md-chip md-chip-filter selected px-2 py-1"
              :style="{
                backgroundColor: getEmotionColor(point.emotion_type) + '20',
                color: getEmotionColor(point.emotion_type),
              }"
            >
              {{ point.emotion_type }}
            </span>
            <span class="md-label-medium" style="color: var(--md-on-surface-variant)">
              强度: {{ point.intensity }}/10
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import Chart from 'chart.js/auto'
import { useAnalyzeEmotionMutation, useEmotionCurveQuery } from '@/queries/novel'

const route = useRoute()
const projectId = route.params.id as string

const chartCanvas = ref<HTMLCanvasElement | null>(null)
const emotionQuery = useEmotionCurveQuery(() => projectId)
const analyzeEmotionMutation = useAnalyzeEmotionMutation(() => projectId)
const isLoading = computed(
  () =>
    emotionQuery.isLoading.value ||
    emotionQuery.isFetching.value ||
    analyzeEmotionMutation.isPending.value,
)
const error = computed(() => {
  const queryError = analyzeEmotionMutation.error.value || emotionQuery.error.value
  return queryError instanceof Error ? queryError.message : queryError ? String(queryError) : null
})
const emotionData = computed(() => emotionQuery.data.value ?? null)
const emotionPoints = computed(() => emotionData.value?.emotion_points ?? [])
const totalChapters = computed(() => emotionData.value?.total_chapters ?? 0)
const averageIntensity = computed(() =>
  emotionData.value ? Number.parseFloat(emotionData.value.average_intensity.toFixed(2)) : 0,
)
const emotionDistribution = computed<Record<string, number>>(
  () => emotionData.value?.emotion_distribution ?? {},
)
let chartInstance: any = null

const EMOTION_KEY_MAP: { [key: string]: string } = {
  joy: '喜悦',
  sadness: '悲伤',
  anger: '愤怒',
  fear: '恐惧',
  surprise: '惊讶',
  calm: '平静',
}

const EMOTION_COLOR_TOKEN_MAP: Record<string, string> = {
  joy: '--md-success',
  sadness: '--md-primary',
  anger: '--md-error',
  fear: '--md-secondary',
  surprise: '--md-warning',
  calm: '--md-on-surface-variant',
}

const DEFAULT_EMOTION_COLOR_FALLBACK = '#5e6674'

const resolveCssVarColor = (tokenName: string, fallback: string) => {
  if (typeof window === 'undefined') return fallback
  const value = window.getComputedStyle(document.documentElement).getPropertyValue(tokenName).trim()
  return value || fallback
}

const getEmotionColorByKey = (emotionKey: string) => {
  const tokenName = EMOTION_COLOR_TOKEN_MAP[emotionKey] || '--md-on-surface-variant'
  const fallback = DEFAULT_EMOTION_COLOR_FALLBACK
  return resolveCssVarColor(tokenName, fallback)
}

const emotionTypes = computed(() =>
  Object.entries(EMOTION_KEY_MAP).map(([key, label]) => ({
    key,
    label,
    color: getEmotionColorByKey(key),
  })),
)

const selectedEmotions = ref(['joy', 'sadness', 'anger'])

const dominantEmotion = computed(() => {
  if (Object.keys(emotionDistribution.value).length === 0) return '-'
  const sorted = Object.entries(emotionDistribution.value).sort((a, b) => b[1] - a[1])
  return sorted[0]?.[0] || '-'
})

const emotionTypeCount = computed(() => {
  return Object.keys(emotionDistribution.value).length
})

const getEmotionColor = (emotionType: string) => {
  const emotionKey = Object.keys(EMOTION_KEY_MAP).find((key) => EMOTION_KEY_MAP[key] === emotionType)
  return emotionKey ? getEmotionColorByKey(emotionKey) : getEmotionColorByKey('calm')
}

const toggleEmotion = (key: string) => {
  const index = selectedEmotions.value.indexOf(key)
  if (index > -1) {
    if (selectedEmotions.value.length > 1) {
      selectedEmotions.value.splice(index, 1)
    }
  } else {
    selectedEmotions.value.push(key)
  }
  updateChart()
}

const updateChart = () => {
  if (!chartInstance) {
    initChart()
    return
  }

  const labels = emotionPoints.value.map((p) => `第${p.chapter_number}章`)
  const datasets = emotionTypes.value
    .filter((et) => selectedEmotions.value.includes(et.key))
    .map((emotionType) => {
      const data = emotionPoints.value.map((p) => {
        const key = Object.keys(EMOTION_KEY_MAP).find((k) => EMOTION_KEY_MAP[k] === p.emotion_type)
        return key === emotionType.key ? p.intensity : null
      })
      return {
        label: emotionType.label,
        data: data,
        borderColor: emotionType.color,
        backgroundColor: emotionType.color + '33',
        tension: 0.4,
        fill: false,
        spanGaps: true,
      }
    })

  chartInstance.data.labels = labels
  chartInstance.data.datasets = datasets
  chartInstance.update()
}

const initChart = () => {
  if (!chartCanvas.value) {
    return
  }

  if (chartInstance) {
    chartInstance.destroy()
  }

  const ctx = chartCanvas.value.getContext('2d')
  if (!ctx) {
    console.error('Failed to get 2D context for canvas.')
    return
  }

  const labels = emotionPoints.value.map((p) => `第${p.chapter_number}章`)
  const datasets = emotionTypes.value
    .filter((et) => selectedEmotions.value.includes(et.key))
    .map((emotionType) => {
      const data = emotionPoints.value.map((p) => {
        const key = Object.keys(EMOTION_KEY_MAP).find((k) => EMOTION_KEY_MAP[k] === p.emotion_type)
        return key === emotionType.key ? p.intensity : null
      })
      return {
        label: emotionType.label,
        data: data,
        borderColor: emotionType.color,
        backgroundColor: emotionType.color + '33',
        tension: 0.4,
        fill: false,
        spanGaps: true,
      }
    })

  chartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: datasets,
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: {
          beginAtZero: true,
          max: 10,
          title: {
            display: true,
            text: '情感强度',
          },
        },
        x: {
          title: {
            display: true,
            text: '章节',
          },
        },
      },
      plugins: {
        tooltip: {
          callbacks: {
            title: function (context) {
              return context[0].label
            },
            label: function (context) {
              const emotionType = emotionTypes.value.find((et) => et.label === context.dataset.label)
              const point = emotionPoints.value[context.dataIndex]
              if (
                point &&
                emotionType &&
                Object.keys(EMOTION_KEY_MAP).find(
                  (k) => EMOTION_KEY_MAP[k] === point.emotion_type,
                ) === emotionType.key
              ) {
                return `${point.emotion_type}: ${point.intensity}/10`
              }
              return ''
            },
          },
        },
        legend: {
          display: true,
          position: 'top',
        },
      },
    },
  })
}

const refreshData = () => {
  emotionQuery.refetch()
}

const useAIAnalysis = () => {
  analyzeEmotionMutation.mutate()
}

watch(
  emotionPoints,
  (newPoints) => {
    if (newPoints && newPoints.length > 0) {
      nextTick(() => {
        if (chartInstance) {
          updateChart()
        } else {
          initChart()
        }
      })
    } else if (chartInstance) {
      chartInstance.destroy()
      chartInstance = null
    }
  },
  { deep: true },
)

watch(
  selectedEmotions,
  () => {
    updateChart()
  },
  { deep: true },
)
</script>

<style scoped>
.emotion-curve-section {
  padding: 20px;
  background-color: var(--md-surface);
  border-radius: var(--md-radius-lg);
  color: var(--md-on-surface);
}

.md-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 40px;
  padding: 0 16px;
  border-radius: 20px;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition:
    background-color 0.2s,
    color 0.2s;
}

.md-btn-tonal {
  background-color: var(--md-secondary-container);
  color: var(--md-on-secondary-container);
}

.md-btn-tonal:hover {
  background-color: var(--md-secondary-container-hover);
}

.refresh-btn {
  gap: 8px;
  padding: 0 12px;
}

.md-spinner {
  width: 32px;
  height: 32px;
  border: 4px solid var(--md-primary);
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(360deg);
  }
}

.md-card {
  background-color: var(--md-surface-container-low);
  border-radius: var(--md-radius-md);
  padding: 16px;
}

.md-card-outlined {
  border: 1px solid var(--md-outline);
  background-color: var(--md-surface);
}

.md-chip {
  display: inline-flex;
  align-items: center;
  height: 32px;
  padding: 0 12px;
  border-radius: 8px;
  font-size: 0.875rem;
  background-color: var(--md-surface-container-low);
  color: var(--md-on-surface);
  border: 1px solid var(--md-outline);
  cursor: pointer;
  transition:
    background-color 0.2s,
    border-color 0.2s;
}

.md-chip.selected {
  background-color: var(--md-primary-container);
  color: var(--md-on-primary-container);
  border-color: var(--md-primary);
}

.md-chip-filter .w-2.h-2 {
  margin-right: 8px;
}

.md-title-medium {
  font-size: 1rem;
  font-weight: 500;
}

.md-body-small {
  font-size: 0.75rem;
}

.md-body-medium {
  font-size: 0.875rem;
}

.md-body-large {
  font-size: 1rem;
}

.md-label-medium {
  font-size: 0.75rem;
  font-weight: 500;
}

.md-headline-small {
  font-size: 1.5rem;
  font-weight: 400;
}

.md-title-small {
  font-size: 0.875rem;
  font-weight: 500;
}

.md-label-large {
  font-size: 1rem;
  font-weight: 500;
}
</style>
