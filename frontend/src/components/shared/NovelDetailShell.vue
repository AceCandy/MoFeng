<!-- AIMETA P=小说详情壳_详情页布局容器|R=详情页布局_导航|NR=不含具体内容|E=component:NovelDetailShell|X=internal|A=布局组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <div
    class="detail-shell"
    :class="{
      'detail-shell--embedded': isAdmin,
      'detail-shell--drawer-collapsed': !isSidebarOpen,
    }"
  >
    <!-- Material 3 Top App Bar -->
    <header class="md-top-app-bar detail-shell__topbar">
      <div class="detail-shell__topbar-inner">
        <!-- Leading: Blueprint navigation toggle -->
        <button
          type="button"
          class="detail-shell__drawer-toggle md-ripple"
          @click="toggleSidebar"
          :aria-label="isSidebarOpen ? '收起蓝图导航' : '展开蓝图导航'"
          aria-controls="novel-detail-blueprint-nav"
          :aria-expanded="isSidebarOpen"
          :title="isSidebarOpen ? '收起蓝图导航' : '展开蓝图导航'"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>

        <!-- Title -->
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 min-w-0">
            <h1 class="md-title-large truncate" style="color: var(--md-on-surface)">
              {{ formattedTitle }}
            </h1>
            <span v-if="isAdmin" class="detail-shell__mode-chip">管理只读</span>
          </div>
          <p
            v-if="overviewMeta.updated_at"
            class="md-body-small"
            style="color: var(--md-on-surface-variant)"
          >
            最近更新：{{ formatDateTime(overviewMeta.updated_at) }}
          </p>
        </div>

        <!-- Trailing: Actions -->
        <div class="flex items-center gap-2 flex-shrink-0">
          <button class="md-btn md-btn-outlined md-ripple" @click="goBack">
            <svg
              class="w-5 h-5 hidden sm:block"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M10 19l-7-7m0 0l7-7m-7 7h18"
              />
            </svg>
            <span class="hidden sm:inline">返回列表</span>
            <span class="sm:hidden">返回</span>
          </button>
          <button v-if="!isAdmin" class="md-btn md-btn-filled md-ripple" @click="goToWritingDesk">
            <svg
              class="w-5 h-5"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"
              />
            </svg>
            <span class="hidden sm:inline">开始创作</span>
            <span class="sm:hidden">创作</span>
          </button>
        </div>
      </div>
    </header>

    <section v-if="!isAdmin" class="detail-shell__overview-strip" aria-label="小说宇宙总览">
      <article class="detail-shell__overview-main">
        <p class="detail-shell__kicker">小说宇宙总览</p>
        <h2>{{ formattedTitle }}</h2>
        <p>
          你可以在这里统一查看世界观、角色关系、章节推进与伏笔状态，再进入正文写作台。
        </p>
        <div class="detail-shell__status-line">
          <span :class="['detail-shell__status-pill', `is-${projectStatus.tone}`]">
            {{ projectStatus.label }}
          </span>
          <span class="detail-shell__status-meta">
            {{ chapterCompleted }}/{{ chapterTotal }} 章已完成
          </span>
        </div>
      </article>

      <div class="detail-shell__overview-metrics">
        <article class="detail-shell__metric">
          <p>角色数量</p>
          <strong>{{ characterCount }}</strong>
          <span>主要角色卡</span>
        </article>
        <article class="detail-shell__metric">
          <p>当前章节</p>
          <strong>{{ currentChapterLabel }}</strong>
          <span>下一步创作焦点</span>
        </article>
        <article class="detail-shell__metric">
          <p>伏笔提醒</p>
          <strong>{{ foreshadowingOverview.overdue }}</strong>
          <span>待回收 · {{ foreshadowingOverview.pending }}</span>
        </article>
      </div>
    </section>

    <!-- Main Content -->
    <div class="detail-shell__body">
      <!-- Material 3 Navigation Drawer -->
      <aside
        id="novel-detail-blueprint-nav"
        class="detail-shell__drawer"
        :class="{ 'is-open': isSidebarOpen }"
        :aria-hidden="!isSidebarOpen ? 'true' : undefined"
        :inert="!isSidebarOpen"
      >
        <!-- Navigation Items -->
        <nav class="detail-shell__nav" aria-label="小说档案分区">
          <button
            v-for="section in sections"
            :key="section.key"
            type="button"
            @click="switchSection(section.key)"
            @mouseenter="prefetchSectionComponent(section.key)"
            @focus="prefetchSectionComponent(section.key)"
            @touchstart.passive="prefetchSectionComponent(section.key)"
            class="detail-shell__nav-item md-ripple"
            :class="{ 'is-active': activeSection === section.key }"
            :aria-current="activeSection === section.key ? 'page' : undefined"
          >
            <span class="detail-shell__nav-icon" aria-hidden="true">
              <component :is="getSectionIcon(section.key)" class="w-5 h-5" />
            </span>
            <span class="detail-shell__nav-label">{{ section.label }}</span>
          </button>
        </nav>
      </aside>

      <!-- Sidebar Overlay (Mobile) -->
      <transition
        enter-active-class="transition-opacity duration-300"
        leave-active-class="transition-opacity duration-300"
        enter-from-class="opacity-0"
        leave-to-class="opacity-0"
      >
        <div
          v-if="isSidebarOpen && !isDesktopViewport"
          class="detail-shell__drawer-backdrop"
          style="background-color: var(--md-scrim)"
          @click="closeSidebar"
        ></div>
      </transition>

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
                <div class="md-spinner"></div>
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
                  class="w-16 h-16 rounded-full flex items-center justify-center"
                  style="background-color: var(--md-error-container)"
                >
                  <svg
                    class="w-8 h-8"
                    style="color: var(--md-error)"
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
import { computed, defineAsyncComponent, onMounted, ref, h, type Component, watch } from 'vue'
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
import { formatDateTime } from '@/utils/date'
import { globalAlert } from '@/composables/useAlert'
import { useDialogA11y } from '@/composables/useDialogA11y'
import BlueprintEditModal from '@/components/BlueprintEditModal.vue'

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
  { key: 'chapters', label: '章节内容' },
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

