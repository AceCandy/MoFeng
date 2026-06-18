<!-- AIMETA P=版本选择器_章节版本切换|R=版本列表_切换|NR=不含版本管理|E=component:VersionSelector|X=internal|A=选择器|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="space-y-6">
    <div
      v-if="showGeneratedBanner"
      class="md-card md-card-filled p-4 version-ready m3-version-notice-box"
      role="status"
      aria-live="polite"
      aria-atomic="true"
    >
      <p class="version-ready__title">第{{ selectedChapter?.chapter_number }}章已生成新版本 {{ latestVersionLabel }}，原版本已保留。</p>
      <div class="version-ready__actions">
        <button type="button" class="md-btn md-btn-outlined md-ripple" @click="$emit('showVersionDetail', selectedVersionIndex)">查看正文</button>
        <button
          type="button"
          class="md-btn md-btn-outlined md-ripple"
          :disabled="availableVersions.length < 2"
          @click="compareWithPreviousVersion"
        >
          与上一版对比
        </button>
        <button
          type="button"
          class="md-btn md-btn-filled md-ripple"
          :disabled="!canConfirmDraft"
          @click="confirmDraft"
        >
          {{ isSelectingVersion ? '定稿中...' : '确认定稿' }}
        </button>
        <button type="button" class="md-btn md-btn-outlined md-ripple" @click="openDraftEdit">编辑草稿</button>
        <button type="button" class="md-btn md-btn-tonal md-ripple" @click="$emit('regenerateChapter')">重新生成</button>
        <button type="button" class="md-btn md-btn-text md-ripple" @click="$emit('showEvaluationDetail')">继续润色</button>
      </div>
    </div>

    <div
      v-if="versionNotice"
      :class="['md-card md-card-filled p-4 version-notice m3-version-notice-box', `version-notice--${versionNotice.tone}`]"
      :role="versionNotice.tone === 'error' ? 'alert' : 'status'"
      :aria-live="versionNotice.tone === 'error' ? 'assertive' : 'polite'"
      aria-atomic="true"
    >
      <div class="version-notice__row">
        <div class="flex items-center gap-3 min-w-0">
          <div class="version-notice__icon">
            <svg
              v-if="versionNotice.icon === 'error'"
              class="w-5 h-5"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fill-rule="evenodd"
                d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
                clip-rule="evenodd"
              />
            </svg>
            <svg
              v-else-if="versionNotice.icon === 'evaluation'"
              class="w-5 h-5"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                d="M10 2a6 6 0 00-6 6v3.586l-1.707 1.707A1 1 0 003 15v1a1 1 0 001 1h12a1 1 0 001-1v-1a1 1 0 00-.293-.707L16 11.586V8a6 6 0 00-6-6zM8.05 17a2 2 0 103.9 0H8.05z"
              ></path>
            </svg>
            <svg v-else class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
              <path
                fill-rule="evenodd"
                d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
                clip-rule="evenodd"
              ></path>
            </svg>
          </div>
          <div class="min-w-0">
            <h4 class="md-title-small font-semibold">
              {{ versionNotice.title }}
            </h4>
            <p class="md-body-small">
              {{ versionNotice.description }}
            </p>
          </div>
        </div>
        <button
          v-if="versionNotice.action"
          type="button"
          @click="handleVersionNoticeAction(versionNotice.action)"
          :disabled="isEvaluatingCurrentChapter && versionNotice.action === 'retry-evaluate'"
          class="md-btn md-btn-filled md-ripple disabled:opacity-50 whitespace-nowrap"
        >
          {{ isEvaluatingCurrentChapter && versionNotice.action === 'retry-evaluate' ? '重试中...' : versionNotice.actionLabel }}
        </button>
      </div>
      <details v-if="chapterGenerationResult?.ai_message" class="version-notice__details">
        <summary class="md-label-large">查看 AI 说明</summary>
        <div
          class="prose prose-sm max-w-none prose-headings:mt-2 prose-headings:mb-1 prose-p:my-1 prose-ul:my-1 prose-ol:my-1 prose-li:my-0"
          v-html="parseMarkdown(chapterGenerationResult.ai_message)"
        ></div>
      </details>
    </div>

    <!-- 版本选择器 -->
    <div class="md-card md-card-outlined p-4 m3-version-container">
      <div class="flex items-center justify-between mb-4">
        <h4 class="md-title-medium font-semibold">
          {{ availableVersions.length > 1 ? '草稿确认' : '生成草稿' }}
          <span class="md-body-small md-on-surface-variant ml-2"
            >({{ availableVersions.length }} 个版本)</span
          >
        </h4>
      </div>

      <div class="version-grid" role="radiogroup" aria-label="章节候选版本">
        <div v-for="(version, index) in availableVersions" :key="index" class="version-card">
          <div
            :ref="(el) => registerVersionCardRef(el, index)"
            @click="$emit('update:selectedVersionIndex', index)"
            @dblclick="$emit('showVersionDetail', index)"
            @keydown.enter.prevent="$emit('update:selectedVersionIndex', index)"
            @keydown.space.prevent="$emit('update:selectedVersionIndex', index)"
            @keydown="handleVersionRadioKeydown($event, index)"
            role="radio"
            :tabindex="selectedVersionIndex === index ? 0 : -1"
            :aria-checked="selectedVersionIndex === index"
            :aria-label="`候选版本 ${index + 1}，双击查看详情`"
            :aria-posinset="index + 1"
            :aria-setsize="availableVersions.length"
            :class="[
              'cursor-pointer p-4 m3-version-card',
              selectedVersionIndex === index
                ? 'm3-version-selected md-elevation-1'
                : isCurrentVersion(index)
                  ? 'm3-version-current'
                  : 'hover:md-elevation-1',
            ]"
          >
            <div class="flex items-start gap-3">
              <div
                :class="[
                  'w-6 h-6 rounded-full flex items-center justify-center text-xs font-semibold flex-shrink-0',
                  selectedVersionIndex === index
                    ? 'bg-[var(--md-primary)] text-[var(--md-on-primary)]'
                    : isCurrentVersion(index)
                      ? 'bg-[var(--md-success)] text-[var(--md-on-success)]'
                      : 'bg-[var(--md-surface-container-highest)] text-[var(--md-on-surface)]',
                ]"
              >
                <svg
                  v-if="isCurrentVersion(index)"
                  class="w-3 h-3"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path
                    fill-rule="evenodd"
                    d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                    clip-rule="evenodd"></path>
                </svg>
                <span v-else>{{ index + 1 }}</span>
              </div>
              <div class="flex-1 min-w-0">
                <p class="md-body-medium md-on-surface line-clamp-3">
                  {{ cleanVersionContent(version.content).substring(0, 150) }}...
                </p>
                <div class="mt-2 flex items-center gap-2 md-body-small md-on-surface-variant">
                  <span>{{ getVersionWordCount(version.content) }} 字</span>
                  <span>•</span>
                  <span>{{ version.style || '标准' }}风格</span>
                  <span
                    v-if="isCurrentVersion(index)"
                    class="m3-version-current-label"
                    >• 当前选中</span
                  >
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="draftEditOpen" class="version-draft-editor">
        <label class="md-label-large" for="draft-edited-content">编辑草稿正文</label>
        <textarea
          id="draft-edited-content"
          v-model="draftEditedContent"
          class="version-draft-editor__textarea"
          rows="14"
        ></textarea>
        <p class="md-body-small md-on-surface-variant">
          当前编辑稿 {{ getVersionWordCount(draftEditedContent) }} 字
        </p>
      </div>

      <div class="version-actions">
        <button
          type="button"
          @click="confirmDraft"
          :disabled="!canConfirmDraft"
          class="md-btn md-btn-filled md-ripple disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
        >
          <svg
            v-if="isSelectingVersion"
            class="w-5 h-5 animate-spin"
            fill="currentColor"
            viewBox="0 0 20 20"
          >
            <path
              fill-rule="evenodd"
              d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z"
              clip-rule="evenodd"></path>
          </svg>
          <span v-else>
            {{ isCurrentVersion(selectedVersionIndex) ? '当前版本' : '确认定稿' }}
          </span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import DOMPurify from 'dompurify'
