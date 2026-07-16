import { computed, type ComputedRef } from 'vue'
import type { Chapter, ChapterVersion, NovelProject } from '@/api/novel'
import WorkspaceInitial from '@/components/writing-desk/workspace/WorkspaceInitial.vue'
import ChapterGenerating from '@/components/writing-desk/workspace/ChapterGenerating.vue'
import VersionSelector from '@/components/writing-desk/workspace/VersionSelector.vue'
import ChapterContent from '@/components/writing-desk/workspace/ChapterContent.vue'
import ChapterFailed from '@/components/writing-desk/workspace/ChapterFailed.vue'
import ChapterEmpty from '@/components/writing-desk/workspace/ChapterEmpty.vue'

// useChapterStatus 只消费的 props 子集（结构同构于 WDWorkspaceProps）
interface ChapterStatusProps {
  selectedChapterNumber: number | null
  evaluatingChapter: number | null
  generatingChapter: number | null
  availableVersions: ChapterVersion[]
  project: NovelProject | null
}

interface UseChapterStatusOptions {
  props: ChapterStatusProps
  selectedChapter: ComputedRef<Chapter | null>
  hasSelectedChapterContent: ComputedRef<boolean>
  lockedPrerequisiteChapterNumber: ComputedRef<number | null>
  isFinalizedSuccessful: ComputedRef<boolean>
  isDraftWaitingConfirm: ComputedRef<boolean>
}

