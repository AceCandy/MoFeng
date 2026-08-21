<!-- AIMETA P=写作台侧边栏_章节目录|R=章节列表_导航|NR=不含内容编辑|E=component:WDSidebar|X=ui|A=侧边栏|D=vue|S=dom|RD=./README.ai -->
<template>
  <aside class="writing-sidebar-shell" aria-label="章节目录">
    <!-- 左侧：蓝图和章节列表 -->
    <div
      class="md-card md-card-outlined writing-sidebar"
      id="writing-desk-chapter-sidebar"
    >
      <div class="h-full flex flex-col">


        <!-- 章节列表 -->
        <div ref="listContainer" class="flex-1 overflow-y-auto">
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
                  <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24">
                    <circle cx="12" cy="12" r="7.5" stroke="currentColor" />
                    <circle cx="12" cy="12" r="2.2" fill="currentColor" />
                  <path d="M12 2.8v2.2M12 19v2.2M2.8 12H5M19 12h2.2" stroke="currentColor" />
                  </svg>
                </button>
              </div>
            </div>
          </div>

          <div class="pl-1 pr-2 pb-6 pt-3">
            <div v-if="project.blueprint?.chapter_outline?.length" class="writing-sidebar__tree">
              <div
                v-for="(chapter, index) in project.blueprint.chapter_outline"
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
                    'cursor-pointer writing-sidebar__chapter-row m3-stagger',
                    selectedChapterNumber === chapter.chapter_number
                      ? 'writing-sidebar__chapter-row--compact-selected'
                      : 'writing-sidebar__chapter-row--compact-idle',
                    isChapterCompleted(chapter.chapter_number)
                      ? 'writing-sidebar__chapter-row--completed'
                      : isChapterLocked(chapter.chapter_number)
                      ? 'writing-sidebar__chapter-row--locked'
                      : 'writing-sidebar__chapter-row--pending',
                  ]"
                  :style="{ animationDelay: `${Math.min(index * 8, 80)}ms` }"
                >
                  <div class="writing-sidebar__chapter-main">
                    <div class="writing-sidebar__chapter-index">
                      <Tooltip :text="getChapterTag(chapter.chapter_number)">
                        <span
                          :class="['writing-sidebar__status-dot', chapterStatusDotClass(chapter.chapter_number)]"
                        ></span>
                      </Tooltip>
                      <span
                        class="writing-sidebar__status-seal"
                        :class="chapterStatusSealClass(chapter.chapter_number)"
                        aria-hidden="true"
                      >{{ chapterStatusSealText(chapter.chapter_number) }}</span>
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
                  class="writing-sidebar__chapter-delete md-ripple"
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
            <div v-else class="text-center py-8 md-body-medium md-on-surface-variant">
              <svg
                class="w-12 h-12 mx-auto mb-3 opacity-50"
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path
                  d="M4 4a2 2 0 00-2 2v1h16V6a2 2 0 00-2-2H4zM18 9H2v5a2 2 0 002 2h12a2 2 0 002-2V9z"
                ></path>
              </svg>
              <p>暂无章节大纲</p>
            </div>
            <div class="mt-4">
              <button
                type="button"
                @click="$emit('generateOutline')"
                :disabled="props.isGeneratingOutline"
                class="md-btn md-btn-tonal md-ripple w-full flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed writing-sidebar__outline-gen-btn"
              >
                <svg
                  v-if="props.isGeneratingOutline"
                  class="w-5 h-5 animate-spin"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path
                    fill-rule="evenodd"
                    d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z"
                    clip-rule="evenodd"
                  ></path>
                </svg>
                <svg v-else class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                  <path
                    d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z"
                  ></path>
                </svg>
                <span>{{ props.isGeneratingOutline ? '生成中...' : '生成后续大纲' }}</span>
              </button>
            </div>
          </div>
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

