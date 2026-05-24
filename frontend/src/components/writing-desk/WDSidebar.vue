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
                    </div>
                  </div>
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
import Tooltip from '@/components/Tooltip.vue'
import { findNearestIncompleteChapterNumber, isChapterCompletedStatus } from '@/utils/chapter'

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

const chapterByNumberOrNull = (chapterNumber: number) => {
  return chapterByNumber.value.get(chapterNumber) ?? null
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

.writing-sidebar {
  position: relative;
  z-index: auto;
  width: 100%;
  min-height: 0;
  height: 100%;
  overflow: hidden;
  background-color: var(--md-surface);
  /* 极致国风脑洞：目录侧边栏独立的手工宣纸帘纹背景 */
  background-image: repeating-linear-gradient(90deg, rgba(28, 32, 34, 0.008) 0px, rgba(28, 32, 34, 0.008) 1px, transparent 1px, transparent 24px);
  border: 3px double var(--md-outline) !important;
  border-radius: 0 !important;
  box-shadow: 3px 3px 0px var(--md-outline);
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
  background-color: var(--md-surface);
  border-bottom: 1px dashed var(--md-outline);
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
  font-family: var(--md-font-serif);
}

.writing-sidebar__outline-action {
  width: 36px;
  height: 36px;
  min-width: 36px;
  min-height: 36px;
  border-radius: 0 !important;
  border: 1.5px solid var(--md-outline);
  color: var(--md-on-surface-variant);
  background-color: var(--md-surface-container-low);
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
  border-color: var(--md-secondary);
  color: var(--md-secondary);
  background-color: rgba(184, 60, 50, 0.04);
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

.writing-sidebar__tree-item::before {
  content: '';
  position: absolute;
  left: 4px;
  top: 0;
  bottom: -4px;
  width: 1px;
  background-color: var(--md-outline-variant);
}

.writing-sidebar__tree-item:last-child::before {
  bottom: 50%;
}

.writing-sidebar__tree-item::after {
  content: '';
  position: absolute;
  left: 4px;
  top: 20px;
  width: 6px;
  height: 1px;
  background-color: var(--md-outline-variant);
}

/* 极致国风脑洞：木刻竹简签条样式章节行 */
.writing-sidebar__chapter-row {
  display: block;
  width: 100%;
  text-align: left;
  appearance: none;
  -webkit-appearance: none;
  padding: 8px 8px 8px 8px;
  border-radius: 0 !important;
  border: 1px solid var(--md-outline-variant);
  background-color: rgba(28, 32, 34, 0.015);
  color: inherit;
  font: inherit;
  outline: none;
  cursor: pointer;
  position: relative;
  transition:
    background-color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    border-color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    transform 0.25s cubic-bezier(0.22, 1, 0.36, 1);
}

/* Hover 脑洞：竹简抽出金石回弹微颤抖 */
.writing-sidebar__chapter-row--compact-idle:hover,
.writing-sidebar__chapter-row:focus-visible {
  border-color: var(--md-outline);
  background-color: color-mix(in srgb, var(--md-secondary) 4%, var(--md-surface));
  box-shadow: 2px 2px 0px var(--md-outline);
  transform: translateX(4px);
  animation: stone-tremble 0.25s cubic-bezier(0.22, 1, 0.36, 1) both;
}

/* 选中章节签条 */
.writing-sidebar__chapter-row--compact-selected {
  border: 1.5px solid var(--md-secondary) !important;
  background-color: rgba(184, 60, 50, 0.04) !important;
  margin-left: -10px !important; /* 向左平移 10px，使其恰好压在竖红线上 */
  width: calc(100% + 14px) !important; /* 显式拓宽卡片（向左超出 10px，向右超出 4px），使其绝对宽于普通卡片 */
  padding-left: 18px !important; /* 增加左侧内边距，精确对齐文字内容与状态点 */
  box-shadow: 2px 2px 0px var(--md-secondary) !important;
  z-index: 10; /* 确保选中章节盖在连线上，显得更有层次 */
}

.writing-sidebar__chapter-row--compact-selected .writing-sidebar__chapter-title {
  font-family: var(--md-font-serif);
  color: var(--md-secondary) !important;
  font-weight: bold;
  letter-spacing: 0.03em;
}

.writing-sidebar__chapter-row--compact-selected .writing-sidebar__chapter-no {
  color: var(--md-secondary) !important;
}

/* 极致国风脑洞：在选中时在右下角轻微旋转渐显出朱砂阳刻方印 [ 閱 ] */
.writing-sidebar__chapter-row--compact-selected::after {
  content: '閱';
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%) rotate(-6deg);
  font-family: var(--md-font-serif);
  font-size: 11px;
  font-weight: bold;
  color: rgba(184, 60, 50, 0.82);
  border: 1.5px solid rgba(184, 60, 50, 0.82);
  padding: 1px 3px;
  line-height: 1;
  background-color: rgba(184, 60, 50, 0.05);
  animation: seal-stamp 0.35s cubic-bezier(0.22, 1, 0.36, 1) both;
  pointer-events: none;
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

/* 极致国风脑洞：小圆点改造为微型“金石印章方印”，融入古典中式传统色 */
.writing-sidebar__status-dot {
  width: 8px;
  height: 8px;
  border-radius: 0 !important; /* 方直印章 */
  background-color: var(--md-outline);
  display: inline-block;
  border: 1px solid transparent;
}

/* 已完成使用“竹青”中式绿 */
.writing-sidebar__status-dot.is-completed {
  background-color: #3f6c5d !important; /* 古典竹青 */
  border-color: #2b5043;
}

/* 进行中使用“朱砂”中式红，并加入水墨呼吸闪烁 */
.writing-sidebar__status-dot.is-progress {
  background-color: var(--md-secondary) !important; /* 古典朱砂 */
  border-color: #92221b;
  animation: dot-ink-pulse 1.4s ease-out infinite;
}

/* 失败使用“赤赭” */
.writing-sidebar__status-dot.is-failed {
  background-color: #b83c32 !important;
  border-color: #8c2820;
}

/* 黛灰兜底 */
.writing-sidebar__status-dot.is-idle {
  background-color: #5c6265 !important; /* 古典黛灰 */
  border-color: #43484a;
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
    filter: blur(2px);
  }
  100% {
    opacity: 1;
    transform: translateY(-50%) scale(1) rotate(-6deg);
    filter: blur(0);
  }
}

@keyframes dot-ink-pulse {
  0% {
    box-shadow: 0 0 0 0 rgba(184, 60, 50, 0.45);
  }
  100% {
    box-shadow: 0 0 0 7px rgba(184, 60, 50, 0);
  }
}

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
