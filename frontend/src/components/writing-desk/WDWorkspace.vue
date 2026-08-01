<!-- AIMETA P=写作台工作区_主编辑区域|R=章节展示_工作流控制_版本评审分区|NR=不调用API_不拥有生命周期|E=component:WDWorkspace|X=ui|A=工作区|D=vue|S=dom,state|RD=./README.ai -->
<template>
  <section class="writing-workspace">
    <div class="md-card md-card-outlined writing-workspace__panel">
      <div v-if="selectedChapterNumber !== null" class="writing-workspace__header">
        <div class="writing-workspace__header-row">
          <ChapterMeta
            :chapter-number="selectedChapterNumber"
            :chapter-outline="selectedChapterOutline"
            :status-label="chapterStatusLabel"
            :status-tone="chapterStatusTone"
            :inline-meta="chapterInlineMeta"
            :title-tooltip-text="chapterTitleTooltipText"
            @copy-title="copySelectedChapterTitle"
            @reset-title-tooltip="resetChapterTitleTooltip"
          />
          <ChapterToolbar
            v-if="shouldShowChapterToolbar"
            :chapter-number="selectedChapterNumber"
            :is-finalized-successful="isFinalizedSuccessful"
            :has-selected-chapter-content="hasSelectedChapterContent"
            :is-chapter-content-view="isChapterContentView"
            :is-ai-menu-disabled="isAiMenuDisabled ?? false"
            :body-component-ref="bodyComponentRef"
            @copy-content="copySelectedChapterContent"
            @open-edit-modal="editModalRef?.openEditModal()"
          />
        </div>
      </div>

      <div v-if="hasSelectedChapterContent" class="writing-workspace__tabs-row">
        <ChapterTabs
          v-model:active-tab="activeTab"
          :versions-count="availableVersions.length"
        />
      </div>

      <div class="writing-workspace__content">
        <ChapterReaderBar
          v-if="hasSelectedChapterContent"
          :status="readerStatus"
          :isBrowserFallback="readerIsBrowserFallback"
          :hasModelTTS="readerHasModelTTS"
          :modelVoice="readerModelVoice"
          :modelVoiceOptions="readerModelVoiceOptions"
          :currentParagraphIndex="readerCurrentParagraphIndex"
          :paragraphCount="readerParagraphCount"
          :voiceURI="readerVoiceURI"
          :rate="readerRate"
          :forceBrowser="readerForceBrowser"
          :voiceOptions="readerVoiceOptions"
          :rateOptions="READER_RATE_OPTIONS"
          @start="handleReaderStart"
          @play-pause="handleReaderPlayPause"
          @reset="handleReaderReset"
          @voice-change="chapterReader.setVoiceURI"
          @model-voice-change="chapterReader.setModelVoice"
          @force-browser-change="chapterReader.setForceBrowser"
          @rate-change="chapterReader.setRate"
          @preview-voice="chapterReader.previewVoice"
        />

        <div class="writing-workspace__body h-full">
          <WorkspaceInitial v-if="selectedChapterNumber === null" />

          <ChapterEmpty
            v-else-if="isSelectedChapterLocked"
            :chapter-number="selectedChapterNumber"
            :locked-prerequisite-chapter-number="lockedPrerequisiteChapterNumber"
            :locked-prerequisite-chapter-title="lockedPrerequisiteChapterTitle"
            @select-chapter="emit('selectChapter', $event)"
          />

          <template v-else>
            <ChapterWorkflowPanel
              :phase="workflowPhase"
              :transport="workflowTransport"
              :allowed-commands="workflowAllowedCommands"
              :pending="workflowPending"
              :error="workflowError"
              :retry-activity-key="workflowRetryActivityKey"
              :candidates="workflowCandidates"
              @start="emit('workflowStart')"
              @select-version="emit('workflowSelectVersion', $event)"
              @retry="emit('workflowRetry')"
              @retry-external="emit('workflowRetryExternal', $event)"
              @retry-projection="emit('workflowRetryProjection')"
              @cancel="emit('workflowCancel')"
              @resync="emit('workflowResync')"
            />

            <ChapterGenerating
              v-if="activeTab === 'content' && shouldShowTraceReplay"
              class="writing-workspace__trace-replay"
              v-bind="traceReplayProps"
            />

            <ChapterContent
              v-if="activeTab === 'content' && selectedChapterForDisplay && hasSelectedChapterContent"
              ref="bodyComponentRef"
              :selected-chapter="selectedChapterForDisplay"
              :project-id="project?.id"
              :active-paragraph-index="readerCurrentParagraphIndex"
              :active-paragraph-end="readerCurrentParagraphEnd"
            />

            <ChapterVersionsPanel
              v-else-if="activeTab === 'versions'"
              :available-versions="availableVersions"
              :selected-chapter-number="selectedChapterNumber"
              :resolved-content="selectedChapterResolvedContent"
              @show-version-detail="emit('showVersionDetail', $event)"
              @edit-chapter="emit('editChapter', $event)"
              @switch-to-content="activeTab = 'content'"
            />

            <ChapterEvaluationPanel
              v-else-if="activeTab === 'evaluation'"
              :evaluation="selectedChapter?.evaluation"
              @show-evaluation-detail="emit('showEvaluationDetail')"
            />
          </template>
        </div>
      </div>

      <EditChapterModal
        ref="editModalRef"
        :has-content="hasSelectedChapterContent"
        :resolved-content="selectedChapterResolvedContent"
        :chapter-number="selectedChapterNumber"
        @edit-chapter="emit('editChapter', $event)"
      />
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useChapterReaderBar } from '@/composables/useChapterReaderBar'
import { useVersionResolver } from '@/composables/useVersionResolver'
import { useChapterClipboard } from '@/composables/useChapterClipboard'
import { useChapterInlineMeta } from '@/composables/useChapterInlineMeta'
import type {
  Chapter,
  ChapterVersion,
  ChapterVersionSelection,
  NovelProject,
} from '@/api/novel'
import type { ChapterWorkflowCommand } from '@/api/chapterWorkflow'
import type { ChapterWorkflowActorPhase } from '@/composables/useChapterWorkflowActor'
import type { ChapterWorkflowTransportPhase } from '@/composables/chapterWorkflowMachine'
import ChapterWorkflowPanel from './ChapterWorkflowPanel.vue'
import ChapterGenerating from './workspace/ChapterGenerating.vue'
import ChapterContent from './workspace/ChapterContent.vue'
import ChapterEmpty from './workspace/ChapterEmpty.vue'
import ChapterReaderBar from './ChapterReaderBar.vue'
import EditChapterModal from './workspace/EditChapterModal.vue'
import ChapterEvaluationPanel from './workspace/ChapterEvaluationPanel.vue'
import ChapterVersionsPanel from './workspace/ChapterVersionsPanel.vue'
import ChapterMeta from './workspace/ChapterMeta.vue'
import ChapterToolbar from './workspace/ChapterToolbar.vue'
import ChapterTabs from './workspace/ChapterTabs.vue'
import WorkspaceInitial from './workspace/WorkspaceInitial.vue'

