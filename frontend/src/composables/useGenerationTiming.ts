import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import type { Chapter } from '@/api/novel'
import { parseBackendTimestampToMs } from '@/utils/generationTrace'

// useGenerationTiming 只消费的 props 子集（结构同构于 ChapterGenerating 的 Props）
interface GenerationTimingProps {
  chapterNumber: number | null
  status: Chapter['generation_status'] | null
  generationProgress?: number | null
  generationStartedAt?: string | null
  statusUpdatedAt?: string | null
}

// 各生成阶段的时间预估与进度区间配置（后端未回传进度时的兜底插值区间）
const STAGE_CONFIG: Record<
  'generating' | 'evaluating' | 'selecting' | 'finalizing',
  { start: number; end: number; expectedSeconds: number; label: string }
> = {
  generating: { start: 8, end: 78, expectedSeconds: 190, label: '生成正文' },
  evaluating: { start: 78, end: 92, expectedSeconds: 55, label: 'AI评审' },
  selecting: { start: 92, end: 98, expectedSeconds: 38, label: '待人工确认' },
  finalizing: { start: 90, end: 99, expectedSeconds: 180, label: '同步定稿' },
}

/**
 * 章节生成进度时序：1s 定时器驱动已耗时（elapsedText），结合后端进度/阶段配置估算预计剩余（etaText）。
 * localStartAt 在章节号/状态/后端起始时间变化时重置；clockNow 由定时器每秒推进。
 * 仅返回模板消费的两个文本，其余时序中间量对本 composable 私有。
 */
export function useGenerationTiming(props: GenerationTimingProps) {
  const clockNow = ref(Date.now())
  const localStartAt = ref(Date.now())
  let timer: number | null = null

  const parsedGenerationStartedAt = computed(() => parseBackendTimestampToMs(props.generationStartedAt))
  const parsedStatusUpdatedAt = computed(() => parseBackendTimestampToMs(props.statusUpdatedAt))

  const startTimestamp = computed(
    () => parsedGenerationStartedAt.value ?? parsedStatusUpdatedAt.value ?? localStartAt.value,
  )

  const elapsedSeconds = computed(() => {
    const delta = Math.floor((clockNow.value - startTimestamp.value) / 1000)
    return Math.max(0, delta)
  })

  const backendProgress = computed(() => {
    if (props.generationProgress === null || props.generationProgress === undefined) return null
    if (!Number.isFinite(props.generationProgress)) return null
    return Math.max(0, Math.min(100, props.generationProgress))
  })

  const currentStageConfig = computed(() => {
    if (
      props.status === 'generating' ||
      props.status === 'evaluating' ||
      props.status === 'selecting' ||
      props.status === 'finalizing'
    ) {
      return STAGE_CONFIG[props.status]
    }
    return null
  })

  const etaText = computed(() => {
    if (backendProgress.value !== null && backendProgress.value > 4 && elapsedSeconds.value > 8) {
      const estimatedTotal = Math.ceil((elapsedSeconds.value * 100) / backendProgress.value)
      const remain = Math.max(0, estimatedTotal - elapsedSeconds.value)
      if (remain < 60) return '约 1 分钟内'
      return `约 ${Math.ceil(remain / 60)} 分钟`
    }

    const config = currentStageConfig.value
    if (!config) return '约 2 分钟'
    const remain = config.expectedSeconds - elapsedSeconds.value
    if (remain <= 0) return '即将完成'
    if (remain < 60) return '不足 1 分钟'
    return `约 ${Math.ceil(remain / 60)} 分钟`
  })

  const elapsedText = computed(() => {
    const total = elapsedSeconds.value
    const mins = Math.floor(total / 60)
    const secs = total % 60
    return `${mins} 分 ${String(secs).padStart(2, '0')} 秒`
  })

  watch(
    () => [props.chapterNumber, props.status, props.generationStartedAt],
    () => {
      localStartAt.value = Date.now()
    },
    { immediate: true },
  )

  onMounted(() => {
    timer = window.setInterval(() => {
      clockNow.value = Date.now()
    }, 1000)
  })

  onUnmounted(() => {
    if (timer !== null) {
      window.clearInterval(timer)
      timer = null
    }
  })

  return { elapsedText, etaText }
}
