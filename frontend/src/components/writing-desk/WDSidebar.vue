<!-- AIMETA P=写作台侧边栏_章节目录|R=章节列表_导航|NR=不含内容编辑|E=component:WDSidebar|X=ui|A=侧边栏|D=vue|S=dom|RD=./README.ai -->
<template>
  <aside class="writing-sidebar-shell" aria-label="章节目录">
    <!-- 左侧：蓝图和章节列表 -->
    <div
      class="md-card md-card-outlined writing-sidebar"
      id="writing-desk-chapter-sidebar"
    >
      <div class="h-full flex flex-col">
        <div class="writing-sidebar__outline-header">
          <div class="writing-sidebar__outline-header-row">
            <div class="writing-sidebar__outline-heading">
              <h3 class="md-title-medium font-semibold">章节大纲</h3>
              <span class="writing-sidebar__outline-count">{{ totalChapters }} 章</span>
            </div>
            <div class="writing-sidebar__outline-toolbar">
              <button
                type="button"
                class="md-icon-btn md-ripple writing-sidebar__outline-action"
                @click="scrollToNearestIncompleteChapter"
                :disabled="!hasIncompleteChapter"
                aria-label="定位最近未完成章节"
                title="定位最近未完成章节"
              >
                <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" aria-hidden="true">
                  <circle cx="12" cy="12" r="7.5" stroke="currentColor" />
                  <circle cx="12" cy="12" r="2.2" fill="currentColor" />
                  <path d="M12 2.8v2.2M12 19v2.2M2.8 12H5M19 12h2.2" stroke="currentColor" />
                </svg>
              </button>
            </div>
          </div>
          <div class="writing-sidebar__search">
            <label for="writing-sidebar-search" class="sr-only">搜索章节标题或章号</label>
            <input
              id="writing-sidebar-search"
              v-model="chapterSearch"
              type="search"
              inputmode="search"
              autocomplete="off"
              placeholder="搜索标题或章号"
            />
          </div>
        </div>

        <!-- 章节列表 -->
        <div ref="listContainer" class="writing-sidebar__outline-list flex-1 overflow-y-auto">
          <div class="writing-sidebar__outline-body">
            <div v-if="filteredOutline.length" class="writing-sidebar__tree">
              <div
                v-for="chapter in filteredOutline"
                :key="chapter.chapter_number"
                class="writing-sidebar__tree-item"
                :class="{ 'has-delete-btn': canDeleteChapter(chapter.chapter_number) }"
              >
                <button
                  type="button"
                  :ref="(el) => setChapterRef(chapter.chapter_number, el)"
                  @click="$emit('selectChapter', chapter.chapter_number)"
                  :aria-current="selectedChapterNumber === chapter.chapter_number ? 'true' : undefined"
                  :aria-label="getChapterA11yLabel(chapter.chapter_number, chapter.title)"
                  :class="[
                    'cursor-pointer writing-sidebar__chapter-row',
                    selectedChapterNumber === chapter.chapter_number
                      ? 'writing-sidebar__chapter-row--compact-selected'
                      : 'writing-sidebar__chapter-row--compact-idle',
                    isChapterCompleted(chapter.chapter_number)
                      ? 'writing-sidebar__chapter-row--completed'
                      : isChapterLocked(chapter.chapter_number)
                      ? 'writing-sidebar__chapter-row--locked'
                      : 'writing-sidebar__chapter-row--pending',
                  ]"
                >
                  <div class="writing-sidebar__chapter-main">
                    <div class="writing-sidebar__chapter-index">
                      <Tooltip :text="getChapterTag(chapter.chapter_number)">
                        <span
                          :class="['writing-sidebar__status-dot', chapterStatusDotClass(chapter.chapter_number)]"
                          aria-hidden="true"
                        ></span>
                      </Tooltip>
                      <Tooltip :text="getChapterTag(chapter.chapter_number)">
                        <span class="writing-sidebar__chapter-no">
                          第{{ chapter.chapter_number }}章
                        </span>
                      </Tooltip>
                      <span class="sr-only">
                        状态：{{ getChapterTag(chapter.chapter_number) }}
                      </span>
                    </div>
                    <div class="writing-sidebar__chapter-title-row">
                      <Tooltip :text="chapter.title">
                        <span
                          class="writing-sidebar__chapter-title md-body-medium font-semibold line-clamp-1"
                        >
                          {{ chapter.title }}
                        </span>
                      </Tooltip>
                      <span
                        v-if="isChapterCompleted(chapter.chapter_number)"
                        class="writing-sidebar__chapter-word-count"
                      >
                        {{ getChapterWordCount(chapter.chapter_number) }} 字
                      </span>
                      <span
                        v-else-if="isChapterLocked(chapter.chapter_number)"
                        class="writing-sidebar__chapter-lock-icon"
                      >
                        <svg
                          class="w-3.5 h-3.5 opacity-70"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          stroke-width="2.5"
                          aria-hidden="true"
                        >
                          <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                          <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
                        </svg>
                      </span>
                      <span
                        v-else
                        class="writing-sidebar__chapter-badge-pending"
                      >
                        待写
                      </span>
                    </div>
                  </div>
                </button>
                <button
                  v-if="canDeleteChapter(chapter.chapter_number)"
                  type="button"
                  class="writing-sidebar__chapter-delete"
                  :aria-label="getDeleteChapterA11yLabel(chapter.chapter_number)"
                  :title="getDeleteChapterA11yLabel(chapter.chapter_number)"
                  @click.stop="emit('deleteChapter', getDeleteChapterNumbers(chapter.chapter_number))"
                >
                  <svg class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                    <path
                      fill-rule="evenodd"
                      d="M8 2a1 1 0 00-.894.553L6.382 4H4a1 1 0 000 2h12a1 1 0 100-2h-2.382l-.724-1.447A1 1 0 0012 2H8zM5 8a1 1 0 011 1v7h8V9a1 1 0 112 0v7a2 2 0 01-2 2H6a2 2 0 01-2-2V9a1 1 0 011-1zm3 1a1 1 0 012 0v5a1 1 0 11-2 0V9zm4 0a1 1 0 112 0v5a1 1 0 11-2 0V9z"
                      clip-rule="evenodd"
                    />
                  </svg>
                </button>
              </div>
            </div>
            <div
              v-else-if="project.blueprint?.chapter_outline?.length"
              class="text-center py-8 md-body-medium md-on-surface-variant"
            >
              <p>未找到匹配章节</p>
              <button type="button" class="md-btn md-btn-text" @click="chapterSearch = ''">
                清除搜索
              </button>
            </div>
            <div v-else class="text-center py-8 md-body-medium md-on-surface-variant">
              <svg
                class="w-12 h-12 mx-auto mb-3 opacity-50"
                fill="currentColor"
                viewBox="0 0 20 20"
                aria-hidden="true"
              >
                <path
                  d="M4 4a2 2 0 00-2 2v1h16V6a2 2 0 00-2-2H4zM18 9H2v5a2 2 0 002 2h12a2 2 0 002-2V9z"
                ></path>
              </svg>
              <p>暂无章节大纲</p>
            </div>
          </div>
        </div>

        <div class="writing-sidebar__outline-footer">
          <button
            type="button"
            @click="$emit('generateOutline')"
            :disabled="props.isGeneratingOutline"
            class="md-btn md-ripple w-full flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed writing-sidebar__outline-gen-btn"
          >
            <svg
              v-if="props.isGeneratingOutline"
              class="w-5 h-5 animate-spin"
              fill="currentColor"
              viewBox="0 0 20 20"
              aria-hidden="true"
            >
              <path
                fill-rule="evenodd"
                d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z"
                clip-rule="evenodd"
              ></path>
            </svg>
            <svg v-else class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
              <path
                d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z"
              ></path>
            </svg>
            <span>{{ props.isGeneratingOutline ? '生成中…' : '生成后续大纲' }}</span>
          </button>
        </div>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed, ref, nextTick, watch } from 'vue'
