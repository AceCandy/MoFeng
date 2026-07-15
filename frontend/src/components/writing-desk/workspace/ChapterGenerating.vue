<!-- AIMETA P=生成中_章节生成进度|R=进度展示_流式输出|NR=不含生成逻辑|E=component:ChapterGenerating|X=internal|A=生成状态|D=vue|S=dom|RD=./README.ai -->
<template>
  <section
    class="chapter-console"
    :class="{ 'chapter-console--read-only': props.readOnly }"
    aria-label="AI章节生成控制台"
  >
    <ChapterPipeline
      :pipeline-steps="pipelineSteps"
      :step-state="stepState"
      :step-tooltip-text="stepTooltipText"
      :should-show-manual-confirm-badge="shouldShowManualConfirmBadge"
      :can-retry-from-node="canRetryFromNode"
      :active-step-key="activeStepKey"
      :status="props.status"
      :read-only="props.readOnly"
      :generating-chapter="props.generatingChapter"
      :chapter-number="props.chapterNumber"
      :elapsed-text="elapsedText"
      :eta-text="etaText"
      @select="selectStep"
      @retry-from-node="(payload) => emit('retryFromNode', payload)"
    />

    <!-- 失败状态展示区域 -->
    <ChapterFailedVersions
      v-if="!props.readOnly && (props.status === 'failed' || props.status === 'evaluation_failed')"
      :status="props.status"
      :failed-version-cards="failedVersionCards"
      :generating-chapter="props.generatingChapter"
      :chapter-number="props.chapterNumber"
      @show-version-detail="(index) => emit('showVersionDetail', index)"
      @evaluate-chapter="() => emit('evaluateChapter')"
      @failed-generate-action="handleFailedGenerateAction"
    />

    <!-- 正常生成中状态展示草稿预览卡片 -->
    <ChapterDraftPreview
      v-else-if="!props.readOnly"
      :chapter-content-preview="props.chapterContentPreview"
    />

    <!-- 节点详情面板 -->
    <ChapterStepInspector
      v-if="activeStepDetails && (!props.readOnly || activeStepKey)"
      :active-step-details="activeStepDetails"
    />

    <footer
      v-if="!props.readOnly && props.status !== 'failed' && props.status !== 'evaluation_failed'"
      class="chapter-console__actions"
    >
      <button type="button" class="md-btn md-btn-outlined md-ripple" @click="moveToBackground">
        转入后台生成
      </button>
      <button type="button" class="md-btn md-btn-outlined md-ripple" @click="cancelGeneration">
        取消生成
      </button>
      <button
        type="button"
        class="md-btn md-btn-tonal md-ripple"
        :class="{ 'is-enabled': notifyWhenDone }"
        @click="toggleNotify"
      >
        {{ notifyWhenDone ? '已开启完成通知' : '完成后通知我' }}
      </button>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import ChapterPipeline from './ChapterPipeline.vue'
import ChapterDraftPreview from './ChapterDraftPreview.vue'
import ChapterFailedVersions from './ChapterFailedVersions.vue'
import ChapterStepInspector from './ChapterStepInspector.vue'
import type { Chapter, ChapterGenerationTrace, ChapterVersion } from '@/api/novel'
import { globalAlert } from '@/composables/useAlert'
import { useGenerationTiming } from '@/composables/useGenerationTiming'
import { useGenerationFailure } from '@/composables/useGenerationFailure'
import { useGenerationPipeline } from '@/composables/useGenerationPipeline'
import { useChapterGenerationTrace } from '@/composables/useChapterGenerationTrace'

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
  generatingChapter?: number | null
  availableVersions?: ChapterVersion[]
  selectedVersionIndex?: number
  readOnly?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  chapterTitle: '',
  chapterSummary: '',
  chapterContentPreview: '',
  generationTraces: () => [],
  generatingChapter: null,
  availableVersions: () => [],
  selectedVersionIndex: 0,
  readOnly: false,
})

