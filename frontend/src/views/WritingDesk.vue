<!-- AIMETA P=写作台_章节编辑主页面|R=写作界面_章节管理|NR=不含详情展示|E=route:/novel/:id#component:WritingDesk|X=ui|A=写作台|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div class="writing-desk-page flex flex-col overflow-hidden">
    <WDHeader
      :project="project"
      :progress="progress"
      :completed-chapters="completedChapters"
      :total-chapters="totalChapters"
      :has-incomplete-chapters="hasIncompleteChapters"
      @go-back="goBack"
      @view-project-detail="viewProjectDetail"
      @toggle-sidebar="toggleSidebar"
      @locate-incomplete="locateFirstIncompleteChapter"
    />

    <!-- 主要内容区域 -->
    <div class="flex-1 w-full px-4 sm:px-6 lg:px-8 py-6 overflow-hidden">
      <!-- 加载状态 -->
      <div v-if="novelStore.isLoading" class="h-full flex justify-center items-center">
        <div class="text-center">
          <div class="md-spinner mx-auto mb-4"></div>
          <p class="md-body-medium md-on-surface-variant">正在加载项目数据...</p>
        </div>
      </div>

      <!-- 错误状态 -->
      <div v-else-if="novelStore.error" class="text-center py-20">
        <div class="md-card md-card-outlined p-8 max-w-md mx-auto" style="border-radius: var(--md-radius-xl);">
          <div class="w-12 h-12 rounded-full mx-auto mb-4 flex items-center justify-center" style="background-color: var(--md-error-container);">
            <svg class="w-6 h-6" style="color: var(--md-error);" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd"></path>
            </svg>
          </div>
          <h3 class="md-title-large mb-2" style="color: var(--md-on-surface);">加载失败</h3>
          <p class="md-body-medium mb-4" style="color: var(--md-error);">{{ novelStore.error }}</p>
          <button @click="loadProject" class="md-btn md-btn-tonal md-ripple">重新加载</button>
        </div>
      </div>

      <!-- 主要内容 -->
      <div v-else-if="project" class="h-full flex gap-6">
        <WDSidebar
          ref="sidebarRef"
          :project="project"
          :sidebar-open="sidebarOpen"
          :selected-chapter-number="selectedChapterNumber"
          :generating-chapter="generatingChapter"
          :evaluating-chapter="evaluatingChapter"
          :is-generating-outline="isGeneratingOutline"
          @close-sidebar="closeSidebar"
          @select-chapter="selectChapter"
          @generate-chapter="generateChapter"
          @edit-chapter="openEditChapterModal"
          @delete-chapter="deleteChapter"
          @generate-outline="generateOutline"
        />

        <div class="flex-1 min-w-0">
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
          @show-evaluation-detail="showEvaluationDetailModal = true"
          @fetch-chapter-status="fetchChapterStatus"
          @edit-chapter="editChapterContent"
          />
        </div>
      </div>
    </div>
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
        <div class="md-dialog m3-result-dialog flex flex-col">
          <div class="p-6 border-b" style="border-bottom-color: var(--md-outline-variant);">
            <div class="flex items-center justify-between gap-4">
              <div>
                <h3 class="md-headline-small font-semibold">评审优化结果预览</h3>
                <p class="md-body-small md-on-surface-variant mt-1">{{ recommendedOptimizeResultNotes }}</p>
              </div>
              <button
                @click="closeRecommendedOptimizeResult"
                :disabled="isApplyingRecommendedOptimization"
                class="md-icon-btn md-ripple disabled:opacity-50"
              >
                <svg class="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"></path>
                </svg>
              </button>
            </div>
          </div>
          <div class="flex-1 overflow-y-auto p-6">
            <div class="whitespace-pre-wrap leading-relaxed" style="color: var(--md-on-surface);">
              <p v-for="(paragraph, index) in recommendedOptimizedParagraphs" :key="`recommended-optimized-${index}`" class="mb-4 last:mb-0">{{ paragraph }}</p>
            </div>
          </div>
          <div class="p-6 border-t flex items-center justify-end gap-3" style="border-top-color: var(--md-outline-variant); background-color: var(--md-surface-container-low);">
            <div class="md-body-small md-on-surface-variant mr-auto">
              {{ recommendedOptimizedWordCount }} 字
            </div>
            <button
              @click="closeRecommendedOptimizeResult"
              :disabled="isApplyingRecommendedOptimization"
              class="md-btn md-btn-outlined md-ripple disabled:opacity-50"
            >
              取消
            </button>
            <button
              @click="applyRecommendedOptimization"
              :disabled="isApplyingRecommendedOptimization"
              class="md-btn md-btn-filled md-ripple disabled:opacity-50 flex items-center gap-2"
              style="background-color: var(--md-success); color: var(--md-on-success);"
            >
              <svg v-if="isApplyingRecommendedOptimization" class="w-4 h-4 animate-spin" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd"></path>
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
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useNovelStore } from '@/stores/novel'
import { OptimizerAPI } from '@/api/novel'
import type { Chapter, ChapterOutline, ChapterGenerationResponse, ChapterVersion } from '@/api/novel'
import { globalAlert } from '@/composables/useAlert'
import { countNonWhitespaceChars } from '@/utils/text'
import WDHeader from '@/components/writing-desk/WDHeader.vue'
import WDSidebar from '@/components/writing-desk/WDSidebar.vue'
import WDWorkspace from '@/components/writing-desk/WDWorkspace.vue'
import WDVersionDetailModal from '@/components/writing-desk/WDVersionDetailModal.vue'
import WDEvaluationDetailModal from '@/components/writing-desk/WDEvaluationDetailModal.vue'
import WDEditChapterModal from '@/components/writing-desk/WDEditChapterModal.vue'
import WDGenerateOutlineModal from '@/components/writing-desk/WDGenerateOutlineModal.vue'

