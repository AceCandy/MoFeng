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
          <span v-if="luomoSealVisible" class="writing-workspace__luomo-seal" aria-hidden="true">定</span>
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
          v-if="hasFinalizedChapterContent"
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
              @preview-candidate="onCandidatePreview"
            />

            <ChapterGenerating
              v-if="activeTab === 'content' && shouldShowTraceReplay"
              class="writing-workspace__trace-replay"
              v-bind="traceReplayProps"
            />

            <ChapterContent
              v-if="activeTab === 'content' && chapterContentChapter && (hasSelectedChapterContent || hasMiaohongPreview || hasLuomoSnapshot)"
              ref="bodyComponentRef"
              :selected-chapter="chapterContentChapter"
              :project-id="project?.id"
              :active-paragraph-index="readerCurrentParagraphIndex"
              :active-paragraph-end="readerCurrentParagraphEnd"
              :miaohong-content="miaohongPreviewContent"
              :luomo-snapshot-content="luomoSnapshotContent"
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
import { computed, onUnmounted, ref, watch } from 'vue'
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
import type { ChapterWorkflowCommand, ChapterWorkflowNodeKey } from '@/api/chapterWorkflow'
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
  workflowRunId: string | null
  workflowNodeKey: ChapterWorkflowNodeKey | null
  workflowProgress: number | null
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
const hasFinalizedChapterContent = computed(() => Boolean(props.selectedChapter?.content?.trim()))

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

// 候选版本描红预览：工作流面板选中候选时把正文接到 ChapterContent
const miaohongPreviewContent = ref<string | null>(null)
const hasMiaohongPreview = computed(() => Boolean(miaohongPreviewContent.value?.trim()))

const onCandidatePreview = (content: string | null) => {
  miaohongPreviewContent.value = content
}

// 落印签名：候选描红稿被选定提交（waitingForSelection → submitting/finalizing/succeeded）时，
// 旧稿转快照原地朱转墨（ChapterContent 渲染 260ms 过渡），标题旁钤「定」字朱砂印一瞬
const luomoSnapshotContent = ref<string | null>(null)
const hasLuomoSnapshot = computed(() => Boolean(luomoSnapshotContent.value?.trim()))
const luomoSealVisible = ref(false)
let luomoSnapshotTimer: number | null = null
let luomoSealTimer: number | null = null

const clearLuomoSignature = () => {
  if (luomoSnapshotTimer !== null) {
    window.clearTimeout(luomoSnapshotTimer)
    luomoSnapshotTimer = null
  }
  if (luomoSealTimer !== null) {
    window.clearTimeout(luomoSealTimer)
    luomoSealTimer = null
  }
  luomoSnapshotContent.value = null
  luomoSealVisible.value = false
}

watch(
  () => props.workflowPhase,
  (phase, prevPhase) => {
    const isLuomoMoment = prevPhase === 'waitingForSelection'
      && (phase === 'submitting' || phase === 'finalizing' || phase === 'succeeded')
    if (!isLuomoMoment) return
    if (miaohongPreviewContent.value?.trim()) {
      luomoSnapshotContent.value = miaohongPreviewContent.value
      miaohongPreviewContent.value = null
      if (luomoSnapshotTimer !== null) window.clearTimeout(luomoSnapshotTimer)
      luomoSnapshotTimer = window.setTimeout(() => {
        luomoSnapshotContent.value = null
        luomoSnapshotTimer = null
      }, 520)
    }
    luomoSealVisible.value = true
    if (luomoSealTimer !== null) window.clearTimeout(luomoSealTimer)
    luomoSealTimer = window.setTimeout(() => {
      luomoSealVisible.value = false
      luomoSealTimer = null
    }, 1400)
  },
)

// 章节记录尚未落库（生成中）时，为描红预览合成最小章节壳
const chapterContentChapter = computed<Chapter | null>(() => {
  if (selectedChapterForDisplay.value) {
    return hasMiaohongPreview.value && !hasFinalizedChapterContent.value
      ? { ...selectedChapterForDisplay.value, content: '' }
      : selectedChapterForDisplay.value
  }
  if ((!hasMiaohongPreview.value && !hasLuomoSnapshot.value) || props.selectedChapterNumber === null) return null
  return {
    chapter_number: props.selectedChapterNumber,
    generation_status: 'generating',
    goals: '',
    summary: '',
    title: '',
    content: '',
  }
})

const hasCurrentWorkflow = computed(
  () => props.workflowPhase === 'submitting' || props.workflowRunId !== null,
)

