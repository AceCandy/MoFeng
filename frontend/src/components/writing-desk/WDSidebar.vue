<!-- AIMETA P=写作台侧边栏_章节目录|R=章节列表_导航|NR=不含内容编辑|E=component:WDSidebar|X=ui|A=侧边栏|D=vue|S=dom|RD=./README.ai -->
<template>
  <aside class="writing-sidebar-shell" aria-label="章节目录">
    <!-- 左侧：蓝图和章节列表 -->
    <div
      class="md-card md-card-outlined writing-sidebar"
      id="writing-desk-chapter-sidebar"
      style="border-radius: var(--md-radius-xl)"
    >
      <div class="h-full flex flex-col">
        <!-- 蓝图预览卡片 -->
        <div class="md-card-header flex-shrink-0">
          <button
            type="button"
            class="writing-sidebar__link writing-sidebar__blueprint-link md-ripple"
            aria-label="打开故事蓝图"
            @click="emit('openProjectDetail')"
          >
            <div
              class="w-10 h-10 rounded-full flex items-center justify-center"
              style="background-color: var(--md-primary-container)"
            >
              <svg
                class="w-5 h-5"
                style="color: var(--md-on-primary-container)"
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
              </svg>
            </div>
            <div class="min-w-0 text-left">
              <h2 class="md-title-medium font-semibold">故事蓝图</h2>
              <p class="md-body-small md-on-surface-variant">
                {{ project.blueprint?.style || '未设定风格' }}
              </p>
            </div>
          </button>
        </div>

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
                  @click="scrollToFirstIncompleteChapter"
                  :disabled="!hasIncompleteChapter"
                  aria-label="定位第一个未完成章节"
                  title="定位第一个未完成章节"
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

          <div class="px-6 pb-6 pt-3">
            <div v-if="project.blueprint?.chapter_outline?.length" class="writing-sidebar__tree">
              <div
                v-for="(chapter, index) in project.blueprint.chapter_outline"
                :key="chapter.chapter_number"
                class="writing-sidebar__tree-item"
              >
                <div
                  :ref="(el) => setChapterRef(chapter.chapter_number, el)"
                  @click="$emit('selectChapter', chapter.chapter_number)"
                  @keydown.enter.prevent="$emit('selectChapter', chapter.chapter_number)"
                  @keydown.space.prevent="$emit('selectChapter', chapter.chapter_number)"
                  role="button"
                  tabindex="0"
                  :aria-pressed="selectedChapterNumber === chapter.chapter_number"
                  :aria-label="getChapterA11yLabel(chapter.chapter_number, chapter.title)"
                  :class="[
                    'cursor-pointer writing-sidebar__chapter-row m3-stagger',
                    selectedChapterNumber === chapter.chapter_number
                      ? 'writing-sidebar__chapter-row--compact-selected'
                      : 'writing-sidebar__chapter-row--compact-idle',
                  ]"
                  :style="{ animationDelay: `${index * 40}ms` }"
                >
                  <div class="writing-sidebar__chapter-main">
                    <div class="writing-sidebar__chapter-index">
                      <Tooltip :text="getChapterTag(chapter.chapter_number)">
                        <span
                          :class="['writing-sidebar__status-dot', chapterStatusDotClass(chapter.chapter_number)]"
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
                        <h4
                          class="writing-sidebar__chapter-title md-body-medium font-semibold line-clamp-1"
                        >
                          {{ chapter.title }}
                        </h4>
                      </Tooltip>
                      <span
                        v-if="isChapterCompleted(chapter.chapter_number)"
                        class="writing-sidebar__chapter-word-count"
                      >
                        {{ getChapterWordCount(chapter.chapter_number) }} 字
                      </span>
                    </div>
                  </div>
                </div>
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
                class="md-btn md-btn-tonal md-ripple w-full flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
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
import { computed, ref, nextTick } from 'vue'
import type { ComponentPublicInstance } from 'vue'
import type { NovelProject } from '@/api/novel'
import Tooltip from '@/components/Tooltip.vue'

