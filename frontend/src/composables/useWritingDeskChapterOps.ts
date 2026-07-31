// AIMETA P=写作台章节删除操作|R=删除范围确认_章节产物二次确认|NR=不触发生成评审或工作流命令|E=composable:writing-desk-chapter-ops|X=internal|A=useWritingDeskChapterOps|D=@tanstack/vue-query|S=state,cache|RD=./README.ai
import type { ComputedRef, Ref } from 'vue'
import { useDeleteChapterMutation } from '@/queries/novel'
import { globalAlert } from '@/composables/useAlert'

interface UseWritingDeskChapterOpsOptions {
  projectId: () => string
  selectedChapterNumber: Ref<number | null>
  latestCompletedChapterNumber: ComputedRef<number | null>
}

/**
 * 写作台章节删除操作。生成、评审恢复与定稿全部属于章节工作流 actor，不能在此
 * 通过 legacy mutation 或 generation_status 乐观写入形成第二 owner。
 */
export const useWritingDeskChapterOps = ({
  projectId,
  selectedChapterNumber,
  latestCompletedChapterNumber,
}: UseWritingDeskChapterOpsOptions) => {
  const deleteChapterMutation = useDeleteChapterMutation(projectId)

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
    deleteChapter,
  }
}