const totalChapters = computed(() => {
  return props.project?.blueprint?.chapter_outline?.length || 0
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
  if (isChapterCompleted(chapterNumber)) return '已完成'
  if (isChapterGeneratingLike(chapterNumber)) return '创作中'
  if (isChapterEvaluating(chapterNumber)) return '待润色'
  if (isChapterSelecting(chapterNumber) || hasChapterInProgress(chapterNumber)) return '待选择'
  if (isChapterFailed(chapterNumber)) return '待修复'
  return '待开始'
}

const chapterStatusDotClass = (chapterNumber: number) => {
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
  if (isChapterCompleted(chapterNumber)) return 'is-completed'
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

// 状态印三态（spec §5）：已钤印（朱砂实底）/ 描红中（淡朱描边）/ 已落墨（焦墨描边）
type ChapterSealState = 'sealed' | 'tracing' | 'inked'

const chapterStatusSealState = (chapterNumber: number): ChapterSealState => {
  // 已完成/已保存 = 已钤印
  if (isChapterCompleted(chapterNumber)) return 'sealed'
  if (props.selectedChapterNumber === chapterNumber) {
    switch (props.workflowPhase) {
      case 'succeeded':
        return 'sealed'
      case 'booting':
      case 'submitting':
      case 'running':
      case 'waitingForSelection':
      case 'finalizing':
      case 'projectionPending':
      case 'superseded':
        // 生成中或已有候选待选 = 描红中
        return 'tracing'
      default:
        break
    }
  }
  if (
    isChapterGeneratingLike(chapterNumber) ||
    isChapterEvaluating(chapterNumber) ||
    isChapterSelecting(chapterNumber) ||
    hasChapterInProgress(chapterNumber)
  ) {
    return 'tracing'
  }
  // 其余 = 已落墨
  return 'inked'
}

const chapterStatusSealClass = (chapterNumber: number) =>
  `writing-sidebar__status-seal--${chapterStatusSealState(chapterNumber)}`

const chapterStatusSealText = (chapterNumber: number): string => {
  switch (chapterStatusSealState(chapterNumber)) {
    case 'sealed':
      return '钤'
    case 'tracing':
      return '描'
    default:
      return '墨'
  }
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

/* 暗室明纸：章节大纲栏沉入固定夜色（不随明暗主题翻转），夜色铬件无影，
   与页底夜色之间只靠 1px night-outline 发线分界；稿纸区保持纸色世界不动 */
.writing-sidebar {
  position: relative;
  z-index: auto;
  width: 100%;
  min-height: 0;
  height: 100%;
  overflow: hidden;
  background-color: var(--md-night-surface);
  color: var(--md-night-on);
  border: 1px solid var(--md-night-outline) !important;
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
  position: sticky;
  top: 0;
  z-index: 24;
  padding: var(--md-spacing-5) var(--md-spacing-6) var(--md-spacing-3);
  background-color: var(--md-night-surface);
  border-bottom: 1px solid var(--md-night-outline);
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
  font-family: var(--md-font-serif);
  color: var(--md-night-on-variant);
}

.writing-sidebar__outline-toolbar {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 6px;
}

.writing-sidebar__outline-count {
  color: var(--md-night-on-variant);
  font-size: var(--md-label-medium);
  font-weight: 600;
  font-family: var(--md-font-serif);
}

/* 夜色安静款图标钮：透明底 + night-outline 边 + night-on-variant 字，hover 转夜色钤印红 */
.writing-sidebar__outline-action {
  width: 36px;
  height: 36px;
  min-width: 36px;
  min-height: 36px;
  border-radius: 0 !important;
  border: 1.5px solid var(--md-night-outline);
  color: var(--md-night-on-variant);
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
  border-color: var(--md-night-seal);
  color: var(--md-night-seal);
  background-color: color-mix(in srgb, var(--md-night-seal) 8%, transparent);
}

.writing-sidebar__outline-action:active:not(:disabled) {
  transform: translate(1px, 1px);
}

.writing-sidebar__outline-action:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.writing-sidebar__tree {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.writing-sidebar__tree-item {
  position: relative;
  padding-left: 10px;
}

/* 目录穿线（2px 朱砂线装书 motif）已由全局 chapter-binding.css 收口，此处不再重复定义 */

/* 极致国风脑洞：木刻竹简签条样式章节行（夜色发线边框） */
.writing-sidebar__chapter-row {
  display: block;
  width: 100%;
  text-align: left;
  appearance: none;
  -webkit-appearance: none;
  padding: 8px;
  border-radius: 0 !important;
  border: 1px solid var(--md-night-outline);
  background-color: color-mix(in srgb, var(--md-night-on) 3%, transparent);
  color: inherit;
  font: inherit;
  outline: none;
  cursor: pointer;
  position: relative;
  transition:
    background-color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    border-color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    transform 0.25s cubic-bezier(0.22, 1, 0.36, 1);
}

/* Hover 脑洞：竹简抽出金石回弹微颤抖（夜色悬停 = 暖纸白 6% 薄光） */
.writing-sidebar__chapter-row--compact-idle:hover,
.writing-sidebar__chapter-row:focus-visible {
  border-color: var(--md-night-outline-strong);
  background-color: rgba(236, 228, 207, 0.06);
  transform: translateX(4px);
  animation: stone-tremble 0.25s cubic-bezier(0.22, 1, 0.36, 1) both;
}

/* 选中章节签条：night-on 8% 浮光底 + 左缘 2px 夜色钤印印线（夜色里的「当前」权责） */
.writing-sidebar__chapter-row--compact-selected {
  border: 1px solid var(--md-night-outline-strong) !important;
  background-color: color-mix(in srgb, var(--md-night-on) 8%, transparent) !important;
  margin-left: -10px !important; /* 向左平移 10px，使其恰好压在竖红线上 */
  width: calc(100% + 14px) !important; /* 显式拓宽卡片（向左超出 10px，向右超出 4px），使其绝对宽于普通卡片 */
  padding-left: 18px !important; /* 增加左侧内边距，精确对齐文字内容与状态点 */
  box-shadow: none !important;
  z-index: 10; /* 确保选中章节盖在连线上，显得更有层次 */
}

.writing-sidebar__chapter-row--compact-selected::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 2px;
  background-color: var(--md-night-seal);
  pointer-events: none;
}

.writing-sidebar__chapter-row--compact-selected .writing-sidebar__chapter-title {
  font-family: var(--md-font-serif);
  color: var(--md-night-seal) !important;
  font-weight: bold;
  letter-spacing: 0.03em;
}

.writing-sidebar__chapter-row--compact-selected .writing-sidebar__chapter-no {
  color: var(--md-night-seal) !important;
}

/* 行尾「著」字闲章与目录穿线在夜色里改用 night-seal 系（覆写全局 chapter-binding.css 纸色定值） */
.writing-sidebar__chapter-row--compact-selected::after {
  background-color: var(--md-night-seal) !important;
  color: var(--md-night-seal-on) !important;
  border-color: var(--md-night-seal) !important;
}

.writing-sidebar__tree-item::before {
  background-color: color-mix(in srgb, var(--md-night-seal) 26%, transparent);
  border-left-color: color-mix(in srgb, var(--md-night-seal) 14%, transparent);
  box-shadow: none;
}

.writing-sidebar__tree-item::after {
  background-color: color-mix(in srgb, var(--md-night-seal) 20%, transparent);
}

/* 选中行尾朱砂方印「著」已由全局 chapter-binding.css 收口，此处不再重复定义 */

/* 已完成/待写/未解锁签条在夜色里统一为中性夜色：状态权责交给状态印与状态点，
   纸色世界的石绿/藤黄彩边在夜底发闷且对比不达标，不带入暗室 */
.writing-sidebar__chapter-row--completed {
  border-color: var(--md-night-outline) !important;
  background-color: color-mix(in srgb, var(--md-night-on) 5%, transparent) !important;
}
.writing-sidebar__chapter-row--completed:hover {
  border-color: var(--md-night-outline-strong) !important;
  background-color: rgba(236, 228, 207, 0.06) !important;
}

.writing-sidebar__chapter-row--pending {
  border-color: var(--md-night-outline) !important;
  background-color: color-mix(in srgb, var(--md-night-on) 3%, transparent) !important;
}
.writing-sidebar__chapter-row--pending:hover {
  border-color: var(--md-night-outline-strong) !important;
  background-color: rgba(236, 228, 207, 0.06) !important;
}

/* 未解锁状态的签条样式 (夜色压暗) */
.writing-sidebar__chapter-row--locked {
  opacity: 0.65;
  border-color: color-mix(in srgb, var(--md-night-outline) 60%, transparent) !important;
  background-color: transparent !important;
}
.writing-sidebar__chapter-row--locked:hover {
  border-color: var(--md-night-outline) !important;
  background-color: rgba(236, 228, 207, 0.06) !important;
  opacity: 0.85;
}

/* 「当前」权责统一：三态章被选中时与基准选中态一致（night-on 8% 底 + 2px 印线 + 夜印红题名） */
.writing-sidebar__chapter-row--completed.writing-sidebar__chapter-row--compact-selected,
.writing-sidebar__chapter-row--pending.writing-sidebar__chapter-row--compact-selected,
.writing-sidebar__chapter-row--locked.writing-sidebar__chapter-row--compact-selected {
  border: 1px solid var(--md-night-outline-strong) !important;
  background-color: color-mix(in srgb, var(--md-night-on) 8%, transparent) !important;
  box-shadow: none !important;
}
.writing-sidebar__chapter-row--completed.writing-sidebar__chapter-row--compact-selected .writing-sidebar__chapter-title,
.writing-sidebar__chapter-row--completed.writing-sidebar__chapter-row--compact-selected .writing-sidebar__chapter-no,
.writing-sidebar__chapter-row--pending.writing-sidebar__chapter-row--compact-selected .writing-sidebar__chapter-title,
.writing-sidebar__chapter-row--pending.writing-sidebar__chapter-row--compact-selected .writing-sidebar__chapter-no {
  color: var(--md-night-seal) !important;
}
.writing-sidebar__chapter-row--locked.writing-sidebar__chapter-row--compact-selected .writing-sidebar__chapter-title,
.writing-sidebar__chapter-row--locked.writing-sidebar__chapter-row--compact-selected .writing-sidebar__chapter-no {
  color: var(--md-night-on-variant) !important;
}
.writing-sidebar__chapter-row--completed.writing-sidebar__chapter-row--compact-selected::after,
.writing-sidebar__chapter-row--pending.writing-sidebar__chapter-row--compact-selected::after,
.writing-sidebar__chapter-row--locked.writing-sidebar__chapter-row--compact-selected::after {
  color: var(--md-night-seal-on) !important;
  border-color: var(--md-night-seal) !important;
  background-color: var(--md-night-seal) !important;
}

/* 锁定章节的锁图标样式 (右侧) */
.writing-sidebar__chapter-lock-icon {
  margin-left: auto;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--md-night-on-variant);
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
  background: color-mix(in srgb, var(--md-night-on) 8%, transparent);
  color: var(--md-night-on-variant) !important;
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
  width: 28px;
  height: 28px;
  min-width: 28px;
  min-height: 28px;
  border: 1px solid var(--md-night-outline);
  border-radius: var(--md-radius-sm) !important;
  background-color: color-mix(in srgb, var(--md-night-on) 6%, transparent);
  color: var(--md-night-on-variant);
  opacity: 0.4; /* 常态半透可见，触屏可达；hover/focus 时全显 */
  transform: translateY(-50%) translateX(10px);
  transition:
    opacity 0.25s cubic-bezier(0.16, 1, 0.3, 1),
    background-color 0.25s cubic-bezier(0.16, 1, 0.3, 1),
    border-color 0.25s cubic-bezier(0.16, 1, 0.3, 1),
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

.writing-sidebar__chapter-delete:hover,
.writing-sidebar__chapter-delete:focus-visible {
  border-color: var(--md-night-seal);
  background-color: color-mix(in srgb, var(--md-night-seal) 12%, transparent);
  color: var(--md-night-seal);
}

/* 当有删除按钮的章节被 hover，或删除按钮获得焦点时，隐藏章节行的各种状态和印章，以进行无缝替换 */
.writing-sidebar__tree-item.has-delete-btn:hover .writing-sidebar__chapter-word-count,
.writing-sidebar__tree-item.has-delete-btn:hover .writing-sidebar__chapter-lock-icon,
.writing-sidebar__tree-item.has-delete-btn:hover .writing-sidebar__chapter-badge-pending,
.writing-sidebar__tree-item.has-delete-btn:hover .writing-sidebar__chapter-row--compact-selected::after {
  opacity: 0 !important;
  pointer-events: none;
}

.writing-sidebar__tree-item.has-delete-btn:has(.writing-sidebar__chapter-delete:focus-visible) .writing-sidebar__chapter-word-count,
.writing-sidebar__tree-item.has-delete-btn:has(.writing-sidebar__chapter-delete:focus-visible) .writing-sidebar__chapter-lock-icon,
.writing-sidebar__tree-item.has-delete-btn:has(.writing-sidebar__chapter-delete:focus-visible) .writing-sidebar__chapter-badge-pending,
.writing-sidebar__tree-item.has-delete-btn:has(.writing-sidebar__chapter-delete:focus-visible) .writing-sidebar__chapter-row--compact-selected::after {
  opacity: 0 !important;
  pointer-events: none;
}
.writing-sidebar__chapter-main {
  display: flex;
  align-items: center;
  gap: 10px;
}

.writing-sidebar__chapter-index {
  min-width: 96px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding-top: 0;
}

/* 状态印（spec §5）：章节状态三态方印，单字宋体 */
.writing-sidebar__status-seal {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  flex-shrink: 0;
  border-radius: 2px;
  font-family: var(--md-font-serif);
  font-size: 11px;
  font-weight: 600;
  line-height: 1;
  user-select: none;
}

/* 已钤印：夜色钤印实底方印（已完成/已保存）——夜底用更饱和的 night-seal，白昼朱砂在夜底发闷 */
.writing-sidebar__status-seal--sealed {
  background-color: var(--md-night-seal);
  color: var(--md-night-seal-on);
}

/* 描红中：夜色描红系描边方印（生成中或已有候选待选） */
.writing-sidebar__status-seal--tracing {
  border: 1px solid var(--md-night-seal);
  background-color: color-mix(in srgb, var(--md-night-seal) 10%, transparent);
  color: var(--md-night-seal);
}

/* 已落墨：夜色中性描边方印（其余）——焦墨在夜底不可读，转为 night-outline + night-on-variant */
.writing-sidebar__status-seal--inked {
  border: 1px solid var(--md-night-outline-strong);
  color: var(--md-night-on-variant);
}

/* 极致国风脑洞：小圆点改造为微型“金石印章方印”，融入古典中式传统色 */
.writing-sidebar__status-dot {
  width: 8px;
  height: 8px;
  border-radius: 0 !important; /* 方直印章 */
  background-color: var(--md-night-on-variant);
  display: inline-block;
  border: 1px solid transparent;
}

/* 已完成沿用“石绿”中式绿（图形语义色，夜底 ≥3:1） */
.writing-sidebar__status-dot.is-completed {
  background-color: var(--md-success) !important; /* 石绿 */
  border-color: color-mix(in srgb, var(--md-success) 70%, var(--md-night-on));
}

/* 进行中使用夜色钤印红 */
.writing-sidebar__status-dot.is-progress {
  background-color: var(--md-night-seal) !important;
  border-color: color-mix(in srgb, var(--md-night-seal) 70%, var(--md-night-on));
}

/* 失败沿用“丹砂”错误语义色 */
.writing-sidebar__status-dot.is-failed {
  background-color: var(--md-error) !important;
  border-color: color-mix(in srgb, var(--md-error) 70%, var(--md-night-on));
}

/* 夜色辅文灰兜底 */
.writing-sidebar__status-dot.is-idle {
  background-color: var(--md-night-on-variant) !important;
  border-color: color-mix(in srgb, var(--md-night-on-variant) 75%, var(--md-night-on));
}

.writing-sidebar__chapter-no {
  color: var(--md-night-on);
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
  color: var(--md-night-on-variant);
  font-size: var(--md-body-small);
  transition: opacity 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

/* 空态「暂无章节大纲」：全局工具类在夜色容器内改读夜色辅文 */
.writing-sidebar .md-on-surface-variant {
  color: var(--md-night-on-variant);
}

.m3-stagger {
  animation: m3-rise 0.2s cubic-bezier(0.22, 1, 0.36, 1) both;
}

@media (max-width: 833px) {
  .writing-sidebar-shell {
    height: auto;
  }
}

/* 动效关键帧 */
@keyframes m3-rise {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 脑洞：Hover 竹简抽出金石阻尼微颤抖 */
@keyframes stone-tremble {
  0% { transform: translateX(0); }
  30% { transform: translateX(5px) rotate(0.4deg); }
  60% { transform: translateX(3px) rotate(-0.3deg); }
  80% { transform: translateX(4.5px) rotate(0.1deg); }
  100% { transform: translateX(4px) rotate(0); }
}

/* 脑洞：朱砂 [閱] 印章空中扣下、落纸微回弹 */
@keyframes seal-stamp {
  0% {
    opacity: 0;
    transform: translateY(-50%) scale(1.45) rotate(-18deg);
  }
  100% {
    opacity: 1;
    transform: translateY(-50%) scale(1) rotate(-6deg);
  }
}

/* dot-ink-pulse 已移除：进行中状态以朱砂静态色点指示，避免常驻动画 */

@media (prefers-reduced-motion: reduce) {
  .m3-stagger,
  .writing-sidebar__chapter-row--compact-idle:hover,
  .writing-sidebar__status-dot.is-progress {
    animation: none !important;
    transform: none !important;
  }
}

.writing-sidebar__outline-gen-btn {
  min-width: 156px;
  flex-shrink: 0;
}

</style>
