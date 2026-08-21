<!-- AIMETA P=小说详情壳_详情页布局容器|R=详情页布局_导航|NR=不含具体内容|E=component:NovelDetailShell|X=internal|A=布局组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <div
    class="detail-shell"
    :class="{
      'detail-shell--embedded': isAdmin,
      'detail-shell--drawer-collapsed': !isSidebarOpen,
    }"
  >
    <ShellTopbar
      v-if="isAdmin"
      :title="formattedTitle"
      :is-admin="isAdmin"
      :is-sidebar-open="isSidebarOpen"
      @toggle-sidebar="toggleSidebar"
      @back="goBack"
      @go-to-writing-desk="goToWritingDesk"
    />

    <OverviewStrip
      v-if="isAdmin"
      :title="formattedTitle"
      :summary="overviewSummary"
      :status="projectStatus"
      :current-chapter-label="currentChapterLabel"
      :updated-at="overviewMeta.updated_at"
      :character-count="characterCount"
      :chapter-completed="chapterCompleted"
      :chapter-total="chapterTotal"
      :foreshadowing-overdue="foreshadowingOverview.overdue"
    />

    <!-- Main Content -->
    <div class="detail-shell__body">
      <!-- Material 3 Navigation Drawer -->
      <ShellDrawerNav
        :sections="sections"
        :active-section="activeSection"
        :is-open="isSidebarOpen"
        :is-desktop="isDesktopViewport"
        @switch="switchSection"
        @prefetch="prefetchSectionComponent"
        @close="closeSidebar"
      />

      <!-- Main Content Area -->
      <ShellContent
        :current-component="currentComponent"
        :is-section-loading="isSectionLoading"
        :current-error="currentError"
        :component-props="componentProps"
        :content-card-class="contentCardClass"
        :component-container-class="componentContainerClass"
        @edit="handleSectionEdit"
        @add="startAddChapter"
        @retry="() => reloadSection(activeSection, true)"
      />
    </div>

    <!-- Blueprint Edit Modal -->
    <BlueprintEditModal
      v-if="!isAdmin"
      :show="isModalOpen"
      :title="modalTitle"
      :content="modalContent"
      :field="modalField"
      @close="isModalOpen = false"
      @save="handleSave"
    />

    <!-- Material 3 Add Chapter Modal -->
    <AddChapterDialog
      v-if="!isAdmin"
      :is-open="isAddChapterModalOpen"
      :initial-title="newChapterInitialTitle"
      @cancel="cancelNewChapter"
      @confirm="saveNewChapter"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  useForeshadowingQuery,
  useNovelProjectQuery,
  useUpdateBlueprintMutation,
} from '@/queries/novel'
import type { NovelProject } from '@/api/novel'
import { desktopMin } from '@/constants/responsive'
import { useResponsiveViewport } from '@/composables/useResponsiveViewport'
import { useShellSectionNavigation } from '@/composables/useShellSectionNavigation'
import { useShellBlueprintEdit } from '@/composables/useShellBlueprintEdit'
import { useShellOverview } from '@/composables/useShellOverview'
import { useShellSectionContent } from '@/composables/useShellSectionContent'
import { resolveChapterNumberForEntry } from '@/utils/chapter'
import { globalAlert } from '@/composables/useAlert'
import BlueprintEditModal from '@/components/BlueprintEditModal.vue'
import AddChapterDialog from '@/components/novel-detail/AddChapterDialog.vue'
import ShellDrawerNav from '@/components/novel-detail/ShellDrawerNav.vue'
import ShellTopbar from '@/components/novel-detail/ShellTopbar.vue'
import OverviewStrip from '@/components/novel-detail/OverviewStrip.vue'
import ShellContent from '@/components/novel-detail/ShellContent.vue'
import '@/assets/blueprint.css'

interface Props {
  isAdmin?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  isAdmin: false,
})

const route = useRoute()
const router = useRouter()