const emit = defineEmits(['generateChapter', 'showVersionDetail', 'evaluateChapter', 'retryFromNode'])

const notifyWhenDone = ref(false)

const activeStepKey = ref<string | null>(null)

const { elapsedText, etaText } = useGenerationTiming(props)

const selectStep = (key: string, index: number) => {
  if (stepState(key, index).tone !== 'waiting') {
    activeStepKey.value = key
  }
}

const pipelineSteps = computed(() => {
  if (props.status === 'finalizing') {
    return [
      { key: 'real_summary', label: '生成章节梳理' },
      { key: 'finalize_memory', label: '更新记忆快照' },
      { key: 'chapter_ingest', label: '写入章节索引' },
      { key: 'foreshadowing_sync', label: '同步伏笔' },
    ]
  }
  return [
    { key: 'context_prep', label: '整理前文' },
    { key: 'director_mission', label: '规划剧情' },
    { key: 'rag_retrieval', label: '调用设定' },
    { key: 'draft_generation', label: '生成正文' },
    { key: 'quality_review', label: 'AI评审' },
    { key: 'review_refinement', label: '修复润色' },
  ]
})

const {
  isFailureStatus,
  terminalFailedTrace,
  failureReason,
  failureScenario,
  failedVersionCards,
  stepExists,
} = useGenerationFailure(props, pipelineSteps)

const {
  currentStepKey,
  stepState,
  canRetryFromNode,
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
    if (!props.readOnly) {
      activeStepKey.value = newKey
    }
  },
  { immediate: true }
)

watch(
  () => props.readOnly,
  (readOnly) => {
    if (!readOnly && !activeStepKey.value) {
      activeStepKey.value = currentStepKey.value
    }
  },
)

const { activeStepDetails } = useChapterGenerationTrace(props, {
  activeStepKey,
  currentStepKey,
  isFailureStatus,
  terminalFailedTrace,
  failureReason,
  failureScenario,
})

const moveToBackground = () => {
  globalAlert.showToast('已切换为后台生成，章节完成后会在列表中显示状态。', 'success')
}

const handleFailedGenerateAction = async () => {
  if (props.chapterNumber === null) return
  if (props.status === 'evaluation_failed') {
    const confirmed = await globalAlert.showConfirm(
      '重新生成会放弃本轮已生成的候选正文，并用新生成结果替换它们。确认要重新生成本章吗？',
      '放弃本轮草稿',
    )
    if (!confirmed) return
  }
  emit('generateChapter', props.chapterNumber)
}

const cancelGeneration = async () => {
  const confirmed = await globalAlert.showConfirm(
    '当前版本暂不支持中途取消生成。你可以先转入后台，或等待本轮生成完成后再处理。',
    '暂不支持取消',
  )
  if (confirmed) {
    globalAlert.showToast('建议使用"转入后台生成"避免阻塞当前写作。', 'info')
  }
}

const toggleNotify = () => {
  notifyWhenDone.value = !notifyWhenDone.value
  localStorage.setItem('writing-desk-notify-when-done', notifyWhenDone.value ? '1' : '0')
  if (notifyWhenDone.value) {
    globalAlert.showToast('已开启完成通知。', 'success')
  } else {
    globalAlert.showToast('已关闭完成通知。', 'info')
  }
}

watch(
  () => props.status,
  async (nextStatus, prevStatus) => {
    if (
      notifyWhenDone.value &&
      prevStatus &&
      ['generating', 'evaluating', 'selecting'].includes(prevStatus) &&
      (nextStatus === 'waiting_for_confirm' || nextStatus === 'successful')
    ) {
      await globalAlert.showSuccess(`第${props.chapterNumber}章已完成 AI 评审和修复润色。`, '生成完成')
    }
  },
)

onMounted(() => {
  notifyWhenDone.value = localStorage.getItem('writing-desk-notify-when-done') === '1'
})
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
  box-shadow: var(--md-elevation-1);
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
  border-radius: var(--md-radius-full);
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