interface Props {
  project: NovelProject
  selectedChapterNumber: number | null
  generatingChapter: number | null
  evaluatingChapter: number | null
  isGeneratingOutline: boolean
}

const props = defineProps<Props>()

const emit = defineEmits([
  'openProjectDetail',
  'selectChapter',
  'generateChapter',
  'editChapter',
  'generateOutline',
])

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

const hasIncompleteChapter = computed(() => {
  if (!props.project?.blueprint?.chapter_outline?.length) return false
  return props.project.blueprint.chapter_outline.some(
    (chapter) => !isChapterCompleted(chapter.chapter_number),
  )
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

const scrollToFirstIncompleteChapter = async () => {
  if (!props.project?.blueprint?.chapter_outline) return
  const sorted = [...props.project.blueprint.chapter_outline].sort(
    (a, b) => a.chapter_number - b.chapter_number,
  )
  const target = sorted.find((chapter) => !isChapterCompleted(chapter.chapter_number))
  if (!target) return
  await nextTick()
  const element = chapterRefs.value[target.chapter_number]
  if (!element) return
  const container = listContainer.value
  const scrollBehavior: ScrollBehavior = shouldReduceMotion() ? 'auto' : 'smooth'
  if (container) {
    element.scrollIntoView({ behavior: scrollBehavior, block: 'center', inline: 'nearest' })
  } else {
    element.scrollIntoView({ behavior: scrollBehavior, block: 'center' })
  }
}

defineExpose({
  scrollToFirstIncompleteChapter,
})

// 章节状态检查
const isChapterCompleted = (chapterNumber: number) => {
  return chapterStatusByNumber(chapterNumber) === 'successful'
}

const hasChapterInProgress = (chapterNumber: number) => {
  return chapterStatusByNumber(chapterNumber) === 'waiting_for_confirm'
}

const isChapterGenerating = (chapterNumber: number) => {
  return chapterStatusByNumber(chapterNumber) === 'generating'
}

const isChapterGeneratingLike = (chapterNumber: number) => {
  return props.generatingChapter === chapterNumber || isChapterGenerating(chapterNumber)
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
  if (typeof chapter.word_count === 'number' && chapter.word_count >= 0) return chapter.word_count
  return (chapter.content || '').replace(/\s+/g, '').length
}

const getChapterTag = (chapterNumber: number): string => {
  if (isChapterCompleted(chapterNumber)) return '已完成'
  if (isChapterGeneratingLike(chapterNumber)) return '创作中'
  if (isChapterEvaluating(chapterNumber)) return '待润色'
  if (isChapterSelecting(chapterNumber) || hasChapterInProgress(chapterNumber)) return '待选择'
  if (isChapterFailed(chapterNumber)) return '待修复'
  return '待开始'
}

const chapterStatusDotClass = (chapterNumber: number) => {
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
</script>

<style scoped>
.writing-sidebar-shell {
  width: 100%;
  min-width: 0;
  height: 100%;
}

.writing-sidebar {
  position: relative;
  z-index: auto;
  width: 100%;
  min-height: 0;
  height: 100%;
  overflow: hidden;
  background-color: color-mix(in srgb, var(--md-surface) 95%, var(--md-surface-container-low));
  border-color: color-mix(in srgb, var(--md-outline-variant) 86%, transparent);
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
  outline: 2px solid var(--md-primary);
  outline-offset: 2px;
}

.writing-sidebar__blueprint-link {
  display: flex;
  align-items: center;
  gap: var(--md-spacing-3);
  margin-bottom: var(--md-spacing-4);
  padding: 0;
  background-color: transparent;
}

.writing-sidebar__outline-header {
  position: sticky;
  top: 0;
  z-index: 24;
  padding: var(--md-spacing-5) var(--md-spacing-6) var(--md-spacing-3);
  background-color: color-mix(in srgb, var(--md-surface) 96%, transparent);
  border-bottom: 1px solid color-mix(in srgb, var(--md-outline-variant) 58%, transparent);
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

.writing-sidebar__outline-toolbar {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 6px;
}

.writing-sidebar__outline-count {
  color: var(--md-on-surface-variant);
  font-size: var(--md-label-medium);
  font-weight: 600;
}

.writing-sidebar__outline-action {
  width: 44px;
  height: 44px;
  min-width: 44px;
  min-height: 44px;
  border-radius: var(--md-radius-full);
  border: 1px solid color-mix(in srgb, var(--md-outline-variant) 84%, transparent);
  color: var(--md-on-surface-variant);
  background-color: color-mix(in srgb, var(--md-surface-container-low) 66%, var(--md-surface));
}

.writing-sidebar__outline-action:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.writing-sidebar__tree {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.writing-sidebar__tree-item {
  position: relative;
  padding-left: 11px;
}

.writing-sidebar__tree-item::before {
  content: '';
  position: absolute;
  left: 6px;
  top: 0;
  bottom: -10px;
  width: 1px;
  background-color: color-mix(in srgb, var(--md-primary) 16%, var(--md-outline-variant));
}

.writing-sidebar__tree-item:last-child::before {
  bottom: 40%;
}

.writing-sidebar__tree-item::after {
  content: '';
  position: absolute;
  left: 6px;
  top: 19px;
  width: 7px;
  height: 1px;
  background-color: color-mix(in srgb, var(--md-primary) 16%, var(--md-outline-variant));
}

.writing-sidebar__chapter-row {
  padding: 9px 4px 9px 5px;
  border-radius: var(--md-radius-md);
  border: 1px solid transparent;
  background-color: transparent;
  outline: none;
  transition:
    background-color var(--md-duration-medium) var(--md-easing-standard),
    border-color var(--md-duration-medium) var(--md-easing-standard);
}

.writing-sidebar__chapter-row--compact-idle:hover,
.writing-sidebar__chapter-row:focus-visible {
  border-color: color-mix(in srgb, var(--md-outline-variant) 66%, transparent);
  background-color: color-mix(in srgb, var(--md-surface-container-low) 62%, transparent);
}

.writing-sidebar__chapter-row--compact-selected {
  border-color: color-mix(in srgb, var(--md-primary) 38%, transparent);
  background-color: color-mix(in srgb, var(--md-primary-container) 48%, var(--md-surface));
}

.writing-sidebar__chapter-main {
  display: flex;
  align-items: center;
  gap: 10px;
}

.writing-sidebar__chapter-index {
  min-width: 72px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding-top: 0;
}

.writing-sidebar__status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: var(--md-outline);
}

.writing-sidebar__status-dot.is-completed {
  background-color: var(--md-success);
}

.writing-sidebar__status-dot.is-progress {
  background-color: var(--md-primary);
  animation: dot-pulse 1.2s ease-out infinite;
}

.writing-sidebar__status-dot.is-failed {
  background-color: var(--md-error);
}

.writing-sidebar__status-dot.is-idle {
  background-color: color-mix(in srgb, var(--md-outline) 76%, var(--md-surface-container-highest));
}

.writing-sidebar__chapter-no {
  color: var(--md-on-surface-variant);
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
  font-size: var(--md-body-small);
}

.m3-stagger {
  animation: m3-rise 0.45s ease-out both;
}

@media (max-width: 833px) {
  .writing-sidebar-shell {
    height: auto;
  }
}

@keyframes m3-rise {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes dot-pulse {
  0% {
    box-shadow: 0 0 0 0 color-mix(in srgb, var(--md-primary) 30%, transparent);
  }

  100% {
    box-shadow: 0 0 0 8px color-mix(in srgb, var(--md-primary) 0%, transparent);
  }
}

@media (prefers-reduced-motion: reduce) {
  .m3-stagger,
  .writing-sidebar__status-dot.is-progress {
    animation: none !important;
  }
}
</style>