interface Props {
  id: string
}

const props = defineProps<Props>()
const router = useRouter()
const novelStore = useNovelStore()

// 状态管理
const selectedChapterNumber = ref<number | null>(null)
const chapterGenerationResult = ref<ChapterGenerationResponse | null>(null)
const selectedVersionIndex = ref<number>(0)
const generatingChapter = ref<number | null>(null)
const sidebarOpen = ref(false)
const sidebarRef = ref<InstanceType<typeof WDSidebar> | null>(null)
const showVersionDetailModal = ref(false)
const detailVersionIndex = ref<number>(0)
const showEvaluationDetailModal = ref(false)
const showEditChapterModal = ref(false)
const editingChapter = ref<ChapterOutline | null>(null)
const isGeneratingOutline = ref(false)
const showGenerateOutlineModal = ref(false)
const isFetchingChapterStatus = ref(false)
const isOptimizingRecommendedVersion = ref(false)
const showRecommendedOptimizeResultModal = ref(false)
const isApplyingRecommendedOptimization = ref(false)
const recommendedOptimizedContent = ref('')
const recommendedOptimizeResultNotes = ref('')

// 计算属性
const project = computed(() => novelStore.currentProject)

const selectedChapter = computed(() => {
  if (!project.value || selectedChapterNumber.value === null) return null
  return project.value.chapters.find(ch => ch.chapter_number === selectedChapterNumber.value) || null
})

const showVersionSelector = computed(() => {
  if (!selectedChapter.value) return false
  const status = selectedChapter.value.generation_status
  return status === 'waiting_for_confirm' || status === 'evaluating' || status === 'evaluation_failed' || status === 'selecting'
})

const evaluatingChapter = computed(() => {
  if (selectedChapter.value?.generation_status === 'evaluating') {
    return selectedChapter.value.chapter_number
  }
  return null
})

const isSelectingVersion = computed(() => {
  return selectedChapter.value?.generation_status === 'selecting'
})

const selectedChapterOutline = computed(() => {
  if (!project.value?.blueprint?.chapter_outline || selectedChapterNumber.value === null) return null
  return project.value.blueprint.chapter_outline.find(ch => ch.chapter_number === selectedChapterNumber.value) || null
})

const progress = computed(() => {
  if (!project.value?.blueprint?.chapter_outline) return 0
  const totalChapters = project.value.blueprint.chapter_outline.length
  const completedChapters = project.value.chapters.filter(ch => ch.content).length
  return Math.round((completedChapters / totalChapters) * 100)
})