const workflowGenerationTraces = computed(() => {
  const traces = selectedChapter.value?.generation_traces ?? []
  if (!hasCurrentWorkflow.value) return traces
  if (props.workflowRunId === null) return []
  // 新 run 中只显示可确认归属的轨迹，避免无 run_id 的旧记录污染当前节点。
  return traces.filter((trace) => trace.metadata?.run_id === props.workflowRunId)
})

const shouldShowTraceReplay = computed(() => {
  const activePhase = props.workflowPhase === 'submitting'
    || props.workflowPhase === 'running'
    || props.workflowPhase === 'waitingForSelection'
    || props.workflowPhase === 'finalizing'
    || props.workflowPhase === 'projectionPending'
    || props.workflowPhase === 'failed'
  return activePhase
    && (props.workflowPhase === 'submitting'
      || props.workflowNodeKey !== null
      || workflowGenerationTraces.value.length > 0)
})

const workflowGenerationStatus = computed<Chapter['generation_status'] | null>(() => {
  if (!hasCurrentWorkflow.value) return selectedChapter.value?.generation_status ?? null
  if (props.workflowPhase === 'running' || props.workflowPhase === 'submitting') return 'generating'
  if (props.workflowPhase === 'waitingForSelection') return 'waiting_for_confirm'
  if (props.workflowPhase === 'finalizing' || props.workflowPhase === 'projectionPending') {
    return 'finalizing'
  }
  if (props.workflowPhase === 'failed') return 'failed'
  if (props.workflowPhase === 'succeeded') return 'successful'
  return selectedChapter.value?.generation_status ?? null
})

const traceReplayProps = computed(() => ({
  chapterNumber: props.selectedChapterNumber,
  chapterTitle: selectedChapterOutline.value?.title || '',
  chapterSummary: selectedChapterOutline.value?.summary || '',
  chapterContentPreview: selectedChapterResolvedContent.value,
  status: workflowGenerationStatus.value,
  generationProgress: !hasCurrentWorkflow.value
    ? selectedChapter.value?.generation_progress ?? null
    : props.workflowProgress,
  generationStep: !hasCurrentWorkflow.value
    ? selectedChapter.value?.generation_step ?? null
    : props.workflowNodeKey,
  generationStepIndex: !hasCurrentWorkflow.value
    ? selectedChapter.value?.generation_step_index ?? null
    : null,
  generationStepTotal: !hasCurrentWorkflow.value
    ? selectedChapter.value?.generation_step_total ?? null
    : null,
  generationStartedAt: selectedChapter.value?.generation_started_at ?? null,
  statusUpdatedAt: selectedChapter.value?.status_updated_at ?? null,
  generationTraces: workflowGenerationTraces.value,
  readOnly: true,
}))

watch(
  () => props.selectedChapterNumber,
  () => {
    activeTab.value = 'content'
    // 切换章节时清空上一章的描红预览与落印签名残留
    miaohongPreviewContent.value = null
    clearLuomoSignature()
  },
)

onUnmounted(clearLuomoSignature)
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
  box-shadow: var(--md-elevation-paper-1);
}

.writing-workspace__header {
  flex-shrink: 0;
  padding: var(--md-spacing-4) var(--md-spacing-5);
  border-bottom: 1px solid var(--md-jiege);
  background-color: var(--md-surface-container-low);
}

.writing-workspace__header-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--md-spacing-4);
}

/* 落印签名：候选描红稿被选定落墨的一瞬，标题旁钤「定」字朱砂印，钤下即走 */
.writing-workspace__luomo-seal {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  align-self: center;
  width: 34px;
  height: 34px;
  margin-right: auto; /* 吸收剩余空间：印贴标题侧，工具栏保持居右 */
  border-radius: var(--md-radius-xs);
  background: var(--md-secondary);
  color: var(--md-on-secondary);
  font-family: var(--md-font-serif);
  font-size: 18px;
  font-weight: 700;
  line-height: 1;
  pointer-events: none;
  user-select: none;
}

@media (prefers-reduced-motion: no-preference) {
  .writing-workspace__luomo-seal {
    animation: workspace-luomo-seal 1.35s cubic-bezier(0.22, 1, 0.36, 1) both;
  }
}

@keyframes workspace-luomo-seal {
  0% {
    opacity: 0;
    transform: rotate(-4deg) scale(1.3);
  }
  22% {
    opacity: 1;
    transform: rotate(-4deg) scale(0.96);
  }
  32% {
    transform: rotate(-4deg) scale(1);
  }
  76% {
    opacity: 1;
  }
  100% {
    opacity: 0;
    transform: rotate(-4deg) scale(1);
  }
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
  border-bottom: 1.5px solid var(--md-jiege);
  padding-bottom: 1px;
}

</style>