import type { ComponentPublicInstance } from 'vue'
import type { NovelProject } from '@/api/novel'
import type { ChapterWorkflowActorPhase } from '@/composables/useChapterWorkflowActor'
import Tooltip from '@/components/Tooltip.vue'
import { findNearestIncompleteChapterNumber, isChapterCompletedStatus } from '@/utils/chapter'
import { resolveChapterDisplayWordCount } from '@/utils/text'

interface Props {
  project: NovelProject
  selectedChapterNumber: number | null
  workflowPhase: ChapterWorkflowActorPhase
  isGeneratingOutline: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (event: 'selectChapter', chapterNumber: number): void
  (event: 'deleteChapter', chapterNumbers: number[]): void
  (event: 'generateOutline'): void
}>()

const listContainer = ref<HTMLElement | null>(null)
const chapterRefs = ref<Record<number, HTMLElement | null>>({})
const chapterSearch = ref('')

const totalChapters = computed(() => {
  return props.project?.blueprint?.chapter_outline?.length || 0
})

const filteredOutline = computed(() => {
  const outline = props.project?.blueprint?.chapter_outline ?? []
  const query = chapterSearch.value.trim().toLocaleLowerCase()
  if (!query) return outline
  return outline.filter((chapter) =>
    chapter.title.toLocaleLowerCase().includes(query)
    || String(chapter.chapter_number).includes(query)
    || `第${chapter.chapter_number}章`.includes(query),
  )
})

