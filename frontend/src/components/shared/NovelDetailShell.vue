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
      :summary="overviewData?.one_sentence_summary"
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
      <div class="detail-shell__main">
        <div class="detail-shell__content-wrap">
          <div class="detail-shell__content-frame">
            <!-- Material 3 Card -->
            <section class="detail-shell__content-surface" :class="contentCardClass">
              <!-- Loading State -->
              <div
                v-if="isSectionLoading"
                class="flex flex-col items-center justify-center py-20 sm:py-28"
              >
                <div class="md-spinner"><span></span></div>
                <p class="mt-4 md-body-medium" style="color: var(--md-on-surface-variant)">
                  加载中...
                </p>
              </div>

              <!-- Error State -->
              <div
                v-else-if="currentError"
                class="flex flex-col items-center justify-center py-20 sm:py-28 space-y-4"
              >
                <div
                  class="w-16 h-16 rounded-xs border border-[var(--md-outline-variant)] flex items-center justify-center"
                  style="background-color: var(--md-error-container)"
                >
                  <svg
                    class="w-8 h-8"
                    style="color: var(--md-error-text)"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                    />
                  </svg>
                </div>
                <p class="md-body-large text-center" style="color: var(--md-on-surface)">
                  {{ currentError }}
                </p>
                <button
                  class="md-btn md-btn-filled md-ripple"
                  @click="reloadSection(activeSection, true)"
                >
                  重试
                </button>
              </div>

              <!-- Content -->
              <component
                v-else
                :is="currentComponent"
                v-bind="componentProps"
                :class="componentContainerClass"
                @edit="handleSectionEdit"
                @add="startAddChapter"
              />
            </section>
          </div>
        </div>
      </div>
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
    outline.length > 0 ? Math.max(...outline.map((item: any) => item.chapter_number)) + 1 : 1
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

/* 提至右上角的方正金石按钮 */
.detail-shell__action-btn {
  flex: 0 0 auto;
  border-radius: 2px !important;
  border: 1px solid var(--md-outline) !important;
  background-color: var(--md-primary) !important;
  color: var(--md-on-primary) !important;
  font-family: var(--md-font-serif);
  font-weight: 600;
  letter-spacing: 0.08em;
  padding: 0 16px;
  height: 36px;
  box-shadow: 2px 2px 0px rgba(28, 32, 34, 0.2);
  transition:
    background-color 0.2s cubic-bezier(0.2, 0, 0, 1),
    box-shadow 0.2s cubic-bezier(0.2, 0, 0, 1),
    transform 0.2s cubic-bezier(0.2, 0, 0, 1);
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.detail-shell__action-btn:hover {
  background-color: var(--md-primary-dark) !important;
  box-shadow: 3px 3px 0px rgba(184, 60, 50, 0.2) !important; /* 朱印深拓 */
  transform: translate(-1px, -1px);
}

.detail-shell__main {
  display: flex;
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  height: 100%;
  max-height: 100%;
  width: 100%;
  margin-left: 0;
  box-sizing: border-box;
  overflow: hidden;
}

.detail-shell__content-wrap {
  display: flex;
  flex: 1 1 auto;
  align-items: stretch;
  min-width: 0;
  min-height: 0;
  height: 100%;
  max-height: 100%;
  width: 100%;
  padding: 1rem;
  box-sizing: border-box;
  overflow: hidden;
}

.detail-shell__content-frame {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  min-width: 0;
  height: 100%;
  max-height: 100%;
  width: 100%;
}

.detail-shell__content-surface {
  flex: 1 1 auto;
  width: 100%;
  min-height: 0;
  height: 100%;
  max-height: 100%;
  display: flex;
  flex-direction: column;
  padding: var(--md-spacing-6);
  box-sizing: border-box;
  transition:
    background-color 0.25s cubic-bezier(0.2, 0, 0, 1),
    border-color 0.25s cubic-bezier(0.2, 0, 0, 1),
    box-shadow 0.25s cubic-bezier(0.2, 0, 0, 1);

  /* 水墨微晕极细滚动条美化，保持纯净宣纸质感并引导高品质滚动 */
  scrollbar-width: thin;
  scrollbar-color: rgba(60, 80, 70, 0.25) transparent;
}

.detail-shell__content-surface::-webkit-scrollbar {
  display: block !important;
  width: 4px;
}

.detail-shell__content-surface::-webkit-scrollbar-track {
  background: transparent;
}

.detail-shell__content-surface::-webkit-scrollbar-thumb {
  background-color: rgba(60, 80, 70, 0.2);
  border-radius: var(--md-radius-xs);
}

.detail-shell__content-surface::-webkit-scrollbar-thumb:hover {
  background-color: rgba(60, 80, 70, 0.45);
}

/* 其它设定分区的双线古籍装订框大卡片 */
.detail-shell__content-surface--classical {
  border: 3px double var(--md-outline) !important; /* 双线装订框 */
  border-radius: 4px !important; /* 方折风骨 */
  box-shadow: 2px 2px 0px rgba(28, 32, 34, 0.15) !important; /* 拓片硬投影 */
  background-color: var(--md-surface) !important; /* 熟宣 */
  /* 宣纸帘纹理 */
  background-image: repeating-linear-gradient(90deg, rgba(28, 32, 34, 0.005) 0px, rgba(28, 32, 34, 0.005) 1px, transparent 1px, transparent 32px);
}

.detail-shell__content-surface--fill {
  min-height: 0;
  height: 100%;
  max-height: 100%;
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

  .detail-shell__content-wrap {
    padding: var(--md-spacing-3) 2rem 1rem;
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

  .detail-shell__content-surface {
    padding: var(--md-spacing-5);
  }
}

@media (min-width: 834px) {
  .detail-shell__content-surface {
    padding: var(--md-spacing-6);
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
   统摄并修正蓝图内部所有子卡片的现代扁平圆角，升级为古风竹纸笺条与碑拓小卡片
   ========================================================================== */
.detail-shell__content-surface--classical :deep(.bg-\[var\(--md-surface\)\]) {
  border: 1.5px solid var(--md-outline-variant) !important;
  border-radius: 4px !important; /* 统一碑拓方直 */
  background-color: var(--md-surface-container-low) !important; /* 竹纸淡黄底，产生层叠景深 */
  box-shadow: 1px 1px 0px rgba(28, 32, 34, 0.08) !important;
}

/* 统一统摄深度子卡片的现代圆角，回归方正骨力 */
.detail-shell__content-surface--classical :deep(.rounded-2xl) {
  border-radius: 4px !important;
}
.detail-shell__content-surface--classical :deep(.rounded-xl) {
  border-radius: 2px !important;
}
.detail-shell__content-surface--classical :deep(.rounded-lg) {
  border-radius: 2px !important;
}
.detail-shell__content-surface--classical :deep(.shadow-sm) {
  box-shadow: 1px 1px 0px rgba(28, 32, 34, 0.08) !important;
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
