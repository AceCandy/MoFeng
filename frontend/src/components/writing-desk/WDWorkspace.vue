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
            :is-ai-menu-disabled="isAiMenuDisabled"
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
        <nav class="writing-workspace__tabs" aria-label="章节工作台分区">
          <button
            type="button"
            class="writing-workspace__tab-btn md-ripple"
            :class="{ 'is-active': activeTab === 'content' }"
            @click="activeTab = 'content'"
          >
            <span class="tab-badge">🎴</span>
            <span>章节正文</span>
          </button>
          <button
            type="button"
            class="writing-workspace__tab-btn md-ripple"
            :class="{ 'is-active': activeTab === 'versions' }"
            @click="activeTab = 'versions'"
          >
            <span class="tab-badge">📜</span>
            <span>查看版本 ({{ availableVersions.length }})</span>
          </button>
          <button
            type="button"
            class="writing-workspace__tab-btn md-ripple"
            :class="{ 'is-active': activeTab === 'evaluation' }"
            @click="activeTab = 'evaluation'"
          >
            <span class="tab-badge">⚖️</span>
            <span>AI 评审反馈</span>
          </button>
        </nav>
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
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { globalAlert } from '@/composables/useAlert'
import { useChapterReader } from '@/composables/useChapterReader'
import { useVersionResolver } from '@/composables/useVersionResolver'
import { useChapterStatus } from '@/composables/useChapterStatus'
import { useChapterBodyProps } from '@/composables/useChapterBodyProps'
import type {
  Chapter,
  ChapterOutline,
  ChapterGenerationResponse,
  ChapterVersion,
  NovelProject,
} from '@/api/novel'
import { countNonWhitespaceChars } from '@/utils/text'
import ChapterGenerating from './workspace/ChapterGenerating.vue'
import ChapterReaderBar from './ChapterReaderBar.vue'
import EditChapterModal from './workspace/EditChapterModal.vue'
import ChapterEvaluationPanel from './workspace/ChapterEvaluationPanel.vue'
import ChapterVersionsPanel from './workspace/ChapterVersionsPanel.vue'
import ChapterMeta from './workspace/ChapterMeta.vue'
import ChapterToolbar from './workspace/ChapterToolbar.vue'

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
const chapterReader = useChapterReader()
const readerStatus = chapterReader.status

const copyTextLegacy = (text: string): boolean => {
  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.setAttribute('readonly', 'readonly')
  textarea.style.position = 'fixed'
  textarea.style.top = '-9999px'
  textarea.style.left = '-9999px'
  document.body.appendChild(textarea)
  textarea.focus()
  textarea.select()

  let copied = false
  try {
    copied = document.execCommand('copy')
  } catch (error) {
    copied = false
  }

  document.body.removeChild(textarea)
  return copied
}

const chapterTitleTooltipText = ref('点击复制')

const resetChapterTitleTooltip = () => {
  chapterTitleTooltipText.value = '点击复制'
}

const copyText = async (text: string) => {
  try {
    if (window.isSecureContext && navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
      return true
    }

    return copyTextLegacy(text)
  } catch (error) {
    console.error('复制失败:', error)
    return copyTextLegacy(text)
  }
}

const copySelectedChapterTitle = async () => {
  const title = (selectedChapterOutline.value?.title || '未知标题').trim()
  if (!title) return

  const copied = await copyText(title)
  chapterTitleTooltipText.value = copied ? '复制成功' : '复制失败'
}

const copySelectedChapterContent = async () => {
  const content = selectedChapterResolvedContent.value.trim()
  if (!content) return

  const copied = await copyText(content)
  if (!copied) {
    globalAlert.showError('复制失败，请手动选择文本复制。')
  }
}

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

const editModalRef = ref<InstanceType<typeof EditChapterModal> | null>(null)

const isFinalizedSuccessful = computed(() => {
  return selectedChapter.value?.generation_status === 'successful' && hasSelectedChapterContent.value
})

// 朗读控件：入口仅在 idle 显示，点击后原地展开为播放条；重置即停止回到入口
const readerCurrentParagraphIndex = chapterReader.currentParagraphIndex
const readerCurrentParagraphEnd = chapterReader.currentParagraphEnd
const readerParagraphCount = chapterReader.paragraphCount
const readerIsBrowserFallback = chapterReader.isBrowserFallback
const readerHasModelTTS = chapterReader.hasModelTTS
const readerModelVoice = chapterReader.modelVoice
const readerModelVoiceOptions = chapterReader.modelVoiceOptions
const readerVoiceURI = chapterReader.voiceURI
const readerRate = chapterReader.rate
const readerForceBrowser = chapterReader.forceBrowser