// 章节号到章节数据的索引，避免模板渲染时多次线性查找。
const chapterByNumber = computed(() => {
  const map = new Map<number, NovelProject['chapters'][number]>()
  for (const chapter of props.project?.chapters ?? []) {
    map.set(chapter.chapter_number, chapter)
  }
  return map
})

const chapterStatusByNumber = (chapterNumber: number) => {
  return chapterByNumber.value.get(chapterNumber)?.generation_status || null
}

const chapterByNumberOrNull = (chapterNumber: number) => {
  return chapterByNumber.value.get(chapterNumber) ?? null
}

const hasIncompleteChapter = computed(() => {
  if (!props.project?.blueprint?.chapter_outline?.length) return false
  return props.project.blueprint.chapter_outline.some(
    (chapter) => !isChapterCompleted(chapter.chapter_number),
  )
})

const latestCompletedChapterNumber = computed(() => {
  const completedNumbers = (props.project?.chapters ?? [])
    .filter((chapter) => chapter.generation_status === 'successful')
    .map((chapter) => chapter.chapter_number)
  return completedNumbers.length ? Math.max(...completedNumbers) : null
})

const sortedOutlineNumbers = computed(() => {
  return [...(props.project?.blueprint?.chapter_outline ?? [])]
    .map((chapter) => chapter.chapter_number)
    .filter((chapterNumber) => Number.isFinite(chapterNumber))
    .sort((left, right) => left - right)
})

const isUngeneratedOutlineChapter = (chapterNumber: number) => {
  const chapter = chapterByNumber.value.get(chapterNumber)
  return !chapter || chapter.generation_status === 'not_generated'
}

const tailUngeneratedChapterNumbers = computed(() => {
  const tail: number[] = []
  for (const chapterNumber of [...sortedOutlineNumbers.value].reverse()) {
    if (!isUngeneratedOutlineChapter(chapterNumber)) {
      break
    }
    tail.unshift(chapterNumber)
  }
  return tail
})

function setChapterRef(chapterNumber: number, el: Element | ComponentPublicInstance | null) {
  if (!el) {
    delete chapterRefs.value[chapterNumber]
    return
  }

  const element = el instanceof Element ? el : el.$el instanceof Element ? el.$el : null

  if (element) {
    chapterRefs.value[chapterNumber] = element as HTMLElement
  }
}

