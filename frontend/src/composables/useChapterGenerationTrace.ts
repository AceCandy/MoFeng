import { computed, type ComputedRef, type Ref } from 'vue'
import type { ChapterGenerationTrace } from '@/api/novel'
import {
  STEP_DETAILS,
  PIPELINE_LABELS,
  TRACE_STATUS_LABELS,
  resolvePipelineStepKey,
  traceMetadata,
  resolveTraceDurationMs,
  formatSystemDuration,
  traceUsesLlm,
  formatTraceInputs,
  formatTraceActions,
  formatTraceOutputs,
  resolveTraceCallType,
  type ActiveStepDetails,
  type PipelineStep,
} from '@/utils/generationTrace'

// useChapterGenerationTrace 只消费的 props 子集（结构同构于 ChapterGenerating 的 Props）
interface GenerationTraceProps {
  generationTraces: ChapterGenerationTrace[]
}

// 步骤状态机 + 失败分析依赖，均由 ChapterGenerating 透传（响应式引用）：
// activeStepKey/currentStepKey 定位当前节点，isFailureStatus/terminalFailedTrace/failureReason/
// failureScenario 提供失败兜底与原因。
interface TraceDeps {
  pipelineSteps: ComputedRef<PipelineStep[]>
  activeStepKey: Ref<string | null>
  currentStepKey: ComputedRef<string>
  isFailureStatus: ComputedRef<boolean>
  terminalFailedTrace: ComputedRef<ChapterGenerationTrace | null>
  failureReason: ComputedRef<string>
  failureScenario: ComputedRef<{ title: string; description: string }>
}

/**
 * 章节生成 trace 组装：从 generationTraces 过滤当前节点 trace（activeStepTraces），解析展示用
 * trace（activeTrace，失败态优先取失败 trace），并据此组装节点详情面板数据（activeStepDetails：
 * label/summary/callType/llmUsage/status/systemDuration/inputs/actions/outputs）。步骤键与失败
 * 分析来自调用方透传，纯响应式组装，零自身状态。activeStepTraces/activeTrace 为内部中间量。
 */
export function useChapterGenerationTrace(props: GenerationTraceProps, deps: TraceDeps) {
  const {
    pipelineSteps,
    activeStepKey,
    currentStepKey,
    isFailureStatus,
    terminalFailedTrace,
    failureReason,
    failureScenario,
  } = deps

  const activeStepTraces = computed(() => {
    const key = activeStepKey.value || currentStepKey.value
    return props.generationTraces.filter(
      (trace) => resolvePipelineStepKey(trace.node_key, pipelineSteps.value) === key,
    )
  })

  const activeTrace = computed(() => {
    const key = activeStepKey.value || currentStepKey.value
    const traces = activeStepTraces.value
    if (isFailureStatus.value && key === currentStepKey.value) {
      const failedTrace = [...traces].reverse().find((trace) => trace.status === 'failed')
      if (failedTrace) return failedTrace
      return terminalFailedTrace.value
    }
    return traces.length ? traces[traces.length - 1] : null
  })

  const activeStepDetails = computed<ActiveStepDetails>(() => {
    const key = activeStepKey.value || currentStepKey.value
    const stepConfig = STEP_DETAILS[key] ?? {
      summary: '正在处理当前章节请求。',
      inputs: '系统自动组装',
      outputs: '处理中',
      next: '请稍候',
    }
    const trace = activeTrace.value

    if (trace) {
      const metadata = traceMetadata(trace)
      return {
        label: PIPELINE_LABELS[key] || trace.node_label || stepConfig.summary,
        summary: metadata.summary || (trace.status === 'failed'
          ? `真实运行记录：${trace.node_label || stepConfig.summary} 执行失败`
          : `真实运行记录：${trace.node_label || stepConfig.summary}`),
        callType: resolveTraceCallType(trace),
        llmUsage: traceUsesLlm(trace) ? '是' : '否',
        status: TRACE_STATUS_LABELS[trace.status] || trace.status || '',
        systemDuration: formatSystemDuration(resolveTraceDurationMs(trace)),
        inputs: formatTraceInputs(trace),
        actions: formatTraceActions(trace),
        outputs: formatTraceOutputs(trace),
      }
    }

    if (isFailureStatus.value && key === currentStepKey.value) {
      const label = PIPELINE_LABELS[key] || stepConfig.summary
      const reason = failureReason.value || failureScenario.value.description
      return {
        label,
        summary: `${label}执行失败，当前章节流程已停止。`,
        callType: '失败节点',
        llmUsage: key === 'quality_review' || key === 'review_refinement' ? '是' : '待确认',
        status: '失败',
        systemDuration: '未记录',
        inputs: stepConfig.inputs,
        actions: '该失败节点未返回完整 trace，前端已按章节失败状态显示兜底详情。',
        outputs: `错误：\n${reason}`,
      }
    }

    return {
      label: PIPELINE_LABELS[key] || stepConfig.summary,
      summary: `暂未收到 ${PIPELINE_LABELS[key] || stepConfig.summary} 的真实运行记录`,
      callType: '等待记录',
      llmUsage: '待记录',
      status: '',
      systemDuration: '未记录',
      inputs: '该节点暂未收到真实运行记录。',
      actions: '该节点暂未收到真实运行记录。',
      outputs: '该节点暂未收到真实运行记录。',
    }
  })

  return { activeStepDetails, activeTrace }
}
