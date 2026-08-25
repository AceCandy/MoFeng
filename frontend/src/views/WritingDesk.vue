<!-- AIMETA P=写作台_章节编辑主页面|R=章节查询_工作流actor接线_弹窗协调|NR=不直接调用业务API|E=route:/novel/:id#component:WritingDesk|X=ui|A=写作台|D=vue|S=dom,state,cache|RD=./README.ai -->
<template>
  <div class="writing-desk-page flex flex-col overflow-hidden">
    <!-- 主要内容区域 -->
    <section class="writing-desk-main" aria-label="写作台内容">
      <WDProjectStatus
        v-if="projectLoading || projectError"
        :loading="projectLoading"
        :error="projectError"
        @retry="loadProject"
      />

      <!-- 主要内容 -->
      <div v-else-if="project" class="writing-desk-layout-wrap">
        <div class="writing-desk-mobile-actions" v-if="useSidebarDrawer">
          <button
            v-if="useSidebarDrawer"
            type="button"
            class="md-btn md-btn-outlined md-ripple writing-desk-mobile-action"
            :aria-expanded="isSidebarDrawerOpen"
            aria-controls="writing-desk-chapter-drawer"
            @click="toggleSidebarDrawer"
          >
            章节大纲
          </button>
        </div>

        <div
          class="writing-desk-layout"
          :class="{
            'writing-desk-layout--assistant-hidden':
              !useAssistantDrawer && !isAssistantPanelVisible,
          }"
        >
          <div
            id="writing-desk-chapter-drawer"
            class="writing-desk-sidebar-shell"
            :class="{
              'is-drawer': useSidebarDrawer,
              'is-open': isSidebarDrawerOpen,
            }"
            :aria-hidden="useSidebarDrawer && !isSidebarDrawerOpen ? 'true' : undefined"
            :inert="useSidebarDrawer && !isSidebarDrawerOpen"
          >
            <WDSidebar
              :project="project"
              :selected-chapter-number="selectedChapterNumber"
              :workflow-phase="workflowPhase"
              :is-generating-outline="isGeneratingOutline"
              @select-chapter="selectChapter"
              @delete-chapter="deleteChapter"
              @generate-outline="generateOutline"
            />
          </div>

          <div class="writing-desk-workspace-shell">
            <WDWorkspace
              :project="project"
              :selected-chapter="selectedChapter"
              :selected-chapter-number="selectedChapterNumber"
              :selected-version-index="selectedVersionIndex"
              :available-versions="availableVersions"
              :workflow-phase="workflowPhase"
              :workflow-run-id="workflowRunId"
              :workflow-node-key="workflowNodeKey"
              :workflow-progress="workflowProgress"
              :workflow-transport="workflowTransport"
              :workflow-allowed-commands="workflowAllowedCommands"
              :workflow-pending="workflowPending"
              :workflow-error="workflowError"
              :workflow-retry-activity-key="workflowRetryActivityKey"
              :workflow-candidates="workflowCandidates"
              :active-section="activeDeskSection"
              :assistant-open="assistantToggleActive"
              @workflow-start="startChapterWorkflow"
              @workflow-select-version="selectWorkflowVersion"
              @workflow-retry="retryChapterWorkflow"
              @workflow-retry-external="retryExternalChapterWorkflow"
              @workflow-retry-projection="retryProjectionChapterWorkflow"
              @workflow-cancel="cancelChapterWorkflow"
              @workflow-resync="resyncChapterWorkflow"
              @workflow-reset="resetSelectedChapterWorkflow"
              @workflow-delete="deleteSelectedBrokenChapter"
              @select-chapter="selectChapter"
              @show-version-detail="showVersionDetail"
              @show-evaluation-detail="openEvaluationDetailModal"
              @edit-chapter="editChapterContent"
              @update:active-section="handleDeskSectionChange"
              @toggle-assistant="toggleAssistantVisibility"
            />
          </div>

          <div
            v-if="shouldRenderAssistantShell"
            id="writing-desk-assistant-panel"
            class="writing-desk-assistant-shell"
            :class="{
              'is-drawer': useAssistantDrawer,
              'is-open': isAssistantDrawerOpen,
              'is-collapsed': !useAssistantDrawer && !isAssistantPanelVisible,
            }"
            :aria-hidden="useAssistantDrawer && !isAssistantDrawerOpen ? 'true' : undefined"
            :inert="useAssistantDrawer && !isAssistantDrawerOpen"
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
import type { Chapter, ChapterOutline, ChapterVersion } from '@/api/novel'
import type { WritingDeskSection } from '@/api/creationContexts'
import {
  useNovelChapterQuery,
  useNovelMutationRefresh,
  useNovelProjectQuery,
} from '@/queries/novel'
import { useChapterWorkflowActorPorts } from '@/queries/chapterWorkflow'
import { useChapterWorkflowActor } from '@/composables/useChapterWorkflowActor'
import { useWritingDeskDrawers } from '@/composables/useWritingDeskDrawers'
import { useWritingDeskChapterOps } from '@/composables/useWritingDeskChapterOps'
import { useWritingDeskChapterState } from '@/composables/useWritingDeskChapterState'
import { useWritingDeskModals } from '@/composables/useWritingDeskModals'
import { useWritingDeskNavigation } from '@/composables/useWritingDeskNavigation'
import { useWritingDeskOptimize } from '@/composables/useWritingDeskOptimize'
import { useWritingDeskProject } from '@/composables/useWritingDeskProject'
import { useWritingDeskVersionDetail } from '@/composables/useWritingDeskVersionDetail'
import {
  useCreationContextsQuery,
  usePatchCreationContextMutation,
} from '@/queries/creationContexts'
import WDProjectStatus from '@/components/writing-desk/WDProjectStatus.vue'
import WDSidebar from '@/components/writing-desk/WDSidebar.vue'
import WDWorkspace from '@/components/writing-desk/WDWorkspace.vue'

