<!-- AIMETA P=写作台工作区_主编辑区域|R=章节编辑_生成|NR=不含侧边栏|E=component:WDWorkspace|X=ui|A=工作区|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <section class="writing-workspace">
    <div class="md-card md-card-outlined writing-workspace__panel">
      <!-- 章节工作区头部 -->
      <div v-if="selectedChapterNumber" class="writing-workspace__header">
        <div class="writing-workspace__header-row">
          <div class="writing-workspace__chapter-meta">
            <div class="flex items-center gap-3 mb-2">
              <h2 class="md-title-large font-semibold">第{{ selectedChapterNumber }}章</h2>
              <span
                :class="[
                  'md-chip',
                  isChapterCompleted(selectedChapterNumber) ? 'm3-chip-success' : 'm3-chip-neutral',
                ]"
              >
                {{ isChapterCompleted(selectedChapterNumber) ? '已完成' : '未完成' }}
              </span>
            </div>
            <div class="flex items-center gap-3 mb-1 flex-wrap">
              <Tooltip :text="chapterTitleTooltipText" :show-delay="150">
                <button
                  type="button"
                  class="writing-workspace__title-copy md-title-medium md-on-surface"
                  @click="copySelectedChapterTitle"
                  @mouseleave="resetChapterTitleTooltip"
                >
                  {{ selectedChapterOutline?.title || '未知标题' }}
                </button>
              </Tooltip>
              <span class="md-body-small md-on-surface-variant whitespace-nowrap">
                {{ selectedChapterWordCount }} 字
              </span>
            </div>
            <p class="writing-workspace__summary md-body-small md-on-surface-variant">
              {{ selectedChapterOutline?.summary || '暂无章节描述' }}
            </p>
          </div>

          <div class="writing-workspace__actions">
            <button
              v-if="isChapterCompleted(selectedChapterNumber)"
              type="button"
              @click="copySelectedChapterContent"
              :disabled="!hasSelectedChapterContent"
              class="md-btn md-btn-outlined md-ripple flex items-center gap-2 whitespace-nowrap disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M8 7V5a2 2 0 012-2h6a2 2 0 012 2v6m-8 8h6a2 2 0 002-2v-6a2 2 0 00-2-2h-6a2 2 0 00-2 2v6a2 2 0 002 2zm-5-5h6a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2z"
                ></path>
              </svg>
              复制正文
            </button>
            <button
              v-if="isChapterCompleted(selectedChapterNumber)"
              type="button"
              @click="openEditModal"
              class="md-btn md-btn-tonal md-ripple flex items-center gap-2 whitespace-nowrap"
            >
              <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path
                  d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z"
                ></path>
              </svg>
              手动编辑
            </button>
            <button
              type="button"
              @click="confirmRegenerateChapter"
              :disabled="isSelectedChapterGeneratingLike"
              class="md-btn md-btn-filled md-ripple flex items-center gap-2 whitespace-nowrap disabled:opacity-50"
            >
              <svg
                v-if="isSelectedChapterGeneratingLike"
                class="w-4 h-4 animate-spin"
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path
                  fill-rule="evenodd"
                  d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z"
                  clip-rule="evenodd"
                ></path>
              </svg>
              <svg v-else class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path
                  fill-rule="evenodd"
                  d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z"
                  clip-rule="evenodd"
                ></path>
              </svg>
              {{ isSelectedChapterGeneratingLike ? '生成中...' : '重新生成' }}
            </button>
          </div>
        </div>
      </div>

      <!-- 章节内容展示区 -->
      <div class="writing-workspace__content">
        <component
          :is="currentComponent"
          v-bind="currentComponentProps"
          @hideVersionSelector="$emit('hideVersionSelector')"
          @update:selectedVersionIndex="$emit('update:selectedVersionIndex', $event)"
          @showVersionDetail="$emit('showVersionDetail', $event)"
          @confirmVersionSelection="$emit('confirmVersionSelection')"
          @generateChapter="$emit('generateChapter', $event)"
          @showVersionSelector="$emit('showVersionSelector')"
          @regenerateChapter="$emit('regenerateChapter')"
          @evaluateChapter="$emit('evaluateChapter')"
          @showEvaluationDetail="$emit('showEvaluationDetail')"
        />
      </div>
    </div>

    <!-- 编辑章节内容模态框 -->
    <div v-if="showEditModal" class="md-dialog-overlay">
      <div class="md-dialog w-full h-full max-w-5xl m3-editor-dialog">
        <!-- 模态框头部 -->
        <div
          class="flex items-center justify-between p-6 border-b"
          style="border-bottom-color: var(--md-outline-variant)"
        >
          <h3 class="md-title-large font-semibold">编辑第{{ selectedChapterNumber }}章内容</h3>
          <button
            type="button"
            @click="closeEditModal"
            class="md-icon-btn md-ripple"
            aria-label="关闭编辑窗口"
          >
            <svg class="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
              <path
                fill-rule="evenodd"
                d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                clip-rule="evenodd"
              ></path>
            </svg>
          </button>
        </div>

        <!-- 模态框内容 -->
        <div class="flex-1 p-6 overflow-hidden">
          <div class="flex flex-col h-full">
            <label class="md-text-field-label mb-2"> 章节内容 </label>
            <textarea
              v-model="editingContent"
              class="md-textarea flex-1 w-full resize-none"
              placeholder="请输入章节内容..."
              :disabled="isSaving"
            ></textarea>
            <div class="md-body-small md-on-surface-variant mt-2">
              字数统计: {{ editingWordCount }}
            </div>
          </div>
        </div>

        <!-- 模态框底部 -->
        <div
          class="flex items-center justify-end gap-3 p-6 border-t"
          style="border-top-color: var(--md-outline-variant)"
        >
          <button
            type="button"
            @click="closeEditModal"
            :disabled="isSaving"
            class="md-btn md-btn-outlined md-ripple disabled:opacity-50"
          >
            取消
          </button>
          <button
            type="button"
            @click="saveEditedContent"
            :disabled="isSaving || !editingContent.trim()"
            class="md-btn md-btn-filled md-ripple disabled:opacity-50 flex items-center gap-2"
          >
            <svg
              v-if="isSaving"
              class="w-4 h-4 animate-spin"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fill-rule="evenodd"
                d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z"
                clip-rule="evenodd"
              ></path>
            </svg>
            {{ isSaving ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch, onUnmounted } from 'vue'
import Tooltip from '@/components/Tooltip.vue'
import { globalAlert } from '@/composables/useAlert'
import type {
  Chapter,
  ChapterOutline,
  ChapterGenerationResponse,
  ChapterVersion,
  NovelProject,
} from '@/api/novel'
import { countNonWhitespaceChars } from '@/utils/text'
import WorkspaceInitial from './workspace/WorkspaceInitial.vue'
import ChapterGenerating from './workspace/ChapterGenerating.vue'
import VersionSelector from './workspace/VersionSelector.vue'
import ChapterContent from './workspace/ChapterContent.vue'
import ChapterFailed from './workspace/ChapterFailed.vue'
import ChapterEmpty from './workspace/ChapterEmpty.vue'

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
  'showVersionSelector',
  'showEvaluationDetail',
  'fetchChapterStatus',
  'editChapter',
])