// Section icons as functional components
const getSectionIcon = (key: SectionKey) => {
  const icons: Record<SectionKey, any> = {
    overview: () =>
      h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2 }, [
        h('rect', { x: 3, y: 3, width: 18, height: 18, rx: 2 }),
        h('line', { x1: 3, y1: 9, x2: 21, y2: 9 }),
        h('line', { x1: 9, y1: 21, x2: 9, y2: 9 }),
      ]),
    world_setting: () =>
      h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2 }, [
        h('circle', { cx: 12, cy: 12, r: 10 }),
        h('path', {
          d: 'M2 12h20M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z',
        }),
      ]),
    characters: () =>
      h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2 }, [
        h('path', { d: 'M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2' }),
        h('circle', { cx: 9, cy: 7, r: 4 }),
        h('path', { d: 'M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75' }),
      ]),
    relationships: () =>
      h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2 }, [
        h('path', { d: 'M16 21v-2a4 4 0 00-4-4H6a4 4 0 00-4 4v2' }),
        h('circle', { cx: 9, cy: 7, r: 4 }),
        h('path', { d: 'M22 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75' }),
      ]),
    chapter_outline: () =>
      h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2 }, [
        h('line', { x1: 8, y1: 6, x2: 21, y2: 6 }),
        h('line', { x1: 8, y1: 12, x2: 21, y2: 12 }),
        h('line', { x1: 8, y1: 18, x2: 21, y2: 18 }),
        h('line', { x1: 3, y1: 6, x2: 3.01, y2: 6 }),
        h('line', { x1: 3, y1: 12, x2: 3.01, y2: 12 }),
        h('line', { x1: 3, y1: 18, x2: 3.01, y2: 18 }),
      ]),
    chapters: () =>
      h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2 }, [
        h('path', { d: 'M4 19.5A2.5 2.5 0 016.5 17H20' }),
        h('path', { d: 'M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z' }),
      ]),
    emotion_curve: () =>
      h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2 }, [
        h('path', {
          d: 'M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z',
        }),
      ]),
    foreshadowing: () =>
      h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2 }, [
        h('path', { d: 'M13 10V3L4 14h7v7l9-11h-7z' }),
      ]),
  }
  return icons[key]
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
  const outlines = novel.value?.blueprint?.chapter_outline ?? []
  const nextChapter = outlines.find((outline) => {
    const chapter = novel.value?.chapters?.find((item) => item.chapter_number === outline.chapter_number)
    return chapter?.generation_status !== 'successful'
  })
  if (!nextChapter) return `已完成 ${chapterTotal.value} 章`
  return `第 ${nextChapter.chapter_number} 章`
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
  const fillSections: SectionKey[] = ['chapters']
  return fillSections.includes(activeSection.value)
    ? 'detail-shell__content-surface--fill overflow-hidden'
    : 'overflow-visible'
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
  const path =
    project.title === '未命名灵感'
      ? `/inspiration?project_id=${project.id}`
      : `/projects/${project.id}/write`
  router.push(path)
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
      return { data: data || null, editable }
    case 'world_setting':
      return { data: data || null, editable }
    case 'characters':
      return { data: data || null, editable }
    case 'relationships':
      return { data: data || null, editable }
    case 'chapter_outline':
      return { outline: data?.chapter_outline || [], editable }
    case 'chapters':
      return { chapters: data?.chapters || [], isAdmin: props.isAdmin }
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
  min-height: var(--app-viewport-unit);
  width: 100%;
  background-color: var(--md-surface-dim);
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
  min-height: 4rem;
  margin: 0 auto;
  padding: 0 1rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  box-sizing: border-box;
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
  border-radius: var(--md-radius-full);
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
  border-radius: 9999px;
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
  flex: 1 0 auto;
  min-height: calc(100vh - 4rem);
  min-height: calc(var(--app-viewport-unit) - 4rem);
  width: 100%;
  max-width: 1800px;
  margin: 0 auto;
  overflow: visible;
}

