<!-- AIMETA P=写作台_章节编辑主页面|R=写作界面_章节管理|NR=不含详情展示|E=route:/novel/:id#component:WritingDesk|X=ui|A=写作台|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div class="writing-desk-page flex flex-col overflow-hidden">
    <!-- 主要内容区域 -->
    <section class="writing-desk-main" aria-label="写作台内容">
      <!-- 加载状态 -->
      <div v-if="projectLoading" class="h-full flex justify-center items-center">
        <div class="text-center">
          <div class="md-spinner mx-auto mb-4"><span></span></div>
          <p class="md-body-medium md-on-surface-variant">正在加载项目数据...</p>
        </div>
      </div>

      <!-- 错误状态 -->
      <div v-else-if="projectError" class="text-center py-20">
        <div
          class="md-card md-card-outlined p-8 max-w-md mx-auto"
          style="border-radius: var(--md-radius-xl)"
        >
          <div
            class="w-12 h-12 rounded-full mx-auto mb-4 flex items-center justify-center"
            style="background-color: var(--md-error-container)"
          >
            <svg
              class="w-6 h-6"
              style="color: var(--md-error)"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fill-rule="evenodd"
                d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
                clip-rule="evenodd"
              ></path>
            </svg>
          </div>
          <h3 class="md-title-large mb-2" style="color: var(--md-on-surface)">加载失败</h3>
          <p class="md-body-medium mb-4" style="color: var(--md-error)">{{ projectError }}</p>
          <button type="button" @click="loadProject" class="md-btn md-btn-tonal md-ripple">
            重新加载
          </button>
        </div>
      </div>

      <!-- 主要内容 -->
      <div v-else-if="project" class="writing-desk-layout-wrap">
        <div class="writing-desk-mobile-actions" v-if="useSidebarDrawer">
          <button
            v-if="useSidebarDrawer"
            type="button"
            class="md-btn md-btn-outlined md-ripple writing-desk-mobile-action"
            @click="toggleSidebarDrawer"
          >
            章节大纲
          </button>
        </div>

        <div
          class="writing-desk-layout"
          :class="{ 'writing-desk-layout--assistant-hidden': !useAssistantDrawer && !isAssistantPanelVisible }"
        >
          <div
            class="writing-desk-sidebar-shell"
            :class="{
              'is-drawer': useSidebarDrawer,
              'is-open': isSidebarDrawerOpen,
            }"
          >
            <WDSidebar
              :project="project"
              :selected-chapter-number="selectedChapterNumber"
              :generating-chapter="generatingChapter"
              :evaluating-chapter="activeEvaluatingChapter"
              :is-generating-outline="isGeneratingOutline"
              @open-project-detail="viewProjectDetail"
              @select-chapter="selectChapter"
              @generate-chapter="generateChapter"
              @edit-chapter="openEditChapterModal"
              @delete-chapter="deleteChapter"
              @generate-outline="generateOutline"
            />
          </div>

          <div class="writing-desk-workspace-shell">
            <WDWorkspace
              :project="project"
              :selected-chapter-number="selectedChapterNumber"
              :generating-chapter="generatingChapter"
              :evaluating-chapter="activeEvaluatingChapter"
              :show-version-selector="showVersionSelector"
              :chapter-generation-result="chapterGenerationResult"
              :selected-version-index="selectedVersionIndex"
              :available-versions="availableVersions"
              :is-selecting-version="isSelectingVersion"
              @regenerate-chapter="regenerateChapter"
              @evaluate-chapter="evaluateChapter"
              @hide-version-selector="hideVersionSelector"
              @update:selected-version-index="selectedVersionIndex = $event"
              @show-version-detail="showVersionDetail"
              @confirm-version-selection="confirmVersionSelection"
              @generate-chapter="generateChapter"
              @retry-from-node="retryFromNode"
              @select-chapter="selectChapter"
              @show-evaluation-detail="openEvaluationDetailModal"
              @fetch-chapter-status="fetchChapterStatus"
              @edit-chapter="editChapterContent"
            />

            <WDSealStamp :is-active="assistantToggleActive" @toggle="toggleAssistantVisibility" />
          </div>

          <div
            v-if="shouldRenderAssistantShell"
            class="writing-desk-assistant-shell"
            :class="{
              'is-drawer': useAssistantDrawer,
              'is-open': isAssistantDrawerOpen,
              'is-collapsed': !useAssistantDrawer && !isAssistantPanelVisible,
            }"
          >
            <WDAssistantPanel
              :project="project"
              :selected-chapter-number="selectedChapterNumber"
              :selected-chapter="selectedChapter"
              :selected-chapter-outline="selectedChapterOutline"
            />
          </div>
        </div>

        <button
          v-if="isDrawerBackdropVisible"
          type="button"
          class="writing-desk-drawer-backdrop"
          aria-label="关闭侧边面板"
          @click="closeAllDrawers"
        ></button>
      </div>
    </section>
    <WDVersionDetailModal
      :show="showVersionDetailModal"
      :detail-version-index="detailVersionIndex"
      :version="availableVersions[detailVersionIndex] ?? null"
      :is-current="isCurrentVersion(detailVersionIndex)"
      @close="closeVersionDetail"
      @select-version="selectVersionFromDetail"
    />
    <WDEvaluationDetailModal
      :show="showEvaluationDetailModal"
      :evaluation="selectedChapter?.evaluation || null"
      :is-optimizing-recommended-version="isOptimizingRecommendedVersion"
      @close="showEvaluationDetailModal = false"
      @optimize-recommended-version="optimizeRecommendedVersionFromEvaluation"
    />
    <WDRecommendedOptimizeResultModal
      :show="showRecommendedOptimizeResultModal"
      :optimized-content="recommendedOptimizedContent"
      :is-applying="isApplyingRecommendedOptimization"
      :notes="recommendedOptimizeResultNotes"
      @close="closeRecommendedOptimizeResult"
      @apply="applyRecommendedOptimization"
    />
    <WDEditChapterModal
      :show="showEditChapterModal"
      :chapter="editingChapter"
      @close="showEditChapterModal = false"
      @save="saveChapterChanges"
    />
    <WDGenerateOutlineModal
      :show="showGenerateOutlineModal"
      @close="showGenerateOutlineModal = false"
      @generate="handleGenerateOutline"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, defineAsyncComponent, watch } from 'vue'
