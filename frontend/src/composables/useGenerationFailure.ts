import { computed, type ComputedRef } from 'vue'
import type { Chapter, ChapterGenerationTrace } from '@/api/novel'
import { formatChapterGenerationError } from '@/utils/chapter'
import {
  parseStepPayload,
  resolvePipelineStepKey,
  type PipelineStep,
} from '@/utils/generationTrace'

// 章节生成状态（供子组件复用类型，避免直接 import @/api/novel）
export type GenerationStatus = Chapter['generation_status']

// useGenerationFailure 只消费的 props 子集（结构同构于 ChapterGenerating 的 Props）
interface GenerationFailureProps {
  status: Chapter['generation_status'] | null
  generationStep?: string | null
  generationTraces: ChapterGenerationTrace[]
}

/**
 * 章节生成失败态分析：从 trace/step 提取失败原因（failureReason）与兜底场景（failureScenario），
 * stepExists 借组件的 pipelineSteps 判断步骤键合法性，因此收 pipelineSteps 入参。
 * isFailureStatus/terminalFailedTrace/stepExists 同时返回，供组件
 * currentStepKey/activeTrace/activeStepDetails 等步骤状态机逻辑复用。
 */
export function useGenerationFailure(
  props: GenerationFailureProps,
  pipelineSteps: ComputedRef<PipelineStep[]>,
) {
  const stepExists = (key: string) => pipelineSteps.value.some((item) => item.key === key)

  const isFailureStatus = computed(
    () => props.status === 'failed' || props.status === 'evaluation_failed',
  )

  const terminalFailedTrace = computed(() => {
    return [...props.generationTraces].reverse().find((trace) => trace.status === 'failed') ?? null
  })

  const failureReason = computed(() => {
    const traceError = terminalFailedTrace.value
      ?.error
      ?.trim()
    if (isFailureStatus.value && traceError) {
      return formatChapterGenerationError(traceError)
    }

    const step = (props.generationStep || '').trim()
    if (!step) {
      return ''
    }

    const parsed = parseStepPayload(step)
    let rawError = step
    if (parsed.meta.error) {
      rawError = parsed.meta.error
    } else if (
      parsed.baseKey
      && stepExists(resolvePipelineStepKey(parsed.baseKey, pipelineSteps.value))
    ) {
      const pipeIdx = step.indexOf('|')
      if (pipeIdx >= 0) {
        rawError = step.slice(pipeIdx + 1)
      }
    }

    if (
      isFailureStatus.value &&
      (parsed.baseKey === 'failed' || parsed.baseKey === 'evaluation_failed') &&
      !parsed.meta.error
    ) {
      return ''
    }

    // 仅在非明确失败状态下，才利用正则过滤标准运行步骤名
    if (!isFailureStatus.value) {
      if (/^[a-z_]+(?:\|.*)?$/i.test(step)) {
        return ''
      }
    }

    return formatChapterGenerationError(rawError)
  })

  const failureScenario = computed(() => {
    const step = (props.generationStep || '').toLowerCase()

    if (failureReason.value) {
      return {
        title: '已定位错误原因',
        description: failureReason.value,
      }
    }

    if (props.status === 'evaluation_failed') {
      return {
        title: 'AI评审失败',
        description: '评审节点未返回更具体的失败原因，请查看节点详情、后端日志，或重新评审。',
      }
    }

    if (step.includes('timeout') || step.includes('time_out')) {
      return {
        title: '模型超时',
        description: '模型响应超时，可能是瞬时拥塞或模型负载过高。',
      }
    }

    if (step.includes('context') || step.includes('length') || step.includes('token')) {
      return {
        title: '上下文过长',
        description: '本章输入上下文超出稳定范围，请精简前文摘要后再点击重试。',
      }
    }

    if (step.includes('persist') || step.includes('save')) {
      return {
        title: '保存失败',
        description: '草稿生成后写入版本库失败，请确认当前章节状态后再点击重试生成。',
      }
    }

    return {
      title: '生成流程中断',
      description: '本轮草稿生成未完成，可直接重试本章生成。',
    }
  })

  return {
    isFailureStatus,
    terminalFailedTrace,
    failureReason,
    failureScenario,
    stepExists,
  }
}
