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
              :evaluating-chapter="evaluatingChapter"
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
              :evaluating-chapter="evaluatingChapter"
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
              @select-chapter="selectChapter"
              @show-evaluation-detail="openEvaluationDetailModal"
              @fetch-chapter-status="fetchChapterStatus"
              @edit-chapter="editChapterContent"
            />

            <!-- 案头宣纸盖印·引首闲章 (写作辅助控制) -->
            <button
              type="button"
              class="writing-desk-seal-stamp md-ripple"
              :class="{ 'is-active': assistantToggleActive }"
              :title="assistantToggleActive ? '折叠右侧辅助面板' : '展开右侧辅助面板'"
              @click="toggleAssistantVisibility"
            >
              <!-- 印信篆字 (阴刻朱砂白文) -->
              <span class="stamp-seal-char">{{ assistantToggleActive ? '閉' : '輔' }}</span>
            </button>
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
    <Teleport to="body">
      <div
        v-if="showRecommendedOptimizeResultModal"
        class="md-dialog-overlay"
        @click.self="closeRecommendedOptimizeResult"
      >
        <div
          ref="recommendedDialogRef"
          class="md-dialog m3-result-dialog flex flex-col"
          role="dialog"
          aria-modal="true"
          :aria-labelledby="recommendedDialogTitleId"
        >
          <div class="p-6 border-b" style="border-bottom-color: var(--md-outline-variant)">
            <div class="flex items-center justify-between gap-4">
              <div>
                <h3 :id="recommendedDialogTitleId" class="md-headline-small font-semibold">
                  评审优化结果预览
                </h3>
                <p class="md-body-small md-on-surface-variant mt-1">
                  {{ recommendedOptimizeResultNotes }}
                </p>
              </div>
              <button
                ref="recommendedDialogCloseButtonRef"
                data-dialog-initial-focus
                type="button"
                @click="closeRecommendedOptimizeResult"
                :disabled="isApplyingRecommendedOptimization"
                class="md-icon-btn md-ripple disabled:opacity-50"
                aria-label="关闭评审优化结果弹窗"
              >
                <svg class="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
                  <path
                    fill-rule="evenodd"
                    d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                    clip-rule="evenodd"
                  ></path>
                </svg>
              </button>
            </div>
          </div>
          <div class="flex-1 overflow-y-auto p-6">
            <div class="whitespace-pre-wrap leading-relaxed" style="color: var(--md-on-surface)">
              <p
                v-for="(paragraph, index) in recommendedOptimizedParagraphs"
                :key="`recommended-optimized-${index}`"
                class="mb-4 last:mb-0"
              >
                {{ paragraph }}
              </p>
            </div>
          </div>
          <div
            class="p-6 border-t flex items-center justify-end gap-3"
            style="
              border-top-color: var(--md-outline-variant);
              background-color: var(--md-surface-container-low);
            "
          >
            <div class="md-body-small md-on-surface-variant mr-auto">
              {{ recommendedOptimizedWordCount }} 字
            </div>
            <button
              type="button"
              @click="closeRecommendedOptimizeResult"
              :disabled="isApplyingRecommendedOptimization"
              class="md-btn md-btn-outlined md-ripple disabled:opacity-50"
            >
              取消
            </button>
            <button
              type="button"
              @click="applyRecommendedOptimization"
              :disabled="isApplyingRecommendedOptimization"
              class="md-btn md-btn-filled md-ripple disabled:opacity-50 flex items-center gap-2"
              style="background-color: var(--md-success); color: var(--md-on-success)"
            >
              <svg
                v-if="isApplyingRecommendedOptimization"
                class="w-4 h-4 animate-spin"
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path
                  fill-rule="evenodd"
                  d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z"
                  clip-rule="evenodd"
                ></path>
              </svg>
              {{ isApplyingRecommendedOptimization ? '应用中...' : '应用优化' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
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
import { ref, computed, defineAsyncComponent, nextTick, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import type {
  Chapter,
  ChapterOutline,
  ChapterGenerationResponse,
  ChapterVersion,
} from '@/api/novel'
import {
  useDeleteChapterMutation,
  useEditChapterContentMutation,
  useEvaluateChapterMutation,
  useApplyOptimizationMutation,
  useConfirmFinalizeChapterMutation,
  useGenerateChapterMutation,
  useGenerateChapterOutlineMutation,
  useNovelChapterQuery,
  useNovelMutationRefresh,
  useNovelProjectQuery,
  useOptimizeRecommendedVersionMutation,
  useUpdateChapterOutlineMutation,
} from '@/queries/novel'
import { globalAlert } from '@/composables/useAlert'
import { useDialogA11y } from '@/composables/useDialogA11y'
import { useResponsiveViewport } from '@/composables/useResponsiveViewport'
import { desktopMin, mobileMax } from '@/constants/responsive'
import { countNonWhitespaceChars } from '@/utils/text'
import {
  formatChapterGenerationError,
  resolveChapterNumberForEntry,
  resolveChapterNumberForProjectEntry,
} from '@/utils/chapter'
import { useNovelStore } from '@/stores/novel'
import WDSidebar from '@/components/writing-desk/WDSidebar.vue'
import WDWorkspace from '@/components/writing-desk/WDWorkspace.vue'

const loadWDVersionDetailModal = () => import('@/components/writing-desk/WDVersionDetailModal.vue')
const loadWDEvaluationDetailModal = () => import('@/components/writing-desk/WDEvaluationDetailModal.vue')
const loadWDEditChapterModal = () => import('@/components/writing-desk/WDEditChapterModal.vue')
const loadWDGenerateOutlineModal = () => import('@/components/writing-desk/WDGenerateOutlineModal.vue')
const loadWDAssistantPanel = () => import('@/components/writing-desk/WDAssistantPanel.vue')

const WDVersionDetailModal = defineAsyncComponent(loadWDVersionDetailModal)
const WDEvaluationDetailModal = defineAsyncComponent(loadWDEvaluationDetailModal)
const WDEditChapterModal = defineAsyncComponent(loadWDEditChapterModal)
const WDGenerateOutlineModal = defineAsyncComponent(loadWDGenerateOutlineModal)
const WDAssistantPanel = defineAsyncComponent(loadWDAssistantPanel)

interface Props {
  id: string
}

const props = defineProps<Props>()
const router = useRouter()
const route = useRoute()
const projectQuery = useNovelProjectQuery(() => props.id)

// 状态管理
const selectedChapterNumber = ref<number | null>(null)
const resolvedProjectEntryId = ref<string | null>(null)
const chapterGenerationResult = ref<ChapterGenerationResponse | null>(null)
const selectedVersionIndex = ref<number>(0)
const generatingChapter = ref<number | null>(null)
const showVersionDetailModal = ref(false)
const detailVersionIndex = ref<number>(0)
const showEvaluationDetailModal = ref(false)
const showEditChapterModal = ref(false)
const editingChapter = ref<ChapterOutline | null>(null)
const isGeneratingOutline = ref(false)
const showGenerateOutlineModal = ref(false)
const isFetchingChapterStatus = ref(false)
const optimizeRecommendedVersionMutation = useOptimizeRecommendedVersionMutation()
const showRecommendedOptimizeResultModal = ref(false)
const recommendedDialogRef = ref<HTMLElement | null>(null)
const recommendedDialogCloseButtonRef = ref<HTMLElement | null>(null)
const recommendedDialogTitleId = 'writing-desk-recommended-optimize-title'
const applyOptimizationMutation = useApplyOptimizationMutation(() => props.id)
const isOptimizingRecommendedVersion = computed(
  () => optimizeRecommendedVersionMutation.isPending.value,
)
const isApplyingRecommendedOptimization = computed(() => applyOptimizationMutation.isPending.value)
const recommendedOptimizedContent = ref('')
const recommendedOptimizeResultNotes = ref('')
const viewport = useResponsiveViewport()
const viewportWidth = computed(() => viewport.width.value)
const novelStore = useNovelStore()
const isSidebarDrawerOpen = ref(false)
const isAssistantDrawerOpen = ref(false)
const isAssistantPanelVisible = computed({
  get: () => novelStore.isAssistantPanelVisible,
  set: (val) => {
    novelStore.isAssistantPanelVisible = val
    persistAssistantPanelVisibility(val)
  }
})
const SIDEBAR_DRAWER_BREAKPOINT = mobileMax
const ASSISTANT_DRAWER_BREAKPOINT = desktopMin - 1
const ASSISTANT_PANEL_VISIBILITY_STORAGE_KEY = 'mofeng.writingDesk.assistant.visible'

const chapterQuery = useNovelChapterQuery(() => props.id, selectedChapterNumber)
const { refreshProjectQueries, upsertChapterInProjectCache } = useNovelMutationRefresh(
  () => props.id,
)
const generateChapterMutation = useGenerateChapterMutation(() => props.id)
const evaluateChapterMutation = useEvaluateChapterMutation(() => props.id)
const confirmFinalizeChapterMutation = useConfirmFinalizeChapterMutation(() => props.id)
const updateChapterOutlineMutation = useUpdateChapterOutlineMutation(() => props.id)
const deleteChapterMutation = useDeleteChapterMutation(() => props.id)
const generateChapterOutlineMutation = useGenerateChapterOutlineMutation(() => props.id)
const editChapterContentMutation = useEditChapterContentMutation(() => props.id)

// 计算属性
const project = computed(() => projectQuery.data.value ?? null)
const projectLoading = computed(() => projectQuery.isPending.value)
const projectError = computed(() => {
  const error = projectQuery.error.value
  return error instanceof Error ? error.message : error ? '加载项目失败' : null
})

const useSidebarDrawer = computed(() => viewportWidth.value <= SIDEBAR_DRAWER_BREAKPOINT)
const useAssistantDrawer = computed(() => viewportWidth.value <= ASSISTANT_DRAWER_BREAKPOINT)
const shouldRenderAssistantShell = computed(() => !!project.value)
const assistantToggleActive = computed(() =>
  useAssistantDrawer.value ? isAssistantDrawerOpen.value : isAssistantPanelVisible.value,
)

const isDrawerBackdropVisible = computed(
  () =>
    (useSidebarDrawer.value && isSidebarDrawerOpen.value) ||
    (useAssistantDrawer.value && isAssistantDrawerOpen.value),
)

watch(
  () => useSidebarDrawer.value,
  (enabled) => {
    if (!enabled) {
      isSidebarDrawerOpen.value = false
    }
  },
  { immediate: true },
)

watch(
  () => useAssistantDrawer.value,
  (enabled) => {
    if (!enabled) {
      isAssistantDrawerOpen.value = false
    }
  },
  { immediate: true },
)

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

const closeAllDrawers = () => {
  isSidebarDrawerOpen.value = false
  isAssistantDrawerOpen.value = false
}

const persistAssistantPanelVisibility = (visible: boolean) => {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(ASSISTANT_PANEL_VISIBILITY_STORAGE_KEY, visible ? '1' : '0')
  } catch (error) {
    console.warn('保存辅助信息面板状态失败:', error)
  }
}

const restoreAssistantPanelVisibility = () => {
  if (typeof window === 'undefined') return
  try {
    const stored = window.localStorage.getItem(ASSISTANT_PANEL_VISIBILITY_STORAGE_KEY)
    if (stored === '0') {
      isAssistantPanelVisible.value = false
    } else if (stored === '1') {
      isAssistantPanelVisible.value = true
    }
  } catch (error) {
    console.warn('读取辅助信息面板状态失败:', error)
  }
}

const toggleSidebarDrawer = () => {
  if (!useSidebarDrawer.value) return
  isSidebarDrawerOpen.value = !isSidebarDrawerOpen.value
  if (isSidebarDrawerOpen.value) {
    isAssistantDrawerOpen.value = false
  }
}

const toggleAssistantDrawer = () => {
  if (!useAssistantDrawer.value) return
  void loadWDAssistantPanel()
  isAssistantDrawerOpen.value = !isAssistantDrawerOpen.value
  if (isAssistantDrawerOpen.value && useSidebarDrawer.value) {
    isSidebarDrawerOpen.value = false
  }
}

const toggleAssistantVisibility = () => {
  if (useAssistantDrawer.value) {
    toggleAssistantDrawer()
    return
  }
  void loadWDAssistantPanel()
  isAssistantPanelVisible.value = !isAssistantPanelVisible.value
  persistAssistantPanelVisibility(isAssistantPanelVisible.value)
}

const selectedChapter = computed(() => {
  if (!project.value || selectedChapterNumber.value === null) return null
  if (chapterQuery.data.value?.chapter_number === selectedChapterNumber.value) {
    return chapterQuery.data.value
  }
  return (
    project.value.chapters.find((ch) => ch.chapter_number === selectedChapterNumber.value) || null
  )
})

const showVersionSelector = computed(() => {
  if (!selectedChapter.value) return false
  const status = selectedChapter.value.generation_status
  return (
    status === 'waiting_for_confirm' ||
    status === 'evaluating' ||
    status === 'evaluation_failed' ||
    status === 'selecting'
  )
})

const evaluatingChapter = computed(() => {
  if (selectedChapter.value?.generation_status === 'evaluating') {
    return selectedChapter.value.chapter_number
  }
  return null
})

const isSelectingVersion = computed(() => {
  return (
    selectedChapter.value?.generation_status === 'finalizing' ||
    confirmFinalizeChapterMutation.isPending.value
  )
})

const selectedChapterOutline = computed(() => {
  if (!project.value?.blueprint?.chapter_outline || selectedChapterNumber.value === null)
    return null
  return (
    project.value.blueprint.chapter_outline.find(
      (ch) => ch.chapter_number === selectedChapterNumber.value,
    ) || null
  )
})

const latestCompletedChapterNumber = computed(() => {
  const completedNumbers =
    project.value?.chapters
      ?.filter((chapter) => chapter.generation_status === 'successful')
      .map((chapter) => chapter.chapter_number) ?? []
  return completedNumbers.length ? Math.max(...completedNumbers) : null
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

const isCurrentVersion = (versionIndex: number) => {
  if (!selectedChapter.value?.content || !availableVersions.value?.[versionIndex]?.content)
    return false

  // 使用cleanVersionContent函数清理内容进行比较
  const cleanCurrentContent = cleanVersionContent(selectedChapter.value.content)
  const cleanVersionContentStr = cleanVersionContent(availableVersions.value[versionIndex].content)

  return cleanCurrentContent === cleanVersionContentStr
}

const cleanVersionContent = (content: string): string => {
  if (!content) return ''

  // 尝试解析JSON，看是否是完整的章节对象
  try {
    const parsed = JSON.parse(content)
    const extractContent = (value: any): string | null => {
      if (!value) return null
      if (typeof value === 'string') return value
      if (Array.isArray(value)) {
        for (const item of value) {
          const nested = extractContent(item)
          if (nested) return nested
        }
        return null
      }
      if (typeof value === 'object') {
        for (const key of ['content', 'chapter_content', 'chapter_text', 'text', 'body', 'story']) {
          if (value[key]) {
            const nested = extractContent(value[key])
            if (nested) return nested
          }
        }
      }
      return null
    }
    const extracted = extractContent(parsed)
    if (extracted) {
      // 如果是章节对象/数组，提取正文
      content = extracted
    }
  } catch (error) {
    // 如果不是JSON，继续处理字符串
  }

  // 去掉开头和结尾的引号
  let cleaned = content.replace(/^"|"$/g, '')

  // 处理转义字符
  cleaned = cleaned.replace(/\\n/g, '\n') // 换行符
  cleaned = cleaned.replace(/\\"/g, '"') // 引号
  cleaned = cleaned.replace(/\\t/g, '\t') // 制表符
  cleaned = cleaned.replace(/\\\\/g, '\\') // 反斜杠

  return cleaned
}

const canGenerateChapter = (chapterNumber: number) => {
  if (!project.value?.blueprint?.chapter_outline) return false

  // 检查前面所有章节是否都已成功生成
  const outlines = project.value.blueprint.chapter_outline.sort(
    (a, b) => a.chapter_number - b.chapter_number,
  )

  for (const outline of outlines) {
    if (outline.chapter_number >= chapterNumber) break

    const chapter = project.value?.chapters.find(
      (ch) => ch.chapter_number === outline.chapter_number,
    )
    if (!chapter || chapter.generation_status !== 'successful') {
      return false // 前面有章节未完成
    }
  }

  // 检查当前章节是否已经完成
  const currentChapter = project.value?.chapters.find((ch) => ch.chapter_number === chapterNumber)
  if (currentChapter && currentChapter.generation_status === 'successful') {
    return true // 已完成的章节可以重新生成
  }

  return true // 前面章节都完成了，可以生成当前章节
}

const isChapterFailed = (chapterNumber: number) => {
  if (!project.value?.chapters) return false
  const chapter = project.value.chapters.find((ch) => ch.chapter_number === chapterNumber)
  return chapter && chapter.generation_status === 'failed'
}

const hasChapterInProgress = (chapterNumber: number) => {
  if (!project.value?.chapters) return false
  const chapter = project.value.chapters.find((ch) => ch.chapter_number === chapterNumber)
  // waiting_for_confirm状态表示等待选择版本 = 进行中状态
  return chapter && chapter.generation_status === 'waiting_for_confirm'
}

const extractVersionContent = (raw: unknown): string => {
  if (typeof raw !== 'string') {
    return ''
  }
  const trimmed = raw.trim()
  if (!trimmed) {
    return ''
  }

  const likelyJson =
    (trimmed.startsWith('{') && trimmed.endsWith('}')) ||
    (trimmed.startsWith('[') && trimmed.endsWith(']'))
  if (!likelyJson) {
    return raw
  }

  try {
    const parsed = JSON.parse(trimmed)
    if (parsed && typeof parsed === 'object') {
      const record = parsed as Record<string, unknown>
      for (const key of ['content', 'chapter_content', 'chapter_text', 'text', 'body', 'story']) {
        const candidate = record[key]
        if (typeof candidate === 'string' && candidate.trim()) {
          return candidate
        }
      }
    }
  } catch {
    // ignore parse errors, fallback to raw text
  }
  return raw
}

// 可用版本列表（来源优先级：生成结果 > 章节 versions > 章节 content 兜底）
const availableVersions = computed<ChapterVersion[]>(() => {
  if (
    Array.isArray(chapterGenerationResult.value?.versions) &&
    chapterGenerationResult.value.versions.length > 0
  ) {
    return chapterGenerationResult.value.versions.filter((item) => Boolean(item?.content?.trim()))
  }

  const chapter = selectedChapter.value
  if (!chapter) {
    return []
  }

  if (Array.isArray(chapter.versions) && chapter.versions.length > 0) {
    const converted = chapter.versions
      .map((versionRaw) => {
        const content = extractVersionContent(versionRaw)
        if (!content.trim()) {
          return null
        }
        return {
          content,
          style: '标准',
        } as ChapterVersion
      })
      .filter((item): item is ChapterVersion => item !== null)
    if (converted.length > 0) {
      return converted
    }
  }

  if (typeof chapter.content === 'string' && chapter.content.trim()) {
    return [{ content: chapter.content, style: '标准' }]
  }

  return []
})

const recommendedOptimizedParagraphs = computed(() => {
  if (!recommendedOptimizedContent.value.trim()) return []
  return recommendedOptimizedContent.value
    .split(/\n{2,}/)
    .map((paragraph) => paragraph.trim())
    .filter(Boolean)
})

const recommendedOptimizedWordCount = computed(() => {
  return countNonWhitespaceChars(recommendedOptimizedContent.value)
})

const tryParseOptimizerPayload = (rawText: string): Record<string, unknown> | null => {
  if (!rawText) return null
  const text = rawText.trim()
  if (!text) return null

  const candidates: string[] = [text]
  const fenceMatch = text.match(/```(?:json|JSON)?\s*([\s\S]*?)\s*```/)
  if (fenceMatch?.[1]) {
    const fenced = fenceMatch[1].trim()
    if (fenced && fenced !== text) candidates.unshift(fenced)
  }

  for (const candidate of candidates) {
    try {
      const parsed = JSON.parse(candidate)
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
        return parsed as Record<string, unknown>
      }
    } catch {
      // ignore
    }
  }
  return null
}

const decodeJsonStringFragment = (fragment: string): string => {
  try {
    return JSON.parse(`"${fragment}"`) as string
  } catch {
    return fragment.replace(/\\"/g, '"').replace(/\\n/g, '\n').replace(/\\t/g, '\t')
  }
}

const extractJsonField = (
  rawText: string,
  field: 'optimized_content' | 'optimization_notes',
): string | null => {
  const pattern = new RegExp(`"${field}"\\s*:\\s*"((?:\\\\.|[^"\\\\])*)"`, 's')
  const match = rawText.match(pattern)
  if (!match?.[1]) return null
  return decodeJsonStringFragment(match[1])
}

const normalizeOptimizeResult = (
  contentRaw: string,
  notesRaw: string,
): { content: string; notes: string } => {
  let content = (contentRaw || '').trim()
  let notes = (notesRaw || '').trim()
  const seen = new Set<string>()

  for (let i = 0; i < 2; i++) {
    if (!content || seen.has(content)) break
    seen.add(content)
    const payload = tryParseOptimizerPayload(content)
    if (!payload) break
    const nestedContent = payload.optimized_content
    if (typeof nestedContent !== 'string' || !nestedContent.trim()) break
    content = nestedContent.trim()
    if (!notes && typeof payload.optimization_notes === 'string') {
      notes = payload.optimization_notes.trim()
    }
  }

  if (content.includes('"optimized_content"')) {
    const extractedContent = extractJsonField(content, 'optimized_content')
    if (extractedContent?.trim()) {
      content = extractedContent.trim()
    }
    if (!notes) {
      const extractedNotes = extractJsonField(contentRaw, 'optimization_notes')
      if (extractedNotes?.trim()) {
        notes = extractedNotes.trim()
      }
    }
  }

  const fenced = content.match(/```(?:json|JSON)?\s*([\s\S]*?)\s*```/)
  if (fenced?.[1]) {
    content = fenced[1].trim()
  }

  return {
    content,
    notes: notes || '优化完成',
  }
}

const parseEvaluationPayload = (evaluation: string | null): Record<string, any> | null => {
  if (!evaluation) return null
  try {
    let data = JSON.parse(evaluation)
    if (typeof data === 'string') {
      data = JSON.parse(data)
    }
    if (data && typeof data === 'object' && !Array.isArray(data)) {
      return data as Record<string, any>
    }
  } catch (error) {
    console.error('解析评审结果失败:', error)
  }
  return null
}

const closeRecommendedOptimizeResult = () => {
  if (isApplyingRecommendedOptimization.value) return
  showRecommendedOptimizeResultModal.value = false
}

useDialogA11y({
  active: showRecommendedOptimizeResultModal,
  dialogRef: recommendedDialogRef,
  onClose: closeRecommendedOptimizeResult,
  initialFocusRef: recommendedDialogCloseButtonRef,
})

const optimizeRecommendedVersionFromEvaluation = async () => {
  if (!project.value || !selectedChapter.value) {
    globalAlert.showError('缺少章节信息，无法执行优化')
    return
  }

  const evaluationPayload = parseEvaluationPayload(selectedChapter.value.evaluation || null)
  if (!evaluationPayload) {
    globalAlert.showError('当前评审结果无法解析，暂时不能执行评审优化')
    return
  }

  const bestChoice = Number(evaluationPayload.best_choice)
  if (!Number.isInteger(bestChoice) || bestChoice < 1) {
    globalAlert.showError('当前评审结果缺少推荐版本，无法执行优化')
    return
  }

  const versionIndex = bestChoice - 1
  const sourceVersion = availableVersions.value[versionIndex]
  if (!sourceVersion?.content?.trim()) {
    globalAlert.showError('推荐版本正文不存在，无法执行优化')
    return
  }

  const versionReview = evaluationPayload.evaluation?.[`version${bestChoice}`] || {}
  try {
    const result = await optimizeRecommendedVersionMutation.mutateAsync({
      project_id: project.value.id,
      chapter_number: selectedChapter.value.chapter_number,
      source_content: cleanVersionContent(sourceVersion.content),
      review_summary: String(evaluationPayload.reason_for_choice || '').trim(),
      version_number: bestChoice,
      version_review: versionReview,
    })

    const normalized = normalizeOptimizeResult(result.optimized_content, result.optimization_notes)
    if (!normalized.content.trim()) {
      globalAlert.showError('优化结果为空，请稍后重试')
      return
    }

    recommendedOptimizedContent.value = normalized.content
    recommendedOptimizeResultNotes.value = normalized.notes
    showRecommendedOptimizeResultModal.value = true
  } catch (error: any) {
    console.error('评审优化失败:', error)
    globalAlert.showError(error.message || '评审优化失败，请稍后重试')
  }
}

const applyRecommendedOptimization = async () => {
  if (!project.value || !selectedChapter.value || !recommendedOptimizedContent.value.trim()) {
    return
  }

  try {
    const applyResult = await applyOptimizationMutation.mutateAsync({
      projectId: project.value.id,
      chapterNumber: selectedChapter.value.chapter_number,
      optimizedContent: recommendedOptimizedContent.value,
    })

    const syncStats = applyResult.foreshadowing_sync
    if (syncStats) {
      globalAlert.showSuccess(
        `优化内容已应用，伏笔同步：新增 ${syncStats.created}，推进 ${syncStats.developing}，回收 ${syncStats.revealed}`,
      )
    } else {
      globalAlert.showSuccess('优化内容已应用')
    }

    showRecommendedOptimizeResultModal.value = false
    showEvaluationDetailModal.value = false
    recommendedOptimizedContent.value = ''
    recommendedOptimizeResultNotes.value = ''
    await refetchChapterIntoProject(selectedChapter.value.chapter_number)
  } catch (error: any) {
    console.error('应用评审优化失败:', error)
    globalAlert.showError(error.message || '应用优化失败，请稍后重试')
  }
}

onMounted(() => {
  restoreAssistantPanelVisibility()
})

// 方法
const goBack = () => {
  router.push('/workspace')
}

const viewProjectDetail = () => {
  if (project.value) {
    router.push(`/projects/${project.value.id}`)
  }
}

const loadProject = async () => {
  try {
    await projectQuery.refetch()
  } catch (error) {
    console.error('加载项目失败:', error)
  }
}

const refetchChapterIntoProject = async (
  chapterNumber: number,
  options: { refreshProject?: boolean } = { refreshProject: true },
) => {
  if (selectedChapterNumber.value !== chapterNumber) {
    selectedChapterNumber.value = chapterNumber
    await nextTick()
  }

  const result = await chapterQuery.refetch()
  if (result.data) {
    upsertChapterInProjectCache(props.id, result.data)
  }
  if (options.refreshProject) {
    await refreshProjectQueries()
  }
}

const fetchChapterStatus = async () => {
  if (selectedChapterNumber.value === null || isFetchingChapterStatus.value) {
    return
  }
  const chapterNumber = selectedChapterNumber.value
  isFetchingChapterStatus.value = true
  try {
    await refetchChapterIntoProject(chapterNumber, { refreshProject: false })
  } catch (error) {
    console.error('轮询章节状态失败:', error)
    // 在这里可以决定是否要通知用户轮询失败
  } finally {
    isFetchingChapterStatus.value = false
  }
}

// 显示版本详情
const showVersionDetail = (versionIndex: number) => {
  if (versionIndex < 0 || versionIndex >= availableVersions.value.length) {
    return
  }
  void loadWDVersionDetailModal()
  detailVersionIndex.value = versionIndex
  showVersionDetailModal.value = true
}

// 关闭版本详情弹窗
const closeVersionDetail = () => {
  showVersionDetailModal.value = false
}

// 隐藏版本选择器，返回内容视图
const hideVersionSelector = () => {
  // Now controlled by computed property, but we can clear the generation result
  chapterGenerationResult.value = null
  selectedVersionIndex.value = 0
}

const selectChapter = (chapterNumber: number) => {
  selectedChapterNumber.value = chapterNumber
  chapterGenerationResult.value = null
  selectedVersionIndex.value = 0
  closeAllDrawers()
}

const generateChapter = async (chapterNumber: number) => {
  // 检查是否可以生成该章节
  if (
    !canGenerateChapter(chapterNumber) &&
    !isChapterFailed(chapterNumber) &&
    !hasChapterInProgress(chapterNumber)
  ) {
    globalAlert.showError('请按顺序生成章节，先完成前面的章节', '生成受限')
    return
  }

  try {
    generatingChapter.value = chapterNumber
    selectedChapterNumber.value = chapterNumber
    const nowIso = new Date().toISOString()

    // 在本地更新章节状态为generating
    if (project.value?.chapters) {
      const chapter = project.value.chapters.find((ch) => ch.chapter_number === chapterNumber)
      if (chapter) {
        chapter.generation_status = 'generating'
        chapter.generation_progress = 0
        chapter.generation_step = 'context_prep'
        chapter.generation_step_index = 1
        chapter.generation_step_total = null
        chapter.generation_started_at = nowIso
        chapter.status_updated_at = nowIso
      } else {
        // If chapter does not exist, create a temporary one to show generating state
        const outline = project.value.blueprint?.chapter_outline?.find(
          (o) => o.chapter_number === chapterNumber,
        )
        project.value.chapters.push({
          chapter_number: chapterNumber,
          title: outline?.title || '加载中...',
          summary: outline?.summary || '',
          content: '',
          versions: [],
          evaluation: null,
          generation_status: 'generating',
          generation_progress: 0,
          generation_step: 'context_prep',
          generation_step_index: 1,
          generation_step_total: null,
          generation_started_at: nowIso,
          status_updated_at: nowIso,
        } as Chapter)
      }
    }

    await generateChapterMutation.mutateAsync(chapterNumber)
    // 关键兜底：生成接口在极少数情况下可能返回旧快照，这里强制拉取当前章最新状态。
    await refetchChapterIntoProject(chapterNumber)

    // 生成完成只进入草稿确认，必须由用户确认定稿后才执行后处理。
    generatingChapter.value = null
    chapterGenerationResult.value = null
    selectedVersionIndex.value = 0
  } catch (error) {
    console.error('生成章节失败:', error)
    const failureMessage = formatChapterGenerationError(error)

    // 错误状态的本地更新仍然是必要的，以立即反映UI
    if (project.value?.chapters) {
      const chapter = project.value.chapters.find((ch) => ch.chapter_number === chapterNumber)
      if (chapter) {
        chapter.generation_status = 'failed'
        chapter.generation_step = failureMessage
        chapter.status_updated_at = new Date().toISOString()
      }
    }

    globalAlert.showError(failureMessage, '生成失败')
  } finally {
    generatingChapter.value = null
  }
}

const regenerateChapter = async () => {
  if (selectedChapterNumber.value !== null) {
    await generateChapter(selectedChapterNumber.value)
  }
}

const confirmVersionSelection = async (payload?: { editedContent?: string | null }) => {
  const targetChapterNumber = selectedChapterNumber.value
  if (targetChapterNumber === null) {
    return
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

// 从详情弹窗中选择版本
const selectVersionFromDetail = async () => {
  selectedVersionIndex.value = detailVersionIndex.value
  closeVersionDetail()
}

const openEditChapterModal = (chapter: ChapterOutline) => {
  void loadWDEditChapterModal()
  editingChapter.value = chapter
  showEditChapterModal.value = true
}

const openEvaluationDetailModal = () => {
  void loadWDEvaluationDetailModal()
  showEvaluationDetailModal.value = true
}

const saveChapterChanges = async (updatedChapter: ChapterOutline) => {
  try {
    await updateChapterOutlineMutation.mutateAsync(updatedChapter)
    globalAlert.showSuccess('章节大纲已更新', '保存成功')
  } catch (error) {
    console.error('更新章节大纲失败:', error)
    globalAlert.showError(
      `更新章节大纲失败: ${error instanceof Error ? error.message : '未知错误'}`,
      '保存失败',
    )
  } finally {
    showEditChapterModal.value = false
  }
}

const evaluateChapter = async () => {
  if (selectedChapterNumber.value !== null) {
    // 保存原始状态，用于失败时恢复
    let previousStatus:
      | 'not_generated'
      | 'generating'
      | 'evaluating'
      | 'selecting'
      | 'failed'
      | 'evaluation_failed'
      | 'waiting_for_confirm'
      | 'finalizing'
      | 'successful'
      | undefined

    try {
      // 在本地更新章节状态为evaluating以立即反映在UI上
      if (project.value?.chapters) {
        const chapter = project.value.chapters.find(
          (ch) => ch.chapter_number === selectedChapterNumber.value,
        )
        if (chapter) {
          previousStatus = chapter.generation_status // 保存原状态
          chapter.generation_status = 'evaluating'
        }
      }
      await evaluateChapterMutation.mutateAsync(selectedChapterNumber.value)

      // 评审完成后，状态会通过store和轮询更新，这里不需要额外操作
      globalAlert.showSuccess('章节评审结果已生成', '评审成功')
    } catch (error) {
      console.error('评审章节失败:', error)

      // 错误状态下恢复章节状态为原始状态
      if (project.value?.chapters) {
        const chapter = project.value.chapters.find(
          (ch) => ch.chapter_number === selectedChapterNumber.value,
        )
        if (chapter && previousStatus) {
          chapter.generation_status = previousStatus // 恢复为原状态
        }
      }

      globalAlert.showError(
        `评审章节失败: ${error instanceof Error ? error.message : '未知错误'}`,
        '评审失败',
      )
    }
  }
}

const deleteChapter = async (chapterNumbers: number | number[]) => {
  const numbersToDelete = Array.isArray(chapterNumbers) ? chapterNumbers : [chapterNumbers]
  const completedChapterNumber = numbersToDelete.find(
    (number) => number === latestCompletedChapterNumber.value,
  )
  const isDeletingCompletedChapter = completedChapterNumber !== undefined
  const outlineOnlyNumbers = isDeletingCompletedChapter
    ? numbersToDelete.filter((number) => number !== completedChapterNumber)
    : numbersToDelete
  const confirmationTitle = isDeletingCompletedChapter ? '删除章节及产物' : '删除章节大纲'
  const confirmationMessage = isDeletingCompletedChapter
    ? outlineOnlyNumbers.length
      ? `您确定要删除第 ${completedChapterNumber} 章及后续 ${outlineOnlyNumbers.length} 个未生成大纲吗？此操作会删除该已完成章的正文、版本、评审、生成 trace 和向量数据等全部产物，且无法撤销。`
      : `您确定要删除第 ${completedChapterNumber} 章吗？此操作会删除正文、版本、评审、生成 trace 和向量数据等全部产物，且无法撤销。`
    : numbersToDelete.length > 1
    ? `您确定要删除选中的 ${numbersToDelete.length} 个章节大纲吗？这个操作无法撤销。`
    : `您确定要删除第 ${numbersToDelete[0]} 章大纲吗？这个操作无法撤销。`

  const confirmed = await globalAlert.showConfirm(confirmationMessage, confirmationTitle)
  if (!confirmed) {
    return
  }

  let artifactConfirmationText: string | null = null
  if (isDeletingCompletedChapter) {
    artifactConfirmationText = `删除第${completedChapterNumber}章及全部产物`
    const typedConfirmation = await globalAlert.showConfirmInput(
      `请再次确认。输入“${artifactConfirmationText}”后，系统才会删除该已完成章节对应产物。`,
      '二次确认',
      {
        inputLabel: '确认文本',
        inputPlaceholder: artifactConfirmationText,
        confirmText: '确认删除',
      },
    )
    if (typedConfirmation !== artifactConfirmationText) {
      globalAlert.showError('确认文本不匹配，已取消删除。', '删除已取消')
      return
    }
  } else {
    const secondConfirmed = await globalAlert.showConfirm(
      '请再次确认删除章节大纲。此操作无法撤销。',
      '二次确认',
    )
    if (!secondConfirmed) {
      return
    }
  }

  try {
    await deleteChapterMutation.mutateAsync({
      chapterNumbers: numbersToDelete,
      deleteArtifactsConfirmed: isDeletingCompletedChapter,
      confirmationText: artifactConfirmationText,
    })
    globalAlert.showSuccess(
      isDeletingCompletedChapter ? '章节及产物已删除' : '章节大纲已删除',
      '操作成功',
    )
    // If the currently selected chapter was deleted, unselect it
    if (selectedChapterNumber.value && numbersToDelete.includes(selectedChapterNumber.value)) {
      selectedChapterNumber.value = null
    }
  } catch (error) {
    console.error('删除章节失败:', error)
    globalAlert.showError(
      `删除章节失败: ${error instanceof Error ? error.message : '未知错误'}`,
      '删除失败',
    )
  }
}

const generateOutline = async () => {
  void loadWDGenerateOutlineModal()
  showGenerateOutlineModal.value = true
}

const editChapterContent = async (data: { chapterNumber: number; content: string }) => {
  if (!project.value) return

  try {
    await editChapterContentMutation.mutateAsync({
      chapterNumber: data.chapterNumber,
      content: data.content,
    })
    globalAlert.showSuccess('章节内容已更新', '保存成功')
  } catch (error) {
    console.error('编辑章节内容失败:', error)
    globalAlert.showError(
      `编辑章节内容失败: ${error instanceof Error ? error.message : '未知错误'}`,
      '保存失败',
    )
  }
}

const handleGenerateOutline = async (numChapters: number) => {
  if (!project.value) return
  isGeneratingOutline.value = true
  try {
    const startChapter = (project.value.blueprint?.chapter_outline?.length || 0) + 1
    await generateChapterOutlineMutation.mutateAsync({ startChapter, numChapters })
    globalAlert.showSuccess('大纲生成任务已加入后台，可在右上角任务日志查看进度', '任务已提交')
  } catch (error) {
    console.error('生成大纲失败:', error)
    globalAlert.showError(
      `生成大纲失败: ${error instanceof Error ? error.message : '未知错误'}`,
      '生成失败',
    )
  } finally {
    isGeneratingOutline.value = false
  }
}
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

.m3-result-dialog {
  max-width: min(900px, calc(100vw - 32px));
  max-height: calc(var(--app-viewport-unit) - 32px);
  border-radius: var(--md-radius-xl);
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

/* 宣纸引首闲章本体 */
.writing-desk-seal-stamp {
  position: absolute;
  right: 0;
  top: 135px;
  z-index: 30; /* 高于工作区，低于弹窗与 drawer 遮罩层 */
  display: flex;
  align-items: center;
  justify-content: center;
  height: 38px;
  width: 38px; /* 默认正方形印章尺寸 */
  padding: 0;
  cursor: pointer;
  border: 1px solid #9c2720;
  border-right: none; /* 右侧贴合分界线，呈无缝盖印状态 */

  /* 运用左圆角、右直角设计，完美模拟盖在纸张右边缘的引首章印记 */
  border-radius: 6px 0 0 6px / 8px 0 0 8px;

  /* 精致沉稳的朱砂印泥色彩渐变 */
  background: linear-gradient(135deg, #c94036 0%, #b83c32 50%, #a32720 100%);

  /* 核心国风魔力：混合相乘模式！
     它会让朱砂红与米黄色的稿纸底纹像素完美混合，呈现出极其逼真的“印泥渗入宣纸”拓印质感 */
  mix-blend-mode: multiply;
  opacity: 0.92;

  /* 盖印后的轻微纸张受压凹凸质感与边缘斑驳微影 */
  box-shadow:
    -1px 2px 4px rgba(107, 21, 16, 0.25),
    inset 1px 1px 1px rgba(255, 255, 255, 0.15),
    inset -1px -1px 2px rgba(0, 0, 0, 0.15);

  transition:
    transform 0.3s cubic-bezier(0.25, 1, 0.5, 1),
    background 0.3s ease,
    opacity 0.3s ease,
    box-shadow 0.3s ease;
  overflow: hidden;
  white-space: nowrap;
}

/* 水墨印痕伪元素：当 hover 时，仿佛墨香未干，在宣纸边缘向外轻柔地晕染开一缕浅墨痕 */
.writing-desk-seal-stamp::before {
  content: '';
  position: absolute;
  inset: -12px;
  border-radius: 50%;
  /* 极轻微向外渐隐的水墨晕染渐变 */
  background: radial-gradient(circle, rgba(28, 32, 34, 0.25) 0%, rgba(28, 32, 34, 0.08) 50%, rgba(28, 32, 34, 0) 70%);
  transform: scale(0.4);
  opacity: 0;
  z-index: -1;
  pointer-events: none;
  transition:
    transform 0.6s cubic-bezier(0.16, 1, 0.3, 1),
    opacity 0.5s ease;
}

/* 闲章 Hover 时：保持宽度恒定，仅作优雅缩放并显金泥温润流光 */
.writing-desk-seal-stamp:hover {
  transform: scale(1.08);
  opacity: 0.98;
  background: linear-gradient(135deg, #d4433b 0%, #b83c32 50%, #b02c25 100%);
  box-shadow:
    -2px 3px 8px rgba(107, 21, 16, 0.35),
    inset 1px 1px 1px rgba(255, 255, 255, 0.2);
}

.writing-desk-seal-stamp:hover::before {
  transform: scale(2.2); /* 墨晕在宣纸上优雅晕散 */
  opacity: 1;
}

/* 阴刻古朴篆字 */
.stamp-seal-char {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  border-radius: var(--md-radius-xs);

  /* 白文阴刻金石托底，使文字如同在章体上镂空透出底部的宣纸暖白 */
  background-color: rgba(28, 32, 34, 0.15);
  color: #faf6ed !important; /* 古香古色的泥金白文 */
  font-family: var(--md-font-serif);
  font-size: 13px;
  font-weight: 800;
  text-shadow: 1px 1px 1px rgba(107, 21, 16, 0.5);
  border: 1px dashed rgba(250, 246, 237, 0.18);
  box-shadow: inset 1px 1px 0px rgba(28, 32, 34, 0.18);
  transition: transform 0.4s cubic-bezier(0.25, 1, 0.5, 1);
}

.writing-desk-seal-stamp:hover .stamp-seal-char {
  transform: scale(1.08) rotate(15deg); /* 悬停时篆字微偏，增添意趣 */
}

/* 移动端/窄屏响应式适配：精美贴合于右下角 */
@media (max-width: 1199px) {
  .writing-desk-seal-stamp {
    top: auto;
    bottom: 30px; /* 贴靠右下角 */
    right: 0;
    width: 38px;
    height: 38px;
    border-radius: 6px 0 0 6px / 8px 0 0 8px;
    box-shadow: -2px 2px 6px rgba(107, 21, 16, 0.3);
  }

  .writing-desk-seal-stamp:hover {
    width: 38px;
    border-radius: 6px 0 0 6px / 8px 0 0 8px;
    transform: scale(1.05); /* 仅做轻微点击缩放提示 */
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