import { useRoute } from 'vue-router'
import type {
  Chapter,
  ChapterOutline,
  ChapterGenerationResponse,
  ChapterVersion,
} from '@/api/novel'
import {
  useConfirmFinalizeChapterMutation,
  useNovelChapterQuery,
  useNovelMutationRefresh,
  useNovelProjectQuery,
} from '@/queries/novel'
import { globalAlert } from '@/composables/useAlert'
import { useWritingDeskDrawers } from '@/composables/useWritingDeskDrawers'
import { useWritingDeskChapterGeneration } from '@/composables/useWritingDeskChapterGeneration'
import { useWritingDeskChapterOps } from '@/composables/useWritingDeskChapterOps'
import { useWritingDeskChapterState } from '@/composables/useWritingDeskChapterState'
import { useWritingDeskModals } from '@/composables/useWritingDeskModals'
import { useWritingDeskOptimize } from '@/composables/useWritingDeskOptimize'
import { useWritingDeskProject } from '@/composables/useWritingDeskProject'
import { useWritingDeskVersionDetail } from '@/composables/useWritingDeskVersionDetail'
import { countNonWhitespaceChars } from '@/utils/text'
import {
  decodeJsonStringFragment,
  extractJsonField,
  formatChapterGenerationError,
  resolveChapterNumberForEntry,
  resolveChapterNumberForProjectEntry,
  tryParseOptimizerPayload,
} from '@/utils/chapter'
import WDSealStamp from '@/components/writing-desk/WDSealStamp.vue'
import WDSidebar from '@/components/writing-desk/WDSidebar.vue'
import WDWorkspace from '@/components/writing-desk/WDWorkspace.vue'