const projectId = route.params.id as string
const projectQuery = useNovelProjectQuery(() => (!props.isAdmin ? projectId : null))
const updateBlueprintMutation = useUpdateBlueprintMutation(() => projectId)
const foreshadowingQuery = useForeshadowingQuery(() => (!props.isAdmin ? projectId : null))
const viewport = useResponsiveViewport()
const isDesktopViewport = computed(() => viewport.width.value >= desktopMin)
const isSidebarOpen = ref(isDesktopViewport.value)

const toggleSidebar = () => {
  isSidebarOpen.value = !isSidebarOpen.value
}

const closeSidebar = () => {
  isSidebarOpen.value = false
}

const navigation = useShellSectionNavigation({
  projectId,
  isAdmin: () => props.isAdmin,
  // 非桌面态切换分区后收起侧栏（侧栏状态归父，composable 经回调知情不持有）
  onAfterSwitch: () => {
    if (!isDesktopViewport.value) {
      closeSidebar()
    }
  },
})
const {
  sections,
  activeSection,
  sectionComponents,
  isNovelSectionKey,
  overviewQuery,
  sectionQuery,
  switchSection,
  prefetchSectionComponent,
  loadSection,
  reloadSection,
} = navigation

// Add chapter modal state (user mode only)
const isAddChapterModalOpen = ref(false)
const newChapterInitialTitle = ref('')
const novel = computed<NovelProject | null>(() =>
  !props.isAdmin ? (projectQuery.data.value ?? null) : null,
)
const {
  projectStatus,
  characterCount,
  chapterTotal,
  chapterCompleted,
  currentChapterLabel,
  foreshadowingOverview,
  overviewData,
  overviewSummary,
  overviewMeta,
  formattedTitle,
} = useShellOverview({
  novel,
  foreshadowingQuery,
  overviewQuery,
})

const {
  currentComponent,
  isSectionLoading,
  currentError,
  componentProps,
  contentCardClass,
  componentContainerClass,
} = useShellSectionContent({
  navigation,
  novel,
  characterCount,
  chapterTotal,
  isAdmin: () => props.isAdmin,
})

// 懒加载完整项目（仅在需要编辑时）
const ensureProjectLoaded = async () => {
  if (props.isAdmin || !projectId) return
  if (novel.value) return // 已加载
  await projectQuery.refetch()
}

const { isModalOpen, modalTitle, modalContent, modalField, handleSectionEdit, handleSave } =
  useShellBlueprintEdit({
    isAdmin: () => props.isAdmin,
    novel,
    ensureProjectLoaded,
    updateBlueprintMutation,
    loadSection,
  })

const goBack = () => {
  if (props.isAdmin) {
    router.push({ name: 'admin', query: { tab: 'novels' } })
    return
  }
  router.push('/workspace')
}

const goToWritingDesk = async () => {
  await ensureProjectLoaded()
  const project = novel.value
  if (!project) return
  if (project.title === '未命名灵感') {
    router.push(`/inspiration?project_id=${project.id}`)
    return
  }
  const chapterNumber = resolveChapterNumberForEntry({
    outlines: project.blueprint?.chapter_outline ?? [],
    chapters: project.chapters ?? [],
  })
  router.push({
    name: 'project-write',
    params: { id: project.id },
    query: chapterNumber === null ? undefined : { chapter_number: String(chapterNumber) },
  })
}

const startAddChapter = async () => {
  if (props.isAdmin) return
  await ensureProjectLoaded()
  const outline = novel.value?.blueprint?.chapter_outline || []
  const nextNumber =
    outline.length > 0 ? Math.max(...outline.map((item) => item.chapter_number)) + 1 : 1
  newChapterInitialTitle.value = `新章节 ${nextNumber}`
  isAddChapterModalOpen.value = true
}

const cancelNewChapter = () => {
  isAddChapterModalOpen.value = false
}