const loadWDVersionDetailModal = () => import('@/components/writing-desk/WDVersionDetailModal.vue')
const loadWDEvaluationDetailModal = () =>
  import('@/components/writing-desk/WDEvaluationDetailModal.vue')
const loadWDEditChapterModal = () => import('@/components/writing-desk/WDEditChapterModal.vue')
const loadWDGenerateOutlineModal = () =>
  import('@/components/writing-desk/WDGenerateOutlineModal.vue')
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
const projectQuery = useNovelProjectQuery(() => props.id)
const contextsQuery = useCreationContextsQuery()
const patchContextMutation = usePatchCreationContextMutation()
const activeDeskSection = ref<WritingDeskSection>('content')
const projectContext = computed(
  () => contextsQuery.data.value?.find((context) => context.project_id === props.id) ?? null,
)

// 状态管理
const selectedChapterNumber = ref<number | null>(null)
const selectedVersionIndex = ref<number>(0)
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

// 计算属性
const project = computed(() => projectQuery.data.value ?? null)
const projectLoading = computed(() => projectQuery.isPending.value)
const projectError = computed(() => {
  const error = projectQuery.error.value
  return error instanceof Error ? error.message : error ? '加载项目失败' : null
})

const shouldRenderAssistantShell = computed(() => !!project.value)

const {
  loadProject,
  refetchChapterIntoProject,
  selectChapter: selectChapterLocally,
} = useWritingDeskProject({
  projectId: () => props.id,
  project,
  projectQuery,
  chapterQuery,
  selectedChapterNumber,
  selectedVersionIndex,
  closeAllDrawers,
  upsertChapterInProjectCache,
  refreshProjectQueries,
})

const selectChapter = (chapterNumber: number) => {
  const context = projectContext.value
  selectChapterLocally(chapterNumber)
  if (context?.surface === 'writing' && context.chapter_number === chapterNumber) return
  void patchContextMutation
    .mutateAsync({
      projectId: props.id,
      patch: { surface: 'writing', chapter_number: chapterNumber },
    })
    .catch(() => undefined)
}

