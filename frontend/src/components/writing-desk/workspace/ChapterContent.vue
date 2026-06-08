<!-- AIMETA P=章节内容_章节文本展示编辑|R=内容展示_编辑|NR=不含版本管理|E=component:ChapterContent|X=internal|A=内容组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="space-y-6 w-full">
    <article class="chapter-paper">

      <div class="prose max-w-none">
        <div class="chapter-prose">
          <p v-for="(paragraph, idx) in chapterDisplayParagraphs" :key="`chapter-${idx}`">
            <template v-if="idx === 0 && paragraph && paragraph.trim().length > 0">
              <span class="first-stamp-char">{{ paragraph.trim()[0] }}</span>{{ paragraph.trim().slice(1) }}
            </template>
            <template v-else>
              {{ paragraph }}
            </template>
          </p>
        </div>
      </div>
    </article>

    <!-- 分层优化弹窗 -->
    <Teleport to="body">
      <div v-if="showOptimizer" class="md-dialog-overlay" @click.self="closeOptimizerModal">
        <div
          ref="optimizerDialogRef"
          class="md-dialog m3-optimizer-dialog"
          role="dialog"
          aria-modal="true"
          :aria-labelledby="optimizerDialogTitleId"
        >
          <div class="p-6">
            <!-- 优化面板头部 -->
            <div class="flex items-center justify-between mb-6">
              <div>
                <h3 :id="optimizerDialogTitleId" class="md-headline-small font-semibold">分层优化</h3>
                <p class="md-body-small md-on-surface-variant mt-1">
                  选择一个维度生成可预览的优化稿。
                </p>
              </div>
              <button
                ref="optimizerCloseButtonRef"
                data-dialog-initial-focus
                type="button"
                @click="closeOptimizerModal"
                :disabled="isOptimizing"
                class="md-icon-btn md-ripple"
                :class="{ 'opacity-40 cursor-not-allowed': isOptimizing }"
                aria-label="关闭分层优化弹窗"
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

            <!-- 优化维度选择 -->
            <div class="grid grid-cols-2 gap-4 mb-6">
              <button
                v-for="dim in optimizeDimensions"
                :key="dim.key"
                type="button"
                @click="selectedDimension = dim.key"
                :disabled="isOptimizing"
                :class="[
                  'md-card md-card-outlined p-4 text-left transition-[background-color,border-color,box-shadow,color] duration-200',
                  selectedDimension === dim.key ? 'm3-option-selected' : 'm3-option',
                  isOptimizing ? 'opacity-70 cursor-not-allowed' : '',
                ]"
              >
                <div class="flex items-center gap-3 mb-2">
                  <span class="m3-option-marker">{{ dim.marker }}</span>
                  <span class="md-title-small font-semibold">{{ dim.label }}</span>
                </div>
                <p class="md-body-small md-on-surface-variant">{{ dim.description }}</p>
              </button>
            </div>

            <!-- 额外说明 -->
            <div class="mb-6">
              <label :for="optimizerNotesInputId" class="md-text-field-label mb-2"> 额外优化指令（可选） </label>
              <textarea
                :id="optimizerNotesInputId"
                v-model="additionalNotes"
                rows="3"
                class="md-textarea w-full resize-none"
                placeholder="例如：加强主角内心的挣扎感，让对话更有张力..."
                :disabled="isOptimizing"
              ></textarea>
            </div>

            <!-- 优化进度 -->
            <div v-if="isOptimizing" class="m3-optimizing-panel mb-6">
              <div class="flex items-center gap-2 mb-2">
                <span class="md-body-small font-medium">
                  正在优化{{ selectedDimensionLabel ? `：${selectedDimensionLabel}` : '' }}
                </span>
                <span class="m3-optimizing-dots" aria-hidden="true"> <i></i><i></i><i></i> </span>
              </div>
              <p class="md-body-small md-on-surface-variant mb-3">{{ currentOptimizeHint }}</p>
              <div
                class="m3-progress-track"
                role="progressbar"
                aria-valuemin="0"
                aria-valuemax="100"
                aria-label="优化进行中"
              >
                <div class="m3-progress-bar"></div>
              </div>
            </div>

            <!-- 操作按钮 -->
            <div class="flex justify-end gap-3">
              <button
                type="button"
                @click="closeOptimizerModal"
                :disabled="isOptimizing"
                class="md-btn md-btn-outlined md-ripple disabled:opacity-50"
              >
                取消
              </button>
              <button
                type="button"
                @click="startOptimize"
                :disabled="!selectedDimension || isOptimizing"
                class="md-btn md-btn-filled md-ripple disabled:opacity-50 flex items-center gap-2"
              >
                <svg
                  v-if="isOptimizing"
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
                {{ isOptimizing ? '优化中...' : '开始优化' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- 优化结果预览弹窗 -->
    <Teleport to="body">
      <div v-if="showOptimizeResult" class="md-dialog-overlay" @click.self="closeOptimizeResult">
        <div
          ref="optimizeResultDialogRef"
          class="md-dialog m3-result-dialog flex flex-col"
          role="dialog"
          aria-modal="true"
          :aria-labelledby="optimizeResultDialogTitleId"
        >
          <div class="p-6 border-b m3-result-dialog__header">
            <div class="flex items-center justify-between">
              <div>
                <h3 :id="optimizeResultDialogTitleId" class="md-headline-small font-semibold">
                  优化结果预览
                </h3>
                <p class="md-body-small md-on-surface-variant mt-1">{{ optimizeResultNotes }}</p>
              </div>
              <button
                ref="optimizeResultCloseButtonRef"
                data-dialog-initial-focus
                type="button"
                @click="closeOptimizeResult"
                class="md-icon-btn md-ripple"
                aria-label="关闭优化结果弹窗"
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
          </div>
          <div class="flex-1 overflow-y-auto p-6">
            <div class="prose max-w-none">
              <div class="chapter-prose">
                <p v-for="(paragraph, idx) in optimizedDisplayParagraphs" :key="`optimized-${idx}`">
                  <template v-if="idx === 0 && paragraph && paragraph.trim().length > 0">
                    <span class="first-stamp-char">{{ paragraph.trim()[0] }}</span>{{ paragraph.trim().slice(1) }}
                  </template>
                  <template v-else>
                    {{ paragraph }}
                  </template>
                </p>
              </div>
            </div>
          </div>
          <div class="p-6 border-t flex items-center justify-end gap-3 m3-result-dialog__footer">
            <div class="md-body-small md-on-surface-variant m3-preview-metric">
              {{ optimizedPreviewWordCount }} 字
            </div>
            <button
              type="button"
              @click="reselectOptimization"
              :disabled="isApplying"
              class="md-btn md-btn-tonal md-ripple disabled:opacity-50"
            >
              重新选择优化
            </button>
            <button
              type="button"
              @click="closeOptimizeResult"
              class="md-btn md-btn-outlined md-ripple"
            >
              取消
            </button>
            <button
              type="button"
              @click="applyOptimization"
              :disabled="isApplying"
              class="md-btn md-btn-filled md-ripple disabled:opacity-50 flex items-center gap-2 m3-btn-success"
            >
              <svg
                v-if="isApplying"
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
              {{ isApplying ? '应用中...' : '应用优化' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue'
import Tooltip from '@/components/Tooltip.vue'
import { globalAlert } from '@/composables/useAlert'
import { useDialogA11y } from '@/composables/useDialogA11y'
import type { Chapter } from '@/api/novel'
import {
  useApplyOptimizationMutation,
  useNovelMutationRefresh,
  useOptimizeChapterMutation,
} from '@/queries/novel'
import { countNonWhitespaceChars } from '@/utils/text'

interface Props {
  selectedChapter: Chapter
  projectId?: string
}

const props = defineProps<Props>()
const { refreshChapter, refreshProjectQueries } = useNovelMutationRefresh(() => props.projectId)
const optimizeChapterMutation = useOptimizeChapterMutation()
const applyOptimizationMutation = useApplyOptimizationMutation(() => props.projectId)

// 优化相关状态
const showOptimizer = ref(false)
const showOptimizeResult = ref(false)
const optimizerDialogRef = ref<HTMLElement | null>(null)
const optimizerCloseButtonRef = ref<HTMLElement | null>(null)
const optimizeResultDialogRef = ref<HTMLElement | null>(null)
const optimizeResultCloseButtonRef = ref<HTMLElement | null>(null)
const optimizerDialogTitleId = 'chapter-content-optimizer-dialog-title'
const optimizeResultDialogTitleId = 'chapter-content-optimize-result-dialog-title'
const optimizerNotesInputId = 'chapter-content-optimizer-notes-input'
const selectedDimension = ref<string>('')
const additionalNotes = ref('')
const isOptimizing = computed(() => optimizeChapterMutation.isPending.value)
const isApplying = computed(() => applyOptimizationMutation.isPending.value)
const optimizedContent = ref('')
const optimizeResultNotes = ref('')
const optimizeHintIndex = ref(0)
let optimizeHintTimer: number | null = null

// 优化维度配置
const optimizeDimensions = [
  {
    key: 'dialogue',
    marker: '对白',
    label: '对话优化',
    description: '让每句对话都有独特的声音和潜台词',
  },
  {
    key: 'environment',
    marker: '场景',
    label: '环境描写',
    description: '让场景氛围与情绪完美融合',
  },
  {
    key: 'psychology',
    marker: '内心',
    label: '心理活动',
    description: '深入角色内心，展现复杂情感',
  },
  {
    key: 'rhythm',
    marker: '节奏',
    label: '节奏韵律',
    description: '优化文字节奏，增强阅读体验',
  },
]

const optimizeHints = [
  '正在重构句式与语气，保持人物声音一致性',
  '正在增强细节密度，补充情绪与感官锚点',
  '正在检查段落节奏，确保阅读流畅且有张力',
  '正在收敛表达，避免空泛描述并强化画面感',
]

const selectedDimensionLabel = computed(() => {
  const item = optimizeDimensions.find((dim) => dim.key === selectedDimension.value)
  return item?.label ?? ''
})

const currentOptimizeHint = computed(
  () => optimizeHints[optimizeHintIndex.value % optimizeHints.length],
)

const startOptimizeHintRotation = () => {
  optimizeHintIndex.value = 0
  if (optimizeHintTimer !== null) {
    window.clearInterval(optimizeHintTimer)
  }
  optimizeHintTimer = window.setInterval(() => {
    optimizeHintIndex.value = (optimizeHintIndex.value + 1) % optimizeHints.length
  }, 1600)
}

const stopOptimizeHintRotation = () => {
  if (optimizeHintTimer !== null) {
    window.clearInterval(optimizeHintTimer)
    optimizeHintTimer = null
  }
}

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

const splitChapterParagraphs = (content: string): string[] => {
  if (!content) return []
  const normalized = content
    .replace(/\r\n?/g, '\n')
    .replace(/\u00A0/g, ' ')
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
  if (!normalized) return []

  const paragraphs = normalized
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean)

  if (paragraphs.length !== 1) {
    return paragraphs
  }

  // 单段超长文本兜底：按句号等标点粗分段，提升可读性
  const singleParagraph = paragraphs[0]
  const sentences = (singleParagraph.match(/[^。！？!?；;]+[。！？!?；;]?/g) || [singleParagraph])
    .map((sentence) => sentence.trim())
    .filter(Boolean)

  if (sentences.length < 6) {
    return paragraphs
  }

  const grouped: string[] = []
  for (let i = 0; i < sentences.length; i += 2) {
    grouped.push(`${sentences[i]}${sentences[i + 1] || ''}`.trim())
  }
  return grouped.filter(Boolean)
}

const chapterDisplayParagraphs = computed(() =>
  splitChapterParagraphs(cleanVersionContent(props.selectedChapter.content || '')),
)

const optimizedPreviewText = computed(() => cleanVersionContent(optimizedContent.value || ''))

const optimizedPreviewWordCount = computed(() =>
  countNonWhitespaceChars(optimizedPreviewText.value),
)
const hasOptimizedResult = computed(() => Boolean(optimizedPreviewText.value.trim()))
const hasChapterContent = computed(() =>
  Boolean(cleanVersionContent(props.selectedChapter.content || '').trim()),
)
const contentTooltipText = ref('点击复制')

const resetContentTooltip = () => {
  contentTooltipText.value = '点击复制'
}

const optimizedDisplayParagraphs = computed(() =>
  splitChapterParagraphs(optimizedPreviewText.value),
)

const openOptimizerPanel = () => {
  if (hasOptimizedResult.value) {
    showOptimizeResult.value = true
    showOptimizer.value = false
    return
  }
  showOptimizer.value = true
}

const openOptimizerPanelWithPreset = (preset?: { dimension?: string; notes?: string }) => {
  if (preset?.dimension) {
    const exists = optimizeDimensions.some((item) => item.key === preset.dimension)
    if (exists) {
      selectedDimension.value = preset.dimension
    }
  }
  if (typeof preset?.notes === 'string') {
    additionalNotes.value = preset.notes
  }
  showOptimizeResult.value = false
  showOptimizer.value = true
}

const closeOptimizeResult = () => {
  if (isApplying.value) return
  showOptimizeResult.value = false
}

const reselectOptimization = () => {
  if (isApplying.value) return
  showOptimizeResult.value = false
  showOptimizer.value = true
}

const sanitizeFileName = (name: string): string => {
  return name.replace(/[\\/:*?"<>|]/g, '_')
}

const exportChapterAsTxt = (chapter?: Chapter | null) => {
  if (!chapter) return

  const title = chapter.title?.trim() || `第${chapter.chapter_number}章`
  const safeTitle = sanitizeFileName(title) || `chapter-${chapter.chapter_number}`
  const content = cleanVersionContent(chapter.content || '')
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${safeTitle}.txt`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

const exportCurrentChapterAsTxt = () => {
  exportChapterAsTxt(props.selectedChapter)
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

const copyChapterContent = async (chapter?: Chapter | null) => {
  if (!chapter) return

  const content = cleanVersionContent(chapter.content || '').trim()
  if (!content) return

  const copied = await copyText(content)
  contentTooltipText.value = copied ? '复制成功' : '复制失败'

  if (!copied) {
    globalAlert.showError('复制失败，请手动选择文本复制。')
  }
}

const tryParseOptimizerPayload = (rawText: string): Record<string, unknown> | null => {
  if (!rawText) return null
  const text = rawText.trim()
  if (!text) return null

  const candidates: string[] = [text]
  const fenceMatch = text.match(/```(?:json|JSON)?\s*([\s\S]*?)\s*```/)
  if (fenceMatch?.[1]) {
    const fenced = fenceMatch[1].trim()
    if (fenced && fenced !== text) candidates.unshift(fenced)
  }

  for (const candidate of candidates) {
    try {
      const parsed = JSON.parse(candidate)
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
        return parsed as Record<string, unknown>
      }
    } catch {
      // ignore
    }
  }
  return null
}

const decodeJsonStringFragment = (fragment: string): string => {
  try {
    return JSON.parse(`"${fragment}"`) as string
  } catch {
    return fragment.replace(/\\"/g, '"').replace(/\\n/g, '\n').replace(/\\t/g, '\t')
  }
}

const extractJsonField = (
  rawText: string,
  field: 'optimized_content' | 'optimization_notes',
): string | null => {
  const pattern = new RegExp(`"${field}"\\s*:\\s*"((?:\\\\.|[^"\\\\])*)"`, 's')
  const match = rawText.match(pattern)
  if (!match?.[1]) return null
  return decodeJsonStringFragment(match[1])
}

const normalizeOptimizeResult = (
  contentRaw: string,
  notesRaw: string,
): { content: string; notes: string } => {
  let content = (contentRaw || '').trim()
  let notes = (notesRaw || '').trim()
  const seen = new Set<string>()

  // 如果 optimized_content 里又套了一层 JSON，递归解开（最多 2 层，防止死循环）
  for (let i = 0; i < 2; i++) {
    if (!content || seen.has(content)) break
    seen.add(content)
    const payload = tryParseOptimizerPayload(content)
    if (!payload) break
    const nestedContent = payload.optimized_content
    if (typeof nestedContent !== 'string' || !nestedContent.trim()) break
    content = nestedContent.trim()
    if (!notes && typeof payload.optimization_notes === 'string') {
      notes = payload.optimization_notes.trim()
    }
  }

  // 非标准响应兜底：从文本中按字段提取
  if (content.includes('"optimized_content"')) {
    const extractedContent = extractJsonField(content, 'optimized_content')
    if (extractedContent?.trim()) {
      content = extractedContent.trim()
    }
    if (!notes) {
      const extractedNotes = extractJsonField(contentRaw, 'optimization_notes')
      if (extractedNotes?.trim()) {
        notes = extractedNotes.trim()
      }
    }
  }

  const fenced = content.match(/```(?:json|JSON)?\s*([\s\S]*?)\s*```/)
  if (fenced?.[1]) {
    content = fenced[1].trim()
  }

  return {
    content,
    notes: notes || '优化完成',
  }
}

const startOptimize = async () => {
  if (!selectedDimension.value) {
    globalAlert.showError('请选择优化维度')
    return
  }
  if (!props.projectId) {
    globalAlert.showError('缺少项目信息，无法执行优化')
    return
  }

  startOptimizeHintRotation()

  try {
    const result = await optimizeChapterMutation.mutateAsync({
      project_id: props.projectId,
      chapter_number: props.selectedChapter.chapter_number,
      dimension: selectedDimension.value as 'dialogue' | 'environment' | 'psychology' | 'rhythm',
      additional_notes: additionalNotes.value || undefined,
    })

    const normalized = normalizeOptimizeResult(result.optimized_content, result.optimization_notes)
    optimizedContent.value = normalized.content
    optimizeResultNotes.value = normalized.notes
    showOptimizer.value = false
    showOptimizeResult.value = true
  } catch (error: any) {
    console.error('优化失败:', error)
    globalAlert.showError(error.message || '优化失败，请稍后重试')
  } finally {
    stopOptimizeHintRotation()
  }
}

const closeOptimizerModal = () => {
  if (isOptimizing.value) return
  showOptimizer.value = false
}

useDialogA11y({
  active: showOptimizer,
  dialogRef: optimizerDialogRef,
  onClose: closeOptimizerModal,
  initialFocusRef: optimizerCloseButtonRef,
})

useDialogA11y({
  active: showOptimizeResult,
  dialogRef: optimizeResultDialogRef,
  onClose: closeOptimizeResult,
  initialFocusRef: optimizeResultCloseButtonRef,
})

const applyOptimization = async () => {
  if (!optimizedContent.value || !props.projectId) return

  try {
    const applyResult = await applyOptimizationMutation.mutateAsync({
      projectId: props.projectId,
      chapterNumber: props.selectedChapter.chapter_number,
      optimizedContent: optimizedContent.value,
    })

    const syncStats = applyResult.foreshadowing_sync
    if (syncStats) {
      globalAlert.showToast(
        `优化内容已应用，伏笔同步：新增 ${syncStats.created}，推进 ${syncStats.developing}，回收 ${syncStats.revealed}`,
        'success',
      )
    } else {
      globalAlert.showToast('优化内容已应用', 'success')
    }
    showOptimizeResult.value = false

    // 重置状态
    selectedDimension.value = ''
    additionalNotes.value = ''
    optimizedContent.value = ''
    optimizeResultNotes.value = ''

    // 仅刷新当前章节数据，避免整页刷新导致路由重载和状态丢失。
    await refreshChapter(props.projectId, props.selectedChapter.chapter_number)
    await refreshProjectQueries(props.projectId)
  } catch (error: any) {
    console.error('应用优化失败:', error)
    globalAlert.showError(error.message || '应用优化失败，请稍后重试')
  }
}

onUnmounted(() => {
  stopOptimizeHintRotation()
})

defineExpose({
  openOptimizerPanel,
  openOptimizerPanelWithPreset,
  exportCurrentChapterAsTxt,
})
</script>

<style scoped>
.chapter-paper {
  padding: var(--md-spacing-6) var(--md-spacing-8) var(--md-spacing-10); /* 四周大气的国风内缩留白，字不贴边 */
  border: none !important; /* 彻底去除边框，在顶格拉满时浑然一体 */
  border-radius: 0 !important; /* 去除圆角以自然铺满红框 */
  background-color: var(--md-surface) !important; /* 宣纸乳黄质感底色 */
  /* 极致国风脑洞：正文区融入古典竹青淡墨横线信笺格与空灵祥云水墨底纹双重背景 */
  background-image:
    linear-gradient(
      180deg,
      transparent 0px,
      transparent calc(1.85em - 1px),
      rgba(63, 108, 93, 0.09) calc(1.85em - 1px),
      rgba(63, 108, 93, 0.09) 1.85em
    ),
    url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='80' height='80' viewBox='0 0 80 80'%3E%3Cpath d='M40 25 c-2-5-8-5-10-2 c-4-2-8 1-7 5 c-3 0-5 3-4 6 c1 3 4 3 6 3 h10 c3 0 5-2 5-5 c0-3-2-5-5-5 z' fill='none' stroke='%231c2022' stroke-width='0.7' stroke-opacity='0.018'/%3E%3Cpath d='M15 55 c-1-3-5-3-6-1 c-2-1-5 0-4 3 c-2 0-3 2-2 4 c1 2 2 2 4 2 h6 c2 0 3-1 3-3 c0-2-1-3-3-3 z' fill='none' stroke='%231c2022' stroke-width='0.7' stroke-opacity='0.012'/%3E%3Cpath d='M65 50 c-1-3-5-3-6-1 c-2-1-5 0-4 3 c-2 0-3 2-2 4 c1 2 2 2 4 2 h6 c2 0 3-1 3-3 c0-2-1-3-3-3 z' fill='none' stroke='%231c2022' stroke-width='0.7' stroke-opacity='0.012'/%3E%3C/svg%3E") !important;
  background-size: 100% 1.85em, 80px 80px !important;
  background-repeat: repeat, repeat !important;
  line-height: 1.85em !important;
  box-shadow: none !important; /* 去除影子，与主工作区合体 */
  min-height: 100%; /* 纵向和高度完全铺满红框 */
}

.chapter-paper__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--md-spacing-3);
  margin-bottom: var(--md-spacing-5);
}

