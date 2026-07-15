<template>
  <!-- Material 3 Add Chapter Modal -->
  <transition
    enter-active-class="md-scale-enter-active"
    leave-active-class="md-scale-leave-active"
    enter-from-class="md-scale-enter-from"
    leave-to-class="md-scale-leave-to"
  >
    <div
      v-if="isOpen"
      class="md-dialog-overlay"
      @click.self="handleCancel"
    >
      <div
        ref="dialogRef"
        class="md-dialog relative w-full max-w-lg mx-4"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="dialogTitleId"
      >
        <div class="md-dialog-header">
          <h3 :id="dialogTitleId" class="md-dialog-title">新增章节大纲</h3>
        </div>
        <div class="md-dialog-content space-y-6">
          <div class="md-text-field">
            <label for="new-chapter-title" class="md-text-field-label"> 章节标题 </label>
            <input
              id="new-chapter-title"
              v-model="title"
              type="text"
              class="md-text-field-input"
              placeholder="例如：意外的相遇"
            />
          </div>
          <div class="md-text-field">
            <label for="new-chapter-summary" class="md-text-field-label"> 章节摘要 </label>
            <textarea
              id="new-chapter-summary"
              v-model="summary"
              rows="4"
              class="md-textarea w-full"
              placeholder="简要描述本章发生的主要事件"
            ></textarea>
          </div>
        </div>
        <div class="md-dialog-actions">
          <button
            ref="cancelButtonRef"
            data-dialog-initial-focus
            type="button"
            class="md-btn md-btn-text md-ripple"
            @click="handleCancel"
          >
            取消
          </button>
          <button type="button" class="md-btn md-btn-filled md-ripple" @click="handleConfirm">
            保存
          </button>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup lang="ts">
import { ref, toRef, watch } from 'vue'
import { useDialogA11y } from '@/composables/useDialogA11y'

interface Props {
  isOpen: boolean
  initialTitle?: string
}

const props = withDefaults(defineProps<Props>(), {
  initialTitle: '',
})

const emit = defineEmits<{
  cancel: []
  confirm: [payload: { title: string; summary: string }]
}>()

const dialogRef = ref<HTMLElement | null>(null)
const cancelButtonRef = ref<HTMLElement | null>(null)
const dialogTitleId = 'novel-detail-add-chapter-title'
const title = ref('')
const summary = ref('')

// 打开对话框时按 initialTitle 重置表单（与原父 startAddChapter 设值行为等价）
watch(
  () => props.isOpen,
  (open) => {
    if (open) {
      title.value = props.initialTitle
      summary.value = ''
    }
  },
)

const handleCancel = () => {
  emit('cancel')
}

const handleConfirm = () => {
  emit('confirm', { title: title.value, summary: summary.value })
}

useDialogA11y({
  active: toRef(props, 'isOpen'),
  dialogRef,
  onClose: handleCancel,
  initialFocusRef: cancelButtonRef,
})
</script>

<style scoped>
/* Material 3 Transition Classes */
.md-scale-enter-active,
.md-scale-leave-active {
  transition:
    opacity 250ms cubic-bezier(0.2, 0, 0, 1),
    transform 250ms cubic-bezier(0.2, 0, 0, 1);
}

.md-scale-enter-from,
.md-scale-leave-to {
  opacity: 0;
  transform: scale(0.95);
}
</style>