const scrollToChapterNumber = async (chapterNumber: number | null) => {
  if (chapterNumber === null) return
  await nextTick()
  const element = chapterRefs.value[chapterNumber]
  if (!element) return
  const container = listContainer.value
  const scrollBehavior: ScrollBehavior = shouldReduceMotion() ? 'auto' : 'smooth'
  if (container) {
    element.scrollIntoView({ behavior: scrollBehavior, block: 'center', inline: 'nearest' })
  } else {
    element.scrollIntoView({ behavior: scrollBehavior, block: 'center' })
  }
}

const scrollToNearestIncompleteChapter = async () => {
  const targetChapterNumber = findNearestIncompleteChapterNumber(
    props.project?.blueprint?.chapter_outline ?? [],
    props.project?.chapters ?? [],
  )
  await scrollToChapterNumber(targetChapterNumber)
}

defineExpose({
  scrollToNearestIncompleteChapter,
})

// 章节状态检查
const isChapterCompleted = (chapterNumber: number) => {
  return isChapterCompletedStatus(chapterByNumberOrNull(chapterNumber))
}

const canDeleteChapter = (chapterNumber: number) => {
  if (chapterNumber === latestCompletedChapterNumber.value) {
    return true
  }

  return tailUngeneratedChapterNumbers.value.includes(chapterNumber)
}

const getDeleteChapterA11yLabel = (chapterNumber: number) => {
  if (chapterNumber === latestCompletedChapterNumber.value) {
    return `删除第${chapterNumber}章及全部产物`
  }

  const deleteNumbers = getDeleteChapterNumbers(chapterNumber)
  return Array.isArray(deleteNumbers) && deleteNumbers.length > 1
    ? `删除第${chapterNumber}章及后续未生成大纲`
    : `删除第${chapterNumber}章大纲`
}

const getDeleteChapterNumbers = (chapterNumber: number): number[] => {
  if (chapterNumber === latestCompletedChapterNumber.value) {
    const tailAfterCompleted = tailUngeneratedChapterNumbers.value.filter(
      (number) => number > chapterNumber,
    )
    return [chapterNumber, ...tailAfterCompleted]
  }

  const tailFromChapter = tailUngeneratedChapterNumbers.value.filter(
    (number) => number >= chapterNumber,
  )
  return tailFromChapter.length ? tailFromChapter : [chapterNumber]
}

const isChapterLocked = (chapterNumber: number) => {
  if (!props.project?.blueprint?.chapter_outline) return true

  const sortedOutlines = [...props.project.blueprint.chapter_outline].sort(
    (left, right) => left.chapter_number - right.chapter_number,
  )

  for (const outline of sortedOutlines) {
    if (outline.chapter_number >= chapterNumber) break
    const chapter = chapterByNumber.value.get(outline.chapter_number)
    if (chapter?.generation_status !== 'successful') {
      return true
    }
  }

  return false
}

const hasChapterInProgress = (chapterNumber: number) => {
  return chapterStatusByNumber(chapterNumber) === 'waiting_for_confirm'
}

const isChapterGenerating = (chapterNumber: number) => {
  return chapterStatusByNumber(chapterNumber) === 'generating'
}

const isChapterGeneratingLike = (chapterNumber: number) => {
  return isChapterGenerating(chapterNumber)
}

const isChapterEvaluating = (chapterNumber: number) => {
  return chapterStatusByNumber(chapterNumber) === 'evaluating'
}

const isChapterFailed = (chapterNumber: number) => {
  const status = chapterStatusByNumber(chapterNumber)
  return status === 'failed' || status === 'evaluation_failed'
}

const isChapterSelecting = (chapterNumber: number) => {
  return chapterStatusByNumber(chapterNumber) === 'selecting'
}

const getChapterWordCount = (chapterNumber: number): number => {
  const chapter = chapterByNumber.value.get(chapterNumber)
  if (!chapter) return 0
  return resolveChapterDisplayWordCount(chapter.content, chapter.word_count)
}

