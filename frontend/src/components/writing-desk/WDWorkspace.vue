<!-- AIMETA P=写作台工作区_主编辑区域|R=章节编辑_生成|NR=不含侧边栏|E=component:WDWorkspace|X=ui|A=工作区|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <section class="writing-workspace">
    <div class="md-card md-card-outlined writing-workspace__panel">
      <!-- 章节工作区头部 -->
      <div v-if="selectedChapterNumber !== null" class="writing-workspace__header">
        <div class="writing-workspace__header-row">
          <div class="writing-workspace__chapter-meta">
            <div class="writing-workspace__chapter-title-line">
              <h2 class="md-title-large font-semibold writing-workspace__chapter-no">
                第{{ selectedChapterNumber }}章
              </h2>
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
              <span
                class="writing-workspace__status-tag"
                :class="`writing-workspace__status-tag--${chapterStatusTone}`"
              >
                {{ chapterStatusLabel }}
              </span>
              <span class="writing-workspace__chapter-inline-meta md-label-small md-on-surface-variant">
                {{ chapterInlineMeta }}
              </span>
            </div>
            <p class="writing-workspace__summary md-body-small md-on-surface-variant">
              {{ selectedChapterOutline?.summary || '暂无章节描述' }}
            </p>
          </div>
          <aside class="writing-workspace__toolbar" role="toolbar" aria-label="章节操作">
            <div class="writing-workspace__toolbar-row writing-workspace__toolbar-row--utility">
              <div class="writing-workspace__toolbar-group writing-workspace__toolbar-group--utility">
                <button
                  type="button"
                  @click="copySelectedChapterContent"
                  :disabled="!hasSelectedChapterContent"
                  class="md-btn md-btn-text md-ripple writing-workspace__tool-btn writing-workspace__tool-btn--ghost disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  复制
                </button>
                <button
                  type="button"
                  @click="exportContentAsTxt"
                  :disabled="!isChapterContentView"
                  class="md-btn md-btn-text md-ripple writing-workspace__tool-btn writing-workspace__tool-btn--ghost disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  导出
                </button>
                <button
                  type="button"
                  @click="openVersionDetail"
                  :disabled="!canViewVersions"
                  class="md-btn md-btn-text md-ripple writing-workspace__tool-btn writing-workspace__tool-btn--ghost disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  查看版本
                </button>
              </div>

              <span class="writing-workspace__toolbar-divider" aria-hidden="true"></span>

              <div ref="moreMenuRef" class="writing-workspace__more-menu">
                <button
                  ref="moreMenuTriggerRef"
                  type="button"
                  @click="toggleMoreMenu"
                  class="md-btn md-btn-text md-ripple writing-workspace__tool-btn writing-workspace__tool-btn--ghost"
                  :aria-expanded="showMoreMenu ? 'true' : 'false'"
                  aria-haspopup="menu"
                  :aria-controls="moreMenuId"
                >
                  更多
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M19 9l-7 7-7-7"
                    ></path>
                  </svg>
                </button>

                <div
                  v-if="showMoreMenu"
                  :id="moreMenuId"
                  ref="moreMenuPanelRef"
                  class="writing-workspace__more-menu-panel"
                  role="menu"
                  tabindex="-1"
                  @keydown="handleMoreMenuKeydown"
                >
                  <button
                    :ref="(el) => registerMoreMenuItemRef(el, 0)"
                    type="button"
                    role="menuitem"
                    @click="handleCopyFromMore"
                    :disabled="!hasSelectedChapterContent"
                    class="writing-workspace__more-menu-item disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    复制
                  </button>
                  <button
                    :ref="(el) => registerMoreMenuItemRef(el, 1)"
                    type="button"
                    role="menuitem"
                    @click="handleExportFromMore"
                    :disabled="!isChapterContentView"
                    class="writing-workspace__more-menu-item disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    导出
                  </button>
                  <button
                    :ref="(el) => registerMoreMenuItemRef(el, 2)"
                    type="button"
                    role="menuitem"
                    @click="handleViewVersionFromMore"
                    :disabled="!canViewVersions"
                    class="writing-workspace__more-menu-item disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    查看版本
                  </button>
                </div>
              </div>
            </div>

            <div class="writing-workspace__toolbar-row writing-workspace__toolbar-row--primary">
              <div class="writing-workspace__toolbar-group writing-workspace__toolbar-group--emphasis">
              <button
                type="button"
                @click="openEditModal"
                :disabled="!hasSelectedChapterContent"
                class="md-btn md-btn-outlined md-ripple writing-workspace__tool-btn writing-workspace__tool-btn--secondary writing-workspace__tool-btn--hero disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <span class="writing-workspace__label-full">编辑正文</span>
                <span class="writing-workspace__label-short">编辑</span>
              </button>

              <div ref="aiMenuRef" class="writing-workspace__ai-menu">
                <button
                  ref="aiMenuTriggerRef"
                  type="button"
                  @click="toggleAiMenu"
                  :disabled="isAiMenuDisabled"
                  class="md-btn md-btn-tonal md-ripple writing-workspace__tool-btn writing-workspace__tool-btn--primary writing-workspace__tool-btn--hero disabled:opacity-50 disabled:cursor-not-allowed"
                  :aria-expanded="showAiMenu ? 'true' : 'false'"
                  aria-haspopup="menu"
                  :aria-controls="aiMenuId"
                >
                  <span class="writing-workspace__label-full">AI优化</span>
                  <span class="writing-workspace__label-short">AI</span>
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M19 9l-7 7-7-7"
                    ></path>
                  </svg>
                </button>

                <div
                  v-if="showAiMenu"
                  :id="aiMenuId"
                  ref="aiMenuPanelRef"
                  class="writing-workspace__ai-menu-panel"
                  role="menu"
                  tabindex="-1"
                  @keydown="handleAiMenuKeydown"
                >
                  <button
                    :ref="(el) => registerAiMenuItemRef(el, 0)"
                    type="button"
                    role="menuitem"
                    @click="handleLayeredOptimize"
                    :disabled="!isChapterContentView"
                    class="writing-workspace__ai-menu-item disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    分层优化
                  </button>
                  <button
                    :ref="(el) => registerAiMenuItemRef(el, 1)"
                    type="button"
                    role="menuitem"
                    @click="handlePolishContent"
                    :disabled="!isChapterContentView"
                    class="writing-workspace__ai-menu-item disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    润色正文
                  </button>
                  <button
                    :ref="(el) => registerAiMenuItemRef(el, 2)"
                    type="button"
                    role="menuitem"
                    @click="handleAdjustRhythm"
                    :disabled="!isChapterContentView"
                    class="writing-workspace__ai-menu-item disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    调整节奏
                  </button>
                  <button
                    :ref="(el) => registerAiMenuItemRef(el, 3)"
                    type="button"
                    role="menuitem"
                    @click="handleRewriteStyle"
                    :disabled="!isChapterContentView"
                    class="writing-workspace__ai-menu-item disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    改写风格
                  </button>
                  <button
                    :ref="(el) => registerAiMenuItemRef(el, 4)"
                    type="button"
                    role="menuitem"
                    @click="handleRegenerateFromMenu"
                    :disabled="isSelectedChapterGeneratingLike"
                    class="writing-workspace__ai-menu-item writing-workspace__ai-menu-item--danger disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {{ isSelectedChapterGeneratingLike ? '生成中...' : '重新生成' }}
                  </button>
                </div>
              </div>
              </div>
            </div>
          </aside>
        </div>
      </div>

      <!-- 章节内容展示区 -->
      <div class="writing-workspace__content">
        <div class="writing-workspace__body">
          <component
            ref="bodyComponentRef"
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
    </div>

    <!-- 编辑章节内容模态框 -->
    <div v-if="showEditModal" class="md-dialog-overlay" @click.self="closeEditModal">
      <div
        ref="editDialogRef"
        class="md-dialog w-full h-full max-w-5xl m3-editor-dialog"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="editDialogTitleId"
      >
        <!-- 模态框头部 -->
        <div
          class="flex items-center justify-between p-6 border-b"
          style="border-bottom-color: var(--md-outline-variant)"
        >
          <h3 :id="editDialogTitleId" class="md-title-large font-semibold">
            编辑第{{ selectedChapterNumber }}章内容
          </h3>
          <button
            ref="editCloseButtonRef"
            data-dialog-initial-focus
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
            <label :for="editingContentInputId" class="md-text-field-label mb-2"> 章节内容 </label>
            <textarea
              :id="editingContentInputId"
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
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import Tooltip from '@/components/Tooltip.vue'
import { globalAlert } from '@/composables/useAlert'
import { useDialogA11y } from '@/composables/useDialogA11y'
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

