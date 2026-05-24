<template>
  <div class="emotion-curve-section blueprint-page">
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
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z"
            />
          </svg>
        </span>
        <div class="blueprint-section-header__text">
          <p class="blueprint-kicker">分析档案</p>
          <h2 class="blueprint-title">情感曲线</h2>
          <p class="blueprint-subtitle">追踪章节情绪强度、主导情感与叙事波动，辅助判断故事节奏是否稳定。</p>
        </div>
      </div>
      <div class="blueprint-action-row">
        <button @click="useAIAnalysis" class="blueprint-button blueprint-button--primary" :disabled="isLoading">
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
          class="blueprint-button refresh-btn"
          :disabled="isLoading"
        >
          <svg
            class="w-5 h-5 emotion-refresh-icon"
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
          刷新
        </button>
      </div>
    </header>

    <!-- Loading State -->
    <div
      v-if="isLoading"
      class="blueprint-state blueprint-state--loading"
      role="status"
      aria-live="polite"
    >
      <div class="blueprint-state__inner">
        <div class="md-spinner"></div>
        <p class="blueprint-state__title">分析情感数据中</p>
        <p class="blueprint-state__desc">正在读取章节情绪强度、主导情感与叙事波动。</p>
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
        <p class="blueprint-state__title">情感数据加载失败</p>
        <p class="blueprint-state__desc">{{ error }}</p>
        <div class="blueprint-state__actions">
          <button type="button" @click="refreshData" class="blueprint-button">重试</button>
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div
      v-else-if="!emotionPoints || emotionPoints.length === 0"
      class="blueprint-state blueprint-state--empty"
    >
      <div class="blueprint-state__inner">
        <div class="blueprint-state__icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
            />
          </svg>
        </div>
        <p class="blueprint-state__title">暂无情感数据</p>
        <p class="blueprint-state__desc">生成章节内容后将自动分析情感曲线。</p>
      </div>
    </div>

    <!-- Chart Container -->
    <div v-else>
      <!-- Statistics Cards -->
      <div class="blueprint-metric-grid mb-6">
        <div class="blueprint-metric stat-card">
          <p class="blueprint-metric__label stat-label">总章节</p>
          <p class="blueprint-metric__value stat-value">{{ totalChapters }}</p>
        </div>
        <div class="blueprint-metric stat-card">
          <p class="blueprint-metric__label stat-label">平均强度</p>
          <p class="blueprint-metric__value stat-value">{{ averageIntensity }}</p>
        </div>
        <div class="blueprint-metric stat-card">
          <p class="blueprint-metric__label stat-label">主导情感</p>
          <p class="blueprint-metric__value stat-value">{{ dominantEmotion }}</p>
        </div>
        <div class="blueprint-metric stat-card">
          <p class="blueprint-metric__label stat-label">情感类型</p>
          <p class="blueprint-metric__value stat-value">{{ emotionTypeCount }}</p>
        </div>
      </div>

      <!-- Emotion Type Filter Chips -->
      <div class="flex flex-wrap gap-2 mb-6" role="group" aria-label="情感类型筛选">
        <button
          v-for="emotion in emotionTypes"
          :key="emotion.key"
          @click="toggleEmotion(emotion.key)"
          class="md-chip md-chip-filter md-ripple"
          :aria-pressed="selectedEmotions.includes(emotion.key)"
          :aria-label="`切换${emotion.label}情感曲线`"
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
          <span class="w-2 h-2 rounded-xs" :style="{ backgroundColor: emotion.color }"></span>
          {{ emotion.label }}
          <span v-if="emotionDistribution[emotion.label]" class="ml-1 opacity-70"
            >({{ emotionDistribution[emotion.label] }})</span
          >
        </button>
      </div>

      <!-- Chart -->
      <div class="blueprint-panel blueprint-panel--paper chart-card">
        <div class="blueprint-panel__body">
        <p :id="chartSummaryId" class="sr-only">{{ chartA11ySummary }}</p>
        <svg
          class="emotion-curve-svg h-[320px] w-full"
          :viewBox="`0 0 ${CHART_VIEWBOX_WIDTH} ${CHART_VIEWBOX_HEIGHT}`"
          preserveAspectRatio="none"
          role="img"
          :aria-describedby="chartSummaryId"
        >
          <title>章节情感曲线图</title>
          <desc>{{ chartA11ySummary }}</desc>
          <rect
            :x="0"
            :y="0"
            :width="CHART_VIEWBOX_WIDTH"
            :height="CHART_VIEWBOX_HEIGHT"
            rx="18"
            fill="var(--md-surface-container-low)"
          />

          <g>
            <line
              v-for="tick in chartYAxisTicks"
              :key="`y-${tick.value}`"
              :x1="CHART_PADDING.left"
              :x2="CHART_VIEWBOX_WIDTH - CHART_PADDING.right"
              :y1="tick.y"
              :y2="tick.y"
              stroke="var(--md-outline-variant)"
              stroke-width="1"
              stroke-dasharray="4 6"
            />
            <text
              v-for="tick in chartYAxisTicks"
              :key="`y-label-${tick.value}`"
              :x="CHART_PADDING.left - 12"
              :y="tick.y + 4"
              text-anchor="end"
              class="fill-[var(--md-on-surface-variant)] text-[12px]"
            >
              {{ tick.value }}
            </text>
          </g>

          <g v-for="axisLabel in chartAxisLabels" :key="axisLabel.label">
            <line
              :x1="axisLabel.x"
              :x2="axisLabel.x"
              :y1="CHART_PADDING.top"
              :y2="CHART_VIEWBOX_HEIGHT - CHART_PADDING.bottom"
              stroke="transparent"
            />
            <text
              :x="axisLabel.x"
              :y="CHART_VIEWBOX_HEIGHT - 14"
              text-anchor="middle"
              class="fill-[var(--md-on-surface-variant)] text-[12px]"
            >
              {{ axisLabel.label }}
            </text>
          </g>

          <g v-for="series in chartSeries" :key="series.key">
            <path
              :d="series.path"
              fill="none"
              :stroke="series.color"
              stroke-width="3"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
            <circle
              v-for="point in series.points"
              :key="`${series.key}-${point.chapterNumber}`"
              :cx="point.x"
              :cy="point.y"
              r="4.5"
              :fill="series.color"
              stroke="var(--md-surface-container-low)"
              stroke-width="2"
            />
          </g>

          <g v-if="selectedEmotionLabels.length" transform="translate(24, 18)">
            <g v-for="(emotionLabel, index) in selectedEmotionLabels" :key="emotionLabel">
              <circle :cx="index * 118" cy="0" r="5" :fill="chartLegendColor(emotionLabel)" />
              <text
                :x="index * 118 + 12"
                y="4"
                class="fill-[var(--md-on-surface-variant)] text-[12px]"
              >
                {{ emotionLabel }}
              </text>
            </g>
          </g>
        </svg>
        </div>
      </div>

      <!-- Chapter Details List -->
      <div class="mt-6 space-y-3">
        <h4 class="md-title-small details-title">章节情感详情</h4>
        <div
          v-for="point in emotionPoints"
          :key="point.chapter_number"
          class="blueprint-item-card flex items-center gap-4 detail-card"
        >
          <div
            class="w-10 h-10 rounded-xs border border-[var(--md-outline-variant)] flex items-center justify-center flex-shrink-0"
            :style="{ backgroundColor: getEmotionColor(point.emotion_type) + '20' }"
          >
            <span class="md-label-large" :style="{ color: getEmotionColor(point.emotion_type) }">{{
              point.chapter_number
            }}</span>
          </div>
          <div class="flex-1 min-w-0">
            <p class="md-body-medium truncate detail-title">
              {{ point.title }}
            </p>
            <p class="md-body-small detail-desc">
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
            <span class="md-label-medium detail-intensity-label">
              强度: {{ point.intensity }}/10
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAnalyzeEmotionMutation, useEmotionCurveQuery } from '@/queries/novel'

