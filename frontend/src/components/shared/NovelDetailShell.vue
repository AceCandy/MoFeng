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
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
          >
            <path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
          <span class="detail-shell__drawer-toggle-text">蓝图导航</span>
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
        <!-- Drawer Header -->
        <div
          class="flex items-center gap-3 px-6 py-4"
          style="border-bottom: 1px solid var(--md-outline-variant)"
        >
          <div
            class="w-10 h-10 rounded-full flex items-center justify-center"
            style="background-color: var(--md-primary-container)"
          >
            <svg
              class="w-5 h-5"
              style="color: var(--md-on-primary-container)"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
              />
            </svg>
          </div>
          <span class="md-title-medium" style="color: var(--md-on-surface)">
            {{ isAdmin ? '内容视图' : '蓝图导航' }}
          </span>
        </div>

        <!-- Navigation Items -->
        <nav class="detail-shell__nav" aria-label="小说档案分区">
          <button
            v-for="section in sections"
            :key="section.key"
            type="button"
            @click="switchSection(section.key)"
            class="detail-shell__nav-item md-ripple"
            :class="{ 'is-active': activeSection === section.key }"
            :aria-current="activeSection === section.key ? 'page' : undefined"
          >
            <span class="detail-shell__nav-icon" aria-hidden="true">
              <component :is="getSectionIcon(section.key)" class="w-5 h-5" />
            </span>
            <span class="detail-shell__nav-copy">
              <span class="block md-label-large">{{ section.label }}</span>
              <span class="md-body-small" style="color: var(--md-on-surface-variant)">{{
                section.description
              }}</span>
            </span>
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
          style="background-color: rgba(0, 0, 0, 0.32)"
          @click="closeSidebar"
        ></div>
      </transition>

      <!-- Main Content Area -->
      <div class="detail-shell__main">
        <div
          class="detail-shell__content-wrap"
        >
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
      <div v-if="isAddChapterModalOpen && !isAdmin" class="md-dialog-overlay">
        <div class="absolute inset-0" @click="cancelNewChapter"></div>
        <div class="md-dialog relative w-full max-w-lg mx-4" @click.stop>
          <div class="md-dialog-header">
            <h3 class="md-dialog-title">新增章节大纲</h3>
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
            <button type="button" class="md-btn md-btn-text md-ripple" @click="cancelNewChapter">
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
import { computed, onBeforeUnmount, onMounted, reactive, ref, h } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useNovelStore } from '@/stores/novel'
import { NovelAPI } from '@/api/novel'
import { AdminAPI } from '@/api/admin'
import type {
  NovelProject,
  NovelSectionResponse,
  NovelSectionType,
  AllSectionType,
} from '@/api/novel'
import { formatDateTime } from '@/utils/date'
import { globalAlert } from '@/composables/useAlert'
import BlueprintEditModal from '@/components/BlueprintEditModal.vue'
import OverviewSection from '@/components/novel-detail/OverviewSection.vue'
import WorldSettingSection from '@/components/novel-detail/WorldSettingSection.vue'
import CharactersSection from '@/components/novel-detail/CharactersSection.vue'
import RelationshipsSection from '@/components/novel-detail/RelationshipsSection.vue'
import ChapterOutlineSection from '@/components/novel-detail/ChapterOutlineSection.vue'
import ChaptersSection from '@/components/novel-detail/ChaptersSection.vue'
import EmotionCurveSection from '@/components/novel-detail/EmotionCurveSection.vue'
import ForeshadowingSection from '@/components/novel-detail/ForeshadowingSection.vue'

interface Props {
  isAdmin?: boolean
}

type SectionKey = AllSectionType

const props = withDefaults(defineProps<Props>(), {
  isAdmin: false,
})

const route = useRoute()
const router = useRouter()
const novelStore = useNovelStore()

const projectId = route.params.id as string
const DESKTOP_BREAKPOINT = 1024
const isDesktopViewport = ref(
  typeof window !== 'undefined' ? window.innerWidth >= DESKTOP_BREAKPOINT : true,
)
const isSidebarOpen = ref(isDesktopViewport.value)