const loadWDVersionDetailModal = () => import('@/components/writing-desk/WDVersionDetailModal.vue')
const loadWDEvaluationDetailModal = () => import('@/components/writing-desk/WDEvaluationDetailModal.vue')
const loadWDEditChapterModal = () => import('@/components/writing-desk/WDEditChapterModal.vue')
const loadWDGenerateOutlineModal = () => import('@/components/writing-desk/WDGenerateOutlineModal.vue')
const loadWDAssistantPanel = () => import('@/components/writing-desk/WDAssistantPanel.vue')
const loadWDRecommendedOptimizeResultModal = () =>
  import('@/components/writing-desk/WDRecommendedOptimizeResultModal.vue')

const WDVersionDetailModal = defineAsyncComponent(loadWDVersionDetailModal)
const WDEvaluationDetailModal = defineAsyncComponent(loadWDEvaluationDetailModal)
const WDEditChapterModal = defineAsyncComponent(loadWDEditChapterModal)
const WDGenerateOutlineModal = defineAsyncComponent(loadWDGenerateOutlineModal)
const WDAssistantPanel = defineAsyncComponent(loadWDAssistantPanel)
const WDRecommendedOptimizeResultModal = defineAsyncComponent(loadWDRecommendedOptimizeResultModal)

interface Props {
  id: string
}

const props = defineProps<Props>()
const route = useRoute()
const projectQuery = useNovelProjectQuery(() => props.id)

// 状态管理
const selectedChapterNumber = ref<number | null>(null)
const resolvedProjectEntryId = ref<string | null>(null)
const chapterGenerationResult = ref<ChapterGenerationResponse | null>(null)
const selectedVersionIndex = ref<number>(0)
const generatingChapter = ref<number | null>(null)
const {
  isSidebarDrawerOpen,
  isAssistantDrawerOpen,
  isAssistantPanelVisible,
  useSidebarDrawer,
  useAssistantDrawer,
  assistantToggleActive,
  isDrawerBackdropVisible,
  closeAllDrawers,
  toggleSidebarDrawer,
  toggleAssistantVisibility,
} = useWritingDeskDrawers({
  loadAssistantPanel: loadWDAssistantPanel,
})

const chapterQuery = useNovelChapterQuery(() => props.id, selectedChapterNumber)
const { refreshProjectQueries, upsertChapterInProjectCache } = useNovelMutationRefresh(
  () => props.id,
)
const confirmFinalizeChapterMutation = useConfirmFinalizeChapterMutation(() => props.id)

// 计算属性
const project = computed(() => projectQuery.data.value ?? null)
const projectLoading = computed(() => projectQuery.isPending.value)
const projectError = computed(() => {
  const error = projectQuery.error.value
  return error instanceof Error ? error.message : error ? '加载项目失败' : null
})

const shouldRenderAssistantShell = computed(() => !!project.value)

const {
  goBack,
  viewProjectDetail,
  loadProject,
  refetchChapterIntoProject,
  stopChapterStatusStream,
  fetchChapterStatus,
  selectChapter,
} = useWritingDeskProject({
  projectId: () => props.id,
  project,
  projectQuery,
  chapterQuery,
  selectedChapterNumber,
  chapterGenerationResult,
  selectedVersionIndex,
  closeAllDrawers,
  upsertChapterInProjectCache,
  refreshProjectQueries,
})

const {
  showEvaluationDetailModal,
  showEditChapterModal,
  editingChapter,
  isGeneratingOutline,
  showGenerateOutlineModal,
  openEditChapterModal,
  openEvaluationDetailModal,
  saveChapterChanges,
  generateOutline,
  editChapterContent,
  handleGenerateOutline,
} = useWritingDeskModals({
  projectId: () => props.id,
  project,
  loadWDEditChapterModal,
  loadWDEvaluationDetailModal,
  loadWDGenerateOutlineModal,
})

const getQueryChapterNumber = () => {
  const rawChapterNumber = Array.isArray(route.query.chapter_number)
    ? route.query.chapter_number[0]
    : route.query.chapter_number
  const chapterNumber = Number(rawChapterNumber)
  return Number.isFinite(chapterNumber) && chapterNumber > 0 ? chapterNumber : null
}

