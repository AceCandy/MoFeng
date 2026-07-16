import { ref } from 'vue'
import type { ComputedRef } from 'vue'
import type { ChapterOutline, NovelProject } from '@/api/novel'
import {
  useEditChapterContentMutation,
  useGenerateChapterOutlineMutation,
  useUpdateChapterOutlineMutation,
} from '@/queries/novel'
import { globalAlert } from '@/composables/useAlert'

interface UseWritingDeskModalsOptions {
  projectId: () => string
  project: ComputedRef<NovelProject | null>
  loadWDEditChapterModal: () => Promise<unknown>
  loadWDEvaluationDetailModal: () => Promise<unknown>
  loadWDGenerateOutlineModal: () => Promise<unknown>
}

/**
 * 写作台章节编辑 / 评审详情 / 大纲生成三类弹窗的状态与操作。
 *
 * 从 WritingDesk.vue 抽出（行为逐行等价）。三类弹窗各依赖独立的 mutation、互不耦合：
 * WDEditChapterModal 编辑章节大纲（updateChapterOutlineMutation）、
 * WDEvaluationDetailModal 展示评审详情（仅开关，无 mutation）、
 * WDGenerateOutlineModal 触发后台大纲生成（generateChapterOutlineMutation）；
 * editChapterContent 是 WDWorkspace 的内联正文快编（editChapterContentMutation），
 * 与编辑大纲同属「章节保存」语义，故一并内聚。弹窗开关 state 与 mutation 仅本块使用，故内化。
 */
export const useWritingDeskModals = ({
  projectId,
  project,
  loadWDEditChapterModal,
  loadWDEvaluationDetailModal,
  loadWDGenerateOutlineModal,
}: UseWritingDeskModalsOptions) => {
  const showEvaluationDetailModal = ref(false)
  const showEditChapterModal = ref(false)
  const editingChapter = ref<ChapterOutline | null>(null)
  const isGeneratingOutline = ref(false)
  const showGenerateOutlineModal = ref(false)

  const updateChapterOutlineMutation = useUpdateChapterOutlineMutation(projectId)
  const generateChapterOutlineMutation = useGenerateChapterOutlineMutation(projectId)
  const editChapterContentMutation = useEditChapterContentMutation(projectId)

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
      globalAlert.showToast('章节大纲已更新', 'success')
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
      globalAlert.showToast('章节内容已更新', 'success')
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
      globalAlert.showToast('大纲生成任务已加入后台，可在右上角任务日志查看进度', 'success')
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

  return {
    showEvaluationDetailModal,
    showEditChapterModal,
    editingChapter,
    isGeneratingOutline,
    showGenerateOutlineModal,
    openEditChapterModal,
    openEvaluationDetailModal,
    saveChapterChanges,
    generateOutline,
    editChapterContent,
    handleGenerateOutline,
  }
}