import type { Chapter, ChapterGenerationResponse, ChapterVersion } from '@/api/novel'
import { countNonWhitespaceChars } from '@/utils/text'

interface Props {
  selectedChapter: Chapter | null
  chapterGenerationResult: ChapterGenerationResponse | null
  availableVersions: ChapterVersion[]
  selectedVersionIndex: number
  evaluatingChapter: number | null
  isSelectingVersion?: boolean
  isEvaluationFailed?: boolean
}

const props = defineProps<Props>()
const versionCardRefs = ref<Array<HTMLElement | null>>([])
const draftEditOpen = ref(false)
const draftEditedContent = ref('')

type VersionNoticeAction = 'retry-evaluate' | 'show-evaluation'

const emit = defineEmits([
  'hideVersionSelector',
  'update:selectedVersionIndex',
  'showVersionDetail',
  'confirmVersionSelection',
  'evaluateChapter',
  'showEvaluationDetail',
  'regenerateChapter',
])

const isEvaluatingCurrentChapter = computed(
  () => props.evaluatingChapter === props.selectedChapter?.chapter_number,
)

const showGeneratedBanner = computed(() => {
  return props.selectedChapter?.generation_status === 'waiting_for_confirm'
})

const latestVersionLabel = computed(() => {
  const length = props.availableVersions.length
  if (!length) return 'V1'
  return `V${length}`
})

