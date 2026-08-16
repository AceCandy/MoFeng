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
 * 据此计算各步骤运行态（stepState）和 tooltip 文案（stepTooltipText）。节点重试能力由
 * 调用方根据真实远程 activity 与服务端 allowed command 决定。
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
    const isProjectionStep = ['summary', 'memory', 'rag', 'foreshadowing'].includes(
      step.group || '',
    )
    return laterSteps.some((laterStep) => {
      if (step.groupMode === 'parallel' && laterStep.group === step.group) return false
      if (isProjectionStep && laterStep.group !== step.group) return false
      if (latestTraceByStep.value.has(laterStep.key)) return true
      return laterStep.key === currentStepKey.value
    })
  }

  const stepGroupFailed = (step: PipelineStep) =>
    Boolean(step.group) && pipelineSteps.value.some((candidate) =>
      candidate.group === step.group
      && latestTraceByStep.value.get(candidate.key)?.status === 'failed',
    )

  const skipLabel = (key: string) => {
    if (key === 'project_rag' || key === 'commit_rag_projection') return '未启用索引'
    if (key === 'foreshadowing_candidate_review') return '无新增伏笔'
    if (key === 'foreshadowing_status_judge') return '无活跃伏笔'
    if (key === 'generate_candidate_2') return '仅生成一个候选'
    if (key === 'compress_candidate') return '正文未超字数'
    return '本轮未启用'
  }

  const previousRemoteStepRunning = (step: PipelineStep, index: number) =>
    step.kind === 'system'
    && pipelineSteps.value.slice(0, index).some((candidate) =>
      candidate.group === step.group
      && candidate.kind === 'execution'
      && latestTraceByStep.value.get(candidate.key)?.status === 'running',
    )

  const stepState = (key: string, index: number) => {
    const step = pipelineSteps.value[index]
    const trace = latestTraceByStep.value.get(key)
    if (trace?.status === 'failed') return { tone: 'failed', label: '失败' }
    if (
      (key === 'wait_for_selection' || key === 'wait_for_projections')
      && (trace?.status === 'running' || key === currentStepKey.value)
    ) {
      return {
        tone: 'pending',
        label: key === 'wait_for_selection' ? '等待你确认' : '等待各投影',
      }
    }
    if (trace?.status === 'running' && step && previousRemoteStepRunning(step, index)) {
      return { tone: 'pending', label: '等待生成结果' }
    }
    if (trace?.status === 'running') return { tone: 'in-progress', label: '进行中' }
    if (
      key === currentStepKey.value
      && (props.status === 'failed' || props.status === 'evaluation_failed')
    ) {
      return { tone: 'failed', label: '失败' }
    }
    if (trace?.status === 'success') {
      const skipped = Boolean(traceMetadata(trace).skip_reason)
      return skipped
        ? { tone: 'skipped', label: skipLabel(key) }
        : { tone: 'done', label: '已完成' }
    }
    if (key === currentStepKey.value) {
      if (props.status === 'successful' && step?.kind === 'terminal') {
        return { tone: 'done', label: '已完成' }
      }
      return { tone: 'in-progress', label: '进行中' }
    }
    if (props.status === 'successful' || (step && hasReachedLaterStep(step, index))) {
      if (step?.optional && props.status !== 'successful' && stepGroupFailed(step)) {
        return { tone: 'waiting', label: '状态待确认' }
      }
      return step?.optional
        ? { tone: 'skipped', label: skipLabel(key) }
        : { tone: 'done', label: '已完成' }
    }
    if (
      currentStepKey.value === 'wait_for_projections'
      && ['summary', 'memory', 'rag', 'foreshadowing'].includes(step?.group || '')
    ) {
      return { tone: 'pending', label: '等待执行' }
    }
    return { tone: 'waiting', label: '等待中' }
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
      return `${label}已跳过：${state.label}。`
    }
    if (state.tone === 'pending') {
      return `${label}：${state.label}。`
    }
    return STEP_DETAILS[key]?.summary || ''
  }

  return {
    currentStepKey,
    stepState,
    shouldShowManualConfirmBadge,
    stepTooltipText,
  }
}