interface Props {
  project: NovelProject | null
  selectedChapter: Chapter | null
  selectedChapterNumber: number | null
  selectedVersionIndex: number
  availableVersions: ChapterVersion[]
  workflowPhase: ChapterWorkflowActorPhase
  workflowTransport: ChapterWorkflowTransportPhase
  workflowAllowedCommands: readonly ChapterWorkflowCommand[]
  workflowPending: boolean
  workflowError: string | null
  workflowRetryActivityKey: string | null
  workflowCandidates: ChapterVersionSelection[]
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (event: 'workflowStart'): void
  (event: 'workflowSelectVersion', versionId: number): void
  (event: 'workflowRetry'): void
  (event: 'workflowRetryExternal', activityKey: string): void
  (event: 'workflowRetryProjection'): void
  (event: 'workflowCancel'): void
  (event: 'workflowResync'): void
  (event: 'selectChapter', chapterNumber: number): void
  (event: 'showVersionDetail', versionIndex: number): void
  (event: 'showEvaluationDetail'): void
  (event: 'editChapter', payload: { chapterNumber: number; content: string }): void
}>()

interface ChapterContentExpose {
  openOptimizerPanel?: () => void
  openOptimizerPanelWithPreset?: (preset?: { dimension?: string; notes?: string }) => void
  exportCurrentChapterAsTxt?: () => void
}