.detail-shell__overview-strip {
  max-width: 1800px;
  width: 100%;
  margin: 0 auto;
  padding: 1rem 1rem 0;
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(280px, 0.8fr);
  gap: var(--md-spacing-4);
}

.detail-shell__overview-main,
.detail-shell__overview-metrics {
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-xl);
  background-color: color-mix(in srgb, var(--md-surface) 95%, transparent);
  box-shadow: var(--md-elevation-1);
}

.detail-shell__overview-main {
  padding: clamp(var(--md-spacing-4), 3vw, var(--md-spacing-6));
}

.detail-shell__kicker {
  margin: 0;
  color: var(--md-primary-dark);
  font-size: var(--md-label-medium);
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.detail-shell__overview-main h2 {
  margin: var(--md-spacing-2) 0 0;
  font-size: clamp(1.25rem, 2vw, 1.75rem);
  color: var(--md-on-surface);
}

.detail-shell__overview-main p {
  margin: var(--md-spacing-3) 0 0;
  color: var(--md-on-surface-variant);
  line-height: 1.7;
}

.detail-shell__status-line {
  margin-top: var(--md-spacing-4);
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--md-spacing-2);
}

.detail-shell__status-pill {
  display: inline-flex;
  align-items: center;
  height: 30px;
  padding: 0 12px;
  border-radius: var(--md-radius-full);
  font-size: var(--md-label-medium);
  font-weight: 700;
}

.detail-shell__status-pill.is-active {
  background-color: var(--md-primary-container);
  color: var(--md-on-primary-container);
}

.detail-shell__status-pill.is-done {
  background-color: var(--md-success-container);
  color: var(--md-on-success-container);
}

.detail-shell__status-pill.is-draft {
  background-color: var(--md-surface-container);
  color: var(--md-on-surface-variant);
}

.detail-shell__status-meta {
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
}

.detail-shell__overview-metrics {
  padding: var(--md-spacing-4);
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--md-spacing-3);
}

.detail-shell__metric {
  padding: var(--md-spacing-3);
  border-radius: var(--md-radius-md);
  border: 1px solid var(--md-outline-variant);
  background-color: var(--md-surface-container-low);
}

.detail-shell__metric p,
.detail-shell__metric span {
  margin: 0;
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
}

.detail-shell__metric strong {
  margin: var(--md-spacing-2) 0 4px;
  display: block;
  color: var(--md-on-surface);
  font-size: var(--md-title-medium);
}

.detail-shell__drawer {
  position: fixed;
  left: 0;
  top: 4rem;
  bottom: 0;
  z-index: 30;
  width: 16.25rem;
  overflow: hidden;
  background-color: var(--md-surface);
  border-right: 1px solid var(--md-outline-variant);
  transform: translateX(-100%);
  transition:
    flex-basis 300ms cubic-bezier(0.2, 0, 0, 1),
    width 300ms cubic-bezier(0.2, 0, 0, 1),
    transform 300ms cubic-bezier(0.2, 0, 0, 1),
    opacity 200ms cubic-bezier(0.2, 0, 0, 1),
    border-color 200ms cubic-bezier(0.2, 0, 0, 1),
    box-shadow 300ms cubic-bezier(0.2, 0, 0, 1);
  will-change: transform;
}

.detail-shell__drawer.is-open {
  transform: translateX(0);
}

.detail-shell__drawer-backdrop {
  position: fixed;
  inset: 0;
  z-index: 20;
}