// 浏览器朗读音色：仅在浏览器 fallback 时可选，选项来自本机 getVoices，存 localStorage
const browserVoiceOptions = ref<SpeechSynthesisVoice[]>([])
const refreshBrowserVoices = () => {
  browserVoiceOptions.value = (window.speechSynthesis?.getVoices?.() ?? []).filter(
    (voice) => /^zh/i.test(voice.lang) && /natural|neural/i.test(voice.name),
  )
}
// 微软在线神经语音英文名 → 中文友好名（带性别/地区），未命中的回退原英文名
const VOICE_CN_LABEL: Record<string, string> = {
  Xiaoxiao: '晓晓（女）',
  Xiaoyi: '晓伊（女）',
  Yunjian: '云健（男）',
  Yunxi: '云希（男）',
  Yunxia: '云夏（女）',
  Yunyang: '云扬（男）',
  Xiaobei: '晓北（女·东北话）',
  Xiaoni: '晓妮（女·陕西话）',
  HsiaoChen: '晓臻（女·台湾）',
  HsiaoYu: '晓雨（女·台湾）',
  YunJhe: '云哲（男·台湾）',
  HiuGaai: '曉佳（女·粤语）',
  HiuMaan: '曉敏（女·粤语）',
  WanLung: '雲龍（男·粤语）',
}
const readerVoiceLabel = (voice: SpeechSynthesisVoice) => {
  const match = voice.name.match(/Microsoft\s+([A-Za-z]+)/i)
  return (match && VOICE_CN_LABEL[match[1]]) || voice.name
}

// 悬浮控件音色选项（URI + 清洗后的标签）
const readerVoiceOptions = computed(() =>
  browserVoiceOptions.value.map((voice) => ({ uri: voice.voiceURI, label: readerVoiceLabel(voice) })),
)

// 朗读倍速：浏览器与模型 TTS 通用
const READER_RATE_OPTIONS = [0.75, 1, 1.25, 1.5, 2]

const handleReaderStart = () => {
  const chapterTitle = `第${props.selectedChapterNumber}章 ${selectedChapterOutline.value?.title || '未知标题'}`
  void chapterReader.start(chapterTitle, selectedChapterResolvedContent.value)
}

const handleReaderPlayPause = () => {
  if (readerStatus.value === 'playing') {
    chapterReader.pause()
    return
  }
  if (readerStatus.value === 'paused') {
    chapterReader.resume()
    return
  }
  if (readerStatus.value === 'generating') {
    chapterReader.stop()
  }
}

// 重置：停止朗读，收缩回「准备播放」入口
const handleReaderReset = () => {
  chapterReader.stop()
}

const isDraftWaitingConfirm = computed(() => {
  const status = selectedChapter.value?.generation_status
  return status === 'waiting_for_confirm'
})

const shouldShowDraftTraceReplay = computed(() => {
  return isDraftWaitingConfirm.value && hasSelectedChapterContent.value
})

const selectedChapterWordCount = computed(() => countNonWhitespaceChars(selectedChapterResolvedContent.value))

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

const formatDateTime = (value?: string | null) => {
  if (!value) return '--'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return '--'
  const year = parsed.getFullYear()
  const month = String(parsed.getMonth() + 1).padStart(2, '0')
  const day = String(parsed.getDate()).padStart(2, '0')
  const hour = String(parsed.getHours()).padStart(2, '0')
  const minute = String(parsed.getMinutes()).padStart(2, '0')
  return `${year}/${month}/${day} ${hour}:${minute}`
}

const chapterLastEditedText = computed(() =>
  formatDateTime(selectedChapter.value?.status_updated_at ?? selectedChapter.value?.generation_started_at),
)

const chapterInlineMeta = computed(() => {
  const segments: string[] = []
  if (hasSelectedChapterContent.value) {
    segments.push(`${selectedChapterWordCount.value}字`)
  }
  segments.push(`最后编辑 ${chapterLastEditedText.value}`)
  return segments.join(' · ')
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

watch(
  () => props.selectedChapterNumber,
  () => {
    // closeAiMenu 随 useAiMenu/ChapterToolbar 迁入子组件，切章收起由子组件 watch chapterNumber 处理
    chapterReader.stop()
  },
)

onMounted(() => {
  refreshBrowserVoices()
  window.speechSynthesis?.addEventListener('voiceschanged', refreshBrowserVoices)
})

onUnmounted(() => {
  window.speechSynthesis?.removeEventListener('voiceschanged', refreshBrowserVoices)
  chapterReader.stop()
})

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

.writing-workspace__tabs {
  display: flex;
  gap: 4px;
}

.writing-workspace__tab-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 38px;
  padding: 0 16px;
  border: 1px solid var(--md-outline-variant) !important;
  border-bottom: none !important;
  border-radius: 4px 4px 0 0 !important; /* 笺片式上圆角 */
  background-color: rgba(28, 32, 34, 0.015) !important;
  color: var(--md-on-surface-variant) !important;
  font-family: var(--md-font-serif);
  font-size: 13.5px;
  font-weight: 600;
  cursor: pointer;
  transition:
    background-color 0.2s ease,
    color 0.2s ease,
    box-shadow 0.2s ease;
}

.writing-workspace__tab-btn:hover {
  background-color: var(--md-surface-container-low) !important;
  color: var(--md-primary-dark) !important;
}

/* 激活的朱砂方章笺条 */
.writing-workspace__tab-btn.is-active {
  border: 1.5px solid var(--md-secondary) !important;
  border-bottom: 1.5px solid var(--md-surface) !important; /* 无缝贴合底线 */
  background-color: var(--md-surface) !important; /* 熟宣暖白 */
  color: var(--md-secondary) !important; /* 朱红色 */
  box-shadow: 0 1.5px 0px var(--md-surface);
  margin-bottom: -1.5px; /* 压住底线，呈现一体化连卷 */
  z-index: 10;
}

.tab-badge {
  font-size: 14px;
}

</style>
