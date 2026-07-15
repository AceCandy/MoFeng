<!-- AIMETA P=小说详情壳_详情页布局容器|R=详情页布局_导航|NR=不含具体内容|E=component:NovelDetailShell|X=internal|A=布局组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <div
    class="detail-shell"
    :class="{
      'detail-shell--embedded': isAdmin,
      'detail-shell--drawer-collapsed': !isSidebarOpen,
    }"
  >
    <header v-if="isAdmin" class="detail-shell__topbar">
      <div class="detail-shell__topbar-inner">
        <button
          type="button"
          class="detail-shell__drawer-toggle"
          :aria-expanded="isSidebarOpen"
          :aria-label="isSidebarOpen ? '收起蓝图导航' : '展开蓝图导航'"
          :title="isSidebarOpen ? '收起蓝图导航' : '展开蓝图导航'"
          aria-controls="novel-detail-blueprint-nav"
          @click="toggleSidebar"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
          <span class="sr-only">切换小说档案分区导航</span>
        </button>
        <button class="md-btn md-btn-outlined md-ripple detail-shell__back-button" @click="goBack">
          返回
        </button>
        <h2 class="detail-shell__title md-title-large truncate" style="color: var(--md-on-surface)">
          {{ formattedTitle }}
        </h2>
        <span v-if="isAdmin" class="detail-shell__mode-chip">管理只读</span>
        <button
          v-if="!isAdmin"
          class="md-btn md-btn-filled md-ripple detail-shell__write-button"
          @click="goToWritingDesk"
        >
          <span class="detail-shell__write-label-full">进入写作台</span>
          <span class="detail-shell__write-label-compact">写作台</span>
        </button>
      </div>
    </header>

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
    <transition
      enter-active-class="md-scale-enter-active"
      leave-active-class="md-scale-leave-active"
      enter-from-class="md-scale-enter-from"
      leave-to-class="md-scale-leave-to"
    >
      <div
        v-if="isAddChapterModalOpen && !isAdmin"
        class="md-dialog-overlay"
        @click.self="cancelNewChapter"
      >
        <div
          ref="addChapterDialogRef"
          class="md-dialog relative w-full max-w-lg mx-4"
          role="dialog"
          aria-modal="true"
          :aria-labelledby="addChapterDialogTitleId"
        >
          <div class="md-dialog-header">
            <h3 :id="addChapterDialogTitleId" class="md-dialog-title">新增章节大纲</h3>
          </div>
          <div class="md-dialog-content space-y-6">
            <div class="md-text-field">
              <label for="new-chapter-title" class="md-text-field-label"> 章节标题 </label>
              <input
                id="new-chapter-title"
                v-model="newChapterTitle"
                type="text"
                class="md-text-field-input"
                placeholder="例如：意外的相遇"
              />
            </div>
            <div class="md-text-field">
              <label for="new-chapter-summary" class="md-text-field-label"> 章节摘要 </label>
              <textarea
                id="new-chapter-summary"
                v-model="newChapterSummary"
                rows="4"
                class="md-textarea w-full"
                placeholder="简要描述本章发生的主要事件"
              ></textarea>
            </div>
          </div>
          <div class="md-dialog-actions">
            <button
              ref="addChapterCancelButtonRef"
              data-dialog-initial-focus
              type="button"
              class="md-btn md-btn-text md-ripple"
              @click="cancelNewChapter"
            >
              取消
            </button>
            <button type="button" class="md-btn md-btn-filled md-ripple" @click="saveNewChapter">
              保存
            </button>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent, onMounted, ref, type Component, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  useForeshadowingQuery,
  useNovelProjectQuery,
  useNovelSectionQuery,
  useUpdateBlueprintMutation,
} from '@/queries/novel'
import type {
  NovelProject,
  NovelSectionType,
  AllSectionType,
} from '@/api/novel'
import { desktopMin } from '@/constants/responsive'
import { useResponsiveViewport } from '@/composables/useResponsiveViewport'
import { resolveChapterNumberForEntry } from '@/utils/chapter'
import { globalAlert } from '@/composables/useAlert'
import { useDialogA11y } from '@/composables/useDialogA11y'
import BlueprintEditModal from '@/components/BlueprintEditModal.vue'
import ShellDrawerNav from '@/components/novel-detail/ShellDrawerNav.vue'
import OverviewStrip from '@/components/novel-detail/OverviewStrip.vue'
import '@/assets/blueprint.css'