const confirmRegenerateChapter = async () => {
  const confirmed = await globalAlert.showConfirm(
    '重新生成会覆盖当前章节的现有内容，确定继续吗？',
    '重新生成确认',
  )
  if (confirmed) {
    emit('regenerateChapter')
  }
}

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
  const content = cleanVersionContent(selectedChapter.value?.content || '').trim()
  if (!content) return

  const copied = await copyText(content)
  if (!copied) {
    globalAlert.showError('复制失败，请手动选择文本复制。')
  }
}

// 编辑模态框状态
const showEditModal = ref(false)
const editingContent = ref('')
const isSaving = ref(false)

// 清理版本内容的辅助函数
const cleanVersionContent = (content: string): string => {
  if (!content) return ''
  try {
    const parsed = JSON.parse(content)
    const extractContent = (value: any): string | null => {
      if (!value) return null
      if (typeof value === 'string') return value
      if (Array.isArray(value)) {
        for (const item of value) {
          const nested = extractContent(item)
          if (nested) return nested
        }
        return null
      }
      if (typeof value === 'object') {
        for (const key of ['content', 'chapter_content', 'chapter_text', 'text', 'body', 'story']) {
          if (value[key]) {
            const nested = extractContent(value[key])
            if (nested) return nested
          }
        }
      }
      return null
    }
    const extracted = extractContent(parsed)
    if (extracted) {
      content = extracted
    }
  } catch (error) {
    // not a json
  }
  let cleaned = content.replace(/^"|"$/g, '')
  cleaned = cleaned.replace(/\\n/g, '\n')
  cleaned = cleaned.replace(/\\"/g, '"')
  cleaned = cleaned.replace(/\\t/g, '\t')
  cleaned = cleaned.replace(/\\\\/g, '\\')
  return cleaned
}

const editingWordCount = computed(() => countNonWhitespaceChars(editingContent.value))

const openEditModal = () => {
  if (selectedChapter.value?.content) {
    editingContent.value = cleanVersionContent(selectedChapter.value.content)
    showEditModal.value = true
  }
}

const closeEditModal = () => {
  showEditModal.value = false
  editingContent.value = ''
  isSaving.value = false
}

const saveEditedContent = async () => {
  if (!props.selectedChapterNumber || !editingContent.value.trim()) return

  isSaving.value = true
  try {
    emit('editChapter', {
      chapterNumber: props.selectedChapterNumber,
      content: editingContent.value,
    })
    closeEditModal()
  } catch (error) {
    console.error('保存章节内容失败:', error)
  } finally {
    isSaving.value = false
  }
}

const selectedChapter = computed(() => {
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

const hasSelectedChapterContent = computed(() => {
  const content = selectedChapter.value?.content
  return typeof content === 'string' && content.trim().length > 0
})

const selectedChapterWordCount = computed(() =>
  countNonWhitespaceChars(cleanVersionContent(selectedChapter.value?.content || '')),
)

const isChapterCompleted = (chapterNumber: number) => {
  if (!props.project?.chapters) return false
  const chapter = props.project.chapters.find((ch) => ch.chapter_number === chapterNumber)
  return chapter && chapter.generation_status === 'successful'
}

const isChapterGenerating = (chapterNumber: number) => {
  if (!props.project?.chapters) return false
  const chapter = props.project.chapters.find((ch) => ch.chapter_number === chapterNumber)
  return chapter && chapter.generation_status === 'generating'
}

const isSelectedChapterGeneratingLike = computed(() => {
  if (props.selectedChapterNumber === null) return false
  return (
    props.generatingChapter === props.selectedChapterNumber ||
    isChapterGenerating(props.selectedChapterNumber)
  )
})

const isChapterFailed = (chapterNumber: number) => {
  if (!props.project?.chapters) return false
  const chapter = props.project.chapters.find((ch) => ch.chapter_number === chapterNumber)
  return chapter && chapter.generation_status === 'failed'
}

const isChapterEvaluationFailed = (chapterNumber: number) => {
  if (!props.project?.chapters) return false
  const chapter = props.project.chapters.find((ch) => ch.chapter_number === chapterNumber)
  return chapter && chapter.generation_status === 'evaluation_failed'
}

const isInProgressStatus = (status: Chapter['generation_status'] | null | undefined) => {
  return status === 'generating' || status === 'evaluating' || status === 'selecting'
}

const isGeneratingInFlight = computed(() => {
  if (props.selectedChapterNumber === null) return false
  if (props.generatingChapter !== props.selectedChapterNumber) return false

  // Regenerating a completed chapter can briefly keep backend status as `successful`
  // before the async pipeline updates to `generating`.
  // Keep showing progress UI while local request is still in-flight.
  const status = selectedChapter.value?.generation_status
  return !(status === 'waiting_for_confirm' || status === 'selecting')
})

const canGenerateChapter = (chapterNumber: number | null) => {
  if (chapterNumber === null || !props.project?.blueprint?.chapter_outline) return false

  const outlines = props.project.blueprint.chapter_outline.sort(
    (a, b) => a.chapter_number - b.chapter_number,
  )

  for (const outline of outlines) {
    if (outline.chapter_number >= chapterNumber) break

    const chapter = props.project?.chapters.find(
      (ch) => ch.chapter_number === outline.chapter_number,
    )
    if (!chapter || chapter.generation_status !== 'successful') {
      return false
    }
  }

  const currentChapter = props.project?.chapters.find((ch) => ch.chapter_number === chapterNumber)
  if (currentChapter && currentChapter.generation_status === 'successful') {
    return true
  }

  return true
}

const currentComponent = computed(() => {
  if (!props.selectedChapterNumber) {
    return WorkspaceInitial
  }

  const status = selectedChapter.value?.generation_status
  const shouldRenderGenerating =
    (isInProgressStatus(status) || isGeneratingInFlight.value) &&
    !(status === 'successful' && hasSelectedChapterContent.value)
  if (shouldRenderGenerating) {
    return ChapterGenerating // Use a generic "in-progress" component
  }

  // 优先展示已同步到前端的正文，避免状态短暂滞后时必须手动刷新
  if (hasSelectedChapterContent.value) {
    return ChapterContent
  }

  if (status === 'waiting_for_confirm' || status === 'evaluation_failed') {
    return VersionSelector
  }

  if (isChapterFailed(props.selectedChapterNumber)) {
    return ChapterFailed
  }
  return ChapterEmpty
})

// Polling for chapter status updates
const pollingTimer = ref<number | null>(null)
const lastPollingChapterNumber = ref<number | null>(null)
const POLLING_INTERVAL_MS = 3000

const requestChapterStatus = () => {
  emit('fetchChapterStatus')
}

const startPolling = (immediate: boolean = false) => {
  // 已在轮询中时不重复启动，避免重置定时器导致请求风暴
  if (pollingTimer.value !== null) {
    return
  }
  if (immediate) {
    requestChapterStatus()
  }
  pollingTimer.value = window.setInterval(() => {
    requestChapterStatus()
  }, POLLING_INTERVAL_MS)
}

const stopPolling = () => {
  if (pollingTimer.value) {
    clearInterval(pollingTimer.value)
    pollingTimer.value = null
  }
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
      stopPolling()
      lastPollingChapterNumber.value = null
      return
    }

    // 需要轮询的场景：
    // 1) 生成/评审/选择中（状态推进）
    // 2) 等待确认但正文还没同步（含版本已到但正文未到的短暂窗口）
    // 3) 已成功但正文暂未同步（避免必须手动刷新）
    const needsPolling =
      status === 'generating' ||
      status === 'evaluating' ||
      status === 'selecting' ||
      (status === 'waiting_for_confirm' && !hasContent) ||
      (status === 'successful' && !hasContent)

    if (needsPolling) {
      const chapterChanged = chapterNumber !== lastPollingChapterNumber.value
      const shouldRequestImmediately = pollingTimer.value === null || chapterChanged
      startPolling(shouldRequestImmediately)
    } else {
      stopPolling()
    }
    lastPollingChapterNumber.value = chapterNumber
  },
  { immediate: true },
)

onUnmounted(() => {
  stopPolling()
})

const currentComponentProps = computed(() => {
  if (!props.selectedChapterNumber) {
    return {}
  }
  const status = selectedChapter.value?.generation_status
  const isBackendInProgress = isInProgressStatus(status)
  const shouldRenderGenerating =
    (isBackendInProgress || isGeneratingInFlight.value) &&
    !(status === 'successful' && hasSelectedChapterContent.value)
  if (shouldRenderGenerating) {
    const renderStatus = isBackendInProgress ? status : 'generating'
    return {
      chapterNumber: props.selectedChapterNumber,
      status: renderStatus,
      generationProgress: isBackendInProgress
        ? (selectedChapter.value?.generation_progress ?? null)
        : null,
      generationStep: isBackendInProgress ? (selectedChapter.value?.generation_step ?? null) : null,
      generationStepIndex: isBackendInProgress
        ? (selectedChapter.value?.generation_step_index ?? null)
        : null,
      generationStepTotal: isBackendInProgress
        ? (selectedChapter.value?.generation_step_total ?? null)
        : null,
      generationStartedAt: isBackendInProgress
        ? (selectedChapter.value?.generation_started_at ?? null)
        : null,
      statusUpdatedAt: isBackendInProgress
        ? (selectedChapter.value?.status_updated_at ?? null)
        : null,
    }
  }

  if (
    (status === 'waiting_for_confirm' || status === 'evaluation_failed') &&
    !hasSelectedChapterContent.value
  ) {
    return {
      selectedChapter: selectedChapter.value,
      chapterGenerationResult: props.chapterGenerationResult,
      availableVersions: props.availableVersions,
      selectedVersionIndex: props.selectedVersionIndex,
      isSelectingVersion: props.isSelectingVersion,
      evaluatingChapter: props.evaluatingChapter,
      isEvaluationFailed: isChapterEvaluationFailed(props.selectedChapterNumber),
    }
  }
  if (hasSelectedChapterContent.value) {
    return {
      selectedChapter: selectedChapter.value,
      projectId: props.project?.id,
    }
  }
  if (isChapterFailed(props.selectedChapterNumber)) {
    return {
      chapterNumber: props.selectedChapterNumber,
      generatingChapter: props.generatingChapter,
    }
  }
  return {
    chapterNumber: props.selectedChapterNumber,
    generatingChapter: props.generatingChapter,
    canGenerate: canGenerateChapter(props.selectedChapterNumber),
  }
})
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
  border-radius: var(--md-radius-xl);
  background-color: var(--md-surface);
}