// 写作台会在不同项目间复用组件，进入新项目时必须按当前项目重新定位章节。
watch(
  () => project.value,
  (newProject) => {
    if (!newProject) {
      selectedChapterNumber.value = null
      resolvedProjectEntryId.value = null
      return
    }

    const resolvedChapterNumber = resolveChapterNumberForProjectEntry({
      projectId: newProject.id,
      previousProjectId: resolvedProjectEntryId.value,
      currentChapterNumber: selectedChapterNumber.value,
      outlines: newProject.blueprint?.chapter_outline ?? [],
      chapters: newProject.chapters ?? [],
      preferredChapterNumber: getQueryChapterNumber(),
    })

    selectedChapterNumber.value = resolvedChapterNumber
    selectedVersionIndex.value = 0
    chapterGenerationResult.value = null
    resolvedProjectEntryId.value = newProject.id
  },
  { immediate: true },
)

watch(
  () => route.query.chapter_number,
  () => {
    if (!project.value) {
      return
    }
    const chapterNumber = getQueryChapterNumber()
    if (!chapterNumber) {
      return
    }
    const resolvedChapterNumber = resolveChapterNumberForEntry({
      outlines: project.value.blueprint?.chapter_outline ?? [],
      chapters: project.value.chapters ?? [],
      preferredChapterNumber: chapterNumber,
    })
    if (resolvedChapterNumber !== null) {
      selectChapter(resolvedChapterNumber)
    }
  },
)

watch(
  () => props.id,
  () => {
    stopChapterStatusStream()
  },
)

const {
  selectedChapter,
  showVersionSelector,
  evaluatingChapter,
  activeEvaluatingChapter,
  isSelectingVersion,
  selectedChapterOutline,
  latestCompletedChapterNumber,
} = useWritingDeskChapterState({
  project,
  selectedChapterNumber,
  chapterQuery,
  confirmFinalizeChapterMutation,
})

const progress = computed(() => {
  if (!project.value?.blueprint?.chapter_outline) return 0
  const totalChapters = project.value.blueprint.chapter_outline.length
  const completedChapters = project.value.chapters.filter((ch) => ch.content).length
  return Math.round((completedChapters / totalChapters) * 100)
})

const totalChapters = computed(() => {
  return project.value?.blueprint?.chapter_outline?.length || 0
})

const completedChapters = computed(() => {
  return project.value?.chapters?.filter((ch) => ch.content)?.length || 0
})

const {
  availableVersions,
  isCurrentVersion,
  resolveRecommendedVersionIndex,
  showVersionDetail,
  closeVersionDetail,
  hideVersionSelector,
  selectVersionFromDetail,
  showVersionDetailModal,
  detailVersionIndex,
} = useWritingDeskVersionDetail({
  selectedChapter,
  chapterGenerationResult,
  selectedVersionIndex,
  loadWDVersionDetailModal,
})

const {
  showRecommendedOptimizeResultModal,
  recommendedOptimizedContent,
  recommendedOptimizeResultNotes,
  isOptimizingRecommendedVersion,
  isApplyingRecommendedOptimization,
  closeRecommendedOptimizeResult,
  optimizeRecommendedVersionFromEvaluation,
  applyRecommendedOptimization,
} = useWritingDeskOptimize({
  projectId: () => props.id,
  project,
  selectedChapter,
  availableVersions,
  refetchChapterIntoProject,
  showEvaluationDetailModal,
})

const { generateChapter, retryFromNode, regenerateChapter } = useWritingDeskChapterGeneration({
  projectId: () => props.id,
  project,
  generatingChapter,
  selectedChapterNumber,
  chapterGenerationResult,
  selectedVersionIndex,
  upsertChapterInProjectCache,
  fetchChapterStatus,
  refetchChapterIntoProject,
})

