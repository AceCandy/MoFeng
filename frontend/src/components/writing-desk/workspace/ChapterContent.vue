<!-- AIMETA P=章节内容_章节文本展示编辑|R=内容展示_编辑|NR=不含版本管理|E=component:ChapterContent|X=internal|A=内容组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="space-y-6 w-full">
    <!-- 落墨签名快照：描红候选被选定后旧稿在此原地朱转墨，优先于同栏渲染 -->
    <article v-if="hasLuomoSnapshot" class="chapter-paper" data-provenance="ink">
      <div class="prose max-w-none">
        <div class="chapter-prose chapter-prose--luomo-snapshot">
          <p v-for="(paragraph, idx) in luomoSnapshotParagraphs" :key="`luomo-${idx}`">
            {{ paragraph }}
          </p>
        </div>
      </div>
    </article>

    <template v-else>
      <!-- 落墨正文：有正文时始终渲染，描红候选在场则同栏对照 -->
      <article v-if="hasChapterContent" class="chapter-paper" data-provenance="ink">

        <div class="prose max-w-none">
          <div class="chapter-prose">
            <p
              v-for="(paragraph, idx) in chapterDisplayParagraphs"
              :key="`chapter-${idx}`"
              :ref="(el) => setParagraphRef(el, idx)"
              :class="{ 'chapter-prose__p--active': isParagraphActive(idx) }"
            >
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

      <!-- 同栏界格题签：落墨与描红同时在场时的分界 -->
      <p v-if="hasMiaohongContent && hasChapterContent" class="chapter-jiege-divider">候选描红稿</p>

      <!-- 描红预览：AI 候选稿以淡朱楷体呈现，待作家审定落墨 -->
      <article v-if="hasMiaohongContent" class="chapter-paper" data-provenance="ai">
        <div class="prose max-w-none">
          <div class="chapter-prose chapter-prose--miaohong">
            <p v-if="!hasChapterContent" class="chapter-miaohong__label">描红稿 · 待落墨</p>
            <p
              v-for="(paragraph, idx) in miaohongDisplayParagraphs"
              :key="`miaohong-${idx}`"
            >
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
    </template>

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
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'
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
import { cleanVersionContent } from '@/utils/chapter'