const saveNewChapter = async (payload: { title: string; summary: string }) => {
  if (props.isAdmin) return
  await ensureProjectLoaded()
  const project = novel.value
  if (!project) return
  if (!payload.title.trim()) {
    globalAlert.showError('章节标题不能为空', '无法新增章节')
    return
  }

  const existingOutline = project.blueprint?.chapter_outline || []
  const nextNumber =
    existingOutline.length > 0 ? Math.max(...existingOutline.map((ch) => ch.chapter_number)) + 1 : 1
  const newOutline = [
    ...existingOutline,
    {
      chapter_number: nextNumber,
      title: payload.title,
      summary: payload.summary,
      goals: '',
    },
  ]

  try {
    await updateBlueprintMutation.mutateAsync({
      chapter_outline: newOutline,
    })
    await loadSection('chapter_outline', true)
    isAddChapterModalOpen.value = false
  } catch (error) {
    console.error('新增章节失败:', error)
  }
}

watch(
  () => isDesktopViewport.value,
  (isDesktop, wasDesktop) => {
    if (wasDesktop === undefined || isDesktop !== wasDesktop) {
      isSidebarOpen.value = isDesktop
    }
  },
  { immediate: true },
)

watch(
  () => route.fullPath,
  () => {
    if (!isDesktopViewport.value) {
      closeSidebar()
    }
  },
)
</script>

<style scoped>
.detail-shell {
  display: flex;
  flex-direction: column;
  min-width: 0;
  height: var(--app-viewport-unit);
  max-height: var(--app-viewport-unit);
  width: 100%;
  background-color: var(--md-surface-dim);
  overflow: hidden; /* 彻底断绝最外层全局大滚动条 */
  --detail-shell-topbar-height: 3.5rem;
  --detail-shell-overview-height: 8.75rem;
  --detail-shell-outer-gap: 1.5rem;
}

.detail-shell--embedded {
  position: relative;
  overflow: visible;
}

.detail-shell__body {
  position: relative;
  display: flex;
  flex: 1 1 auto;
  min-height: 0;
  height: calc(
    var(--app-viewport-unit) - var(--detail-shell-topbar-height) -
      var(--detail-shell-overview-height) - var(--detail-shell-outer-gap)
  );
  max-height: calc(
    var(--app-viewport-unit) - var(--detail-shell-topbar-height) -
      var(--detail-shell-overview-height) - var(--detail-shell-outer-gap)
  );
  width: 100%;
  max-width: 1800px;
  margin: 0 auto;
  overflow: hidden; /* 绝不产生全局溢出滚动 */
}

@media (min-width: 1200px) {
  .detail-shell--drawer-collapsed .detail-shell__drawer {
    flex-basis: 0;
    width: 0;
    opacity: 0;
    pointer-events: none;
    border-right-color: transparent;
    transform: translateX(-100%);
  }

  .detail-shell__body {
    height: calc(
      var(--app-viewport-unit) - var(--detail-shell-topbar-height) -
        var(--detail-shell-overview-height) - var(--detail-shell-outer-gap)
    );
    max-height: calc(
      var(--app-viewport-unit) - var(--detail-shell-topbar-height) -
        var(--detail-shell-overview-height) - var(--detail-shell-outer-gap)
    );
  }
}

@media (min-width: 1200px) and (max-height: 700px) {
  .detail-shell {
    --detail-shell-overview-height: 7.75rem;
    --detail-shell-outer-gap: 1rem;
  }
}

@media (max-width: 1199px) {
  .detail-shell {
    --detail-shell-overview-height: 12.5rem;
    --detail-shell-outer-gap: 1.5rem;
  }
}

@media (max-width: 833px) {
  .detail-shell {
    --detail-shell-overview-height: 11.75rem;
    --detail-shell-outer-gap: 1rem;
  }
}

/* ==========================================================================
   修正非管理员视图（作者蓝图工作区）在隐藏重复头部后的满屏高度占比
   ========================================================================== */
.detail-shell:not(.detail-shell--embedded) .detail-shell__body {
  height: 100% !important;
  max-height: 100% !important;
}

@media (min-width: 1200px) {
  .detail-shell:not(.detail-shell--embedded) .detail-shell__body {
    height: 100% !important;
    max-height: 100% !important;
  }
  .detail-shell:not(.detail-shell--embedded) .detail-shell__drawer {
    height: 100% !important;
    max-height: 100% !important;
  }
}
</style>
