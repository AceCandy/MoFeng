// AIMETA P=写作台当前章节查询派生|R=章节实体_大纲_最近完成章|NR=不镜像工作流状态_不持有mutation状态|E=composable:writing-desk-chapter-state|X=internal|A=useWritingDeskChapterState|D=vue,@tanstack/vue-query|S=cache|RD=./README.ai
import { computed } from 'vue'
import type { ComputedRef, Ref } from 'vue'
import type { NovelProject } from '@/api/novel'
import { useNovelChapterQuery } from '@/queries/novel'

interface UseWritingDeskChapterStateOptions {
  project: ComputedRef<NovelProject | null>
  selectedChapterNumber: Ref<number | null>
  chapterQuery: ReturnType<typeof useNovelChapterQuery>
}

/**
 * 写作台当前章节的派生状态。
 *
 * 从 WritingDesk.vue 抽出（行为逐行等价）。集中维护由「选中章节 + 项目数据」派生的
 * 状态：当前章节对象、章节大纲与最近完成章节号。工作流交互状态只由 XState actor
 * 持有，不能从 generation_status 或 mutation pending 再构造本地镜像。
 */
export const useWritingDeskChapterState = ({
  project,
  selectedChapterNumber,
  chapterQuery,
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
    selectedChapterOutline,
    latestCompletedChapterNumber,
  }
}