// 章节状态判定 + 组件分发：给定选中章节与生成状态，派生状态标签/工具栏可见性/当前应渲染的子组件。
// currentComponentProps（数据装配，耦合朗读控件 ref 与锁定前置标题）留组件，本 composable 只负责「判定 + 分发」。
export function useChapterStatus(options: UseChapterStatusOptions) {
  const {
    props,
    selectedChapter,
    hasSelectedChapterContent,
    lockedPrerequisiteChapterNumber,
    isFinalizedSuccessful,
    isDraftWaitingConfirm,
  } = options

  const isSelectedChapterLocked = computed(() => {
    if (props.selectedChapterNumber === null) return false
    if (lockedPrerequisiteChapterNumber.value === null) return false
    if (hasSelectedChapterContent.value) return false
    const status = selectedChapter.value?.generation_status
    return status !== 'failed' && status !== 'evaluation_failed' && status !== 'waiting_for_confirm'
  })

  const shouldShowChapterToolbar = computed(() => {
    if (isSelectedChapterLocked.value) return false
    return isFinalizedSuccessful.value || isDraftWaitingConfirm.value
  })

  const chapterStatusLabel = computed(() => {
    const status = props.evaluatingChapter === props.selectedChapterNumber
      ? 'evaluating'
      : selectedChapter.value?.generation_status
    switch (status) {
      case 'successful':
        return '已完成'
      case 'generating':
        return '生成中'
      case 'evaluating':
        return '评审中'
      case 'selecting':
        return '选择版本'
      case 'finalizing':
        return '定稿中'
      case 'waiting_for_confirm':
        return '待确认'
      case 'failed':
        return '生成失败'
      case 'evaluation_failed':
        return '评审失败'
      default:
        return '待开始'
    }
  })

  const chapterStatusTone = computed(() => {
    const status = props.evaluatingChapter === props.selectedChapterNumber
      ? 'evaluating'
      : selectedChapter.value?.generation_status
    if (status === 'successful') return 'success'
    if (status === 'failed' || status === 'evaluation_failed') return 'error'
    if (status === 'generating' || status === 'evaluating' || status === 'selecting' || status === 'finalizing') return 'progress'
    if (status === 'waiting_for_confirm') return 'pending'
    return 'idle'
  })

  const isChapterGenerating = (chapterNumber: number) => {
    if (!props.project?.chapters) return false
    const chapter = props.project.chapters.find((ch) => ch.chapter_number === chapterNumber)
    return chapter && chapter.generation_status === 'generating'
  }

  const isSelectedChapterGeneratingLike = computed(() => {
    if (props.selectedChapterNumber === null) return false
    return (
      props.generatingChapter === props.selectedChapterNumber ||
      isChapterGenerating(props.selectedChapterNumber)
    )
  })

  const isChapterFailed = (chapterNumber: number) => {
    if (!props.project?.chapters) return false
    const chapter = props.project.chapters.find((ch) => ch.chapter_number === chapterNumber)
    return chapter?.generation_status === 'failed'
  }

  const isChapterEvaluationFailed = (chapterNumber: number) => {
    if (!props.project?.chapters) return false
    const chapter = props.project.chapters.find((ch) => ch.chapter_number === chapterNumber)
    return chapter?.generation_status === 'evaluation_failed'
  }

  const isInProgressStatus = (status: Chapter['generation_status'] | null | undefined) => {
    return status === 'generating' || status === 'evaluating' || status === 'selecting' || status === 'finalizing'
  }

  const isGeneratingInFlight = computed(() => {
    if (props.selectedChapterNumber === null) return false
    if (props.generatingChapter !== props.selectedChapterNumber) return false

    // Regenerating a completed chapter can briefly keep backend status as `successful`
    // before the async pipeline updates to `generating`.
    // Keep showing progress UI while local request is still in-flight.
    const status = selectedChapter.value?.generation_status
    return !(status === 'waiting_for_confirm' || status === 'selecting')
  })

  const canGenerateChapter = (chapterNumber: number | null) => {
    if (chapterNumber === null || !props.project?.blueprint?.chapter_outline) return false

    const outlines = props.project.blueprint.chapter_outline.sort(
      (a, b) => a.chapter_number - b.chapter_number,
    )

    for (const outline of outlines) {
      if (outline.chapter_number >= chapterNumber) break

      const chapter = props.project?.chapters.find(
        (ch) => ch.chapter_number === outline.chapter_number,
      )
      if (!chapter || chapter.generation_status !== 'successful') {
        return false
      }
    }

    const currentChapter = props.project?.chapters.find((ch) => ch.chapter_number === chapterNumber)
    if (currentChapter && currentChapter.generation_status === 'successful') {
      return true
    }

    return true
  }

  const currentComponent = computed(() => {
    if (props.selectedChapterNumber === null) {
      return WorkspaceInitial
    }

    const status = props.evaluatingChapter === props.selectedChapterNumber
      ? 'evaluating'
      : selectedChapter.value?.generation_status
    const shouldRenderGenerating =
      (isInProgressStatus(status) || isGeneratingInFlight.value || status === 'failed' || status === 'evaluation_failed') &&
      !(status === 'successful' && hasSelectedChapterContent.value)
    if (shouldRenderGenerating) {
      return ChapterGenerating // Use a generic "in-progress" component
    }

    if (status === 'waiting_for_confirm') {
      if (hasSelectedChapterContent.value) {
        return ChapterContent
      }
      return VersionSelector
    }

    // 仅在不处于选版态时展示正文，避免生成完成后看不到新版本选择区。
    if (hasSelectedChapterContent.value) {
      return ChapterContent
    }

    if (isChapterFailed(props.selectedChapterNumber)) {
      return ChapterFailed
    }
    return ChapterEmpty
  })

  const isChapterContentView = computed(
    () => currentComponent.value === ChapterContent && hasSelectedChapterContent.value,
  )
  const canViewVersions = computed(() => props.availableVersions.length > 0)
  const isAiMenuDisabled = computed(
    () => isSelectedChapterGeneratingLike.value && !isChapterContentView.value,
  )

  return {
    isSelectedChapterLocked,
    shouldShowChapterToolbar,
    chapterStatusLabel,
    chapterStatusTone,
    isChapterGenerating,
    isSelectedChapterGeneratingLike,
    isChapterFailed,
    isChapterEvaluationFailed,
    isInProgressStatus,
    isGeneratingInFlight,
    canGenerateChapter,
    currentComponent,
    isChapterContentView,
    canViewVersions,
    isAiMenuDisabled,
  }
}
