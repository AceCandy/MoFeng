import { computed, type ComputedRef } from 'vue'
import type { Chapter, ChapterGenerationTrace } from '@/api/novel'
import {
  STEP_DETAILS,
  PIPELINE_LABELS,
  normalizePipelineStepKey,
  parseStepPayload,
} from '@/utils/generationTrace'

interface PipelineStep {
  key: string
  label: string
}

// useGenerationPipeline 只消费的 props 子集（结构同构于 ChapterGenerating 的 Props）
interface GenerationPipelineProps {
  status: Chapter['generation_status'] | null
  generationStep?: string | null
  readOnly?: boolean
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

  const isWaitingForManualConfirm = computed(() => props.status === 'waiting_for_confirm')

  const shouldShowManualConfirmBadge = (key: string) =>
    key === 'review_refinement' && isWaitingForManualConfirm.value

  const currentStepKey = computed(() => {
    const traceStepKey = normalizePipelineStepKey(terminalFailedTrace.value?.node_key)
    if (isFailureStatus.value && traceStepKey && stepExists(traceStepKey)) {
      return traceStepKey
    }
    if (props.status === 'evaluation_failed') {
      return 'quality_review'
    }
    const stepKey = normalizePipelineStepKey(parsedStepPayload.value.baseKey)
    if (stepKey === 'waiting_for_confirm' || stepKey === 'selecting_version') {
      return 'review_refinement'
    }
    if (props.status === 'finalizing') {
      if (stepKey === 'confirm_finalize') {
        return 'real_summary'
      }
      if (stepKey && pipelineSteps.value.some((item) => item.key === stepKey)) {
        return stepKey
      }
      return 'real_summary'
    }
    if (stepKey && pipelineSteps.value.some((item) => item.key === stepKey)) {
      return stepKey
    }

    if (props.status === 'failed') {
      const errorMsg = (props.generationStep || '').toLowerCase()
      if (errorMsg.includes('版本') || errorMsg.includes('字数') || errorMsg.includes('生成章节') || errorMsg.includes('draft')) {
        return 'draft_generation'
      }
      if (errorMsg.includes('评审') || errorMsg.includes('评分') || errorMsg.includes('连贯') || errorMsg.includes('evaluation') || errorMsg.includes('review')) {
        return 'quality_review'
      }
      if (errorMsg.includes('润色') || errorMsg.includes('修复') || errorMsg.includes('optimization') || errorMsg.includes('refinement')) {
        return 'review_refinement'
      }
      if (errorMsg.includes('保存') || errorMsg.includes('存储') || errorMsg.includes('save') || errorMsg.includes('persist')) {
        return 'save_draft'
      }
      if (errorMsg.includes('设定') || errorMsg.includes('retrieval') || errorMsg.includes('rag')) {
        return 'rag_retrieval'
      }
      if (errorMsg.includes('剧情') || errorMsg.includes('规划') || errorMsg.includes('director')) {
        return 'director_mission'
      }
      if (errorMsg.includes('前文') || errorMsg.includes('上下文') || errorMsg.includes('context')) {
        return 'context_prep'
      }
      return 'draft_generation'
    }

    if (props.status === 'evaluating') return 'quality_review'
    if (props.status === 'selecting' || props.status === 'waiting_for_confirm') return 'review_refinement'
    return 'context_prep'
  })

  const currentStepIndex = computed(() => {
    const index = pipelineSteps.value.findIndex((item) => item.key === currentStepKey.value)
    return index >= 0 ? index : 0
  })

  const stepState = (key: string, index: number) => {
    if (props.status === 'failed' || props.status === 'evaluation_failed') {
      if (key === currentStepKey.value) {
        return { tone: 'failed', label: '失败' }
      }
      if (index < currentStepIndex.value) {
        return { tone: 'done', label: '已完成' }
      }
      return { tone: 'waiting', label: '等待中' }
    }

    if (props.readOnly && props.status === 'waiting_for_confirm') {
      if (index <= currentStepIndex.value) {
        return { tone: 'done', label: '已完成' }
      }
      return { tone: 'waiting', label: '等待中' }
    }

    if (index < currentStepIndex.value) {
      return { tone: 'done', label: '已完成' }
    }
    if (index === currentStepIndex.value) {
      return { tone: 'in-progress', label: '进行中' }
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
