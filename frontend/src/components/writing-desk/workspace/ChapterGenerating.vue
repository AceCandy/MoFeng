<!-- AIMETA P=章节工作流生成轨迹回溯|R=只读节点进度_真实trace详情|NR=不提交重试取消评审命令|E=component:ChapterGenerating|X=internal|A=workflow-trace|D=vue|S=dom|RD=./README.ai -->
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
      @select="selectStep"
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
import type { Chapter, ChapterGenerationTrace } from '@/api/novel'
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
  readOnly?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  chapterTitle: '',
  chapterSummary: '',
  chapterContentPreview: '',
  generationTraces: () => [],
  readOnly: true,
})

const activeStepKey = ref<string | null>(null)

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

const { activeStepDetails } = useChapterGenerationTrace(props, {
  activeStepKey,
  currentStepKey,
  isFailureStatus,
  terminalFailedTrace,
  failureReason,
  failureScenario,
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
