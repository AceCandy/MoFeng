import type { ComputedRef, Ref } from 'vue'
import type { Chapter, ChapterGenerationResponse, NovelProject } from '@/api/novel'
import { useConfirmFinalizeChapterMutation } from '@/queries/novel'
import { useWritingDeskProject } from '@/composables/useWritingDeskProject'
import { useWritingDeskVersionDetail } from '@/composables/useWritingDeskVersionDetail'
import { globalAlert } from '@/composables/useAlert'

interface UseWritingDeskConfirmOptions {
  selectedChapterNumber: Ref<number | null>
  availableVersions: ReturnType<typeof useWritingDeskVersionDetail>['availableVersions']
  selectedVersionIndex: Ref<number>
  resolveRecommendedVersionIndex: ReturnType<typeof useWritingDeskVersionDetail>['resolveRecommendedVersionIndex']
  selectedChapter: ComputedRef<Chapter | null>
  project: ComputedRef<NovelProject | null>
  confirmFinalizeChapterMutation: ReturnType<typeof useConfirmFinalizeChapterMutation>
  refetchChapterIntoProject: ReturnType<typeof useWritingDeskProject>['refetchChapterIntoProject']
  chapterGenerationResult: Ref<ChapterGenerationResponse | null>
}

/**
 * 写作台「章节定稿确认」流程。
 *
 * 从 WritingDesk.vue 抽出（行为逐行等价）。负责将选中版本定稿：校验版本内容（缺失时回退推荐版本）、
 * 乐观更新章节状态为 finalizing、调用定稿 mutation、刷新章节、清空生成结果；失败时回滚状态并提示。
 * 依赖版本提取群（availableVersions/resolveRecommendedVersionIndex）、章节派生（selectedChapter）、
 * 项目加载（refetchChapterIntoProject）的 composable 返回值，均透传入参。
 */
export const useWritingDeskConfirm = ({
  selectedChapterNumber,
  availableVersions,
  selectedVersionIndex,
  resolveRecommendedVersionIndex,
  selectedChapter,
  project,
  confirmFinalizeChapterMutation,
  refetchChapterIntoProject,
  chapterGenerationResult,
}: UseWritingDeskConfirmOptions) => {
  const confirmVersionSelection = async (payload?: { editedContent?: string | null }) => {
    const targetChapterNumber = selectedChapterNumber.value
    if (targetChapterNumber === null) {
      return
    }

    if (!availableVersions.value?.[selectedVersionIndex.value]?.content) {
      const recommendedIndex = resolveRecommendedVersionIndex(
        selectedChapter.value,
        availableVersions.value,
      )
      if (recommendedIndex !== null) {
        selectedVersionIndex.value = recommendedIndex
      }
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

  return { confirmVersionSelection }
}