interface Props {
  isAdmin?: boolean
}

type SectionKey = AllSectionType

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

const sections: Array<{ key: SectionKey; label: string }> = [
  { key: 'overview', label: '项目概览' },
  { key: 'world_setting', label: '世界设定' },
  { key: 'characters', label: '主要角色' },
  { key: 'relationships', label: '人物关系' },
  { key: 'chapter_outline', label: '章节大纲' },
  { key: 'emotion_curve', label: '情感曲线' },
  { key: 'foreshadowing', label: '伏笔管理' },
]

const sectionKeys = sections.map((section) => section.key)

const resolveInitialSection = (): SectionKey => {
  const rawSection = Array.isArray(route.query.section)
    ? route.query.section[0]
    : route.query.section
  return sectionKeys.includes(rawSection as SectionKey) ? (rawSection as SectionKey) : 'overview'
}

const initialSection = resolveInitialSection()

type AsyncSectionModule = { default: Component }

const sectionLoaders: Record<SectionKey, () => Promise<AsyncSectionModule>> = {
  overview: () => import('@/components/novel-detail/OverviewSection.vue'),
  world_setting: () => import('@/components/novel-detail/WorldSettingSection.vue'),
  characters: () => import('@/components/novel-detail/CharactersSection.vue'),
  relationships: () => import('@/components/novel-detail/RelationshipsSection.vue'),
  chapter_outline: () => import('@/components/novel-detail/ChapterOutlineSection.vue'),
  chapters: () => import('@/components/novel-detail/ChaptersSection.vue'),
  emotion_curve: () => import('@/components/novel-detail/EmotionCurveSection.vue'),
  foreshadowing: () => import('@/components/novel-detail/ForeshadowingSection.vue'),
}

const sectionComponents = Object.fromEntries(
  Object.entries(sectionLoaders).map(([key, loader]) => [key, defineAsyncComponent(loader)]),
) as Record<SectionKey, ReturnType<typeof defineAsyncComponent>>

const prefetchedSections = new Set<SectionKey>()
const prefetchInFlight = new Map<SectionKey, Promise<void>>()

const prefetchSectionComponent = (key: SectionKey) => {
  if (prefetchedSections.has(key)) {
    return
  }

  const existingRequest = prefetchInFlight.get(key)
  if (existingRequest) {
    return
  }

  const request = sectionLoaders[key]()
    .then(() => {
      prefetchedSections.add(key)
    })
    .catch(() => {
      // 预取失败不阻塞切换，点击分区后会自动重试。
    })
    .finally(() => {
      prefetchInFlight.delete(key)
    })

  prefetchInFlight.set(key, request)
}

const isNovelSectionKey = (section: SectionKey): section is NovelSectionType =>
  !['emotion_curve', 'foreshadowing'].includes(section)

const activeSection = ref<SectionKey>(initialSection)
const activeNovelSection = computed<NovelSectionType | null>(() =>
  isNovelSectionKey(activeSection.value) ? activeSection.value : null,
)
const overviewQuery = useNovelSectionQuery(() => projectId, 'overview', () => props.isAdmin)
const sectionQuery = useNovelSectionQuery(
  () => projectId,
  () => activeNovelSection.value,
  () => props.isAdmin,
)

// Modal state (user mode only)
const isModalOpen = ref(false)
const modalTitle = ref('')
const modalContent = ref<any>('')
const modalField = ref('')