const versionNotice = computed(() => {
  if (props.isEvaluationFailed) {
    return {
      tone: 'error',
      icon: 'error',
      title: 'AI 评审失败',
      description: '评审遇到问题，可以直接重试。',
      action: 'retry-evaluate' as VersionNoticeAction,
      actionLabel: '重新评审',
    }
  }

  if (props.selectedChapter?.evaluation) {
    return {
      tone: 'secondary',
      icon: 'evaluation',
      title: 'AI 评审已完成',
      description: '已完成多版本评估，可以直接查看详情。',
      action: 'show-evaluation' as VersionNoticeAction,
      actionLabel: '查看 AI 评审',
    }
  }

  if (props.selectedChapter?.content) {
    return {
      tone: 'warning',
      icon: 'info',
      title: '当前章节已有正文',
      description: '可横向对比候选版本，再决定是否替换当前正文。',
      action: null,
      actionLabel: '',
    }
  }

  return {
    tone: 'primary',
    icon: 'info',
    title: '请选择候选版本',
    description: '先选择一个版本确认，章节才会进入完成状态。',
    action: null,
    actionLabel: '',
  }
})

const handleVersionNoticeAction = (action: VersionNoticeAction) => {
  if (action === 'retry-evaluate') {
    emit('evaluateChapter')
    return
  }
  emit('showEvaluationDetail')
}