.chapter-paper__title {
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--md-on-surface);
  text-align: left;
  cursor: pointer;
  appearance: none;
  font-family: var(--md-font-serif);
  font-size: var(--md-headline-small);
  letter-spacing: 0.08em;
  transition: color var(--md-duration-short) var(--md-easing-standard);
}

.chapter-paper__title:hover:not(:disabled) {
  color: var(--md-primary-dark);
}

.chapter-paper__title:focus-visible {
  outline: 2px solid var(--md-primary);
  outline-offset: 3px;
  border-radius: var(--md-radius-xs);
}

.m3-optimizer-dialog {
  max-width: min(720px, calc(100vw - 32px));
  max-height: calc(var(--app-viewport-unit) - 32px);
  border-radius: var(--md-radius-md) !important;
  border: 3px double var(--md-outline) !important;
  background-color: var(--md-surface) !important;
  box-shadow: 3px 3px 0px rgba(28, 32, 34, 0.15) !important;
  animation: optimizer-pop-in 0.24s ease-out both;
}

.m3-result-dialog {
  max-width: min(900px, calc(100vw - 32px));
  max-height: calc(var(--app-viewport-unit) - 32px);
  border-radius: var(--md-radius-md) !important;
  border: 3px double var(--md-outline) !important;
  background-color: var(--md-surface) !important;
  box-shadow: 3px 3px 0px rgba(28, 32, 34, 0.15) !important;
}

