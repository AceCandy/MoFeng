<!-- AIMETA P=章节工作流生成轨迹回溯|R=节点进度_真实trace详情_失败节点重试|NR=不直接调用API_不持有命令状态|E=component:ChapterGenerating|X=internal|A=workflow-trace|D=vue|S=dom|RD=./README.ai -->
<template>
  <section
    class="chapter-console"
    aria-label="AI章节生成控制台"
  >
    <ChapterPipeline
      :pipeline-steps="pipelineSteps"
      :step-state="stepState"
      :step-tooltip-text="stepTooltipText"
      :should-show-manual-confirm-badge="shouldShowManualConfirmBadge"
      :active-step-key="activeStepKey"
      :can-retry-active-step="canRetryActiveStep"
      :can-cancel="canCancel"
      :pending="pending || retryConfirming"
      @select="selectStep"
      @cancel="emit('cancel')"
      @retry-active-step="retryActiveStep"
    />

    <ChapterDraftPreview
      v-if="props.chapterContentPreview"
      :chapter-content-preview="props.chapterContentPreview"
    />

    <!-- 节点详情面板 -->
    <ChapterStepInspector
      v-if="activeStepDetails && activeStepKey"
      :active-step-details="activeStepDetails"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import ChapterPipeline from './ChapterPipeline.vue'
import ChapterDraftPreview from './ChapterDraftPreview.vue'
import ChapterStepInspector from './ChapterStepInspector.vue'
import type { ChapterWorkflowCommand } from '@/api/chapterWorkflow'
import type { Chapter, ChapterGenerationTrace } from '@/api/novel'
import { useGenerationFailure } from '@/composables/useGenerationFailure'
import { useGenerationPipeline } from '@/composables/useGenerationPipeline'
import { useChapterGenerationTrace } from '@/composables/useChapterGenerationTrace'
import { globalAlert } from '@/composables/useAlert'
import {
  PIPELINE_LABELS,
  traceMetadata,
  type PipelineStep,
} from '@/utils/generationTrace'

interface Props {
  chapterNumber: number | null
  chapterTitle?: string | null
  chapterSummary?: string | null
  chapterContentPreview?: string | null
  status: Chapter['generation_status'] | null
  generationProgress?: number | null
  generationStep?: string | null
  generationStepIndex?: number | null
  generationStepTotal?: number | null
  generationStartedAt?: string | null
  statusUpdatedAt?: string | null
  generationTraces?: ChapterGenerationTrace[]
  readOnly?: boolean
  allowedCommands?: readonly ChapterWorkflowCommand[]
  retryActivityKey?: string | null
  canCancel?: boolean
  pending?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  chapterTitle: '',
  chapterSummary: '',
  chapterContentPreview: '',
  generationTraces: () => [],
  readOnly: true,
  allowedCommands: () => [],
  retryActivityKey: null,
  canCancel: false,
  pending: false,
})

const emit = defineEmits<{
  cancel: []
  retry: []
  retryExternal: [activityKey: string]
  retryProjection: []
}>()

const activeStepKey = ref<string | null>(null)
const retryStepKey = ref<string | null>(null)
const retryConfirming = ref(false)

const selectStep = (key: string, index: number) => {
  if (stepState(key, index).tone !== 'waiting') {
    activeStepKey.value = key
    retryStepKey.value = key
  }
}

const pipelineStep = (
  key: string,
  group: string,
  groupLabel: string,
  options: Partial<PipelineStep> = {},
): PipelineStep => ({
  key,
  label: PIPELINE_LABELS[key] || key,
  kind: 'execution',
  group,
  groupLabel,
  groupMode: 'serial',
  ...options,
})