const resolveVersionCardElement = (element: unknown) => {
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

const registerVersionCardRef = (element: unknown, index: number) => {
  versionCardRefs.value[index] = resolveVersionCardElement(element)
}

const focusAndSelectVersion = async (index: number) => {
  if (index < 0 || index >= props.availableVersions.length) {
    return
  }
  emit('update:selectedVersionIndex', index)
  await nextTick()
  versionCardRefs.value[index]?.focus()
}

const handleVersionRadioKeydown = (event: KeyboardEvent, index: number) => {
  if (props.availableVersions.length === 0) {
    return
  }
  if (event.key === 'ArrowDown' || event.key === 'ArrowRight') {
    event.preventDefault()
    const nextIndex = (index + 1) % props.availableVersions.length
    void focusAndSelectVersion(nextIndex)
    return
  }
  if (event.key === 'ArrowUp' || event.key === 'ArrowLeft') {
    event.preventDefault()
    const prevIndex = (index - 1 + props.availableVersions.length) % props.availableVersions.length
    void focusAndSelectVersion(prevIndex)
    return
  }
  if (event.key === 'Home') {
    event.preventDefault()
    void focusAndSelectVersion(0)
    return
  }
  if (event.key === 'End') {
    event.preventDefault()
    void focusAndSelectVersion(props.availableVersions.length - 1)
  }
}

const compareWithPreviousVersion = () => {
  if (props.availableVersions.length < 2) return
  const previousIndex = Math.max(0, props.selectedVersionIndex - 1)
  emit('showVersionDetail', previousIndex)
}

const selectedDraftContent = computed(() =>
  cleanVersionContent(props.availableVersions?.[props.selectedVersionIndex]?.content || ''),
)

const canConfirmDraft = computed(() => {
  if (props.isSelectingVersion || !props.availableVersions?.[props.selectedVersionIndex]?.content) {
    return false
  }
  if (draftEditOpen.value && draftEditedContent.value.trim()) {
    return true
  }
  return !isCurrentVersion(props.selectedVersionIndex)
})

const openDraftEdit = () => {
  draftEditedContent.value = selectedDraftContent.value
  draftEditOpen.value = true
}

const confirmDraft = () => {
  emit('confirmVersionSelection', {
    editedContent: draftEditOpen.value ? draftEditedContent.value : null,
  })
}

const isCurrentVersion = (versionIndex: number) => {
  if (!props.selectedChapter?.content || !props.availableVersions?.[versionIndex]?.content)
    return false
  const cleanCurrentContent = cleanVersionContent(props.selectedChapter.content)
  const cleanVersionContentStr = cleanVersionContent(props.availableVersions[versionIndex].content)
  return cleanCurrentContent === cleanVersionContentStr
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

const getVersionWordCount = (content: string): number => {
  return countNonWhitespaceChars(cleanVersionContent(content))
}

const parseMarkdown = (text: string): string => {
  if (!text) return ''
  let parsed = text
    .replace(/\\n/g, '\n')
    .replace(/\\"/g, '"')
    .replace(/\\'/g, "'")
    .replace(/\\\\/g, '\\')
  parsed = parsed.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
  parsed = parsed.replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, '<em>$1</em>')
  parsed = parsed.replace(
    /^([A-Z])\)\s*\*\*(.*?)\*\*(.*)/gm,
    '<div class="mb-2"><span class="inline-flex items-center justify-center w-6 h-6 text-sm font-semibold rounded-full mr-2 m3-eval-badge">$1</span><strong>$2</strong>$3</div>',
  )
  parsed = parsed.replace(/\n/g, '<br>')
  parsed = parsed.replace(/(<br\s*\/?>\s*){2,}/g, '</p><p class="mt-2">')
  if (!parsed.includes('<p>')) {
    parsed = `<p>${parsed}</p>`
  }
  return DOMPurify.sanitize(parsed, {
    USE_PROFILES: { html: true },
  })
}
</script>

<style scoped>
.m3-version-notice-box {
  border-radius: var(--md-radius-sm) !important;
  border-color: var(--md-outline) !important;
  box-shadow: 2px 2px 0px rgba(28, 32, 34, 0.05) !important;
}

.version-ready {
  border: 1px solid color-mix(in srgb, var(--md-success) 28%, var(--md-outline-variant)) !important;
  background:
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--md-success-container) 70%, var(--md-surface)),
      color-mix(in srgb, var(--md-surface) 94%, transparent)
    ) !important;
}

.version-ready__title {
  margin: 0;
  color: var(--md-on-surface);
  font-size: var(--md-body-medium);
  font-weight: 600;
}

.version-ready__actions {
  margin-top: var(--md-spacing-3);
  display: flex;
  flex-wrap: wrap;
  gap: var(--md-spacing-2);
}

.version-notice {
  border: 1px solid var(--md-outline-variant);
}

.version-notice__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--md-spacing-4);
}