const getChapterTag = (chapterNumber: number): string => {
  if (isChapterCompleted(chapterNumber)) return '已完成'
  if (props.selectedChapterNumber === chapterNumber) {
    switch (props.workflowPhase) {
      case 'booting':
      case 'superseded':
        return '同步中'
      case 'submitting':
      case 'running':
      case 'finalizing':
      case 'projectionPending':
        return '创作中'
      case 'waitingForSelection':
        return '待选择'
      case 'succeeded':
        return '已完成'
      case 'failed':
        return '待修复'
      case 'fatal':
        return '同步失败'
      case 'idle':
      case 'cancelled':
        return '待开始'
    }
  }
  if (isChapterGeneratingLike(chapterNumber)) return '创作中'
  if (isChapterEvaluating(chapterNumber)) return '待润色'
  if (isChapterSelecting(chapterNumber) || hasChapterInProgress(chapterNumber)) return '待选择'
  if (isChapterFailed(chapterNumber)) return '待修复'
  return '待开始'
}

const chapterStatusDotClass = (chapterNumber: number) => {
  if (isChapterCompleted(chapterNumber)) return 'is-completed'
  if (props.selectedChapterNumber === chapterNumber) {
    if (props.workflowPhase === 'succeeded') return 'is-completed'
    if (props.workflowPhase === 'failed' || props.workflowPhase === 'fatal') return 'is-failed'
    if (
      props.workflowPhase !== 'idle'
      && props.workflowPhase !== 'cancelled'
    ) {
      return 'is-progress'
    }
  }
  if (
    isChapterGeneratingLike(chapterNumber) ||
    isChapterEvaluating(chapterNumber) ||
    isChapterSelecting(chapterNumber) ||
    hasChapterInProgress(chapterNumber)
  ) {
    return 'is-progress'
  }
  if (isChapterFailed(chapterNumber)) return 'is-failed'
  return 'is-idle'
}

// 为屏幕阅读器补充章节状态，避免仅依赖颜色或悬浮提示传达关键信息。
const getChapterA11yLabel = (chapterNumber: number, title?: string | null): string => {
  const stateText = getChapterTag(chapterNumber)
  const safeTitle = title?.trim() || `第${chapterNumber}章`
  return `打开第${chapterNumber}章：${safeTitle}，状态${stateText}`
}

const shouldReduceMotion = (): boolean => {
  if (typeof window === 'undefined') return false
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

watch(
  () => props.selectedChapterNumber,
  (chapterNumber) => {
    void scrollToChapterNumber(chapterNumber)
  },
  { immediate: true },
)
</script>

<style scoped>
.writing-sidebar-shell {
  width: 100%;
  min-width: 0;
  height: 100%;
}

/* 章节大纲栏保持连续工作面，层级由色面和 1px 对位线承担。 */
.writing-sidebar {
  position: relative;
  z-index: auto;
  width: 100%;
  min-height: 0;
  height: 100%;
  overflow: hidden;
  background-color: var(--md-surface);
  color: var(--md-on-surface);
  border: 1px solid var(--md-outline-variant) !important;
  border-radius: 0 !important;
  box-shadow: none;
}

.writing-sidebar__link {
  width: 100%;
  appearance: none;
  border: 0;
  color: inherit;
  font: inherit;
  text-align: inherit;
  cursor: pointer;
}

.writing-sidebar__link:focus-visible {
  outline: 2px solid var(--md-secondary);
  outline-offset: 2px;
}

.writing-sidebar__outline-header {
  flex-shrink: 0;
  padding: var(--md-spacing-3) var(--md-spacing-4);
  background-color: var(--md-surface);
  border-bottom: 1px solid var(--md-outline-variant);
}

.writing-sidebar__search {
  max-width: 220px;
  margin-top: var(--md-spacing-2);
}

.writing-sidebar__search input {
  width: 100%;
  height: 36px;
  padding: 0 var(--md-spacing-2);
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-sm);
  background-color: var(--md-surface);
  color: var(--md-on-surface);
}