const pipelineSteps = computed<PipelineStep[]>(() => {
  return [
    pipelineStep('freeze_base_context', 'context', '上下文与规划', { kind: 'system' }),
    pipelineStep('retrieve_context', 'context', '上下文与规划', { retryCommand: 'retry' }),
    pipelineStep('plan_chapter', 'context', '上下文与规划', { retryCommand: 'retry_external' }),
    pipelineStep('generate_candidate_1', 'candidates', '候选版本', { groupMode: 'parallel', retryCommand: 'retry_external' }),
    pipelineStep('generate_candidate_2', 'candidates', '候选版本', { groupMode: 'parallel', optional: true, retryCommand: 'retry_external' }),
    pipelineStep('review_candidates', 'revision', '评审与修订', { retryCommand: 'retry_external' }),
    pipelineStep('refine_candidate', 'revision', '评审与修订', { retryCommand: 'retry_external' }),
    pipelineStep('enhance_content', 'revision', '评审与修订', { optional: true, retryCommand: 'retry_external' }),
    pipelineStep('repair_consistency', 'revision', '评审与修订', { optional: true, retryCommand: 'retry_external' }),
    pipelineStep('optimize_style', 'revision', '评审与修订', { optional: true, retryCommand: 'retry_external' }),
    pipelineStep('enrich_content', 'revision', '评审与修订', { optional: true, retryCommand: 'retry_external' }),
    pipelineStep('compress_candidate', 'revision', '评审与修订', { optional: true, retryCommand: 'retry_external' }),
    pipelineStep('persist_drafts', 'selection', '草稿与选择', { kind: 'system' }),
    pipelineStep('wait_for_selection', 'selection', '草稿与选择', { kind: 'control' }),
    pipelineStep('finalize_revision', 'finalize', '正式定稿', { kind: 'system' }),
    pipelineStep('generate_summary', 'summary', '章节梳理', { retryCommand: 'retry_projection' }),
    pipelineStep('commit_summary_projection', 'summary', '章节梳理', { kind: 'system' }),
    pipelineStep('memory_global_summary', 'memory', '并行投影 · 记忆', { retryCommand: 'retry_projection' }),
    pipelineStep('memory_character_state', 'memory', '并行投影 · 记忆', { retryCommand: 'retry_projection' }),
    pipelineStep('memory_plot_arcs', 'memory', '并行投影 · 记忆', { retryCommand: 'retry_projection' }),
    pipelineStep('memory_chapter_summary', 'memory', '并行投影 · 记忆', { retryCommand: 'retry_projection' }),
    pipelineStep('commit_memory_projection', 'memory', '并行投影 · 记忆', { kind: 'system' }),
    pipelineStep('project_rag', 'rag', '并行投影 · 索引', { retryCommand: 'retry_projection' }),
    pipelineStep('commit_rag_projection', 'rag', '并行投影 · 索引', { kind: 'system' }),
    pipelineStep('foreshadowing_candidate_review', 'foreshadowing', '并行投影 · 伏笔', { retryCommand: 'retry_projection' }),
    pipelineStep('foreshadowing_status_judge', 'foreshadowing', '并行投影 · 伏笔', { retryCommand: 'retry_projection' }),
    pipelineStep('commit_foreshadowing_projection', 'foreshadowing', '并行投影 · 伏笔', { kind: 'system' }),
    pipelineStep('wait_for_projections', 'completion', '汇合与完成', { kind: 'control' }),
    pipelineStep('reconcile_projections', 'completion', '汇合与完成', { kind: 'control' }),
    pipelineStep('successful', 'completion', '汇合与完成', { kind: 'terminal' }),
  ]
})

const {
  isFailureStatus,
  terminalFailedTrace,
  failureReason,
  failureScenario,
  stepExists,
} = useGenerationFailure(props, pipelineSteps)

const {
  currentStepKey,
  stepState,
  shouldShowManualConfirmBadge,
  stepTooltipText,
} = useGenerationPipeline(props, pipelineSteps, {
  isFailureStatus,
  terminalFailedTrace,
  stepExists,
  failureReason,
  failureScenario,
})

watch(
  () => currentStepKey.value,
  (newKey) => {
    activeStepKey.value = newKey
    retryStepKey.value = null
  },
  { immediate: true }
)

const { activeStepDetails, activeTrace } = useChapterGenerationTrace(props, {
  pipelineSteps,
  activeStepKey,
  currentStepKey,
  isFailureStatus,
  terminalFailedTrace,
  failureReason,
  failureScenario,
})

const activeRetryCommand = computed(() =>
  pipelineSteps.value.find((step) => step.key === activeStepKey.value)?.retryCommand ?? null,
)

const resolvedRetryCommand = computed(() => {
  if (activeRetryCommand.value !== 'retry_projection') return activeRetryCommand.value
  const metadata = activeTrace.value ? traceMetadata(activeTrace.value) : {}
  if (
    props.allowedCommands.includes('retry_external')
    && props.retryActivityKey !== null
    && metadata.activity_key === props.retryActivityKey
  ) return 'retry_external'
  return activeRetryCommand.value
})

