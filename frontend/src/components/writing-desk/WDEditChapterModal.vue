<!-- AIMETA P=编辑章节弹窗_章节信息编辑|R=章节编辑表单|NR=不含内容生成|E=component:WDEditChapterModal|X=ui|A=编辑弹窗|D=vue|S=dom|RD=./README.ai -->
<template>
  <div v-if="show" class="md-dialog-overlay" @click.self="handleClose">
    <div
      ref="dialogRef"
      class="md-dialog w-full max-w-lg m3-edit-dialog p-8"
      :class="show ? 'scale-100 opacity-100' : 'scale-95 opacity-0'"
      role="dialog"
      aria-modal="true"
      :aria-labelledby="dialogTitleId"
    >
      <div class="flex justify-between items-center mb-6">
        <h2 :id="dialogTitleId" class="md-headline-small font-semibold">编辑章节大纲</h2>
        <button
          ref="closeButtonRef"
          data-dialog-initial-focus
          @click="handleClose"
          class="md-icon-btn md-ripple"
          aria-label="关闭编辑章节大纲弹窗"
        >
          <svg class="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"></path>
          </svg>
        </button>
      </div>

      <div v-if="editableChapter" class="space-y-6">
        <div>
          <label for="chapter-title" class="md-text-field-label mb-2">章节标题</label>
          <input
            type="text"
            id="chapter-title"
            v-model="editableChapter.title"
            class="md-text-field-input w-full"
            placeholder="请输入章节标题"
          />
        </div>
        <div>
          <label for="chapter-summary" class="md-text-field-label mb-2">章节摘要</label>
          <textarea
            id="chapter-summary"
            v-model="editableChapter.summary"
            rows="5"
            class="md-textarea w-full"
            placeholder="请输入章节摘要"
          ></textarea>
        </div>
      </div>

      <div class="mt-8 flex justify-end gap-4">
        <button @click="handleClose" class="md-btn md-btn-outlined md-ripple">
          取消
        </button>
        <button @click="saveChanges" class="md-btn md-btn-filled md-ripple disabled:opacity-50" :disabled="!isChanged">
          保存更改
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed, toRef } from 'vue'
import type { ChapterOutline } from '@/api/novel'
import { useDialogA11y } from '@/composables/useDialogA11y'

interface Props {
  show: boolean
  chapter: ChapterOutline | null
}

const props = defineProps<Props>()
const emit = defineEmits(['close', 'save'])

const editableChapter = ref<ChapterOutline | null>(null)
const dialogRef = ref<HTMLElement | null>(null)
const closeButtonRef = ref<HTMLElement | null>(null)
const dialogInstanceId = `chapter-edit-${Math.random().toString(36).slice(2, 10)}`
const dialogTitleId = `${dialogInstanceId}-title`

const handleClose = () => {
  emit('close')
}

watch(() => props.chapter, (newChapter) => {
  if (newChapter) {
    editableChapter.value = { ...newChapter }
  } else {
    editableChapter.value = null
  }
}, { deep: true, immediate: true })

const isChanged = computed(() => {
  if (!props.chapter || !editableChapter.value) {
    return false
  }
  return props.chapter.title !== editableChapter.value.title || props.chapter.summary !== editableChapter.value.summary
})

const saveChanges = () => {
  if (editableChapter.value && isChanged.value) {
    emit('save', editableChapter.value)
  }
}

useDialogA11y({
  active: toRef(props, 'show'),
  dialogRef,
  onClose: handleClose,
  initialFocusRef: closeButtonRef,
})
</script>

<style scoped>
.m3-edit-dialog {
  border-radius: var(--md-radius-md, 6px);
  border: 3px double var(--md-outline);
  box-shadow: 4px 4px 0px rgba(28, 32, 34, 0.15);
  max-width: min(560px, calc(100vw - 32px));
}
</style>