const {
  showEvaluationDetailModal,
  showEditChapterModal,
  editingChapter,
  isGeneratingOutline,
  showGenerateOutlineModal,
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

useWritingDeskNavigation({
  projectId: () => props.id,
  project,
  selectedChapterNumber,
  selectedVersionIndex,
  selectChapter,
  contextReady: () => !contextsQuery.isPending.value,
  preferredChapterNumber: () => projectContext.value?.chapter_number ?? null,
})

const handleDeskSectionChange = (section: WritingDeskSection) => {
  activeDeskSection.value = section
  void patchContextMutation
    .mutateAsync({
      projectId: props.id,
      patch: { surface: 'writing', desk_section: section },
    })
    .catch(() => undefined)
}

let restoredDeskSectionProjectId: string | null = null
watch(
  () => [
    project.value,
    selectedChapterNumber.value,
    contextsQuery.isPending.value,
    chapterQuery.isPending.value,
    chapterQuery.data.value,
  ] as const,
  ([currentProject, chapterNumber, contextsPending, chapterPending, chapterDetail]) => {
    if (!currentProject || chapterNumber === null || contextsPending || chapterPending) return
    const chapter =
      chapterDetail?.chapter_number === chapterNumber
        ? chapterDetail
        : currentProject.chapters?.find((item) => item.chapter_number === chapterNumber)
    const isProjectEntry = restoredDeskSectionProjectId !== currentProject.id
    const requestedSection = isProjectEntry
      ? (projectContext.value?.desk_section ?? 'content')
      : activeDeskSection.value
    const hasReadableContent = Boolean(chapter?.content?.trim() || chapter?.versions?.length)
    const canRestoreSection =
      requestedSection === 'content' ||
      (hasReadableContent &&
        (requestedSection === 'versions' || Boolean(chapter?.evaluation?.trim())))
    const nextSection = canRestoreSection ? requestedSection : 'content'
    if (nextSection !== requestedSection) {
      handleDeskSectionChange(nextSection)
    } else {
      activeDeskSection.value = nextSection
    }
    restoredDeskSectionProjectId = currentProject.id
  },
  { immediate: true, flush: 'post' },
)

const { selectedChapter, selectedChapterOutline, latestCompletedChapterNumber } =
  useWritingDeskChapterState({
  project,
  selectedChapterNumber,
  chapterQuery,
})

const {
  availableVersions,
  isCurrentVersion,
  showVersionDetail,
  closeVersionDetail,
  selectVersionFromDetail,
  showVersionDetailModal,
  detailVersionIndex,
} = useWritingDeskVersionDetail({
  selectedChapter,
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

const workflowPorts = useChapterWorkflowActorPorts()
const chapterWorkflow = useChapterWorkflowActor(
  () => props.id,
  selectedChapterNumber,
  workflowPorts,
)
const { deleteChapter, resetChapter, deleteBrokenChapter, recoveryPending } =
  useWritingDeskChapterOps({
  projectId: () => props.id,
  selectedChapterNumber,
  latestCompletedChapterNumber,
})
const workflowPhase = chapterWorkflow.phase
const workflowTransport = chapterWorkflow.transport
const workflowRunId = computed(() => chapterWorkflow.snapshot.value.context.runId)
const workflowNodeKey = computed(() => chapterWorkflow.snapshot.value.context.nodeKey)
const workflowProgress = computed(() => chapterWorkflow.snapshot.value.context.progress)
const workflowAllowedCommands = computed(
  () => chapterWorkflow.snapshot.value.context.allowedCommands,
)
const workflowPending = computed(
  () =>
    chapterWorkflow.snapshot.value.context.pendingCommandId !== null ||
    chapterWorkflow.resyncing.value ||
    recoveryPending.value,
)
const workflowError = computed(
  () =>
    chapterWorkflow.snapshot.value.context.lastContractError ??
    chapterWorkflow.snapshot.value.context.lastCommandError,
)
const workflowRetryActivityKey = computed(
  () => chapterWorkflow.snapshot.value.context.retryActivityKey,
)
const workflowCandidates = computed(() => {
  const runId = chapterWorkflow.snapshot.value.context.runId
  if (runId === null) return []
  return (selectedChapter.value?.version_selections ?? []).filter(
    (candidate) => candidate.workflow_run_id === runId,
  )
})

const startChapterWorkflow = () => {
  void chapterWorkflow.start({ flow_config: { preset: 'ultimate' } })
}

const selectWorkflowVersion = (versionId: number) => {
  void chapterWorkflow.submitCommand('select', { selected_version_id: versionId })
}

const retryChapterWorkflow = () => {
  void chapterWorkflow.submitCommand('retry')
}

const retryExternalChapterWorkflow = (activityKey: string) => {
  void chapterWorkflow.submitCommand('retry_external', {
    activity_key: activityKey,
    acknowledge_possible_duplicate: true,
  })
}

const retryProjectionChapterWorkflow = () => {
  void chapterWorkflow.submitCommand('retry_projection')
}

const cancelChapterWorkflow = () => {
  void chapterWorkflow.submitCommand('cancel')
}

const resyncChapterWorkflow = () => {
  void chapterWorkflow.resync()
}

const resetSelectedChapterWorkflow = async () => {
  const chapterNumber = selectedChapterNumber.value
  if (chapterNumber === null) return
  if (await resetChapter(chapterNumber)) {
    await chapterWorkflow.resync()
  }
}

const deleteSelectedBrokenChapter = async () => {
  const chapterNumber = selectedChapterNumber.value
  if (chapterNumber === null) return
  const chaptersByNumber = new Map(
    (project.value?.chapters ?? []).map((chapter) => [chapter.chapter_number, chapter]),
  )
  const deleteNumbers = [chapterNumber]
  const laterOutlineNumbers = (project.value?.blueprint?.chapter_outline ?? [])
    .map((outline) => outline.chapter_number)
    .filter((number) => number > chapterNumber)
    .sort((left, right) => left - right)
  for (const number of laterOutlineNumbers) {
    const chapter = chaptersByNumber.get(number)
    if (chapter && chapter.generation_status !== 'not_generated') break
    deleteNumbers.push(number)
  }
  await deleteBrokenChapter(chapterNumber, deleteNumbers)
}
</script>

<style scoped>
.writing-desk-page {
  /* 极致国风脑洞与视口自适应布局：自适应减去顶部中控台导航栏高度（宽屏 92px，窄屏 72px），彻底消除浏览器最右侧全局滚动条溢出，实现满屏高自适应 */
  height: calc(var(--app-viewport-unit) - 92px);
  min-height: calc(640px - 92px);
  /* 写作台以素骨为大底，中央稿纸使用更亮的熟宣阅读面 */
  background-color: var(--md-background);
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

/* 移动端「章节大纲」抽屉钮：暖纸页底上的安静款 outlined 钮 */
.writing-desk-mobile-action {
  min-height: 44px;
  padding: 0 14px;
  border-radius: var(--md-radius-sm);
  font-size: var(--md-label-medium);
  color: var(--md-on-surface);
  border-color: var(--md-outline-variant);
}

.writing-desk-mobile-action:hover:not(:disabled) {
  color: var(--md-on-surface);
  border-color: var(--md-outline);
  background-color: var(--md-state-layer-hover);
}

.writing-desk-mobile-action:active:not(:disabled) {
  background-color: var(--md-state-layer-pressed);
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
    box-shadow: var(--md-elevation-paper-2); /* 抽屉弹层纸影 */
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
    /* 覆盖模板上的 overflow-hidden 工具类：移动端页面必须能随文档流整体滚动，
       否则章节 scrollIntoView 会把整页内容推到视口上方裁成白屏 */
    overflow-x: clip;
    overflow-y: visible;
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
    bottom: auto;
    height: calc(var(--app-viewport-unit) - var(--app-topbar-height) - 88px);
    max-height: 680px;
    overflow: hidden;
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
    box-shadow: var(--md-elevation-paper-2); /* 抽屉弹层纸影 */
  }

  .writing-desk-assistant-shell.is-drawer.is-open {
    box-shadow: var(--md-elevation-paper-2); /* 抽屉弹层纸影 */
  }
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