interface ChapterContentExpose {
  openOptimizerPanel?: () => void
  openOptimizerPanelWithPreset?: (preset?: { dimension?: string; notes?: string }) => void
  exportCurrentChapterAsTxt?: () => void
}

const bodyComponentRef = ref<ChapterContentExpose | null>(null)
const aiMenuRef = ref<HTMLElement | null>(null)
const moreMenuRef = ref<HTMLElement | null>(null)
const aiMenuPanelRef = ref<HTMLElement | null>(null)
const moreMenuPanelRef = ref<HTMLElement | null>(null)
const aiMenuTriggerRef = ref<HTMLButtonElement | null>(null)
const moreMenuTriggerRef = ref<HTMLButtonElement | null>(null)
const aiMenuItemRefs = ref<Array<HTMLElement | null>>([])
const moreMenuItemRefs = ref<Array<HTMLElement | null>>([])
const aiMenuId = 'wd-workspace-ai-menu'
const moreMenuId = 'wd-workspace-more-menu'
const showAiMenu = ref(false)
const showMoreMenu = ref(false)

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
  const content = selectedChapterResolvedContent.value.trim()
  if (!content) return

  const copied = await copyText(content)
  if (!copied) {
    globalAlert.showError('复制失败，请手动选择文本复制。')
  }
}

