import { computed, type ComputedRef, type Ref } from 'vue'
import type {
  Chapter,
  ChapterGenerationResponse,
  ChapterOutline,
  ChapterVersion,
  NovelProject,
} from '@/api/novel'
import { cleanVersionContent } from '@/utils/chapter'

// useChapterBodyProps 只消费的 props 子集（结构同构于 WDWorkspaceProps）
interface BodyProps {
  selectedChapterNumber: number | null
  evaluatingChapter: number | null
  generatingChapter: number | null
  availableVersions: ChapterVersion[]
  selectedVersionIndex: number
  isSelectingVersion?: boolean
  chapterGenerationResult: ChapterGenerationResponse | null
  project: NovelProject | null
}

interface UseChapterBodyPropsOptions {
  props: BodyProps
  selectedChapter: ComputedRef<Chapter | null>
  selectedChapterOutline: ComputedRef<ChapterOutline | null>
  selectedChapterForDisplay: ComputedRef<Chapter | null>
  selectedChapterResolvedContent: ComputedRef<string>
  hasSelectedChapterContent: ComputedRef<boolean>
  readerCurrentParagraphIndex: Readonly<Ref<number>>
  readerCurrentParagraphEnd: Readonly<Ref<number>>
  lockedPrerequisiteChapterNumber: ComputedRef<number | null>
  lockedPrerequisiteChapterTitle: ComputedRef<string | null>
  isInProgressStatus: (status: Chapter['generation_status'] | null | undefined) => boolean
  isGeneratingInFlight: ComputedRef<boolean>
  isChapterFailed: (chapterNumber: number) => boolean
  isChapterEvaluationFailed: (chapterNumber: number) => boolean
  canGenerateChapter: (chapterNumber: number | null) => boolean
}

/**
 * 章节正文区动态组件的 props 装配。
 *
 * 从 WDWorkspace.vue 抽出（行为逐行等价）。依据选中章节的生成状态，为正文区
 * `<component :is="currentComponent">` 与草稿回放 `<ChapterGenerating readOnly>`
 * 装配各自所需的 props。纯 computed，无副作用。
 */
