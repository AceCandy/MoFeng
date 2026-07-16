<!-- AIMETA P=写作台工作区_主编辑区域|R=章节编辑_生成|NR=不含侧边栏|E=component:WDWorkspace|X=ui|A=工作区|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <section class="writing-workspace">
    <div class="md-card md-card-outlined writing-workspace__panel">
      <!-- 章节工作区头部 -->
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
            :is-draft-waiting-confirm="isDraftWaitingConfirm"
            :has-selected-chapter-content="hasSelectedChapterContent"
            :is-chapter-content-view="isChapterContentView"
            :is-ai-menu-disabled="isAiMenuDisabled ?? false"
            :body-component-ref="bodyComponentRef"
            @copy-content="copySelectedChapterContent"
            @open-edit-modal="editModalRef?.openEditModal()"
            @confirm-version-selection="$emit('confirmVersionSelection', $event)"
          />
        </div>
      </div>

      <div
        v-if="selectedChapter?.generation_status === 'successful' && hasSelectedChapterContent"
        class="writing-workspace__tabs-row"
      >
        <ChapterTabs
          v-model:active-tab="activeTab"
          :versions-count="availableVersions.length"
        />
      </div>

      <!-- 章节内容展示区 -->
      <div class="writing-workspace__content">
          <ChapterReaderBar
            v-if="isFinalizedSuccessful"
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
            <ChapterGenerating
              v-if="shouldShowDraftTraceReplay"
              class="writing-workspace__trace-replay"
              v-bind="draftTraceReplayProps"
            />

            <!-- 1. 章节正文 Tab 分支 -->
            <component
              v-if="activeTab === 'content' || selectedChapter?.generation_status !== 'successful' || !hasSelectedChapterContent"
              ref="bodyComponentRef"
              :is="currentComponent"
              v-bind="currentComponentProps"
              @hideVersionSelector="$emit('hideVersionSelector')"
              @update:selectedVersionIndex="$emit('update:selectedVersionIndex', $event)"
              @showVersionDetail="$emit('showVersionDetail', $event)"
              @confirmVersionSelection="$emit('confirmVersionSelection', $event)"
              @generateChapter="$emit('generateChapter', $event)"
              @retryFromNode="$emit('retryFromNode', $event)"
              @selectChapter="$emit('selectChapter', $event)"
              @showVersionSelector="$emit('showVersionSelector')"
              @regenerateChapter="$emit('regenerateChapter')"
              @evaluateChapter="$emit('evaluateChapter')"
              @showEvaluationDetail="$emit('showEvaluationDetail')"
            />

            <!-- 2. 历史版本多维平铺查阅面板 -->
            <ChapterVersionsPanel
              v-else-if="activeTab === 'versions'"
              :available-versions="availableVersions"
              :selected-chapter-number="selectedChapterNumber"
              :resolved-content="selectedChapterResolvedContent"
              @edit-chapter="$emit('editChapter', $event)"
              @switch-to-content="activeTab = 'content'"
            />

            <!-- 3. AI 章节评审反馈面板 -->
            <ChapterEvaluationPanel
              v-else-if="activeTab === 'evaluation'"
              :evaluation="selectedChapter?.evaluation"
              :evaluating-chapter="evaluatingChapter"
              @evaluate-chapter="$emit('evaluateChapter')"
            />
          </div>
        </div>
      </div>

    <!-- 编辑章节内容模态框（抽至 ./workspace/EditChapterModal.vue） -->
    <EditChapterModal
      ref="editModalRef"
      :has-content="hasSelectedChapterContent"
      :resolved-content="selectedChapterResolvedContent"
      :chapter-number="selectedChapterNumber"
      @edit-chapter="$emit('editChapter', $event)"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { globalAlert } from '@/composables/useAlert'
import { useChapterReaderBar } from '@/composables/useChapterReaderBar'
import { useVersionResolver } from '@/composables/useVersionResolver'
import { useChapterStatus } from '@/composables/useChapterStatus'
import { useChapterBodyProps } from '@/composables/useChapterBodyProps'
import { useChapterClipboard } from '@/composables/useChapterClipboard'
import { useChapterInlineMeta } from '@/composables/useChapterInlineMeta'
import type {
  Chapter,
  ChapterOutline,
  ChapterGenerationResponse,
  ChapterVersion,
  NovelProject,
} from '@/api/novel'
import ChapterGenerating from './workspace/ChapterGenerating.vue'
import ChapterReaderBar from './ChapterReaderBar.vue'
import EditChapterModal from './workspace/EditChapterModal.vue'
import ChapterEvaluationPanel from './workspace/ChapterEvaluationPanel.vue'
import ChapterVersionsPanel from './workspace/ChapterVersionsPanel.vue'
import ChapterMeta from './workspace/ChapterMeta.vue'
import ChapterToolbar from './workspace/ChapterToolbar.vue'
import ChapterTabs from './workspace/ChapterTabs.vue'

interface Props {
  project: NovelProject | null
  selectedChapterNumber: number | null
  generatingChapter: number | null
  evaluatingChapter: number | null
  showVersionSelector: boolean
  chapterGenerationResult: ChapterGenerationResponse | null
  selectedVersionIndex: number
  availableVersions: ChapterVersion[]
  isSelectingVersion?: boolean
}

