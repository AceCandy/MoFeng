import { computed, ref, type ComputedRef } from 'vue'
import { useDialogA11y } from '@/composables/useDialogA11y'
import { countNonWhitespaceChars } from '@/utils/text'

interface UseEditChapterModalOptions {
  /** 当前选中章节是否有正文（用于决定能否打开编辑） */
  hasContent: ComputedRef<boolean>
  /** 当前选中章节的已解析正文（打开时填入编辑框） */
  resolvedContent: ComputedRef<string>
  /** 当前选中章节号（保存时随 payload 回传） */
  chapterNumber: ComputedRef<number | null>
  /** 保存回调：将编辑结果上抛父组件 */
  onEditChapter: (payload: { chapterNumber: number; content: string }) => void
}

/**
 * 章节正文编辑模态框的状态与交互。
 *
 * 从 WDWorkspace.vue 抽出（行为逐行等价）。内部仍调用 useDialogA11y，
 * 故必须在组件 setup 顶层同步调用，以正确注册 watch / onBeforeUnmount。
 */
export const useEditChapterModal = ({
  hasContent,
  resolvedContent,
  chapterNumber,
  onEditChapter,
}: UseEditChapterModalOptions) => {
  const editDialogTitleId = 'wd-workspace-edit-dialog-title'
  const editingContentInputId = 'wd-workspace-edit-content-input'

  const showEditModal = ref(false)
  const editDialogRef = ref<HTMLElement | null>(null)
  const editCloseButtonRef = ref<HTMLElement | null>(null)
  const editingContent = ref('')
  const isSaving = ref(false)

  const editingWordCount = computed(() => countNonWhitespaceChars(editingContent.value))

  const openEditModal = () => {
    if (hasContent.value) {
      editingContent.value = resolvedContent.value
      showEditModal.value = true
    }
  }

  const closeEditModal = () => {
    if (isSaving.value) return
    showEditModal.value = false
    editingContent.value = ''
    isSaving.value = false
  }

  useDialogA11y({
    active: showEditModal,
    dialogRef: editDialogRef,
    onClose: closeEditModal,
    initialFocusRef: editCloseButtonRef,
  })

  const saveEditedContent = async () => {
    if (chapterNumber.value === null || !editingContent.value.trim()) return

    isSaving.value = true
    try {
      onEditChapter({
        chapterNumber: chapterNumber.value,
        content: editingContent.value,
      })
      closeEditModal()
    } catch (error) {
      console.error('保存章节内容失败:', error)
    } finally {
      isSaving.value = false
    }
  }

  return {
    showEditModal,
    editDialogRef,
    editCloseButtonRef,
    editDialogTitleId,
    editingContentInputId,
    editingContent,
    isSaving,
    editingWordCount,
    openEditModal,
    closeEditModal,
    saveEditedContent,
  }
}