const sections: Array<{ key: SectionKey; label: string; description: string }> = [
  { key: 'overview', label: '项目概览', description: '定位与整体梗概' },
  { key: 'world_setting', label: '世界设定', description: '规则、地点与阵营' },
  { key: 'characters', label: '主要角色', description: '人物性格与目标' },
  { key: 'relationships', label: '人物关系', description: '角色之间的联系' },
  {
    key: 'chapter_outline',
    label: '章节大纲',
    description: props.isAdmin ? '故事章节规划' : '故事结构规划',
  },
  {
    key: 'chapters',
    label: '章节内容',
    description: props.isAdmin ? '生成章节与正文' : '生成状态与摘要',
  },
  { key: 'emotion_curve', label: '情感曲线', description: '追踪章节情感变化' },
  { key: 'foreshadowing', label: '伏笔管理', description: '故事线索与回收' },
]

const sectionKeys = sections.map((section) => section.key)

const resolveInitialSection = (): SectionKey => {
  const rawSection = Array.isArray(route.query.section)
    ? route.query.section[0]
    : route.query.section
  return sectionKeys.includes(rawSection as SectionKey) ? (rawSection as SectionKey) : 'overview'
}

const initialSection = resolveInitialSection()

const sectionComponents: Record<SectionKey, any> = {
  overview: OverviewSection,
  world_setting: WorldSettingSection,
  characters: CharactersSection,
  relationships: RelationshipsSection,
  chapter_outline: ChapterOutlineSection,
  chapters: ChaptersSection,
  emotion_curve: EmotionCurveSection,
  foreshadowing: ForeshadowingSection,
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

const sectionData = reactive<Partial<Record<SectionKey, any>>>({})
const sectionLoading = reactive<Record<SectionKey, boolean>>({
  overview: false,
  world_setting: false,
  characters: false,
  relationships: false,
  chapter_outline: false,
  chapters: false,
  emotion_curve: false,
  foreshadowing: false,
})
const sectionError = reactive<Record<SectionKey, string | null>>({
  overview: null,
  world_setting: null,
  characters: null,
  relationships: null,
  chapter_outline: null,
  chapters: null,
  emotion_curve: null,
  foreshadowing: null,
})

const overviewMeta = reactive<{ title: string; updated_at: string | null }>({
  title: '加载中...',
  updated_at: null,
})

const activeSection = ref<SectionKey>(initialSection)

// Modal state (user mode only)
const isModalOpen = ref(false)
const modalTitle = ref('')
const modalContent = ref<any>('')
const modalField = ref('')

// Add chapter modal state (user mode only)
const isAddChapterModalOpen = ref(false)
const newChapterTitle = ref('')
const newChapterSummary = ref('')
const novel = computed(() =>
  !props.isAdmin ? (novelStore.currentProject as NovelProject | null) : null,
)

const formattedTitle = computed(() => {
  const title = overviewMeta.title || '加载中...'
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
  await novelStore.loadProject(projectId)
}

const toggleSidebar = () => {
  isSidebarOpen.value = !isSidebarOpen.value
}

const closeSidebar = () => {
  isSidebarOpen.value = false
}

const handleResize = () => {
  if (typeof window === 'undefined') return
  const wasDesktop = isDesktopViewport.value
  const nowDesktop = window.innerWidth >= DESKTOP_BREAKPOINT
  isDesktopViewport.value = nowDesktop
  if (wasDesktop !== nowDesktop) {
    isSidebarOpen.value = nowDesktop
  }
}

const loadSection = async (section: SectionKey, force = false) => {
  if (!projectId) return

  // 分析型Section使用独立的API，不需要在这里加载
  const analysisSections: SectionKey[] = ['emotion_curve', 'foreshadowing']
  if (analysisSections.includes(section)) {
    return
  }

  if (!force && sectionData[section]) {
    return
  }

  sectionLoading[section] = true
  sectionError[section] = null
  try {
    const response: NovelSectionResponse = props.isAdmin
      ? await AdminAPI.getNovelSection(projectId, section as NovelSectionType)
      : await NovelAPI.getSection(projectId, section as NovelSectionType)
    sectionData[section] = response.data
    if (section === 'overview') {
      overviewMeta.title = response.data?.title || overviewMeta.title
      overviewMeta.updated_at = response.data?.updated_at || null
    }
  } catch (error) {
    console.error('加载模块失败:', error)
    sectionError[section] = error instanceof Error ? error.message : '加载失败'
  } finally {
    sectionLoading[section] = false
  }
}

const reloadSection = (section: SectionKey, force = false) => {
  loadSection(section, force)
}

const switchSection = (section: SectionKey) => {
  activeSection.value = section
  if (!isDesktopViewport.value) {
    closeSidebar()
  }
  loadSection(section)
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
const isSectionLoading = computed(() => sectionLoading[activeSection.value])
const currentError = computed(() => sectionError[activeSection.value])

const componentProps = computed(() => {
  const data = sectionData[activeSection.value]
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
    const updatedProject = await NovelAPI.updateBlueprint(project.id, payload)
    novelStore.setCurrentProject(updatedProject)
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
  const outline =
    sectionData.chapter_outline?.chapter_outline || novel.value?.blueprint?.chapter_outline || []
  const nextNumber =
    outline.length > 0 ? Math.max(...outline.map((item: any) => item.chapter_number)) + 1 : 1
  newChapterTitle.value = `新章节 ${nextNumber}`
  newChapterSummary.value = ''
  isAddChapterModalOpen.value = true
}

const cancelNewChapter = () => {
  isAddChapterModalOpen.value = false
}

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
    const updatedProject = await NovelAPI.updateBlueprint(project.id, {
      chapter_outline: newOutline,
    })
    novelStore.setCurrentProject(updatedProject)
    await loadSection('chapter_outline', true)
    isAddChapterModalOpen.value = false
  } catch (error) {
    console.error('新增章节失败:', error)
  }
}

onMounted(async () => {
  if (typeof window !== 'undefined') {
    window.addEventListener('resize', handleResize)
    handleResize()
  }

  // 只加载必要的 section 数据，不预加载完整项目
  await loadSection(initialSection, true)
  if (initialSection !== 'overview') {
    loadSection('overview', true)
  }
  if (initialSection !== 'world_setting') {
    loadSection('world_setting')
  }
})

onBeforeUnmount(() => {
  if (typeof window !== 'undefined') {
    window.removeEventListener('resize', handleResize)
  }
})
</script>

<style scoped>
.detail-shell {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 100vh;
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

.detail-shell__drawer-toggle-text {
  color: currentColor;
  font-size: var(--md-label-large);
  font-weight: 600;
  line-height: 1;
  white-space: nowrap;
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
  width: 100%;
  max-width: 1800px;
  margin: 0 auto;
  overflow: visible;
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
  height: calc(100% - 5rem);
  padding: var(--md-spacing-3);
  overflow-y: auto;
}

.detail-shell__nav-item {
  width: 100%;
  min-height: 4.5rem;
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

.detail-shell__nav-copy {
  flex: 1 1 auto;
  min-width: 0;
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
  max-height: calc(100vh - 6rem);
}

@media (min-width: 1024px) {
  .detail-shell__drawer {
    position: sticky;
    top: 4rem;
    bottom: auto;
    flex: 0 0 16.25rem;
    height: calc(100vh - 4rem);
    max-height: calc(100vh - 4rem);
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
    max-height: calc(100vh - 7.5rem);
  }
}

@media (min-width: 640px) {
  .detail-shell__content-surface {
    padding: var(--md-spacing-8);
  }
}

@media (max-width: 640px) {
  .detail-shell__drawer-toggle {
    width: 44px;
    padding: 0;
  }

  .detail-shell__drawer-toggle-text {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
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

/* Smooth scrollbar */
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: var(--md-outline);
  border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
  background: var(--md-on-surface-variant);
}
</style>