.writing-workspace__header {
  flex-shrink: 0;
  padding: var(--md-spacing-5) var(--md-spacing-5) var(--md-spacing-4);
  border-bottom: 1px solid var(--md-outline-variant);
  background-color: color-mix(in srgb, var(--md-surface) 88%, var(--md-surface-container-low));
}

.writing-workspace__header-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--md-spacing-5);
}

.writing-workspace__chapter-meta {
  min-width: 0;
}

.writing-workspace__title-copy {
  padding: 0;
  border: 0;
  background: transparent;
  text-align: left;
  cursor: pointer;
  appearance: none;
  transition: color var(--md-duration-short) var(--md-easing-standard);
}

.writing-workspace__title-copy:hover {
  color: var(--md-primary-dark);
}

.writing-workspace__title-copy:focus-visible {
  outline: 2px solid var(--md-primary);
  outline-offset: 3px;
  border-radius: var(--md-radius-xs);
}

.writing-workspace__summary {
  max-width: 86ch;
  line-height: 1.6;
}

.writing-workspace__actions {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: flex-end;
  gap: var(--md-spacing-2);
  flex-wrap: wrap;
}

.writing-workspace__content {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: var(--md-spacing-5);
}

.m3-chip-success {
  background-color: var(--md-success-container);
  color: var(--md-on-success-container);
}

.m3-chip-neutral {
  background-color: var(--md-surface-container);
  color: var(--md-on-surface-variant);
}

.m3-editor-dialog {
  max-width: min(1200px, calc(100vw - 32px));
  max-height: calc(100vh - 32px);
  border-radius: var(--md-radius-xl);
}

@media (max-width: 900px) {
  .writing-workspace__header-row {
    flex-direction: column;
    gap: var(--md-spacing-4);
  }

  .writing-workspace__actions {
    width: 100%;
    justify-content: flex-start;
  }
}

@media (max-width: 640px) {
  .writing-workspace__header {
    padding: var(--md-spacing-4);
  }

  .writing-workspace__content {
    padding: var(--md-spacing-4);
  }

  .writing-workspace__actions .md-btn {
    flex: 1 1 auto;
    min-width: min(100%, 132px);
  }
}
</style>