.writing-sidebar__search input:focus-visible {
  border-color: var(--md-stage);
  outline: 3px solid var(--md-note);
  outline-offset: 2px;
}

.writing-sidebar__outline-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--md-spacing-2);
}

.writing-sidebar__outline-heading {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.writing-sidebar__outline-heading h3 {
  color: var(--md-ink);
  font-family: var(--md-font-family);
}

.writing-sidebar__outline-toolbar {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 6px;
}

.writing-sidebar__outline-count {
  color: var(--md-on-surface-variant);
  font-size: var(--md-label-medium);
  font-weight: 700;
  font-family: var(--md-font-mono);
  font-variant-numeric: tabular-nums;
}

.writing-sidebar__outline-action {
  width: 44px;
  height: 44px;
  min-width: 44px;
  min-height: 44px;
  border-radius: var(--md-radius-sm) !important;
  border: 1px solid var(--md-outline);
  color: var(--md-on-surface-variant);
  background-color: transparent;
  transition:
    background-color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    border-color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    transform 0.25s cubic-bezier(0.22, 1, 0.36, 1);
  display: flex;
  align-items: center;
  justify-content: center;
}

.writing-sidebar__outline-action:hover:not(:disabled) {
  border-color: var(--md-stage);
  color: var(--md-stage-deep);
  background-color: var(--md-stage-soft);
}

.writing-sidebar__outline-action:active:not(:disabled) {
  background-color: color-mix(in srgb, var(--md-stage-soft) 76%, var(--md-stage));
}

.writing-sidebar__outline-action:focus-visible {
  outline: 3px solid var(--md-note);
  outline-offset: 2px;
}

.writing-sidebar__outline-action:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.writing-sidebar__outline-list {
  min-height: 0;
  background-color: var(--md-surface-container-low);
}

.writing-sidebar__outline-body {
  padding: var(--md-spacing-3) var(--md-spacing-4) var(--md-spacing-4);
}

.writing-sidebar__outline-footer {
  flex-shrink: 0;
  padding: var(--md-spacing-3) var(--md-spacing-4);
  border-top: 1px solid var(--md-outline-variant);
  background-color: var(--md-surface);
}

.writing-sidebar__tree {
  display: flex;
  flex-direction: column;
  border-top: 1px solid var(--md-outline-variant);
}

.writing-sidebar__tree-item {
  position: relative;
}

.writing-sidebar__chapter-row {
  display: block;
  width: 100%;
  min-height: 54px;
  text-align: left;
  appearance: none;
  -webkit-appearance: none;
  padding: 10px 12px;
  border-radius: 0 !important;
  border: 1px solid transparent;
  border-bottom-color: var(--md-outline-variant);
  background-color: var(--md-surface);
  color: inherit;
  font: inherit;
  cursor: pointer;
  position: relative;
  transition:
    background-color var(--md-duration-short) var(--md-easing-standard),
    border-color var(--md-duration-short) var(--md-easing-standard),
    box-shadow var(--md-duration-short) var(--md-easing-standard);
}

.writing-sidebar__chapter-row--compact-idle:hover {
  border-bottom-color: var(--md-stage);
  background-color: var(--md-surface-container-low);
}

.writing-sidebar__chapter-row:focus-visible {
  z-index: 1;
  outline: 3px solid var(--md-note);
  outline-offset: -3px;
}

.writing-sidebar__chapter-row--compact-selected {
  border-color: var(--md-stage) !important;
  background-color: var(--md-stage-soft) !important;
  box-shadow: inset 3px 0 0 var(--md-cue) !important;
}

.writing-sidebar__chapter-row--compact-selected .writing-sidebar__chapter-title {
  color: var(--md-ink) !important;
  font-family: var(--md-font-family);
  font-weight: 700;
}

.writing-sidebar__chapter-row--compact-selected .writing-sidebar__chapter-no {
  color: var(--md-stage-deep) !important;
}

.writing-sidebar__chapter-row--locked {
  opacity: 0.65;
}

.writing-sidebar__chapter-row--locked:hover {
  background-color: var(--md-surface-container-low) !important;
  opacity: 0.85;
}

.writing-sidebar__chapter-row--locked.writing-sidebar__chapter-row--compact-selected {
  opacity: 1;
}

/* 锁定章节的锁图标样式 (右侧) */
.writing-sidebar__chapter-lock-icon {
  margin-left: auto;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--md-on-surface-variant);
  width: 20px;
  height: 20px;
  transition: opacity 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

/* 待完成章节的中性标签样式 */
.writing-sidebar__chapter-badge-pending {
  margin-left: auto;
  flex-shrink: 0;
  font-size: 12px;
  line-height: 1.2;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: var(--md-radius-sm);
  background: color-mix(in srgb, var(--md-on-surface) 8%, transparent);
  color: var(--md-on-surface-variant) !important;
  transition: opacity 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

.writing-sidebar__chapter-delete {
  position: absolute;
  top: 50%;
  right: 12px;
  z-index: 12;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  min-width: 32px;
  min-height: 32px;
  border: 0;
  background-color: transparent;
  color: var(--md-on-surface-variant);
  opacity: 0;
  transform: translateY(-50%) translateX(10px);
  transition:
    opacity 0.25s cubic-bezier(0.16, 1, 0.3, 1),
    color 0.25s cubic-bezier(0.16, 1, 0.3, 1),
    transform 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

.writing-sidebar__chapter-delete::before {
  content: '';
  position: absolute;
  inset: -6px;
}

.writing-sidebar__tree-item:hover .writing-sidebar__chapter-delete,
.writing-sidebar__tree-item:focus-within .writing-sidebar__chapter-delete,
.writing-sidebar__chapter-delete:focus-visible {
  opacity: 1;
  transform: translateY(-50%) translateX(0);
}

.writing-sidebar__chapter-delete:hover {
  color: var(--md-cue);
}

.writing-sidebar__chapter-delete:focus-visible {
  color: var(--md-cue);
  outline: 3px solid var(--md-note);
  outline-offset: 2px;
}

/* 删除入口出现时让出行尾空间，避免与字数或状态标签重叠。 */
.writing-sidebar__tree-item.has-delete-btn:hover .writing-sidebar__chapter-word-count,
.writing-sidebar__tree-item.has-delete-btn:hover .writing-sidebar__chapter-lock-icon,
.writing-sidebar__tree-item.has-delete-btn:hover .writing-sidebar__chapter-badge-pending {
  opacity: 0 !important;
  pointer-events: none;
}

.writing-sidebar__tree-item.has-delete-btn:has(.writing-sidebar__chapter-delete:focus-visible)
  .writing-sidebar__chapter-word-count,
.writing-sidebar__tree-item.has-delete-btn:has(.writing-sidebar__chapter-delete:focus-visible)
  .writing-sidebar__chapter-lock-icon,
.writing-sidebar__tree-item.has-delete-btn:has(.writing-sidebar__chapter-delete:focus-visible)
  .writing-sidebar__chapter-badge-pending {
  opacity: 0 !important;
  pointer-events: none;
}
.writing-sidebar__chapter-main {
  display: flex;
  align-items: center;
  gap: var(--md-spacing-2);
}

.writing-sidebar__chapter-index {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-top: 0;
}

.writing-sidebar__status-dot {
  position: relative;
  display: inline-block;
  flex-shrink: 0;
  width: 12px;
  height: 12px;
  border: 1.5px solid var(--md-outline);
  border-radius: var(--md-radius-xs);
  background-color: var(--md-surface);
}

.writing-sidebar__status-dot.is-completed {
  border-color: var(--md-success);
  background-color: var(--md-success);
}

.writing-sidebar__status-dot.is-completed::after {
  content: '';
  position: absolute;
  left: 3px;
  top: 1px;
  width: 4px;
  height: 7px;
  border: solid var(--md-on-primary);
  border-width: 0 2px 2px 0;
  transform: rotate(45deg);
}

.writing-sidebar__status-dot.is-progress {
  border-color: var(--md-cue);
  border-radius: 50%;
  background-color: var(--md-cue);
}

.writing-sidebar__status-dot.is-failed {
  border-color: var(--md-error);
  background-color: var(--md-surface);
  color: var(--md-error);
}

.writing-sidebar__status-dot.is-failed::before,
.writing-sidebar__status-dot.is-failed::after {
  content: '';
  position: absolute;
  left: 2px;
  top: 4px;
  width: 6px;
  height: 1.5px;
  background-color: currentColor;
}

.writing-sidebar__status-dot.is-failed::before {
  transform: rotate(45deg);
}

.writing-sidebar__status-dot.is-failed::after {
  transform: rotate(-45deg);
}

.writing-sidebar__chapter-no {
  color: var(--md-on-surface);
  font-size: var(--md-label-medium);
  font-weight: 600;
}

.writing-sidebar__chapter-title-row {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: var(--md-spacing-1);
}

.writing-sidebar__chapter-title {
  flex: 1;
  min-width: 0;
}

.writing-sidebar__chapter-word-count {
  margin-left: auto;
  flex-shrink: 0;
  min-width: 56px;
  text-align: right;
  color: var(--md-on-surface-variant);
  font-family: var(--md-font-mono);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  transition: opacity 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

.writing-sidebar .md-on-surface-variant {
  color: var(--md-on-surface-variant);
}

/* 触屏无法悬停：删除操作占用独立栏位，避免覆盖锁定与状态信息。 */
@media (hover: none), (max-width: 833px) {
  .writing-sidebar__tree-item.has-delete-btn {
    display: flex;
  }

  .writing-sidebar__tree-item.has-delete-btn .writing-sidebar__chapter-row {
    flex: 1;
    min-width: 0;
    width: auto;
  }

  .writing-sidebar__chapter-delete {
    position: static;
    flex: 0 0 44px;
    width: 44px;
    height: auto;
    min-width: 44px;
    min-height: 54px;
    opacity: 0.55;
    transform: none;
  }

  .writing-sidebar__chapter-delete::before {
    inset: 0;
  }

  .writing-sidebar__tree-item.has-delete-btn .writing-sidebar__chapter-word-count,
  .writing-sidebar__tree-item.has-delete-btn .writing-sidebar__chapter-lock-icon,
  .writing-sidebar__tree-item.has-delete-btn .writing-sidebar__chapter-badge-pending {
    display: none;
  }

  .writing-sidebar__tree-item:hover .writing-sidebar__chapter-delete,
  .writing-sidebar__tree-item:focus-within .writing-sidebar__chapter-delete,
  .writing-sidebar__chapter-delete:focus-visible {
    transform: none;
  }
}

@media (max-width: 833px) {
  .writing-sidebar-shell {
    height: 100%;
    overflow: hidden;
  }
}

.writing-sidebar__outline-gen-btn {
  min-width: 0;
  flex-shrink: 0;
  border-color: var(--md-stage);
  border-radius: var(--md-radius-sm);
  background-color: var(--md-stage);
  color: var(--md-on-primary);
  font-weight: 700;
}

.writing-sidebar__outline-gen-btn:hover:not(:disabled) {
  border-color: var(--md-stage-strong);
  background-color: var(--md-stage-strong);
}

.writing-sidebar__outline-gen-btn:active:not(:disabled) {
  border-color: var(--md-stage-deep);
  background-color: var(--md-stage-deep);
}

.writing-sidebar__outline-gen-btn:focus-visible {
  outline: 3px solid var(--md-note);
  outline-offset: 2px;
}

@media (prefers-reduced-motion: reduce) {
  .writing-sidebar__outline-gen-btn .animate-spin {
    animation: none !important;
  }
}
</style>