const canRetryActiveStep = computed(() => {
  const command = resolvedRetryCommand.value
  if (
    command === null
    || retryStepKey.value !== activeStepKey.value
    || activeStepDetails.value?.status !== '失败'
    || !props.allowedCommands.includes(command)
  ) return false
  if (command === 'retry_external') {
    return props.retryActivityKey !== null
      && (activeRetryCommand.value === 'retry_projection'
        || activeStepKey.value === currentStepKey.value)
  }
  if (command === 'retry') return activeStepKey.value === currentStepKey.value
  const metadata = activeTrace.value ? traceMetadata(activeTrace.value) : {}
  return metadata.remote_call !== false
})

const retryActiveStep = async () => {
  if (
    !canRetryActiveStep.value
    || props.pending
    || retryConfirming.value
  ) return
  retryConfirming.value = true
  try {
    if (resolvedRetryCommand.value === 'retry') {
      emit('retry')
      return
    }
    if (resolvedRetryCommand.value === 'retry_projection') {
      emit('retryProjection')
      return
    }
    if (props.retryActivityKey === null) return
    const confirmed = await globalAlert.showConfirm(
      '上一次外部模型调用可能已经发生。再次提交可能产生重复调用与费用，确认承担该风险后重试吗？',
      '确认外部重试风险',
    )
    if (confirmed) emit('retryExternal', props.retryActivityKey)
  } finally {
    retryConfirming.value = false
  }
}

</script>

<style scoped>
.chapter-console {
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-4);
}

.chapter-console__header,
.chapter-console__summary-card,
.chapter-console__task-card,
.chapter-console__explain-card,
.chapter-console__log {
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-sm);
  background: color-mix(in srgb, var(--md-surface) 96%, transparent);
  box-shadow: var(--md-elevation-paper-1); /* 浮起纸影 */
}

.chapter-console__header {
  padding: var(--md-spacing-4);
  display: flex;
  justify-content: space-between;
  gap: var(--md-spacing-3);
  align-items: flex-start;
}

.chapter-console__title {
  margin: 0;
  color: var(--md-on-surface);
  font-size: var(--md-title-large);
}

.chapter-console__status-line {
  margin: 8px 0 0;
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.chapter-console__state-badge {
  display: inline-flex;
  align-items: center;
  height: 30px;
  padding: 0 12px;
  border-radius: var(--md-radius-xs);
  background: var(--md-primary-container);
  color: var(--md-on-primary-container);
  font-size: var(--md-label-medium);
  font-weight: 700;
  white-space: nowrap;
}

.chapter-console__summary-card,
.chapter-console__explain-card,
.chapter-console__log {
  padding: var(--md-spacing-4);
}

.chapter-console__summary-label {
  margin: 0;
  color: var(--md-on-surface-variant);
  font-size: var(--md-label-medium);
}

.chapter-console__summary-body {
  margin: var(--md-spacing-2) 0 0;
  color: var(--md-on-surface);
  line-height: 1.8;
}

.chapter-console--read-only {
  gap: var(--md-spacing-3);
}

.chapter-console--read-only .chapter-console__pipeline-card,
.chapter-console--read-only .chapter-console__inspector-card {
  border-radius: 0;
  box-shadow: none;
}

.chapter-console--read-only .chapter-console__pipeline-card {
  padding: var(--md-spacing-3) var(--md-spacing-4);
  background-color: color-mix(in srgb, var(--md-surface-container-low) 66%, var(--md-surface));
}

.chapter-console__log summary {
  cursor: pointer;
  color: var(--md-primary-dark);
  font-weight: 600;
}

.chapter-console__log-body {
  margin-top: var(--md-spacing-3);
  border-top: 1px solid var(--md-outline-variant);
  padding-top: var(--md-spacing-3);
}

.chapter-console__log-body p {
  margin: 0;
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
  line-height: 1.7;
}

.chapter-console__log-body p + p {
  margin-top: 4px;
}

.chapter-console__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--md-spacing-2);
}

.chapter-console__actions .is-enabled {
  border-color: color-mix(in srgb, var(--md-success) 28%, var(--md-outline-variant));
}

@media (max-width: 833px) {
  .chapter-console__pipeline-meta {
    margin-top: 6px;
    align-self: flex-start;
    justify-content: flex-start;
  }

  .chapter-console__actions {
    flex-direction: column;
  }

  .chapter-console__actions .md-btn {
    width: 100%;
  }
}

@keyframes fadeInTooltip {
  to {
    opacity: 1;
  }
}
</style>