const confirmVersionSelection = async (payload?: { editedContent?: string | null }) => {
  const targetChapterNumber = selectedChapterNumber.value
  if (targetChapterNumber === null) {
    return
  }

  if (!availableVersions.value?.[selectedVersionIndex.value]?.content) {
    const recommendedIndex = resolveRecommendedVersionIndex(
      selectedChapter.value,
      availableVersions.value,
    )
    if (recommendedIndex !== null) {
      selectedVersionIndex.value = recommendedIndex
    }
  }

  if (!availableVersions.value?.[selectedVersionIndex.value]?.content) {
    return
  }

  try {
    if (project.value?.chapters) {
      const chapter = project.value.chapters.find((ch) => ch.chapter_number === targetChapterNumber)
      if (chapter) {
        chapter.generation_status = 'finalizing'
        chapter.generation_step = 'confirm_finalize'
        chapter.generation_progress = 90
      }
    }

    await confirmFinalizeChapterMutation.mutateAsync({
      chapterNumber: targetChapterNumber,
      selectedVersionIndex: selectedVersionIndex.value,
      editedContent: payload?.editedContent ?? null,
    })
    await refetchChapterIntoProject(targetChapterNumber)
    chapterGenerationResult.value = null
    globalAlert.showSuccess('章节已定稿，后处理已完成', '定稿完成')
  } catch (error) {
    console.error('确认定稿失败:', error)
    if (project.value?.chapters) {
      const chapter = project.value.chapters.find((ch) => ch.chapter_number === targetChapterNumber)
      if (chapter) {
        chapter.generation_status = 'waiting_for_confirm'
      }
    }
    globalAlert.showError(
      `确认定稿失败: ${error instanceof Error ? error.message : '未知错误'}`,
      '定稿失败',
    )
  }
}

const { evaluateChapter, deleteChapter } = useWritingDeskChapterOps({
  projectId: () => props.id,
  project,
  selectedChapterNumber,
  evaluatingChapter,
  latestCompletedChapterNumber,
})

</script>

<style scoped>
.writing-desk-page {
  /* 极致国风脑洞与视口自适应布局：自适应减去顶部中控台导航栏高度（宽屏 92px，窄屏 72px），彻底消除浏览器最右侧全局滚动条溢出，实现满屏高自适应 */
  height: calc(var(--app-viewport-unit) - 92px);
  min-height: calc(640px - 92px);
  background-color: var(--md-surface-dim);
  color: var(--md-on-surface);
  font-family: var(--md-font-family);
  animation: m3-fade 0.6s ease-out both;
}

@media (max-width: 1199px) {
  .writing-desk-page {
    height: calc(var(--app-viewport-unit) - 72px);
    min-height: calc(640px - 72px);
  }
}

.writing-desk-main {
  flex: 1;
  min-height: 0;
  width: 100%;
  position: relative;
  padding: var(--md-spacing-5) clamp(var(--md-spacing-4), 2.4vw, var(--md-spacing-8))
    var(--md-spacing-6);
  overflow: hidden;
}

.writing-desk-layout-wrap {
  position: relative;
  height: 100%;
  min-height: 0;
}

.writing-desk-mobile-actions {
  display: none;
  align-items: center;
  gap: var(--md-spacing-2);
  margin-bottom: var(--md-spacing-3);
}

.writing-desk-mobile-action {
  min-height: 44px;
  padding: 0 14px;
  border-radius: var(--md-radius-sm);
  font-size: var(--md-label-medium);
}

.writing-desk-layout {
  display: grid;
  grid-template-columns: minmax(250px, 300px) minmax(0, 1fr) auto;
  align-items: stretch;
  gap: var(--md-spacing-4);
  height: 100%;
  min-height: 0;
  width: min(100%, 1720px);
  margin: 0 auto;
}

.writing-desk-layout--assistant-hidden {
  grid-template-columns: minmax(250px, 300px) minmax(0, 1fr) auto;
}

.writing-desk-sidebar-shell,
.writing-desk-workspace-shell {
  min-width: 0;
  min-height: 0;
  height: 100%;
}

.writing-desk-assistant-shell {
  min-width: 0;
  min-height: 0;
  height: 100%;
  width: 296px;
  opacity: 1;
  overflow: hidden !important; /* 强制在过渡中及日常中隐藏外部滚动条，防止闪跳 */
  will-change: width, opacity, margin-left; /* 开启 GPU 硬件加速，确保100%跑满帧率 */
  transition:
    width 0.45s cubic-bezier(0.16, 1, 0.3, 1),
    opacity 0.3s cubic-bezier(0.16, 1, 0.3, 1),
    margin-left 0.45s cubic-bezier(0.16, 1, 0.3, 1);
}

.writing-desk-assistant-shell > * {
  width: 296px;
  flex-shrink: 0;
}