const bodyComponentRef = ref<ChapterContentExpose | null>(null)

const selectedChapter = computed(() => props.selectedChapter)

const selectedChapterOutline = computed(() => {
  if (!props.project?.blueprint?.chapter_outline || props.selectedChapterNumber === null)
    return null
  return (
    props.project.blueprint.chapter_outline.find(
      (ch) => ch.chapter_number === props.selectedChapterNumber,
    ) || null
  )
})

const {
  selectedChapterResolvedContent,
  selectedChapterForDisplay,
  hasSelectedChapterContent,
} = useVersionResolver({
  selectedChapter,
  availableVersions: computed(() => props.availableVersions),
  selectedVersionIndex: computed(() => props.selectedVersionIndex),
})

const {
  chapterTitleTooltipText,
  resetChapterTitleTooltip,
  copySelectedChapterTitle,
  copySelectedChapterContent,
} = useChapterClipboard({
  selectedChapterOutline,
  selectedChapterResolvedContent,
})

const editModalRef = ref<InstanceType<typeof EditChapterModal> | null>(null)

const isFinalizedSuccessful = computed(() => hasSelectedChapterContent.value)

const {
  chapterReader,
  readerStatus,
  readerCurrentParagraphIndex,
  readerCurrentParagraphEnd,
  readerParagraphCount,
  readerIsBrowserFallback,
  readerHasModelTTS,
  readerModelVoice,
  readerModelVoiceOptions,
  readerVoiceURI,
  readerRate,
  readerForceBrowser,
  readerVoiceOptions,
  READER_RATE_OPTIONS,
  handleReaderStart,
  handleReaderPlayPause,
  handleReaderReset,
} = useChapterReaderBar({
  props,
  selectedChapterOutline,
  selectedChapterResolvedContent,
})

const lockedPrerequisiteChapterNumber = computed(() => {
  if (props.selectedChapterNumber === null || !props.project?.blueprint?.chapter_outline) {
    return null
  }

  const chaptersByNumber = new Map(
    (props.project.chapters ?? []).map((chapter) => [chapter.chapter_number, chapter]),
  )
  const sortedOutlines = [...props.project.blueprint.chapter_outline].sort(
    (left, right) => left.chapter_number - right.chapter_number,
  )

  // 未解锁的核心规则：当前章之前必须全部生成成功，才允许推进当前章。
  for (const outline of sortedOutlines) {
    if (outline.chapter_number >= props.selectedChapterNumber) break
    const chapter = chaptersByNumber.get(outline.chapter_number)
    if (chapter?.generation_status !== 'successful') {
      return outline.chapter_number
    }
  }

  return null
})

const lockedPrerequisiteChapterTitle = computed(() => {
  const num = lockedPrerequisiteChapterNumber.value
  if (num === null || !props.project?.blueprint?.chapter_outline) {
    return null
  }
  const outline = props.project.blueprint.chapter_outline.find(
    (ch) => ch.chapter_number === num,
  )
  return outline?.title || null
})

const isSelectedChapterLocked = computed(() =>
  lockedPrerequisiteChapterNumber.value !== null
  && !hasSelectedChapterContent.value
  && props.workflowPhase === 'idle',
)

const activeTab = ref<'content' | 'versions' | 'evaluation'>('content')
const shouldShowChapterToolbar = computed(() => hasSelectedChapterContent.value)
const isChapterContentView = computed(() => activeTab.value === 'content' && hasSelectedChapterContent.value)
const isAiMenuDisabled = computed(() => props.workflowPending)

const workflowStatus = computed(() => {
  switch (props.workflowPhase) {
    case 'booting':
      return { label: '同步中', tone: 'progress' }
    case 'idle':
      return { label: '待开始', tone: 'idle' }
    case 'submitting':
      return { label: '提交中', tone: 'progress' }
    case 'running':
      return { label: '生成中', tone: 'progress' }
    case 'waitingForSelection':
      return { label: '待选版本', tone: 'pending' }
    case 'finalizing':
      return { label: '定稿中', tone: 'progress' }
    case 'projectionPending':
      return { label: '同步中', tone: 'pending' }
    case 'succeeded':
      return { label: '已完成', tone: 'success' }
    case 'failed':
      return { label: '待处理', tone: 'error' }
    case 'cancelled':
      return { label: '已取消', tone: 'idle' }
    case 'superseded':
      return { label: '切换中', tone: 'progress' }
    case 'fatal':
      return { label: '同步失败', tone: 'error' }
  }
  return { label: '同步失败', tone: 'error' }
})
const chapterStatusLabel = computed(() => workflowStatus.value.label)
const chapterStatusTone = computed(() => workflowStatus.value.tone)