const route = useRoute()
const projectId = route.params.id as string

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

const EMOTION_KEY_MAP: { [key: string]: string } = {
  joy: '喜悦',
  sadness: '悲伤',
  anger: '愤怒',
  fear: '恐惧',
  surprise: '惊讶',
  calm: '平静',
}

const EMOTION_LABEL_TO_KEY_MAP = Object.fromEntries(
  Object.entries(EMOTION_KEY_MAP).map(([key, label]) => [label, key]),
) as Record<string, string>

const EMOTION_COLOR_TOKEN_MAP: Record<string, string> = {
  joy: '--md-success',
  sadness: '--md-primary',
  anger: '--md-error',
  fear: '--md-secondary',
  surprise: '--md-warning',
  calm: '--md-on-surface-variant',
}

const DEFAULT_EMOTION_COLOR_FALLBACK = 'currentColor'

const resolveCssVarColor = (tokenName: string, fallback: string) => {
  if (typeof window === 'undefined') return fallback
  const value = window.getComputedStyle(document.documentElement).getPropertyValue(tokenName).trim()
  return value || fallback
}

const getEmotionColorByKey = (emotionKey: string) => {
  const tokenName = EMOTION_COLOR_TOKEN_MAP[emotionKey] || '--md-on-surface-variant'
  const fallback = resolveCssVarColor('--md-on-surface-variant', DEFAULT_EMOTION_COLOR_FALLBACK)
  return resolveCssVarColor(tokenName, fallback)
}