// Add chapter modal state (user mode only)
const isAddChapterModalOpen = ref(false)
const addChapterDialogRef = ref<HTMLElement | null>(null)
const addChapterCancelButtonRef = ref<HTMLElement | null>(null)
const addChapterDialogTitleId = 'novel-detail-add-chapter-title'
const newChapterTitle = ref('')
const newChapterSummary = ref('')
const novel = computed<NovelProject | null>(() =>
  !props.isAdmin ? (projectQuery.data.value ?? null) : null,
)
const projectStatus = computed(() => {
  const total = novel.value?.blueprint?.chapter_outline?.length ?? 0
  const completed =
    novel.value?.chapters?.filter((chapter) => chapter.generation_status === 'successful').length ?? 0
  if (total > 0 && completed >= total) {
    return { label: '已完稿', tone: 'done' as const }
  }
  if (completed > 0) {
    return { label: '创作中', tone: 'active' as const }
  }
  return { label: '筹备中', tone: 'draft' as const }
})
const characterCount = computed(() => novel.value?.blueprint?.characters?.length ?? 0)
const chapterTotal = computed(() => novel.value?.blueprint?.chapter_outline?.length ?? 0)
const chapterCompleted = computed(
  () => novel.value?.chapters?.filter((chapter) => chapter.generation_status === 'successful').length ?? 0,
)
const currentChapterLabel = computed(() => {
  if (!chapterTotal.value) return '未开始'
  const nextChapterNumber = resolveChapterNumberForEntry({
    outlines: novel.value?.blueprint?.chapter_outline ?? [],
    chapters: novel.value?.chapters ?? [],
  })
  if (nextChapterNumber === null) return `已完成 ${chapterTotal.value} 章`
  const completed =
    novel.value?.chapters?.filter((chapter) => chapter.generation_status === 'successful').length ?? 0
  if (completed >= chapterTotal.value) return `已完成 ${chapterTotal.value} 章`
  return `第 ${nextChapterNumber} 章`
})
const foreshadowingOverview = computed(() => {
  const payload = foreshadowingQuery.data.value
  if (!payload) {
    return { overdue: 0, pending: 0, paidOff: 0 }
  }
  return {
    overdue: payload.overdue_count,
    pending: payload.planted_count,
    paidOff: payload.paid_off_count,
  }
})

const activeQuery = computed(() => (activeSection.value === 'overview' ? overviewQuery : sectionQuery))
const currentSectionResponse = computed(() => {
  if (!isNovelSectionKey(activeSection.value)) {
    return null
  }
  return activeSection.value === 'overview'
    ? overviewQuery.data.value
    : sectionQuery.data.value
})
const currentSectionData = computed(() => currentSectionResponse.value?.data ?? null)
const overviewData = computed(() => overviewQuery.data.value?.data ?? null)
const overviewMeta = computed(() => ({
  title: overviewData.value?.title || novel.value?.title || '加载中...',
  updated_at: overviewData.value?.updated_at || null,
}))

const formattedTitle = computed(() => {
  const title = overviewMeta.value.title || '加载中...'
  return title.startsWith('《') && title.endsWith('》') ? title : `《${title}》`
})

const componentContainerClass = computed(() => {
  const fillSections: SectionKey[] = ['chapters']
  return fillSections.includes(activeSection.value)
    ? 'flex-1 min-h-0 h-full flex flex-col overflow-hidden'
    : 'min-w-0'
})

const contentCardClass = computed(() => {
  // 所有蓝图分区共享同一装订外框，概览页不再使用特殊透明托盘。
  return 'detail-shell__content-surface--fill detail-shell__content-surface--classical overflow-y-auto overscroll-contain'
})

// 懒加载完整项目（仅在需要编辑时）
const ensureProjectLoaded = async () => {
  if (props.isAdmin || !projectId) return
  if (novel.value) return // 已加载
  await projectQuery.refetch()
}