interface Props {
  selectedChapter: Chapter
  projectId?: string
  /** 朗读高亮的正文段落区间起点，-1 或缺省表示不高亮 */
  activeParagraphIndex?: number
  /** 朗读高亮的正文段落区间终点（短段合并时与起点共同覆盖多段），缺省时取起点 */
  activeParagraphEnd?: number
  /** 候选版本描红预览文本：非空时以描红模式渲染该 AI 草稿，替代落墨正文 */
  miaohongContent?: string | null
  /** 落墨签名快照文本：描红候选被选定落墨后由父级短暂注入，原地朱转墨后清空 */
  luomoSnapshotContent?: string | null
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

// 描红预览：与正文共用同一套分段逻辑，仅替换文本来源
const miaohongPreviewText = computed(() => cleanVersionContent(props.miaohongContent || ''))
const hasMiaohongContent = computed(() => Boolean(miaohongPreviewText.value.trim()))
const miaohongDisplayParagraphs = computed(() =>
  splitChapterParagraphs(miaohongPreviewText.value),
)

// 落墨签名快照：父级在选定落墨瞬间把旧描红稿文本短暂注入，原地朱转墨后清空
const luomoSnapshotText = computed(() => cleanVersionContent(props.luomoSnapshotContent || ''))
const luomoSnapshotParagraphs = computed(() => splitChapterParagraphs(luomoSnapshotText.value))
const hasLuomoSnapshot = computed(() => luomoSnapshotParagraphs.value.length > 0)

// 朗读高亮：收集每段 DOM，当前段变化时滚动居中
const paragraphEls: HTMLElement[] = []
const setParagraphRef = (el: Element | unknown, idx: number) => {
  if (el instanceof HTMLElement) {
    paragraphEls[idx] = el
  }
}

// 合并段区间高亮：activeParagraphIndex/End 构成闭区间，缺省或负值表示不高亮
const isParagraphActive = (idx: number): boolean => {
  const start = props.activeParagraphIndex
  if (start == null || start < 0) return false
  const end = props.activeParagraphEnd ?? start
  return idx >= start && idx <= end
}

watch(
  () => props.activeParagraphIndex,
  (idx) => {
    if (idx == null || idx < 0) return
    void nextTick(() => {
      paragraphEls[idx]?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    })
  },
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

    globalAlert.showToast(applyResult.message, 'success')
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
/* 稿纸古籍双线框与朱砂竖界格已由全局 chapter-paper.css 收口（DESIGN 点名主写作容器），
   scoped 仅保留铺满高度这一布局诉求，视觉层不再另起炉灶 */
.chapter-paper {
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
  box-shadow: var(--md-elevation-paper-2) !important;
  animation: optimizer-pop-in 0.24s ease-out both;
}

.m3-result-dialog {
  max-width: min(900px, calc(100vw - 32px));
  max-height: calc(var(--app-viewport-unit) - 32px);
  border-radius: var(--md-radius-md) !important;
  border: 3px double var(--md-outline) !important;
  background-color: var(--md-surface) !important;
  box-shadow: var(--md-elevation-paper-2) !important;
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
  border-radius: var(--md-radius-xs);
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
  border-radius: var(--md-radius-xs);
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
  box-shadow: var(--md-elevation-paper-1);
}

.m3-option-marker {
  display: inline-flex;
  min-width: 44px;
  height: 28px;
  align-items: center;
  justify-content: center;
  border-radius: var(--md-radius-xs);
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

/* 稿纸行线与本组件正文节奏对齐（15px × 行高 2 = 30px），防行线与文字相位漂移 */
.chapter-paper {
  --paper-line: 30px;
}

/* 描红稿三信号（spec §4）：淡朱色 + 真楷体 + wash 底与左缘 1px 界栏，缺一不可 */
.chapter-prose--miaohong {
  color: var(--md-miaohong) !important;
  font-family: var(--md-font-kai) !important;
  background-color: var(--md-miaohong-wash);
  border-left: 1px solid var(--md-miaohong-line-strong);
  padding: var(--md-spacing-3) var(--md-spacing-4);
}

/* 落墨签名快照：静止态即落墨终态（焦墨宋体、无 wash 无界栏），动画只负责由朱转墨的 260ms */
.chapter-prose--luomo-snapshot {
  color: var(--md-on-surface);
  font-family: var(--md-font-serif);
  background-color: transparent;
  border-left: 1px solid transparent;
  padding: var(--md-spacing-3) var(--md-spacing-4);
}

@media (prefers-reduced-motion: no-preference) {
  .chapter-prose--luomo-snapshot {
    animation: chapter-luomo 260ms var(--md-easing-standard) both;
  }
}

/* 朱→墨连续过渡；楷→宋为离散属性，在动画中点翻转 */
@keyframes chapter-luomo {
  from {
    color: var(--md-miaohong);
    font-family: var(--md-font-kai);
    background-color: var(--md-miaohong-wash);
    border-left-color: var(--md-miaohong-line-strong);
  }
  to {
    color: var(--md-on-surface);
    font-family: var(--md-font-serif);
    background-color: transparent;
    border-left-color: transparent;
  }
}

/* 同栏界格题签：落墨与描红同在场时的分界（12px 淡朱楷体，不用 eyebrow 式小字眉） */
.chapter-jiege-divider {
  display: flex;
  align-items: center;
  gap: var(--md-spacing-3);
  margin: 0;
  color: var(--md-miaohong);
  font-family: var(--md-font-kai);
  font-size: 12px;
  line-height: 1.5;
  letter-spacing: 0.35em;
  text-indent: 0;
}

.chapter-jiege-divider::before,
.chapter-jiege-divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background-color: var(--md-miaohong-line-strong);
}

/* 描红区首段前小字签 */
.chapter-miaohong__label {
  margin: 0 0 var(--md-spacing-2) !important;
  color: var(--md-miaohong) !important;
  font-family: var(--md-font-kai);
  font-size: 12px !important;
  line-height: 1.5 !important;
  letter-spacing: 0.08em;
  text-indent: 0 !important;
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

/* 朗读当前段：石青变色 + 波浪线高亮（石青 primary-container，明暗主题自适应） */
.chapter-prose p.chapter-prose__p--active {
  font-weight: 700;
  color: var(--md-primary-container);
  text-decoration: underline wavy var(--md-primary-container);
  text-decoration-thickness: 2px;
  text-underline-offset: 0.16em;
}

/* 暗色下石青容器色过深，混入素骨黄提亮保持可读 */
:root[data-theme='dark'] .chapter-prose p.chapter-prose__p--active {
  color: color-mix(in srgb, var(--md-on-surface) 65%, var(--md-info));
  text-decoration-color: color-mix(in srgb, var(--md-on-surface) 65%, var(--md-info));
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