// 编辑模态框状态
const showEditModal = ref(false)
const editDialogRef = ref<HTMLElement | null>(null)
const editCloseButtonRef = ref<HTMLElement | null>(null)
const editDialogTitleId = 'wd-workspace-edit-dialog-title'
const editingContentInputId = 'wd-workspace-edit-content-input'
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
  if (hasSelectedChapterContent.value) {
    editingContent.value = selectedChapterResolvedContent.value
    showEditModal.value = true
  }
}

const closeEditModal = () => {
  if (isSaving.value) return
  showEditModal.value = false
  editingContent.value = ''
  isSaving.value = false
}

useDialogA11y({
  active: showEditModal,
  dialogRef: editDialogRef,
  onClose: closeEditModal,
  initialFocusRef: editCloseButtonRef,
})

const saveEditedContent = async () => {
  if (props.selectedChapterNumber === null || !editingContent.value.trim()) return

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

const resolveChapterContent = (chapter: Chapter | null): string => {
  if (!chapter) {
    return ''
  }

  const directContent = cleanVersionContent(chapter?.content || '')
  if (directContent.trim()) {
    return directContent
  }

  for (const version of props.availableVersions) {
    const normalized = cleanVersionContent(version.content || '')
    if (normalized.trim()) {
      return normalized
    }
  }

  return ''
}

const selectedChapterResolvedContent = computed(() => resolveChapterContent(selectedChapter.value))

const selectedChapterForDisplay = computed<Chapter | null>(() => {
  const chapter = selectedChapter.value
  if (!chapter) return null
  if (chapter.content && cleanVersionContent(chapter.content).trim()) {
    return chapter
  }
  return {
    ...chapter,
    content: selectedChapterResolvedContent.value,
  }
})

const hasSelectedChapterContent = computed(() => {
  return selectedChapterResolvedContent.value.trim().length > 0
})

const selectedChapterWordCount = computed(() => countNonWhitespaceChars(selectedChapterResolvedContent.value))

const chapterStatusLabel = computed(() => {
  const status = selectedChapter.value?.generation_status
  switch (status) {
    case 'successful':
      return '已完成'
    case 'generating':
      return '生成中'
    case 'evaluating':
      return '评审中'
    case 'selecting':
      return '选择版本'
    case 'waiting_for_confirm':
      return '待确认'
    case 'failed':
      return '生成失败'
    case 'evaluation_failed':
      return '评审失败'
    default:
      return '待开始'
  }
})

const chapterStatusTone = computed(() => {
  const status = selectedChapter.value?.generation_status
  if (status === 'successful') return 'success'
  if (status === 'failed' || status === 'evaluation_failed') return 'error'
  if (status === 'generating' || status === 'evaluating' || status === 'selecting') return 'progress'
  if (status === 'waiting_for_confirm') return 'pending'
  return 'idle'
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
  if (props.selectedChapterNumber === null) {
    return WorkspaceInitial
  }

  const status = selectedChapter.value?.generation_status
  const shouldRenderGenerating =
    (isInProgressStatus(status) || isGeneratingInFlight.value) &&
    !(status === 'successful' && hasSelectedChapterContent.value)
  if (shouldRenderGenerating) {
    return ChapterGenerating // Use a generic "in-progress" component
  }

  if (status === 'waiting_for_confirm' || status === 'evaluation_failed') {
    return VersionSelector
  }

  // 仅在不处于选版态时展示正文，避免生成完成后看不到新版本选择区。
  if (hasSelectedChapterContent.value) {
    return ChapterContent
  }

  if (isChapterFailed(props.selectedChapterNumber)) {
    return ChapterFailed
  }
  return ChapterEmpty
})

const isChapterContentView = computed(
  () => currentComponent.value === ChapterContent && hasSelectedChapterContent.value,
)
const canViewVersions = computed(() => props.availableVersions.length > 0)
const isAiMenuDisabled = computed(
  () => isSelectedChapterGeneratingLike.value && !isChapterContentView.value,
)

const resolveMenuElement = (element: unknown) => {
  if (element instanceof HTMLElement) {
    return element
  }
  if (element && typeof element === 'object' && '$el' in element) {
    const componentElement = (element as { $el?: unknown }).$el
    if (componentElement instanceof HTMLElement) {
      return componentElement
    }
  }
  return null
}

const registerAiMenuItemRef = (element: unknown, index: number) => {
  aiMenuItemRefs.value[index] = resolveMenuElement(element)
}

const registerMoreMenuItemRef = (element: unknown, index: number) => {
  moreMenuItemRefs.value[index] = resolveMenuElement(element)
}

const getEnabledMenuItems = (items: Array<HTMLElement | null>) => {
  return items.filter((item) => item && !item.hasAttribute('disabled')) as HTMLElement[]
}

const focusMenuItemAtIndex = (items: Array<HTMLElement | null>, targetIndex: number) => {
  const enabledItems = getEnabledMenuItems(items)
  if (enabledItems.length === 0) return
  const safeIndex = ((targetIndex % enabledItems.length) + enabledItems.length) % enabledItems.length
  enabledItems[safeIndex]?.focus()
}

const focusFirstMenuItem = (items: Array<HTMLElement | null>) => {
  focusMenuItemAtIndex(items, 0)
}

const handleMenuKeydown = (
  event: KeyboardEvent,
  items: Array<HTMLElement | null>,
  closeMenu: (restoreFocus?: boolean) => void,
) => {
  const enabledItems = getEnabledMenuItems(items)
  if (enabledItems.length === 0) return

  const activeElement = document.activeElement as HTMLElement | null
  const currentIndex = enabledItems.findIndex((item) => item === activeElement)

  if (event.key === 'Escape') {
    event.preventDefault()
    closeMenu(true)
    return
  }

  if (event.key === 'Tab') {
    closeMenu()
    return
  }

  if (event.key === 'ArrowDown') {
    event.preventDefault()
    focusMenuItemAtIndex(enabledItems, currentIndex + 1)
    return
  }

  if (event.key === 'ArrowUp') {
    event.preventDefault()
    focusMenuItemAtIndex(enabledItems, currentIndex - 1)
    return
  }

  if (event.key === 'Home') {
    event.preventDefault()
    focusMenuItemAtIndex(enabledItems, 0)
    return
  }

  if (event.key === 'End') {
    event.preventDefault()
    focusMenuItemAtIndex(enabledItems, enabledItems.length - 1)
  }
}

const handleAiMenuKeydown = (event: KeyboardEvent) => {
  handleMenuKeydown(event, aiMenuItemRefs.value, closeAiMenu)
}

const handleMoreMenuKeydown = (event: KeyboardEvent) => {
  handleMenuKeydown(event, moreMenuItemRefs.value, closeMoreMenu)
}

const closeAiMenu = (restoreFocus: boolean = false) => {
  showAiMenu.value = false
  if (restoreFocus) {
    aiMenuTriggerRef.value?.focus()
  }
}

const closeMoreMenu = (restoreFocus: boolean = false) => {
  showMoreMenu.value = false
  if (restoreFocus) {
    moreMenuTriggerRef.value?.focus()
  }
}

const toggleAiMenu = () => {
  if (isAiMenuDisabled.value) return
  closeMoreMenu()
  showAiMenu.value = !showAiMenu.value
  if (showAiMenu.value) {
    nextTick(() => {
      focusFirstMenuItem(aiMenuItemRefs.value)
    })
  }
}

const toggleMoreMenu = () => {
  closeAiMenu()
  showMoreMenu.value = !showMoreMenu.value
  if (showMoreMenu.value) {
    nextTick(() => {
      focusFirstMenuItem(moreMenuItemRefs.value)
    })
  }
}

const openVersionDetail = () => {
  if (!canViewVersions.value) {
    globalAlert.showError('当前章节暂无可查看版本')
    return
  }

  const maxIndex = props.availableVersions.length - 1
  const safeIndex = Math.min(Math.max(props.selectedVersionIndex, 0), maxIndex)
  emit('showVersionDetail', safeIndex)
}

const openContentOptimizer = () => {
  bodyComponentRef.value?.openOptimizerPanel?.()
}

const openContentOptimizerWithPreset = (preset?: { dimension?: string; notes?: string }) => {
  bodyComponentRef.value?.openOptimizerPanelWithPreset?.(preset)
}

const exportContentAsTxt = () => {
  bodyComponentRef.value?.exportCurrentChapterAsTxt?.()
}

const handleCopyFromMore = async () => {
  closeMoreMenu()
  await copySelectedChapterContent()
}

const handleExportFromMore = () => {
  closeMoreMenu()
  exportContentAsTxt()
}

const handleViewVersionFromMore = () => {
  closeMoreMenu()
  openVersionDetail()
}

const handleLayeredOptimize = () => {
  closeAiMenu()
  if (!isChapterContentView.value) return
  openContentOptimizer()
}

const handlePolishContent = () => {
  closeAiMenu()
  if (!isChapterContentView.value) return
  openContentOptimizerWithPreset({
    dimension: 'dialogue',
    notes: '请优先润色正文表达，让叙述更顺滑、更有画面感。',
  })
}

const handleAdjustRhythm = () => {
  closeAiMenu()
  if (!isChapterContentView.value) return
  openContentOptimizerWithPreset({
    dimension: 'rhythm',
    notes: '请重点调整章节节奏，控制信息密度与推进速度。',
  })
}

const handleRewriteStyle = () => {
  closeAiMenu()
  if (!isChapterContentView.value) return
  openContentOptimizerWithPreset({
    dimension: 'dialogue',
    notes: '请在不改变剧情事实的前提下改写文风，统一语气并提升辨识度。',
  })
}

const handleRegenerateFromMenu = async () => {
  closeAiMenu()
  if (isSelectedChapterGeneratingLike.value) return
  await confirmRegenerateChapter()
}

const handleAiMenuOutsideClick = (event: MouseEvent) => {
  const targetNode = event.target as Node | null
  if (!targetNode) return
  if (showAiMenu.value && !aiMenuRef.value?.contains(targetNode)) {
    showAiMenu.value = false
  }
  if (showMoreMenu.value && !moreMenuRef.value?.contains(targetNode)) {
    showMoreMenu.value = false
  }
}

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

watch(
  () => props.selectedChapterNumber,
  () => {
    closeAiMenu()
    closeMoreMenu()
  },
)

onMounted(() => {
  document.addEventListener('click', handleAiMenuOutsideClick)
})

onUnmounted(() => {
  document.removeEventListener('click', handleAiMenuOutsideClick)
  stopPolling()
})

const currentComponentProps = computed(() => {
  if (props.selectedChapterNumber === null) {
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
      chapterTitle: selectedChapterOutline.value?.title || '',
      chapterSummary: selectedChapterOutline.value?.summary || '',
      chapterContentPreview: cleanVersionContent(selectedChapter.value?.content || ''),
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

  if (status === 'waiting_for_confirm' || status === 'evaluation_failed') {
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
      selectedChapter: selectedChapterForDisplay.value,
      projectId: props.project?.id,
    }
  }
  if (isChapterFailed(props.selectedChapterNumber)) {
    return {
      chapterNumber: props.selectedChapterNumber,
      generatingChapter: props.generatingChapter,
      generationStatus: selectedChapter.value?.generation_status ?? 'failed',
      generationStep: selectedChapter.value?.generation_step ?? null,
      chapterContentPreview: cleanVersionContent(selectedChapter.value?.content || ''),
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
  background:
    linear-gradient(
      180deg,
      color-mix(in srgb, var(--md-surface) 96%, transparent),
      color-mix(in srgb, var(--md-surface-container-low) 82%, transparent)
    );
  border-color: color-mix(in srgb, var(--md-outline-variant) 82%, transparent);
}

.writing-workspace__header {
  flex-shrink: 0;
  padding: var(--md-spacing-4) var(--md-spacing-5);
  border-bottom: 1px solid var(--md-outline-variant);
  background-color: color-mix(in srgb, var(--md-surface) 92%, var(--md-surface-container-low));
}

.writing-workspace__header-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--md-spacing-4);
}

.writing-workspace__chapter-meta {
  flex: 1 1 auto;
  min-width: 0;
}

.writing-workspace__chapter-title-line {
  display: flex;
  align-items: center;
  gap: var(--md-spacing-2);
  margin-bottom: var(--md-spacing-1);
  flex-wrap: wrap;
}

.writing-workspace__chapter-no {
  flex-shrink: 0;
  font-size: clamp(1.2rem, 1.8vw, 1.45rem);
}

.writing-workspace__status-tag {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border-radius: 7px;
  border: 1px solid transparent;
  font-size: var(--md-label-small);
  font-weight: 600;
  letter-spacing: 0.02em;
  white-space: nowrap;
}

.writing-workspace__status-tag--success {
  color: color-mix(in srgb, var(--md-success) 78%, var(--md-on-surface));
  background-color: color-mix(in srgb, var(--md-success-container) 78%, var(--md-surface));
  border-color: color-mix(in srgb, var(--md-success) 26%, var(--md-outline-variant));
}

.writing-workspace__status-tag--error {
  color: color-mix(in srgb, var(--md-error) 80%, var(--md-on-surface));
  background-color: color-mix(in srgb, var(--md-error-container) 74%, var(--md-surface));
  border-color: color-mix(in srgb, var(--md-error) 24%, var(--md-outline-variant));
}

.writing-workspace__status-tag--progress {
  color: color-mix(in srgb, var(--md-primary-dark) 80%, var(--md-on-surface));
  background-color: color-mix(in srgb, var(--md-primary-container) 78%, var(--md-surface));
  border-color: color-mix(in srgb, var(--md-primary) 24%, var(--md-outline-variant));
}

.writing-workspace__status-tag--pending {
  color: color-mix(in srgb, var(--md-secondary) 72%, var(--md-on-surface));
  background-color: color-mix(in srgb, var(--md-secondary-container) 74%, var(--md-surface));
  border-color: color-mix(in srgb, var(--md-secondary) 20%, var(--md-outline-variant));
}

.writing-workspace__status-tag--idle {
  color: var(--md-on-surface-variant);
  background-color: color-mix(in srgb, var(--md-surface-container-low) 90%, var(--md-surface));
  border-color: color-mix(in srgb, var(--md-outline-variant) 82%, transparent);
}

.writing-workspace__chapter-inline-meta {
  white-space: nowrap;
  letter-spacing: 0.01em;
}

.writing-workspace__title-copy {
  min-width: 0;
  flex: 1;
  padding: 0;
  border: 0;
  background: transparent;
  text-align: left;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
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
  max-width: 88ch;
  line-height: 1.6;
  color: color-mix(in srgb, var(--md-on-surface-variant) 86%, transparent);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.writing-workspace__toolbar {
  margin-left: auto;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  justify-content: flex-start;
  gap: 8px;
  padding-top: 4px;
  white-space: nowrap;
}

.writing-workspace__toolbar-row {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
  width: 100%;
}

.writing-workspace__toolbar-row--utility {
  opacity: 0.96;
}

.writing-workspace__toolbar-row--primary {
  justify-content: flex-end;
}

.writing-workspace__toolbar-group {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
}

.writing-workspace__toolbar-group--utility {
  gap: 6px;
}

.writing-workspace__toolbar-group--emphasis {
  gap: 8px;
}

.writing-workspace__toolbar-divider {
  width: 1px;
  height: 20px;
  background-color: color-mix(in srgb, var(--md-outline-variant) 72%, transparent);
}

.writing-workspace__tool-btn {
  min-height: 36px;
  height: 36px;
  padding-inline: 10px;
  border-radius: 8px;
  font-size: var(--md-label-medium);
  letter-spacing: 0.015em;
  box-shadow: none;
}

.writing-workspace__tool-btn--hero {
  height: 40px;
  min-height: 40px;
  padding-inline: 16px;
  font-size: var(--md-title-small);
  font-weight: 600;
  border-width: 1px;
}

@media (pointer: coarse) {
  .writing-workspace__tool-btn,
  .writing-workspace__tool-btn--hero {
    min-height: 44px;
    height: 44px;
  }
}

.writing-workspace__label-short {
  display: none;
}

.writing-workspace__tool-btn--ghost {
  border-color: color-mix(in srgb, var(--md-outline-variant) 56%, transparent);
  color: var(--md-on-surface-variant);
  background-color: transparent;
}

.writing-workspace__tool-btn--ghost:hover:not(:disabled) {
  color: var(--md-on-surface);
  background-color: color-mix(in srgb, var(--md-surface-container-low) 62%, var(--md-surface));
  border-color: color-mix(in srgb, var(--md-outline) 84%, transparent);
}

.writing-workspace__tool-btn--secondary {
  border-color: color-mix(in srgb, var(--md-primary) 18%, var(--md-outline-variant));
  background-color: color-mix(in srgb, var(--md-surface-container-low) 72%, var(--md-surface));
  color: var(--md-on-surface);
}

.writing-workspace__tool-btn--secondary.writing-workspace__tool-btn--hero {
  border-color: color-mix(in srgb, var(--md-primary) 24%, var(--md-outline-variant));
  box-shadow: var(--md-elevation-1);
}

.writing-workspace__tool-btn--primary {
  border-color: color-mix(in srgb, var(--md-primary) 26%, var(--md-outline-variant));
  background-color: color-mix(in srgb, var(--md-primary-container) 90%, var(--md-surface));
  color: var(--md-on-primary-container);
}

.writing-workspace__tool-btn--primary:hover:not(:disabled) {
  background-color: color-mix(in srgb, var(--md-primary-container) 95%, var(--md-surface));
  box-shadow: var(--md-elevation-2);
}

.writing-workspace__tool-btn--primary.writing-workspace__tool-btn--hero {
  border-color: color-mix(in srgb, var(--md-primary) 32%, var(--md-outline-variant));
  box-shadow: var(--md-elevation-2);
}

.writing-workspace__more-menu {
  position: relative;
  display: none;
}

.writing-workspace__more-menu-panel {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  z-index: 8;
  min-width: 148px;
  padding: 6px;
  border-radius: 10px;
  border: 1px solid color-mix(in srgb, var(--md-outline-variant) 86%, transparent);
  background: color-mix(in srgb, var(--md-surface) 94%, var(--md-surface-container-low));
  box-shadow: var(--md-elevation-2);
}

.writing-workspace__more-menu-item {
  display: block;
  width: 100%;
  min-height: 44px;
  padding: 10px 12px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  text-align: left;
  font-size: var(--md-label-medium);
  color: var(--md-on-surface);
  cursor: pointer;
  transition:
    background-color var(--md-duration-short) var(--md-easing-standard),
    color var(--md-duration-short) var(--md-easing-standard);
}

.writing-workspace__more-menu-item:hover:not(:disabled) {
  background-color: color-mix(in srgb, var(--md-primary-dark) 10%, transparent);
}

.writing-workspace__more-menu-item:focus-visible {
  outline: 2px solid var(--md-primary);
  outline-offset: 2px;
}

.writing-workspace__ai-menu {
  position: relative;
}

.writing-workspace__ai-menu-panel {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  z-index: 8;
  min-width: 176px;
  padding: 6px;
  border-radius: 10px;
  border: 1px solid color-mix(in srgb, var(--md-outline-variant) 86%, transparent);
  background: color-mix(in srgb, var(--md-surface) 94%, var(--md-surface-container-low));
  box-shadow: 0 10px 20px rgba(24, 38, 58, 0.14);
}

.writing-workspace__ai-menu-item {
  display: block;
  width: 100%;
  min-height: 44px;
  padding: 10px 12px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  text-align: left;
  font-size: var(--md-label-medium);
  color: var(--md-on-surface);
  cursor: pointer;
  transition:
    background-color var(--md-duration-short) var(--md-easing-standard),
    color var(--md-duration-short) var(--md-easing-standard);
}

.writing-workspace__ai-menu-item:hover:not(:disabled) {
  background-color: color-mix(in srgb, var(--md-primary-dark) 10%, transparent);
}

.writing-workspace__ai-menu-item:focus-visible {
  outline: 2px solid var(--md-primary);
  outline-offset: 2px;
}

.writing-workspace__ai-menu-item--danger {
  color: color-mix(in srgb, var(--md-error) 82%, var(--md-on-surface));
}

.writing-workspace__ai-menu-item--danger:hover:not(:disabled) {
  background-color: color-mix(in srgb, var(--md-error) 12%, transparent);
}

.writing-workspace__content {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: var(--md-spacing-6);
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-4);
  background-image: linear-gradient(
    180deg,
    transparent 0,
    transparent calc(1.6em - 1px),
    color-mix(in srgb, var(--md-outline-variant) 14%, transparent) calc(1.6em - 1px),
    color-mix(in srgb, var(--md-outline-variant) 14%, transparent) 1.6em
  );
  background-size: 100% 1.6em;
}

.writing-workspace__body {
  min-height: 0;
}

.m3-editor-dialog {
  max-width: min(1200px, calc(100vw - 32px));
  max-height: calc(var(--app-viewport-unit) - 32px);
  border-radius: var(--md-radius-xl);
}

@media (max-width: 1160px) {
  .writing-workspace__toolbar-group--utility,
  .writing-workspace__toolbar-divider {
    display: none;
  }

  .writing-workspace__more-menu {
    display: block;
  }
}

@media (max-width: 940px) {
  .writing-workspace__header-row {
    flex-direction: column;
    gap: var(--md-spacing-3);
  }

  .writing-workspace__toolbar {
    width: 100%;
    align-items: stretch;
    margin-left: 0;
  }

  .writing-workspace__toolbar-row {
    justify-content: flex-end;
  }

  .writing-workspace__summary {
    max-width: 100%;
  }
}

@media (max-width: 640px) {
  .writing-workspace__header {
    padding: var(--md-spacing-4);
  }

  .writing-workspace__chapter-title-line {
    gap: 6px;
  }

  .writing-workspace__chapter-inline-meta {
    width: 100%;
  }

  .writing-workspace__tool-btn {
    min-width: 70px;
    padding-inline: 8px;
  }

  .writing-workspace__tool-btn--hero {
    height: 44px;
    min-height: 44px;
    padding-inline: 12px;
  }

  .writing-workspace__label-full {
    display: none;
  }

  .writing-workspace__label-short {
    display: inline;
  }

  .writing-workspace__ai-menu-panel,
  .writing-workspace__more-menu-panel {
    right: 0;
    left: auto;
  }

  .writing-workspace__content {
    padding: var(--md-spacing-4);
  }
}
</style>
