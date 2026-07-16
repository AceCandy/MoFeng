import { computed, ref } from 'vue'
import type { ComputedRef, Ref } from 'vue'
import type { NovelProject } from '@/api/novel'
import { useConfirmFinalizeChapterMutation, useNovelChapterQuery } from '@/queries/novel'

interface UseWritingDeskChapterStateOptions {
  project: ComputedRef<NovelProject | null>
  selectedChapterNumber: Ref<number | null>
  chapterQuery: ReturnType<typeof useNovelChapterQuery>
  confirmFinalizeChapterMutation: ReturnType<typeof useConfirmFinalizeChapterMutation>
}

/**
 * 写作台当前章节的派生状态。
 *
 * 从 WritingDesk.vue 抽出（行为逐行等价）。集中维护由「选中章节 + 项目数据」派生的
 * 状态：当前章节对象、版本选择器可见性、评审中章节号、定稿选择中标志、章节大纲、
 * 最近完成章节号。这些 computed 共享 project/selectedChapterNumber/chapterQuery 三个
 * 响应式源，内聚度高；evaluatingChapter ref 仅 activeEvaluatingChapter 消费，故同入本块。
 */
export const useWritingDeskChapterState = ({
  project,
  selectedChapterNumber,
  chapterQuery,
  confirmFinalizeChapterMutation,
}: UseWritingDeskChapterStateOptions) => {
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

  const evaluatingChapter = ref<number | null>(null)

  const activeEvaluatingChapter = computed(() => {
    return (
      evaluatingChapter.value ??
      (selectedChapter.value?.generation_status === 'evaluating'
        ? selectedChapter.value.chapter_number
        : null)
    )
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

  return {
    selectedChapter,
    showVersionSelector,
    evaluatingChapter,
    activeEvaluatingChapter,
    isSelectingVersion,
    selectedChapterOutline,
    latestCompletedChapterNumber,
  }
}