export const useChapterBodyProps = (options: UseChapterBodyPropsOptions) => {
  const {
    props,
    selectedChapter,
    selectedChapterOutline,
    selectedChapterForDisplay,
    selectedChapterResolvedContent,
    hasSelectedChapterContent,
    readerCurrentParagraphIndex,
    readerCurrentParagraphEnd,
    lockedPrerequisiteChapterNumber,
    lockedPrerequisiteChapterTitle,
    isInProgressStatus,
    isGeneratingInFlight,
    isChapterFailed,
    isChapterEvaluationFailed,
    canGenerateChapter,
  } = options

  const currentComponentProps = computed(() => {
    if (props.selectedChapterNumber === null) {
      return {}
    }
    const status = props.evaluatingChapter === props.selectedChapterNumber
      ? 'evaluating'
      : selectedChapter.value?.generation_status
    const isBackendInProgress = isInProgressStatus(status)
    const isFailed = status === 'failed' || status === 'evaluation_failed'
    const shouldRenderGenerating =
      (isBackendInProgress || isGeneratingInFlight.value || isFailed) &&
      !(status === 'successful' && hasSelectedChapterContent.value)
    if (shouldRenderGenerating) {
      // 重试请求仍在途时，忽略旧 failed 快照，避免轮询旧响应把进度条拉回失败节点。
      const renderAsLocalGenerating = isGeneratingInFlight.value && !isBackendInProgress
      const renderStatus = renderAsLocalGenerating ? 'generating' : status
      const generationProgress = renderAsLocalGenerating
        ? 0
        : isBackendInProgress
          ? (selectedChapter.value?.generation_progress ?? null)
          : null
      const generationStep = renderAsLocalGenerating
        ? 'context_prep'
        : isBackendInProgress || isFailed
          ? (selectedChapter.value?.generation_step ?? null)
          : null
      const generationStepIndex = renderAsLocalGenerating
        ? 1
        : isBackendInProgress
          ? (selectedChapter.value?.generation_step_index ?? null)
          : null
      const generationStepTotal = renderAsLocalGenerating
        ? 7
        : isBackendInProgress
          ? (selectedChapter.value?.generation_step_total ?? null)
          : null

      return {
        chapterNumber: props.selectedChapterNumber,
        chapterTitle: selectedChapterOutline.value?.title || '',
        chapterSummary: selectedChapterOutline.value?.summary || '',
        chapterContentPreview: cleanVersionContent(selectedChapter.value?.content || ''),
        status: renderStatus,
        generationProgress,
        generationStep,
        generationStepIndex,
        generationStepTotal,
        generationStartedAt: isBackendInProgress
          ? (selectedChapter.value?.generation_started_at ?? null)
          : null,
        statusUpdatedAt: isBackendInProgress
          ? (selectedChapter.value?.status_updated_at ?? null)
          : null,
        generationTraces: renderAsLocalGenerating
          ? []
          : (selectedChapter.value?.generation_traces ?? []),
        generatingChapter: props.generatingChapter,
        availableVersions: props.availableVersions,
        selectedVersionIndex: props.selectedVersionIndex,
      }
    }

    if (status === 'waiting_for_confirm') {
      if (hasSelectedChapterContent.value) {
        return {
          selectedChapter: selectedChapterForDisplay.value,
          projectId: props.project?.id,
          activeParagraphIndex: readerCurrentParagraphIndex.value,
          activeParagraphEnd: readerCurrentParagraphEnd.value,
        }
      }

      return {
        selectedChapter: selectedChapter.value,
        chapterGenerationResult: props.chapterGenerationResult,
        availableVersions: props.availableVersions,
        selectedVersionIndex: props.selectedVersionIndex,
        isSelectingVersion: props.isSelectingVersion,
        evaluatingChapter: props.evaluatingChapter,
        isEvaluationFailed: isChapterEvaluationFailed(props.selectedChapterNumber),
      }
    }
    if (hasSelectedChapterContent.value) {
      return {
        selectedChapter: selectedChapterForDisplay.value,
        projectId: props.project?.id,
        activeParagraphIndex: readerCurrentParagraphIndex.value,
        activeParagraphEnd: readerCurrentParagraphEnd.value,
      }
    }
    if (isChapterFailed(props.selectedChapterNumber)) {
      return {
        chapterNumber: props.selectedChapterNumber,
        generatingChapter: props.generatingChapter,
        generationStatus: selectedChapter.value?.generation_status ?? 'failed',
        generationStep: selectedChapter.value?.generation_step ?? null,
      }
    }
    return {
      chapterNumber: props.selectedChapterNumber,
      generatingChapter: props.generatingChapter,
      canGenerate: canGenerateChapter(props.selectedChapterNumber),
      lockedPrerequisiteChapterNumber: lockedPrerequisiteChapterNumber.value,
      lockedPrerequisiteChapterTitle: lockedPrerequisiteChapterTitle.value,
      chapterOutline: selectedChapterOutline.value,
      project: props.project,
    }
  })

  const draftTraceReplayProps = computed(() => ({
    chapterNumber: props.selectedChapterNumber,
    chapterTitle: selectedChapterOutline.value?.title || '',
    chapterSummary: selectedChapterOutline.value?.summary || '',
    chapterContentPreview: selectedChapterResolvedContent.value,
    status: selectedChapter.value?.generation_status ?? null,
    generationProgress: selectedChapter.value?.generation_progress ?? null,
    generationStep: selectedChapter.value?.generation_step ?? 'waiting_for_confirm',
    generationStepIndex: selectedChapter.value?.generation_step_index ?? null,
    generationStepTotal: selectedChapter.value?.generation_step_total ?? null,
    generationStartedAt: selectedChapter.value?.generation_started_at ?? null,
    statusUpdatedAt: selectedChapter.value?.status_updated_at ?? null,
    generationTraces: selectedChapter.value?.generation_traces ?? [],
    generatingChapter: props.generatingChapter,
    availableVersions: props.availableVersions,
    selectedVersionIndex: props.selectedVersionIndex,
    readOnly: true,
  }))

  return {
    currentComponentProps,
    draftTraceReplayProps,
  }
}
