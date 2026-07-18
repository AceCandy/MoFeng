import type { ComputedRef, Ref } from 'vue'
import type { NovelProject } from '@/api/novel'
import { useDeleteChapterMutation, useEvaluateChapterMutation } from '@/queries/novel'
import { globalAlert } from '@/composables/useAlert'

interface UseWritingDeskChapterOpsOptions {
  projectId: () => string
  project: ComputedRef<NovelProject | null>
  selectedChapterNumber: Ref<number | null>
  evaluatingChapter: Ref<number | null>
  latestCompletedChapterNumber: ComputedRef<number | null>
}

/**
 * 写作台章节评审与删除操作。
 *
 * 从 WritingDesk.vue 抽出（行为逐行等价）。评审与删除各自依赖独立的 mutation、
 * 互不耦合，故同处一个 composable；章节定稿（confirmVersionSelection）因依赖
 * 版本提取群（availableVersions/resolveRecommendedVersionIndex），待该群抽出后
 * 另行收敛，故未纳入本 composable。
 */
export const useWritingDeskChapterOps = ({
  projectId,
  project,
  selectedChapterNumber,
  evaluatingChapter,
  latestCompletedChapterNumber,
}: UseWritingDeskChapterOpsOptions) => {
  const evaluateChapterMutation = useEvaluateChapterMutation(projectId)
  const deleteChapterMutation = useDeleteChapterMutation(projectId)

  const evaluateChapter = async () => {
    if (selectedChapterNumber.value !== null) {
      const targetChapter = selectedChapterNumber.value
      evaluatingChapter.value = targetChapter

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
            (ch) => ch.chapter_number === targetChapter,
          )
          if (chapter) {
            previousStatus = chapter.generation_status // 保存原状态
            chapter.generation_status = 'evaluating'
          }
        }
        await evaluateChapterMutation.mutateAsync(targetChapter)

        // 评审完成后，状态会通过store和轮询更新，这里不需要额外操作
        globalAlert.showToast('章节评审结果已生成', 'success')
      } catch (error) {
        console.error('评审章节失败:', error)

        // 错误状态下恢复章节状态为原始状态
        if (project.value?.chapters) {
          const chapter = project.value.chapters.find(
            (ch) => ch.chapter_number === targetChapter,
          )
          if (chapter && previousStatus) {
            chapter.generation_status = previousStatus // 恢复为原状态
          }
        }

        globalAlert.showError(
          `评审章节失败: ${error instanceof Error ? error.message : '未知错误'}`,
          '评审失败',
        )
      } finally {
        if (evaluatingChapter.value === targetChapter) {
          evaluatingChapter.value = null
        }
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

    if (isDeletingCompletedChapter) {
      const artifactsConfirmed = await globalAlert.showConfirm(
        `请再次确认删除第 ${completedChapterNumber} 章对应的正文、版本、评审、生成 trace 和向量数据等全部产物。此操作无法撤销。`,
        '二次确认',
      )
      if (!artifactsConfirmed) {
        return
      }
    }

    try {
      await deleteChapterMutation.mutateAsync({
        chapterNumbers: numbersToDelete,
        deleteArtifactsConfirmed: isDeletingCompletedChapter,
      })
      globalAlert.showToast(
        isDeletingCompletedChapter ? '章节及产物已删除' : '章节大纲已删除',
        'success',
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

  return {
    evaluateChapter,
    deleteChapter,
  }
}