.writing-desk-assistant-shell.is-collapsed {
  display: block !important;
  width: 0;
  opacity: 0;
  margin-left: -16px;
  pointer-events: none;
}

.writing-desk-drawer-backdrop {
  position: absolute;
  inset: 0;
  border: 0;
  background-color: var(--md-scrim-soft);
  z-index: 34;
}

@media (max-width: 1535px) {
  .writing-desk-layout {
    grid-template-columns: minmax(220px, 276px) minmax(0, 1fr) auto;
    width: 100%;
    max-width: none;
  }

  .writing-desk-layout--assistant-hidden {
    grid-template-columns: minmax(220px, 276px) minmax(0, 1fr) auto;
  }

  .writing-desk-assistant-shell {
    width: 260px;
  }

  .writing-desk-assistant-shell > * {
    width: 260px;
  }

  .writing-desk-assistant-shell.is-collapsed {
    width: 0;
    margin-left: -16px;
  }
}

@media (max-width: 1199px) {
  .writing-desk-mobile-actions {
    display: flex;
    justify-content: flex-end;
  }

  .writing-desk-layout {
    grid-template-columns: minmax(220px, 276px) minmax(0, 1fr);
    width: 100%;
    max-width: none;
  }

  .writing-desk-assistant-shell.is-drawer {
    position: absolute;
    top: 0;
    right: 0;
    bottom: 0;
    width: min(320px, calc(100vw - 56px));
    transform: translateX(110%);
    transition: transform var(--md-duration-medium) var(--md-easing-emphasized);
    z-index: 40;
    pointer-events: none;
  }

  .writing-desk-assistant-shell.is-drawer.is-open {
    transform: translateX(0);
    pointer-events: auto;
    box-shadow: var(--md-elevation-drawer-right);
  }
}

@media (prefers-reduced-motion: reduce) {
  .writing-desk-page {
    animation: none;
  }

  .writing-desk-sidebar-shell.is-drawer,
  .writing-desk-assistant-shell.is-drawer {
    transition: none;
  }
}

@media (max-width: 833px) {
  .writing-desk-page {
    height: auto;
    min-height: calc(var(--app-viewport-unit) - 104px);
  }

  .writing-desk-main {
    padding: var(--md-spacing-4);
    overflow: visible;
  }

  .writing-desk-mobile-actions {
    margin-bottom: var(--md-spacing-3);
    justify-content: flex-start;
    flex-wrap: wrap;
  }

  .writing-desk-layout {
    grid-template-columns: minmax(0, 1fr);
    gap: var(--md-spacing-4);
    height: auto;
    overflow: visible;
  }

  .writing-desk-workspace-shell {
    min-height: 560px;
  }

  .writing-desk-sidebar-shell.is-drawer,
  .writing-desk-assistant-shell.is-drawer {
    position: absolute;
    top: 0;
    bottom: 0;
    width: min(320px, calc(100vw - 56px));
    z-index: 40;
    pointer-events: none;
    transition: transform var(--md-duration-medium) var(--md-easing-emphasized);
  }

  .writing-desk-sidebar-shell.is-drawer {
    left: 0;
    transform: translateX(-110%);
  }

  .writing-desk-assistant-shell.is-drawer {
    right: 0;
    transform: translateX(110%);
  }

  .writing-desk-sidebar-shell.is-drawer.is-open,
  .writing-desk-assistant-shell.is-drawer.is-open {
    transform: translateX(0);
    pointer-events: auto;
  }

  .writing-desk-sidebar-shell.is-drawer.is-open {
    box-shadow: var(--md-elevation-drawer-left);
  }

  .writing-desk-assistant-shell.is-drawer.is-open {
    box-shadow: var(--md-elevation-drawer-right);
  }
}

/* 自定义样式 */
.line-clamp-1 {
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.line-clamp-3 {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 动画效果 */
@keyframes ink-backdrop-fade {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

/* ==========================================================================
   写作台辅助控制悬浮按钮 (案头宣纸盖印·引首闲章)
   ========================================================================== */
.writing-desk-workspace-shell {
  position: relative; /* 确保闲章相对于工作区容器定位 */
}

@keyframes m3-fade {
  from {
    opacity: 0;
    transform: translateY(18px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
