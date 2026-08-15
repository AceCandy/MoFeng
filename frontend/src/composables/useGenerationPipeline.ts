import { computed, type ComputedRef } from 'vue'
import type { Chapter, ChapterGenerationTrace } from '@/api/novel'
import {
  STEP_DETAILS,
  PIPELINE_LABELS,
  parseStepPayload,
  resolvePipelineStepKey,
  traceMetadata,
  type PipelineStep,
} from '@/utils/generationTrace'

// useGenerationPipeline 只消费的 props 子集（结构同构于 ChapterGenerating 的 Props）
interface GenerationPipelineProps {
  status: Chapter['generation_status'] | null
  generationStep?: string | null
  readOnly?: boolean
  generationTraces: ChapterGenerationTrace[]
}

// useGenerationFailure 返回的失败分析子集：currentStepKey 需定位失败节点，stepTooltipText 需失败原因
interface FailureAnalysis {
  isFailureStatus: ComputedRef<boolean>
  terminalFailedTrace: ComputedRef<ChapterGenerationTrace | null>
  stepExists: (key: string) => boolean
  failureReason: ComputedRef<string>
  failureScenario: ComputedRef<{ title: string; description: string }>
}

/**
 * 章节生成步骤状态机：从 status/step 推导当前步骤键（currentStepKey，含失败节点定位），
 * 据此计算各步骤运行态（stepState）、节点级重试可达性（canRetryFromNode）、tooltip 文案
 * （stepTooltipText）。stepExists 与失败 trace 来自 useGenerationFailure，故收 failure 入参。
 */
export function useGenerationPipeline(
  props: GenerationPipelineProps,
  pipelineSteps: ComputedRef<PipelineStep[]>,
  failure: FailureAnalysis,
) {
  const { isFailureStatus, terminalFailedTrace, stepExists, failureReason, failureScenario } = failure

  const parsedStepPayload = computed(() => parseStepPayload(props.generationStep))
  const resolveStepKey = (key?: string | null) => resolvePipelineStepKey(key, pipelineSteps.value)

  const isWaitingForManualConfirm = computed(() => props.status === 'waiting_for_confirm')

  const shouldShowManualConfirmBadge = (key: string) =>
    key === 'wait_for_selection' && isWaitingForManualConfirm.value

  const currentStepKey = computed(() => {
    const traceStepKey = resolveStepKey(terminalFailedTrace.value?.node_key)
    if (isFailureStatus.value && traceStepKey && stepExists(traceStepKey)) {
      return traceStepKey
    }
    const stepKey = resolveStepKey(parsedStepPayload.value.baseKey)
    if (stepKey && pipelineSteps.value.some((item) => item.key === stepKey)) {
      return stepKey
    }
    if (props.status === 'successful') return 'successful'
    if (props.status === 'finalizing') return 'finalize_revision'
    if (props.status === 'evaluating' || props.status === 'evaluation_failed') {
      return 'review_candidates'
    }
    if (props.status === 'selecting' || props.status === 'waiting_for_confirm') {
      return 'wait_for_selection'
    }
    return 'freeze_base_context'
  })

  const latestTraceByStep = computed(() => {
    const traces = new Map<string, ChapterGenerationTrace>()
    for (const trace of props.generationTraces) {
      const key = resolveStepKey(trace.node_key)
      if (stepExists(key)) traces.set(key, trace)
    }
    return traces
  })

  const hasReachedLaterStep = (step: PipelineStep, index: number) => {
    const laterSteps = pipelineSteps.value.slice(index + 1)
    return laterSteps.some((laterStep) => {
      if (step.groupMode === 'parallel' && laterStep.group === step.group) return false
      if (latestTraceByStep.value.has(laterStep.key)) return true
      return laterStep.key === currentStepKey.value
    })
  }

  const stepState = (key: string, index: number) => {
    const step = pipelineSteps.value[index]
    const trace = latestTraceByStep.value.get(key)
    if (trace?.status === 'failed') return { tone: 'failed', label: '失败' }
    if (trace?.status === 'running') return { tone: 'in-progress', label: '进行中' }
    if (
      key === currentStepKey.value
      && (props.status === 'failed' || props.status === 'evaluation_failed')
    ) {
      return { tone: 'failed', label: '失败' }
    }
    if (
      key === currentStepKey.value
      && (key === 'wait_for_selection' || key === 'wait_for_projections')
    ) {
      return { tone: 'in-progress', label: '进行中' }
    }
    if (trace?.status === 'success') {
      const skipped = Boolean(traceMetadata(trace).skip_reason)
      return skipped
        ? { tone: 'skipped', label: '已跳过' }
        : { tone: 'done', label: '已完成' }
    }
    if (key === currentStepKey.value) {
      if (props.status === 'successful' && step?.kind === 'terminal') {
        return { tone: 'done', label: '已完成' }
      }
      return { tone: 'in-progress', label: '进行中' }
    }
    if (props.status === 'successful' || (step && hasReachedLaterStep(step, index))) {
      return step?.optional
        ? { tone: 'skipped', label: '已跳过' }
        : { tone: 'done', label: '已完成' }
    }
    return { tone: 'waiting', label: '等待中' }
  }

  // 失败态下，已完成或失败的节点允许作为节点级重试起点
  const canRetryFromNode = (key: string, index: number) => {
    if (props.readOnly) return false
    if (props.status !== 'failed' && props.status !== 'evaluation_failed') return false
    const tone = stepState(key, index).tone
    return tone === 'failed' || tone === 'done'
  }

  const stepTooltipText = (key: string, index: number) => {
    const state = stepState(key, index)
    const label = PIPELINE_LABELS[key] || STEP_DETAILS[key]?.summary || '当前节点'
    if (state.tone === 'failed') {
      const reason = failureReason.value || failureScenario.value.description
      return `${label}失败：${reason}`
    }
    if (shouldShowManualConfirmBadge(key)) {
      return `${label}已完成：当前待人工确认，可人工编辑草稿或确认定稿。`
    }
    if (state.tone === 'skipped') {
      const trace = latestTraceByStep.value.get(key)
      const reason = trace ? traceMetadata(trace).skip_reason : ''
      return `${label}已跳过：${reason || '本轮配置未启用该节点。'}`
    }
    return STEP_DETAILS[key]?.summary || ''
  }

  return {
    currentStepKey,
    stepState,
    canRetryFromNode,
    shouldShowManualConfirmBadge,
    stepTooltipText,
  }
}