const toggleSidebar = () => {
  isSidebarOpen.value = !isSidebarOpen.value
}

const closeSidebar = () => {
  isSidebarOpen.value = false
}

const loadSection = async (section: SectionKey, _force = false) => {
  if (!projectId) return

  if (!isNovelSectionKey(section)) {
    return
  }

  if (section === 'overview') {
    await overviewQuery.refetch()
    return
  }
  if (section === activeSection.value) {
    await sectionQuery.refetch()
  }
}

const reloadSection = (section: SectionKey, force = false) => {
  loadSection(section, force)
}

const switchSection = (section: SectionKey) => {
  activeSection.value = section
  prefetchSectionComponent(section)
  if (!isDesktopViewport.value) {
    closeSidebar()
  }
}

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

const currentComponent = computed(() => sectionComponents[activeSection.value])
const isSectionLoading = computed(() => {
  if (!isNovelSectionKey(activeSection.value)) {
    return false
  }
  return activeQuery.value.isLoading.value || activeQuery.value.isFetching.value
})
const currentError = computed(() => {
  if (!isNovelSectionKey(activeSection.value)) {
    return null
  }
  const error = activeQuery.value.error.value
  if (!error) {
    return null
  }
  return error instanceof Error ? error.message : String(error)
})

const componentProps = computed(() => {
  const data = currentSectionData.value
  const editable = !props.isAdmin

  switch (activeSection.value) {
    case 'overview':
      return {
        data: data || null,
        editable,
        characterCount: characterCount.value,
        chapterCount: chapterTotal.value,
      }
    case 'world_setting':
      return { data: data || null, editable }
    case 'characters':
      return { data: data || null, editable }
    case 'relationships':
      return { data: data || null, editable }
    case 'chapter_outline':
      return { outline: data?.chapter_outline || [], editable }
    case 'chapters':
      return {
        chapters: data?.chapters || [],
        chapterOutlines: novel.value?.blueprint?.chapter_outline || [],
        isAdmin: props.isAdmin,
      }
    default:
      return {}
  }
})

const handleSectionEdit = (payload: { field: string; title: string; value: any }) => {
  if (props.isAdmin) return
  modalField.value = payload.field
  modalTitle.value = payload.title
  modalContent.value = payload.value
  isModalOpen.value = true
}

const resolveSectionKey = (field: string): SectionKey => {
  if (field.startsWith('world_setting')) return 'world_setting'
  if (field.startsWith('characters')) return 'characters'
  if (field.startsWith('relationships')) return 'relationships'
  if (field.startsWith('chapter_outline')) return 'chapter_outline'
  return 'overview'
}

const handleSave = async (data: { field: string; content: any }) => {
  if (props.isAdmin) return
  await ensureProjectLoaded()
  const project = novel.value
  if (!project) return

  const { field, content } = data
  const payload: Record<string, any> = {}

  if (field.includes('.')) {
    const [parentField, childField] = field.split('.')
    payload[parentField] = {
      ...(project.blueprint?.[parentField as keyof typeof project.blueprint] as
        | Record<string, any>
        | undefined),
      [childField]: content,
    }
  } else {
    payload[field] = content
  }

  try {
    await updateBlueprintMutation.mutateAsync(payload)
    const sectionToReload = resolveSectionKey(field)
    await loadSection(sectionToReload, true)
    if (sectionToReload !== 'overview') {
      await loadSection('overview', true)
    }
    isModalOpen.value = false
  } catch (error) {
    console.error('保存变更失败:', error)
  }
}

const startAddChapter = async () => {
  if (props.isAdmin) return
  await ensureProjectLoaded()
  const outline = novel.value?.blueprint?.chapter_outline || []
  const nextNumber =
    outline.length > 0 ? Math.max(...outline.map((item: any) => item.chapter_number)) + 1 : 1
  newChapterTitle.value = `新章节 ${nextNumber}`
  newChapterSummary.value = ''
  isAddChapterModalOpen.value = true
}