const { chapterInlineMeta } = useChapterInlineMeta({
  selectedChapter,
  selectedChapterResolvedContent,
  hasSelectedChapterContent,
})

const shouldShowTraceReplay = computed(() => {
  const traces = selectedChapter.value?.generation_traces ?? []
  return traces.length > 0
    && props.workflowPhase !== 'idle'
    && props.workflowPhase !== 'succeeded'
    && props.workflowPhase !== 'cancelled'
    && props.workflowPhase !== 'fatal'
})

const traceReplayProps = computed(() => ({
  chapterNumber: props.selectedChapterNumber,
  chapterTitle: selectedChapterOutline.value?.title || '',
  chapterSummary: selectedChapterOutline.value?.summary || '',
  chapterContentPreview: selectedChapterResolvedContent.value,
  status: selectedChapter.value?.generation_status ?? null,
  generationProgress: selectedChapter.value?.generation_progress ?? null,
  generationStep: selectedChapter.value?.generation_step ?? null,
  generationStepIndex: selectedChapter.value?.generation_step_index ?? null,
  generationStepTotal: selectedChapter.value?.generation_step_total ?? null,
  generationStartedAt: selectedChapter.value?.generation_started_at ?? null,
  statusUpdatedAt: selectedChapter.value?.status_updated_at ?? null,
  generationTraces: selectedChapter.value?.generation_traces ?? [],
  readOnly: true,
}))

watch(
  () => props.selectedChapterNumber,
  () => {
    activeTab.value = 'content'
  },
)
</script>

<style scoped>
.writing-workspace {
  min-width: 0;
  min-height: 0;
  height: 100%;
}

.writing-workspace__panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  border-radius: 0 !important; /* 方直古籍 */
  background: var(--md-surface);
  /* 极致国风脑洞：工作区熟宣纹理 */
  background-image: repeating-linear-gradient(90deg, color-mix(in srgb, var(--md-on-surface) 0.6%, transparent) 0px, color-mix(in srgb, var(--md-on-surface) 0.6%, transparent) 1px, transparent 1px, transparent 36px);
  border: 3px double var(--md-outline) !important;
  box-shadow: 3px 3px 0px var(--md-outline);
}

.writing-workspace__header {
  flex-shrink: 0;
  padding: var(--md-spacing-4) var(--md-spacing-5);
  border-bottom: 1px dashed var(--md-outline);
  background-color: var(--md-surface-container-low);
}

.writing-workspace__header-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--md-spacing-4);
}

/* 极致国风脑洞：正文区融入古典竹青淡墨横线信笺格背景 */
.writing-workspace__content {
  position: relative;
  flex: 1;
  min-height: 0;
  overflow: hidden;
  padding: 0 !important; /* 彻底去除灰色间距，使内部稿纸能够完美顶边铺满 */
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-4);
  background-color: var(--md-surface);
}

.writing-workspace__body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.writing-workspace__trace-replay {
  padding: var(--md-spacing-3) var(--md-spacing-5) 0;
}

@media (max-width: 940px) {
  .writing-workspace__header-row {
    flex-direction: column;
    gap: var(--md-spacing-3);
  }
}

@media (max-width: 640px) {
  .writing-workspace__header {
    padding: var(--md-spacing-4);
  }

  .writing-workspace__content {
    padding: var(--md-spacing-4);
  }
}

/* ==========================================================================
   三合一 Tab 切换栏样式与中国风金石重塑
   ========================================================================== */
.writing-workspace__tabs-row {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  margin-top: var(--md-spacing-3);
  padding: 0 var(--md-spacing-4);
  border-bottom: 1.5px solid var(--md-outline-variant);
  padding-bottom: 1px;
}

</style>