.version-notice__icon {
  width: 32px;
  height: 32px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.version-notice__details {
  margin-top: var(--md-spacing-3);
}

.version-notice__details summary {
  cursor: pointer;
  user-select: none;
  color: inherit;
}

.version-notice__details .prose {
  margin-top: var(--md-spacing-2);
  color: inherit;
}

.version-notice--error {
  background-color: var(--md-error-container) !important;
  color: var(--md-on-error-container) !important;
}

.version-notice--error .version-notice__icon {
  background-color: var(--md-error) !important;
  color: var(--md-on-error) !important;
}

.version-notice--secondary {
  background-color: var(--md-secondary-container) !important;
  color: var(--md-on-secondary-container) !important;
}

.version-notice--secondary .version-notice__icon {
  background-color: var(--md-secondary) !important;
  color: var(--md-on-secondary) !important;
}

.version-notice--warning {
  background-color: var(--md-warning-container) !important;
  color: var(--md-on-warning-container) !important;
}

.version-notice--warning .version-notice__icon {
  background-color: color-mix(in srgb, var(--md-warning) 70%, var(--md-surface)) !important;
  color: var(--md-on-warning-container) !important;
}

.version-notice--primary {
  background-color: var(--md-primary-container) !important;
  color: var(--md-on-primary-container) !important;
}

.version-notice--primary .version-notice__icon {
  background-color: var(--md-primary) !important;
  color: var(--md-on-primary) !important;
}

.m3-version-container {
  border-radius: var(--md-radius-sm) !important;
  border-color: var(--md-outline) !important;
  background-color: var(--md-surface-dim) !important;
  box-shadow: 2px 2px 0px rgba(28, 32, 34, 0.08) !important;
}

.version-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--md-spacing-3);
}

.version-card {
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-2);
  min-width: 0;
}

.version-actions {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--md-spacing-3);
  margin-top: var(--md-spacing-4);
}

.version-draft-editor {
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-2);
  margin-top: var(--md-spacing-4);
}

.version-draft-editor__textarea {
  width: 100%;
  min-height: 320px;
  resize: vertical;
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-sm);
  background: var(--md-surface);
  color: var(--md-on-surface);
  padding: var(--md-spacing-3);
  line-height: 1.8;
  font-family: var(--md-font-family);
  outline: none;
}

.version-draft-editor__textarea:focus {
  border-color: var(--md-primary);
  box-shadow: inset 0 0 0 1px var(--md-primary);
}

.m3-version-card {
  border: 1px solid var(--md-outline-variant) !important;
  border-radius: var(--md-radius-sm) !important;
  background-color: var(--md-surface) !important;
  outline: none;
  transition:
    background-color var(--md-duration-medium) var(--md-easing-standard),
    border-color var(--md-duration-medium) var(--md-easing-standard),
    box-shadow var(--md-duration-medium) var(--md-easing-standard);
}

.m3-version-card:hover {
  background-color: var(--md-surface-container-low) !important;
  border-color: var(--md-outline) !important;
}

.m3-version-card:focus-visible {
  outline: 2px solid var(--md-primary) !important;
  outline-offset: 2px !important;
}

.m3-version-selected {
  border-color: var(--md-primary) !important;
  background-color: color-mix(in srgb, var(--md-primary-container) 12%, var(--md-surface)) !important;
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--md-primary) 35%, transparent) !important;
}

.m3-version-current {
  border-color: var(--md-success) !important;
  background-color: var(--md-success-container) !important;
}

.m3-version-current-label {
  color: var(--md-success) !important;
  font-weight: 600;
}

.m3-eval-badge {
  background-color: var(--md-primary-container) !important;
  color: var(--md-on-primary-container) !important;
}

@media (max-width: 640px) {
  .version-ready__actions {
    flex-direction: column;
  }

  .version-ready__actions .md-btn {
    width: 100%;
  }

  .version-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .version-notice__row {
    align-items: stretch;
    flex-direction: column;
  }

  .version-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .version-actions .md-btn {
    width: 100%;
  }
}
</style>
