<!-- AIMETA P=章节工作流生成轨迹回溯|R=节点进度_真实trace详情_失败节点重试_人工确认转发|NR=不直接调用API_不持有命令状态|E=component:ChapterGenerating|X=internal|A=workflow-trace|D=vue|S=dom|RD=./README.ai -->
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
      :can-confirm-manual="manualConfirmCandidateId !== null"
      :can-cancel="canCancel"
      :pending="pending || retryConfirming"
      :generation-progress="generationProgress"
      :is-generating="isActivelyGenerating"
      :stage-label="stageLabel"
      @select="selectStep"
      @cancel="emit('cancel')"
      @retry-active-step="retryActiveStep"
      @confirm-manual="confirmManual"
    />

    <!-- 研墨舞台：生成中尚未收到正文预览时，稿纸待写行随进度逐行点亮，
         承接全产品最长的等待「情绪谷」；内容到达后即由描红预览接棒 -->
    <Transition name="chapter-console__stage-quiet">
      <article
        v-if="showDraftStage"
        class="chapter-console__draft-stage"
        data-provenance="ai"
        aria-label="章节草稿研墨舞台"
      >
        <div class="chapter-console__draft-stage-lines" aria-hidden="true">
          <span
            v-for="row in DRAFT_STAGE_ROWS"
            :key="row"
            class="chapter-console__draft-stage-line"
            :class="{ 'is-lit': row <= litStageRows }"
            :style="{ transitionDelay: `${(row - 1) * 100}ms` }"
          ></span>
        </div>
      </article>
    </Transition>

    <ChapterDraftPreview
      v-if="props.chapterContentPreview"
      :chapter-content-preview="props.chapterContentPreview"
      :is-generating="isActivelyGenerating"
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
  CHAPTER_WORKFLOW_STEPS,
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
  manualConfirmCandidateId?: number | null
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
  manualConfirmCandidateId: null,
})

const emit = defineEmits<{
  cancel: []
  retry: []
  retryExternal: [activityKey: string]
  retryProjection: []
  confirmManual: [versionId: number]
}>()

const activeStepKey = ref<string | null>(null)
const retryConfirming = ref(false)

const selectStep = (key: string, index: number) => {
  if (stepState(key, index).tone !== 'waiting') {
    activeStepKey.value = key
  }
}

const pipelineSteps = computed<PipelineStep[]>(() =>
  CHAPTER_WORKFLOW_STEPS.map((step) => ({ ...step })),
)

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

// 研墨舞台亮台条件：仅工作流活跃推进（generating/evaluating/finalizing）时呈现；
// 待人工确认/失败/成功/空闲一律安静退场，失败与取消呈现维持 ChapterWorkflowPanel 既有契约
const isActivelyGenerating = computed(
  () => props.status === 'generating' || props.status === 'evaluating' || props.status === 'finalizing',
)

// 研墨进度数值：与后端 snapshot.progress 同标度（0-100 整数），钳制兜底
const inkProgressValue = computed(() => {
  const raw = props.generationProgress
  if (typeof raw !== 'number' || !Number.isFinite(raw)) return 0
  return Math.min(100, Math.max(0, Math.round(raw)))
})

// 阶段小签：取当前推进节点的数据文案（如「润色推荐版本」），缺省回落「研墨」
const stageLabel = computed(() => {
  const key = currentStepKey.value
  const label = key
    ? pipelineSteps.value.find((step) => step.key === key)?.label
    : null
  return label || '研墨'
})

// 待写行：固定 6 行稿纸行，点亮行数随研墨进度联动，起笔即点亮第一行
const DRAFT_STAGE_ROWS = [1, 2, 3, 4, 5, 6]
const showDraftStage = computed(
  () => isActivelyGenerating.value && !(props.chapterContentPreview || '').trim(),
)
const litStageRows = computed(() =>
  Math.max(1, Math.ceil((inkProgressValue.value / 100) * DRAFT_STAGE_ROWS.length)),
)

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
  return command === 'retry_projection' || metadata.remote_call !== false
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

const confirmManual = () => {
  if (props.manualConfirmCandidateId === null || props.pending) return
  emit('confirmManual', props.manualConfirmCandidateId)
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

/* ============================================
   研墨舞台（生成中等待区）：熟宣稿纸 + 左右朱丝栏 +
   横向描红行线底，待写行随研墨进度逐行点亮。
   行线只铺在本容器内（行线不出稿纸），结构面不出现。
   ============================================ */
.chapter-console__draft-stage {
  --paper-line: 27px; /* 稿纸行线节奏，同 chapter-paper 行笺 */
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-sm);
  box-shadow: var(--md-elevation-paper-1); /* 浮起纸影 */
  background:
    /* 左右朱丝栏竖线（各 1px 描红边栏，贴容器左右缘） */
    linear-gradient(to bottom, var(--md-miaohong-line-strong), var(--md-miaohong-line-strong)) left top / 1px 100% no-repeat local,
    linear-gradient(to bottom, var(--md-miaohong-line-strong), var(--md-miaohong-line-strong)) right top / 1px 100% no-repeat local,
    /* 横向描红行线底，--paper-line 循环 */
    repeating-linear-gradient(
      to bottom,
      transparent 0,
      transparent calc(var(--paper-line) - 1px),
      var(--md-miaohong-line) calc(var(--paper-line) - 1px),
      var(--md-miaohong-line) var(--paper-line)
    ) local,
    /* 熟宣温润底色 */
    linear-gradient(var(--md-surface), var(--md-surface));
  background-attachment: local;
  padding: var(--md-spacing-4) var(--md-spacing-8);
}

.chapter-console__draft-stage-lines {
  display: flex;
  flex-direction: column;
}

/* 待写行：默认隐于行线底，点亮时 opacity 0→1 + translateY 4px→0，
   行线加浓并泛 wash 微光（stagger 由各行 transition-delay 级进） */
.chapter-console__draft-stage-line {
  position: relative;
  height: var(--paper-line);
  opacity: 0;
  transform: translateY(4px);
  transition:
    opacity var(--md-duration-medium) var(--md-easing-standard),
    transform var(--md-duration-medium) var(--md-easing-standard),
    background-color var(--md-duration-medium) var(--md-easing-standard);
}

.chapter-console__draft-stage-line::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 1px;
  background-color: var(--md-miaohong-line-strong);
}

.chapter-console__draft-stage-line.is-lit {
  opacity: 1;
  transform: translateY(0);
  background-color: var(--md-miaohong-wash);
}

/* 舞台进退场：仅透明度淡入淡出，生成完成或空闲时安静退场 */
.chapter-console__stage-quiet-enter-active,
.chapter-console__stage-quiet-leave-active {
  transition: opacity var(--md-duration-medium) var(--md-easing-standard);
}

.chapter-console__stage-quiet-enter-from,
.chapter-console__stage-quiet-leave-to {
  opacity: 0;
}

@media (max-width: 833px) {
  .chapter-console__draft-stage {
    padding: var(--md-spacing-3) var(--md-spacing-4);
  }

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

@media (prefers-reduced-motion: reduce) {
  /* 研墨舞台直落终态：静态稿纸，待写行与舞台进退场均无过渡 */
  .chapter-console__draft-stage-line,
  .chapter-console__stage-quiet-enter-active,
  .chapter-console__stage-quiet-leave-active {
    transition: none;
  }
}
</style>