.detail-shell__nav {
  height: 100%;
  padding: var(--md-spacing-3);
  overflow-y: auto;
}

.detail-shell__nav-item {
  width: 100%;
  min-height: 3.25rem;
  display: flex;
  align-items: center;
  gap: var(--md-spacing-3);
  padding: var(--md-spacing-3);
  border: 1px solid transparent;
  border-radius: var(--md-radius-lg);
  background-color: transparent;
  color: var(--md-on-surface);
  text-align: left;
  cursor: pointer;
  transition:
    background-color var(--md-duration-short) var(--md-easing-standard),
    border-color var(--md-duration-short) var(--md-easing-standard),
    color var(--md-duration-short) var(--md-easing-standard);
}

.detail-shell__nav-item + .detail-shell__nav-item {
  margin-top: var(--md-spacing-1);
}

.detail-shell__nav-item:hover {
  background-color: var(--md-surface-container-low);
}

.detail-shell__nav-item:focus-visible {
  outline: 2px solid var(--md-primary);
  outline-offset: 2px;
}

.detail-shell__nav-item.is-active {
  border-color: color-mix(in srgb, var(--md-primary) 24%, var(--md-outline-variant));
  background-color: var(--md-primary-container);
}

.detail-shell__nav-icon {
  width: 2.5rem;
  height: 2.5rem;
  flex: 0 0 auto;
  display: grid;
  place-items: center;
  border-radius: var(--md-radius-full);
  background-color: var(--md-surface-container);
  color: var(--md-on-surface-variant);
  transition:
    background-color var(--md-duration-short) var(--md-easing-standard),
    color var(--md-duration-short) var(--md-easing-standard);
}

.detail-shell__nav-item.is-active .detail-shell__nav-icon {
  background-color: var(--md-surface);
  color: var(--md-primary-dark);
}

.detail-shell__nav-label {
  flex: 1 1 auto;
  min-width: 0;
  color: var(--md-on-surface);
  font-size: var(--md-label-large);
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.detail-shell__main {
  display: flex;
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
  width: 100%;
  margin-left: 0;
  box-sizing: border-box;
}

.detail-shell__content-wrap {
  display: flex;
  flex: 1 1 auto;
  align-items: flex-start;
  min-width: 0;
  min-height: 0;
  width: 100%;
  padding: 1rem;
  box-sizing: border-box;
  overflow: visible;
}

.detail-shell__content-frame {
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  min-width: 0;
  width: 100%;
}

.detail-shell__content-surface {
  flex: 1 1 auto;
  width: 100%;
  min-height: 20rem;
  height: auto;
  display: flex;
  flex-direction: column;
  padding: var(--md-spacing-6);
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-lg);
  background-color: var(--md-surface);
  box-sizing: border-box;
}

.detail-shell__content-surface--fill {
  min-height: 0;
  height: calc(100vh - 6rem);
  height: calc(var(--app-viewport-unit) - 6rem);
  max-height: calc(100vh - 6rem);
  max-height: calc(var(--app-viewport-unit) - 6rem);
}

@media (min-width: 1200px) {
  .detail-shell__drawer {
    position: sticky;
    top: 4rem;
    bottom: auto;
    flex: 0 0 16.25rem;
    height: calc(var(--app-viewport-unit) - 4rem);
    max-height: calc(var(--app-viewport-unit) - 4rem);
    transform: translateX(0);
  }

  .detail-shell--drawer-collapsed .detail-shell__drawer {
    flex-basis: 0;
    width: 0;
    opacity: 0;
    pointer-events: none;
    border-right-color: transparent;
    transform: translateX(-100%);
  }

  .detail-shell__content-wrap {
    padding: 1.5rem 2rem 2rem;
  }

  .detail-shell__content-surface--fill {
    height: calc(100vh - 7.5rem);
    height: calc(var(--app-viewport-unit) - 7.5rem);
    max-height: calc(100vh - 7.5rem);
    max-height: calc(var(--app-viewport-unit) - 7.5rem);
  }
}

@media (min-width: 834px) {
  .detail-shell__content-surface {
    padding: var(--md-spacing-8);
  }
}

@media (max-width: 1199px) {
  .detail-shell__overview-strip {
    grid-template-columns: minmax(0, 1fr);
    padding: var(--md-spacing-4) var(--md-spacing-4) 0;
  }

  .detail-shell__overview-metrics {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 833px) {
  .detail-shell__overview-metrics {
    grid-template-columns: minmax(0, 1fr);
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

</style>