const cancelNewChapter = () => {
  isAddChapterModalOpen.value = false
}

useDialogA11y({
  active: isAddChapterModalOpen,
  dialogRef: addChapterDialogRef,
  onClose: cancelNewChapter,
  initialFocusRef: addChapterCancelButtonRef,
})

const saveNewChapter = async () => {
  if (props.isAdmin) return
  await ensureProjectLoaded()
  const project = novel.value
  if (!project) return
  if (!newChapterTitle.value.trim()) {
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
      title: newChapterTitle.value,
      summary: newChapterSummary.value,
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

onMounted(async () => {
  prefetchSectionComponent(activeSection.value)
})

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

.detail-shell__topbar {
  position: sticky;
  top: 0;
  z-index: 40;
}

.detail-shell__topbar-inner {
  max-width: 1800px;
  width: 100%;
  min-height: var(--detail-shell-topbar-height);
  margin: 0 auto;
  padding: 0 1rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  box-sizing: border-box;
}

.detail-shell__title {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.detail-shell__back-button,
.detail-shell__write-button {
  flex: 0 0 auto;
  white-space: nowrap;
}

.detail-shell__write-label-compact {
  display: none;
}

.detail-shell__drawer-toggle {
  min-width: 44px;
  min-height: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--md-spacing-2);
  margin-right: var(--md-spacing-2);
  padding: 0 var(--md-spacing-3);
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-xs);
  background-color: var(--md-surface);
  color: var(--md-on-surface-variant);
  font-family: var(--md-font-family);
  cursor: pointer;
  transition:
    background-color var(--md-duration-short) var(--md-easing-standard),
    border-color var(--md-duration-short) var(--md-easing-standard),
    color var(--md-duration-short) var(--md-easing-standard);
}

.detail-shell__drawer-toggle:hover {
  border-color: color-mix(in srgb, var(--md-primary) 36%, var(--md-outline-variant));
  background-color: color-mix(in srgb, var(--md-primary-dark) 8%, var(--md-surface));
  color: var(--md-primary-dark);
}

.detail-shell__drawer-toggle:focus-visible {
  outline: 2px solid var(--md-primary);
  outline-offset: 2px;
}

.detail-shell--drawer-collapsed .detail-shell__drawer-toggle {
  border-color: transparent;
  background-color: var(--md-primary-container);
  color: var(--md-on-primary-container);
}

.detail-shell__drawer-toggle svg {
  width: 20px;
  height: 20px;
  flex: 0 0 auto;
}

.detail-shell__mode-chip {
  display: inline-flex;
  align-items: center;
  flex-shrink: 0;
  height: 1.75rem;
  padding: 0 0.625rem;
  border-radius: var(--md-radius-xs);
  background-color: color-mix(in srgb, var(--md-secondary-container) 78%, transparent);
  color: var(--md-on-secondary-container);
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  white-space: nowrap;
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

  .detail-shell__topbar-inner {
    padding-inline: var(--md-spacing-3);
    gap: var(--md-spacing-2);
  }

  .detail-shell__drawer-toggle {
    margin-right: 0;
    padding-inline: var(--md-spacing-2);
  }

  .detail-shell__back-button,
  .detail-shell__write-button {
    min-width: 58px;
    padding-inline: var(--md-spacing-3);
  }

  .detail-shell__write-label-full {
    display: none;
  }

  .detail-shell__write-label-compact {
    display: inline;
  }
}

/* Material 3 Transition Classes */
.md-scale-enter-active,
.md-scale-leave-active {
  transition:
    opacity 250ms cubic-bezier(0.2, 0, 0, 1),
    transform 250ms cubic-bezier(0.2, 0, 0, 1);
}

.md-scale-enter-from,
.md-scale-leave-to {
  opacity: 0;
  transform: scale(0.95);
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