.m3-result-dialog__header {
  border-bottom-color: var(--md-outline-variant) !important;
}

.m3-result-dialog__footer {
  border-top-color: var(--md-outline-variant) !important;
}

.m3-btn-success {
  background-color: var(--md-success) !important;
  color: var(--md-on-success) !important;
}

.m3-optimizing-panel {
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-md);
  background: linear-gradient(
    120deg,
    color-mix(in srgb, var(--md-primary-container) 70%, var(--md-surface)) 0%,
    color-mix(in srgb, var(--md-surface-container-low) 85%, var(--md-surface)) 100%
  );
  padding: 12px 14px;
}

.m3-progress-track {
  position: relative;
  width: 100%;
  height: 6px;
  border-radius: 999px;
  overflow: hidden;
  background-color: color-mix(in srgb, var(--md-primary) 16%, var(--md-surface));
}

.m3-progress-bar {
  width: 45%;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(
    90deg,
    color-mix(in srgb, var(--md-primary) 72%, var(--md-surface)) 0%,
    var(--md-primary) 55%,
    color-mix(in srgb, var(--md-primary) 82%, var(--md-surface)) 100%
  );
  animation: optimizer-progress-slide 1.05s ease-in-out infinite;
}

.m3-optimizing-dots {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.m3-optimizing-dots i {
  width: 5px;
  height: 5px;
  border-radius: 999px;
  background: var(--md-primary);
  display: inline-block;
  animation: optimizer-dot-breath 0.9s ease-in-out infinite;
}

.m3-optimizing-dots i:nth-child(2) {
  animation-delay: 0.12s;
}

.m3-optimizing-dots i:nth-child(3) {
  animation-delay: 0.24s;
}

.m3-option {
  border-color: var(--md-outline-variant);
}

.m3-option-selected {
  border-color: var(--md-primary);
  background-color: var(--md-primary-container);
  box-shadow: var(--md-elevation-1);
}

.m3-option-marker {
  display: inline-flex;
  min-width: 44px;
  height: 28px;
  align-items: center;
  justify-content: center;
  border-radius: var(--md-radius-full);
  background-color: var(--md-surface-container);
  color: var(--md-on-surface-variant);
  font-size: var(--md-label-medium);
  font-weight: 600;
}

.m3-option-selected .m3-option-marker {
  background-color: var(--md-primary);
  color: var(--md-on-primary);
}

.chapter-prose {
  max-width: 74ch;
  margin: 0 auto;
  color: var(--md-on-surface);
  font-size: var(--md-body-large);
}

.chapter-prose p {
  margin: 0 0 1.15em;
  line-height: 2;
  text-indent: 2em;
  white-space: pre-wrap;
}

.chapter-prose p:last-child {
  margin-bottom: 0;
}

@keyframes optimizer-pop-in {
  from {
    opacity: 0;
    transform: translateY(14px) scale(0.985);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@keyframes optimizer-progress-slide {
  0% {
    transform: translateX(-120%);
  }
  100% {
    transform: translateX(240%);
  }
}

@keyframes optimizer-dot-breath {
  0%,
  100% {
    transform: scale(0.92);
    opacity: 0.25;
  }
  50% {
    transform: scale(1.05);
    opacity: 1;
  }
}

@media (prefers-reduced-motion: reduce) {
  .m3-optimizer-dialog,
  .m3-progress-bar,
  .m3-optimizing-dots i {
    animation: none;
  }
}

@media (max-width: 640px) {
  .chapter-paper {
    padding: var(--md-spacing-4);
  }

  .chapter-prose {
    font-size: var(--md-body-medium);
  }
}
</style>
