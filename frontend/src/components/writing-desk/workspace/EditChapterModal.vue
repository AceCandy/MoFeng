<!-- AIMETA P=章节编辑模态框_正文编辑|R=MofengEditor编辑_保存|NR=不含章节生成_版本选择|E=component:EditChapterModal|X=internal|A=编辑模态框|D=vue|S=dom|RD=./README.ai -->
<template>
  <div v-if="showEditModal" class="md-dialog-overlay" @click.self="closeEditModal">
    <div
      ref="editDialogRef"
      class="md-dialog w-full h-full max-w-5xl m3-editor-dialog"
      role="dialog"
      aria-modal="true"
      :aria-labelledby="editDialogTitleId"
    >
      <!-- 模态框头部 -->
      <div
        class="flex items-center justify-between p-6 border-b m3-editor-dialog__header"
      >
        <h3 :id="editDialogTitleId" class="md-title-large font-semibold">
          编辑第{{ chapterNumber }}章内容
        </h3>
        <button
          ref="editCloseButtonRef"
          data-dialog-initial-focus
          type="button"
          @click="closeEditModal"
          class="md-icon-btn md-ripple"
          aria-label="关闭编辑窗口"
        >
          <svg class="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
            <path
              fill-rule="evenodd"
              d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
              clip-rule="evenodd"
            ></path>
          </svg>
        </button>
      </div>

      <!-- 模态框内容：MofengEditor 方格稿纸编辑器（替换旧纯文本 textarea） -->
      <div class="flex-1 p-6 overflow-hidden">
        <div class="flex flex-col h-full">
          <span class="md-text-field-label mb-2">章节内容</span>
          <div class="m3-editor-dialog__editor-host flex-1">
            <MofengEditor
              v-model="editingContent"
              placeholder="请输入章节内容..."
              :readonly="isSaving"
            />
          </div>
          <div class="md-body-small md-on-surface-variant mt-2">
            字数统计: {{ editingWordCount }}
          </div>
        </div>
      </div>

      <!-- 模态框底部 -->
      <div
        class="flex items-center justify-end gap-3 p-6 border-t m3-editor-dialog__footer"
      >
        <button
          type="button"
          @click="closeEditModal"
          :disabled="isSaving"
          class="md-btn md-btn-outlined md-ripple disabled:opacity-50"
        >
          取消
        </button>
        <button
          type="button"
          @click="saveEditedContent"
          :disabled="isSaving || !editingContent.trim()"
          class="md-btn md-btn-filled md-ripple m3-editor-dialog__save disabled:opacity-50 flex items-center gap-2"
        >
          <svg
            v-if="isSaving"
            class="w-4 h-4 animate-spin"
            fill="currentColor"
            viewBox="0 0 20 20"
          >
            <path
              fill-rule="evenodd"
              d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-1-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z"
              clip-rule="evenodd"
            ></path>
          </svg>
          {{ isSaving ? '保存中...' : '落墨保存' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useEditChapterModal } from '@/composables/useEditChapterModal'
import MofengEditor from '@/components/writing-desk/editor/MofengEditor.vue'

interface Props {
  /** 当前选中章节是否有正文（决定能否打开编辑） */
  hasContent: boolean
  /** 当前选中章节的已解析正文（打开时填入编辑框） */
  resolvedContent: string
  /** 当前选中章节号（标题展示 + 保存 payload） */
  chapterNumber: number | null
}

const props = defineProps<Props>()

const emit = defineEmits<{
  editChapter: [payload: { chapterNumber: number; content: string }]
}>()

// composable 随 template 迁入：useDialogA11y 的 watch/onBeforeUnmount 操作本组件内部 ref，
// 必须在此 setup 同步调用。props 裸值用 computed 包装以匹配 composable 的 ComputedRef 入参。
const {
  showEditModal,
  editDialogRef,
  editCloseButtonRef,
  editDialogTitleId,
  editingContent,
  isSaving,
  editingWordCount,
  openEditModal,
  closeEditModal,
  saveEditedContent,
} = useEditChapterModal({
  hasContent: computed(() => props.hasContent),
  resolvedContent: computed(() => props.resolvedContent),
  chapterNumber: computed(() => props.chapterNumber),
  onEditChapter: (payload) => emit('editChapter', payload),
})

defineExpose({ openEditModal })
</script>

<style scoped>
.m3-editor-dialog {
  max-width: min(1200px, calc(100vw - 32px));
  max-height: calc(var(--app-viewport-unit) - 32px);
  border-radius: var(--md-radius-xs) !important;
  border: 3px double var(--md-outline) !important; /* 古籍双粗细线框 */
  background-color: var(--md-surface) !important;
  box-shadow: var(--md-elevation-paper-2) !important; /* 纸页软影，替代旧拓片硬影 */
}

.m3-editor-dialog__header {
  border-bottom: 1px dashed var(--md-outline) !important;
  background-color: var(--md-surface-container-low);
  font-family: var(--md-font-serif);
}

.m3-editor-dialog__header h3 {
  font-weight: bold;
  letter-spacing: 0.05em;
}

.m3-editor-dialog__editor-host {
  min-height: 0;
  overflow: auto;
}

.m3-editor-dialog__editor-host :deep(.mofeng-editor) {
  height: 100%;
}

.m3-editor-dialog__footer {
  border-top: 1px dashed var(--md-outline) !important;
  background-color: var(--md-surface-container-low) !important;
}

/* 落印主按钮：朱砂方章印纽，「落墨保存」是本章的钤章时刻 */
.m3-editor-dialog__save.md-btn-filled {
  background-color: var(--md-secondary);
  color: var(--md-on-secondary);
  border: 1px solid var(--md-secondary-dark);
  border-radius: var(--md-radius-xs);
  font-weight: 600;
  letter-spacing: 0.08em;
  box-shadow: var(--md-elevation-paper-1);
  transition:
    background-color var(--md-duration-short) var(--md-easing-standard),
    transform var(--md-duration-short) var(--md-easing-standard),
    box-shadow var(--md-duration-short) var(--md-easing-standard);
}

.m3-editor-dialog__save.md-btn-filled:hover:not(:disabled) {
  background-color: var(--md-miaohong-strong);
  border-color: var(--md-secondary-dark);
  box-shadow: var(--md-elevation-paper-2);
}

.m3-editor-dialog__save.md-btn-filled:active:not(:disabled) {
  transform: translateY(1px);
  box-shadow: none;
}

.m3-editor-dialog__save.md-btn-filled:focus-visible {
  outline: 1px solid var(--md-primary);
  outline-offset: 2px;
}
</style>