const props = defineProps<Props>()

const emit = defineEmits([
  'regenerateChapter',
  'evaluateChapter',
  'hideVersionSelector',
  'update:selectedVersionIndex',
  'showVersionDetail',
  'confirmVersionSelection',
  'generateChapter',
  'retryFromNode',
  'selectChapter',
  'showVersionSelector',
  'showEvaluationDetail',
  'fetchChapterStatus',
  'editChapter',
])

interface ChapterContentExpose {
  openOptimizerPanel?: () => void
  openOptimizerPanelWithPreset?: (preset?: { dimension?: string; notes?: string }) => void
  exportCurrentChapterAsTxt?: () => void
}

const bodyComponentRef = ref<ChapterContentExpose | null>(null)

const selectedChapter = computed<Chapter | null>(() => {
  if (!props.project || props.selectedChapterNumber === null) return null
  return (
    props.project.chapters.find((ch) => ch.chapter_number === props.selectedChapterNumber) || null
  )
})

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

const isFinalizedSuccessful = computed(() => {
  return selectedChapter.value?.generation_status === 'successful' && hasSelectedChapterContent.value
})

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

const isDraftWaitingConfirm = computed(() => {
  const status = selectedChapter.value?.generation_status
  return status === 'waiting_for_confirm'
})

const shouldShowDraftTraceReplay = computed(() => {
  return isDraftWaitingConfirm.value && hasSelectedChapterContent.value
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

const {
  isSelectedChapterLocked,
  shouldShowChapterToolbar,
  chapterStatusLabel,
  chapterStatusTone,
  isChapterGenerating,
  isSelectedChapterGeneratingLike,
  isChapterFailed,
  isChapterEvaluationFailed,
  isInProgressStatus,
  isGeneratingInFlight,
  canGenerateChapter,
  currentComponent,
  isChapterContentView,
  canViewVersions,
  isAiMenuDisabled,
} = useChapterStatus({
  props,
  selectedChapter,
  hasSelectedChapterContent,
  lockedPrerequisiteChapterNumber,
  isFinalizedSuccessful,
  isDraftWaitingConfirm,
})

const { chapterInlineMeta } = useChapterInlineMeta({
  selectedChapter,
  selectedChapterResolvedContent,
  hasSelectedChapterContent,
})

const openVersionDetail = () => {
  if (!canViewVersions.value) {
    globalAlert.showError('当前章节暂无可查看版本')
    return
  }

  const maxIndex = props.availableVersions.length - 1
  const safeIndex = Math.min(Math.max(props.selectedVersionIndex, 0), maxIndex)
  emit('showVersionDetail', safeIndex)
}

const requestChapterStatus = () => {
  emit('fetchChapterStatus')
}

watch(
  [
    () => props.selectedChapterNumber,
    () => selectedChapter.value?.generation_status ?? null,
    () => selectedChapter.value?.versions?.length ?? 0,
    () => Boolean(selectedChapter.value?.content),
  ],
  ([chapterNumber, status, versionsCount, hasContent]) => {
    if (chapterNumber === null) {
      return
    }

    // 需要服务端推送同步的场景：
    // 1) 生成/评审/选择中（状态推进）
    // 2) 等待确认但正文还没同步（含版本已到但正文未到的短暂窗口）
    // 3) 已成功但正文暂未同步（避免必须手动刷新）
    const needsPolling =
      isGeneratingInFlight.value ||
      status === 'generating' ||
      status === 'evaluating' ||
      status === 'selecting' ||
      status === 'finalizing' ||
      (status === 'waiting_for_confirm' && !hasContent) ||
      (status === 'successful' && !hasContent)

    if (needsPolling) {
      requestChapterStatus()
    }
  },
  { immediate: true },
)

const { currentComponentProps, draftTraceReplayProps } = useChapterBodyProps({
  props,
  selectedChapter,
  selectedChapterOutline,
  selectedChapterForDisplay,
  selectedChapterResolvedContent,
  hasSelectedChapterContent,
  readerCurrentParagraphIndex,
  readerCurrentParagraphEnd,
  lockedPrerequisiteChapterNumber,
  lockedPrerequisiteChapterTitle,
  isInProgressStatus,
  isGeneratingInFlight,
  isChapterFailed,
  isChapterEvaluationFailed,
  canGenerateChapter,
})

// ==========================================================================
// 写作台正文/历史版本/AI评审三合一 Tab 切换区状态与逻辑
// ==========================================================================
const activeTab = ref<'content' | 'versions' | 'evaluation'>('content')
// 切换章节时回到正文 tab（版本预览索引的重置随 ChapterVersionsPanel 迁入子组件）
watch(
  () => props.selectedChapterNumber,
  () => {
    activeTab.value = 'content'
  }
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
  background-image: repeating-linear-gradient(90deg, rgba(28, 32, 34, 0.006) 0px, rgba(28, 32, 34, 0.006) 1px, transparent 1px, transparent 36px);
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