const getEmotionKeyByType = (emotionType: string) => {
  return EMOTION_LABEL_TO_KEY_MAP[emotionType] || 'calm'
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

const chartSummaryId = 'emotion-curve-chart-summary'
const CHART_VIEWBOX_WIDTH = 800
const CHART_VIEWBOX_HEIGHT = 320
const CHART_PADDING = {
  top: 24,
  right: 24,
  bottom: 44,
  left: 48,
}
const CHART_MAX_INTENSITY = 10

const selectedEmotionLabels = computed(() =>
  emotionTypes.value
    .filter((emotionType) => selectedEmotions.value.includes(emotionType.key))
    .map((emotionType) => emotionType.label),
)

const chartA11ySummary = computed(() => {
  if (!emotionPoints.value.length) {
    return '暂无可视化情感数据。'
  }
  const selectedLabels = selectedEmotionLabels.value.length
    ? selectedEmotionLabels.value.join('、')
    : '无'
  return `共 ${totalChapters.value} 章。当前显示 ${selectedLabels} 情感曲线，主导情感为 ${dominantEmotion.value}，平均强度 ${averageIntensity.value}。`
})

const getEmotionColor = (emotionType: string) => {
  return getEmotionColorByKey(getEmotionKeyByType(emotionType))
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
}

const refreshData = () => {
  emotionQuery.refetch()
}

const useAIAnalysis = () => {
  analyzeEmotionMutation.mutate()
}

const chartGeometry = computed(() => {
  const innerWidth = CHART_VIEWBOX_WIDTH - CHART_PADDING.left - CHART_PADDING.right
  const innerHeight = CHART_VIEWBOX_HEIGHT - CHART_PADDING.top - CHART_PADDING.bottom
  const pointCount = emotionPoints.value.length
  const step = pointCount > 1 ? innerWidth / (pointCount - 1) : 0

  return {
    innerWidth,
    innerHeight,
    step,
    pointCount,
  }
})

const toChartX = (index: number) => {
  if (chartGeometry.value.pointCount <= 1) {
    return CHART_PADDING.left + chartGeometry.value.innerWidth / 2
  }

  return CHART_PADDING.left + index * chartGeometry.value.step
}

const toChartY = (intensity: number) => {
  const ratio = Math.max(0, Math.min(intensity, CHART_MAX_INTENSITY)) / CHART_MAX_INTENSITY
  return CHART_PADDING.top + (1 - ratio) * chartGeometry.value.innerHeight
}

const buildPath = (points: Array<{ x: number; y: number } | null>) => {
  const commands: string[] = []
  let segmentOpen = false

  for (const point of points) {
    if (!point) {
      segmentOpen = false
      continue
    }

    commands.push(`${segmentOpen ? 'L' : 'M'} ${point.x.toFixed(1)} ${point.y.toFixed(1)}`)
    segmentOpen = true
  }

  return commands.join(' ')
}

const chartSeries = computed(() =>
  emotionTypes.value
    .filter((emotionType) => selectedEmotions.value.includes(emotionType.key))
    .map((emotionType) => {
      const rawPoints = emotionPoints.value
        .map((point, index) => {
          if (getEmotionKeyByType(point.emotion_type) !== emotionType.key) {
            return null
          }

          return {
            chapterNumber: point.chapter_number,
            intensity: point.intensity,
            x: toChartX(index),
            y: toChartY(point.intensity),
          }
        })
      const points = rawPoints.filter(
        (point): point is { chapterNumber: number; intensity: number; x: number; y: number } =>
          Boolean(point),
      )

      return {
        key: emotionType.key,
        color: emotionType.color,
        points,
        path: buildPath(rawPoints.map((point) => (point ? { x: point.x, y: point.y } : null))),
      }
    }),
)

const chartYAxisTicks = computed(() =>
  [10, 8, 6, 4, 2, 0].map((value) => ({
    value,
    y: toChartY(value),
  })),
)

const chartAxisLabels = computed(() => {
  const pointCount = emotionPoints.value.length
  if (pointCount === 0) {
    return []
  }

  const step = Math.max(1, Math.ceil(pointCount / 6))

  return emotionPoints.value
    .map((point, index) => {
      if (index !== 0 && index !== pointCount - 1 && index % step !== 0) {
        return null
      }

      return {
        label: `第${point.chapter_number}章`,
        x: toChartX(index),
      }
    })
    .filter((label): label is { label: string; x: number } => Boolean(label))
})

const chartLegendColor = (emotionLabel: string) => {
  const emotionKey = EMOTION_LABEL_TO_KEY_MAP[emotionLabel] || 'calm'
  return getEmotionColorByKey(emotionKey)
}
</script>

<style scoped>
.emotion-curve-section {
  color: var(--md-on-surface);
}

.refresh-btn {
  gap: 8px;
  padding: 0 12px;
}

.emotion-refresh-icon {
  transition: transform var(--md-duration-short) var(--md-easing-standard);
}

.emotion-refresh-icon.is-spinning {
  animation: blueprint-refresh-spin 1s linear infinite;
}

.md-chip-filter .w-2.h-2 {
  margin-right: 8px;
}

/* 墨风重构样式 */
.emotion-header-icon-container {
  background-color: var(--md-primary-container);
}

.emotion-header-icon {
  color: var(--md-on-primary-container);
}

.emotion-title {
  color: var(--md-on-surface);
}

.emotion-subtitle {
  color: var(--md-on-surface-variant);
}

.stat-card {
  text-align: left;
}

.stat-label {
  color: var(--md-on-surface-variant);
}

.stat-value {
  color: var(--md-primary);
}

.chart-card {
  overflow: hidden;
}

.details-title {
  color: var(--md-on-surface);
}

.detail-card {
  border-radius: var(--md-radius-sm);
}

.emotion-curve-svg {
  display: block;
  min-width: 560px;
}

.chart-card .blueprint-panel__body {
  overflow-x: auto;
}

.detail-title {
  color: var(--md-on-surface);
}

.detail-desc {
  color: var(--md-on-surface-variant);
}

.detail-intensity-label {
  color: var(--md-on-surface-variant);
}

@media (prefers-reduced-motion: reduce) {
  .emotion-refresh-icon.is-spinning,
  .md-spinner {
    animation: none;
  }
}

@keyframes blueprint-refresh-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