const totalChapters = computed(() => {
  return project.value?.blueprint?.chapter_outline?.length || 0
})

const completedChapters = computed(() => {
  return project.value?.chapters?.filter(ch => ch.content)?.length || 0
})

const hasIncompleteChapters = computed(() => {
  if (!project.value?.blueprint?.chapter_outline) return false
  return project.value.blueprint.chapter_outline.some((outline) => {
    const chapter = project.value?.chapters.find(ch => ch.chapter_number === outline.chapter_number)
    return chapter?.generation_status !== 'successful'
  })
})

const isCurrentVersion = (versionIndex: number) => {
  if (!selectedChapter.value?.content || !availableVersions.value?.[versionIndex]?.content) return false

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
  cleaned = cleaned.replace(/\\n/g, '\n')  // 换行符
  cleaned = cleaned.replace(/\\"/g, '"')   // 引号
  cleaned = cleaned.replace(/\\t/g, '\t')  // 制表符
  cleaned = cleaned.replace(/\\\\/g, '\\') // 反斜杠

  return cleaned
}

const canGenerateChapter = (chapterNumber: number) => {
  if (!project.value?.blueprint?.chapter_outline) return false

  // 检查前面所有章节是否都已成功生成
  const outlines = project.value.blueprint.chapter_outline.sort((a, b) => a.chapter_number - b.chapter_number)
  
  for (const outline of outlines) {
    if (outline.chapter_number >= chapterNumber) break
    
    const chapter = project.value?.chapters.find(ch => ch.chapter_number === outline.chapter_number)
    if (!chapter || chapter.generation_status !== 'successful') {
      return false // 前面有章节未完成
    }
  }

  // 检查当前章节是否已经完成
  const currentChapter = project.value?.chapters.find(ch => ch.chapter_number === chapterNumber)
  if (currentChapter && currentChapter.generation_status === 'successful') {
    return true // 已完成的章节可以重新生成
  }

  return true // 前面章节都完成了，可以生成当前章节
}

const isChapterFailed = (chapterNumber: number) => {
  if (!project.value?.chapters) return false
  const chapter = project.value.chapters.find(ch => ch.chapter_number === chapterNumber)
  return chapter && chapter.generation_status === 'failed'
}

const hasChapterInProgress = (chapterNumber: number) => {
  if (!project.value?.chapters) return false
  const chapter = project.value.chapters.find(ch => ch.chapter_number === chapterNumber)
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

  const likelyJson = (
    (trimmed.startsWith('{') && trimmed.endsWith('}'))
    || (trimmed.startsWith('[') && trimmed.endsWith(']'))
  )
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
  if (Array.isArray(chapterGenerationResult.value?.versions) && chapterGenerationResult.value.versions.length > 0) {
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
          style: '标准'
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
    .map(paragraph => paragraph.trim())
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
    return fragment
      .replace(/\\"/g, '"')
      .replace(/\\n/g, '\n')
      .replace(/\\t/g, '\t')
  }
}

const extractJsonField = (rawText: string, field: 'optimized_content' | 'optimization_notes'): string | null => {
  const pattern = new RegExp(`"${field}"\\s*:\\s*"((?:\\\\.|[^"\\\\])*)"`, 's')
  const match = rawText.match(pattern)
  if (!match?.[1]) return null
  return decodeJsonStringFragment(match[1])
}

const normalizeOptimizeResult = (
  contentRaw: string,
  notesRaw: string
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
    notes: notes || '优化完成'
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
  isOptimizingRecommendedVersion.value = true

  try {
    const result = await OptimizerAPI.optimizeRecommendedVersion({
      project_id: project.value.id,
      chapter_number: selectedChapter.value.chapter_number,
      source_content: cleanVersionContent(sourceVersion.content),
      review_summary: String(evaluationPayload.reason_for_choice || '').trim(),
      version_number: bestChoice,
      version_review: versionReview
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
  } finally {
    isOptimizingRecommendedVersion.value = false
  }
}

const applyRecommendedOptimization = async () => {
  if (!project.value || !selectedChapter.value || !recommendedOptimizedContent.value.trim()) {
    return
  }

  isApplyingRecommendedOptimization.value = true

  try {
    const applyResult = await OptimizerAPI.applyOptimization(
      project.value.id,
      selectedChapter.value.chapter_number,
      recommendedOptimizedContent.value
    )

    const syncStats = applyResult.foreshadowing_sync
    if (syncStats) {
      globalAlert.showSuccess(
        `优化内容已应用，伏笔同步：新增 ${syncStats.created}，推进 ${syncStats.developing}，回收 ${syncStats.revealed}`
      )
    } else {
      globalAlert.showSuccess('优化内容已应用')
    }

    showRecommendedOptimizeResultModal.value = false
    showEvaluationDetailModal.value = false
    recommendedOptimizedContent.value = ''
    recommendedOptimizeResultNotes.value = ''
    await novelStore.loadChapter(selectedChapter.value.chapter_number)
  } catch (error: any) {
    console.error('应用评审优化失败:', error)
    globalAlert.showError(error.message || '应用优化失败，请稍后重试')
  } finally {
    isApplyingRecommendedOptimization.value = false
  }
}


// 方法
const goBack = () => {
  router.push('/workspace')
}

const viewProjectDetail = () => {
  if (project.value) {
    router.push(`/projects/${project.value.id}`)
  }
}

const toggleSidebar = () => {
  sidebarOpen.value = !sidebarOpen.value
}

const closeSidebar = () => {
  sidebarOpen.value = false
}

const locateFirstIncompleteChapter = () => {
  sidebarRef.value?.scrollToFirstIncompleteChapter()
}

const loadProject = async () => {
  try {
    await novelStore.loadProject(props.id)
  } catch (error) {
    console.error('加载项目失败:', error)
  }
}

const fetchChapterStatus = async () => {
  if (selectedChapterNumber.value === null || isFetchingChapterStatus.value) {
    return
  }
  const chapterNumber = selectedChapterNumber.value
  isFetchingChapterStatus.value = true
  try {
    await novelStore.loadChapter(chapterNumber)
    console.log('Chapter status polled and updated.')
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
  closeSidebar()
}

const generateChapter = async (chapterNumber: number) => {
  // 检查是否可以生成该章节
  if (!canGenerateChapter(chapterNumber) && !isChapterFailed(chapterNumber) && !hasChapterInProgress(chapterNumber)) {
    globalAlert.showError('请按顺序生成章节，先完成前面的章节', '生成受限')
    return
  }

  try {
    generatingChapter.value = chapterNumber
    selectedChapterNumber.value = chapterNumber
    const nowIso = new Date().toISOString()

    // 在本地更新章节状态为generating
    if (project.value?.chapters) {
      const chapter = project.value.chapters.find(ch => ch.chapter_number === chapterNumber)
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
        const outline = project.value.blueprint?.chapter_outline?.find(o => o.chapter_number === chapterNumber)
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
          status_updated_at: nowIso
        } as Chapter)
      }
    }

    await novelStore.generateChapter(chapterNumber)
    // 关键兜底：生成接口在极少数情况下可能返回旧快照，这里强制拉取当前章最新状态。
    await novelStore.loadChapter(chapterNumber)

    // store 中的 project 已经被更新，所以我们不需要手动修改本地状态。
    // 单版本场景自动确认，直接进入正文视图。
    const generatedChapter = project.value?.chapters.find(ch => ch.chapter_number === chapterNumber)
    const generatedVersions = Array.isArray(generatedChapter?.versions) ? generatedChapter.versions : []
    const validVersionCount = generatedVersions
      .map((versionRaw) => extractVersionContent(versionRaw))
      .filter((content) => Boolean(content.trim()))
      .length

    if (generatedChapter?.generation_status === 'waiting_for_confirm' && validVersionCount === 1) {
      selectedVersionIndex.value = 0
      // 单版本自动确认阶段已进入“确认版本”流程，不应再被当作“生成中”渲染。
      generatingChapter.value = null
      await selectVersion(0, {
        chapterNumber,
        suppressSuccessToast: true,
        skipAvailabilityCheck: true
      })
      globalAlert.showSuccess('唯一版本已自动确认，已进入正文', '生成成功')
    } else {
      // 非单版本场景保留版本选择流程
      chapterGenerationResult.value = null
      selectedVersionIndex.value = 0
    }
  } catch (error) {
    console.error('生成章节失败:', error)

    // 错误状态的本地更新仍然是必要的，以立即反映UI
    if (project.value?.chapters) {
      const chapter = project.value.chapters.find(ch => ch.chapter_number === chapterNumber)
      if (chapter) {
        chapter.generation_status = 'failed'
        chapter.status_updated_at = new Date().toISOString()
      }
    }

    globalAlert.showError(`生成章节失败: ${error instanceof Error ? error.message : '未知错误'}`, '生成失败')
  } finally {
    generatingChapter.value = null
  }
}

const regenerateChapter = async () => {
  if (selectedChapterNumber.value !== null) {
    await generateChapter(selectedChapterNumber.value)
  }
}

const selectVersion = async (
  versionIndex: number,
  options: { chapterNumber?: number; suppressSuccessToast?: boolean; skipAvailabilityCheck?: boolean } = {}
) => {
  const targetChapterNumber = options.chapterNumber ?? selectedChapterNumber.value
  if (targetChapterNumber === null) {
    return
  }
  if (!options.skipAvailabilityCheck && !availableVersions.value?.[versionIndex]?.content) {
    return
  }

  try {
    // 在本地立即更新状态以反映UI
    if (project.value?.chapters) {
      const chapter = project.value.chapters.find(ch => ch.chapter_number === targetChapterNumber)
      if (chapter) {
        chapter.generation_status = 'selecting'
      }
    }

    selectedVersionIndex.value = versionIndex
    await novelStore.selectChapterVersion(targetChapterNumber, versionIndex)
    // 兜底同步：避免后端响应中正文字段短暂滞后导致界面需手动刷新。
    await novelStore.loadChapter(targetChapterNumber)

    // 状态更新将由 store 自动触发，本地无需手动更新
    // 轮询机制会处理状态变更，成功后会自动隐藏选择器
    // showVersionSelector.value = false
    chapterGenerationResult.value = null
    if (!options.suppressSuccessToast) {
      globalAlert.showSuccess('版本已确认', '操作成功')
    }
  } catch (error) {
    console.error('选择章节版本失败:', error)
    // 错误状态下恢复章节状态
    if (project.value?.chapters) {
      const chapter = project.value.chapters.find(ch => ch.chapter_number === targetChapterNumber)
      if (chapter) {
        chapter.generation_status = 'waiting_for_confirm' // Or the previous state
      }
    }
    globalAlert.showError(`选择章节版本失败: ${error instanceof Error ? error.message : '未知错误'}`, '选择失败')
  }
}

// 从详情弹窗中选择版本
const selectVersionFromDetail = async () => {
  selectedVersionIndex.value = detailVersionIndex.value
  await selectVersion(detailVersionIndex.value)
  closeVersionDetail()
}

const confirmVersionSelection = async () => {
  await selectVersion(selectedVersionIndex.value)
}

const openEditChapterModal = (chapter: ChapterOutline) => {
  editingChapter.value = chapter
  showEditChapterModal.value = true
}

const saveChapterChanges = async (updatedChapter: ChapterOutline) => {
  try {
    await novelStore.updateChapterOutline(updatedChapter)
    globalAlert.showSuccess('章节大纲已更新', '保存成功')
  } catch (error) {
    console.error('更新章节大纲失败:', error)
    globalAlert.showError(`更新章节大纲失败: ${error instanceof Error ? error.message : '未知错误'}`, '保存失败')
  } finally {
    showEditChapterModal.value = false
  }
}

const evaluateChapter = async () => {
  if (selectedChapterNumber.value !== null) {
    // 保存原始状态，用于失败时恢复
    let previousStatus: "not_generated" | "generating" | "evaluating" | "selecting" | "failed" | "evaluation_failed" | "waiting_for_confirm" | "successful" | undefined
    
    try {
      // 在本地更新章节状态为evaluating以立即反映在UI上
      if (project.value?.chapters) {
        const chapter = project.value.chapters.find(ch => ch.chapter_number === selectedChapterNumber.value)
        if (chapter) {
          previousStatus = chapter.generation_status // 保存原状态
          chapter.generation_status = 'evaluating'
        }
      }
      await novelStore.evaluateChapter(selectedChapterNumber.value)
      
      // 评审完成后，状态会通过store和轮询更新，这里不需要额外操作
      globalAlert.showSuccess('章节评审结果已生成', '评审成功')
    } catch (error) {
      console.error('评审章节失败:', error)
      
      // 错误状态下恢复章节状态为原始状态
      if (project.value?.chapters) {
        const chapter = project.value.chapters.find(ch => ch.chapter_number === selectedChapterNumber.value)
        if (chapter && previousStatus) {
          chapter.generation_status = previousStatus // 恢复为原状态
        }
      }
      
      globalAlert.showError(`评审章节失败: ${error instanceof Error ? error.message : '未知错误'}`, '评审失败')
    }
  }
}

const deleteChapter = async (chapterNumbers: number | number[]) => {
  const numbersToDelete = Array.isArray(chapterNumbers) ? chapterNumbers : [chapterNumbers]
  const confirmationMessage = numbersToDelete.length > 1
    ? `您确定要删除选中的 ${numbersToDelete.length} 个章节吗？这个操作无法撤销。`
    : `您确定要删除第 ${numbersToDelete[0]} 章吗？这个操作无法撤销。`

  if (window.confirm(confirmationMessage)) {
    try {
      await novelStore.deleteChapter(numbersToDelete)
      globalAlert.showSuccess('章节已删除', '操作成功')
      // If the currently selected chapter was deleted, unselect it
      if (selectedChapterNumber.value && numbersToDelete.includes(selectedChapterNumber.value)) {
        selectedChapterNumber.value = null
      }
    } catch (error) {
      console.error('删除章节失败:', error)
      globalAlert.showError(`删除章节失败: ${error instanceof Error ? error.message : '未知错误'}`, '删除失败')
    }
  }
}

const generateOutline = async () => {
  showGenerateOutlineModal.value = true
}

const editChapterContent = async (data: { chapterNumber: number, content: string }) => {
  if (!project.value) return

  try {
    await novelStore.editChapterContent(project.value.id, data.chapterNumber, data.content)
    globalAlert.showSuccess('章节内容已更新', '保存成功')
  } catch (error) {
    console.error('编辑章节内容失败:', error)
    globalAlert.showError(`编辑章节内容失败: ${error instanceof Error ? error.message : '未知错误'}`, '保存失败')
  }
}

const handleGenerateOutline = async (numChapters: number) => {
  if (!project.value) return
  isGeneratingOutline.value = true
  try {
    const startChapter = (project.value.blueprint?.chapter_outline?.length || 0) + 1
    await novelStore.generateChapterOutline(startChapter, numChapters)
    globalAlert.showSuccess('新的章节大纲已生成', '操作成功')
  } catch (error) {
    console.error('生成大纲失败:', error)
    globalAlert.showError(`生成大纲失败: ${error instanceof Error ? error.message : '未知错误'}`, '生成失败')
  } finally {
    isGeneratingOutline.value = false
  }
}

onMounted(() => {
  loadProject()
})
</script>

<style scoped>
.writing-desk-page {
  min-height: calc(100vh - 112px);
  background-color: var(--md-surface-dim);
  color: var(--md-on-surface);
  font-family: var(--md-font-family);
  animation: m3-fade 0.6s ease-out both;
}

@media (prefers-reduced-motion: reduce) {
  .writing-desk-page {
    animation: none;
  }
}

.m3-result-dialog {
  max-width: min(900px, calc(100vw - 32px));
  max-height: calc(100vh - 32px);
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

/* 自定义滚动条 */
::-webkit-scrollbar {
  width: 6px;
}

::-webkit-scrollbar-track {
  background: var(--md-surface-container);
  border-radius: 3px;
}

::-webkit-scrollbar-thumb {
  background: var(--md-outline);
  border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
  background: var(--md-on-surface-variant);
}

/* 动画效果 */
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
