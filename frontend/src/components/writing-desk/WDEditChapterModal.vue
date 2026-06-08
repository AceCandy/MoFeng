<!-- AIMETA P=编辑章节弹窗_章节信息编辑|R=章节编辑表单|NR=不含内容生成|E=component:WDEditChapterModal|X=ui|A=编辑弹窗|D=vue|S=dom|RD=./README.ai -->
<template>
  <GlobalModalContainer
    v-if="show"
    title="编辑章节大纲"
    badge-text="编"
    width="min(90vw, 560px)"
    @close="handleClose"
  >
    <template #header-actions>
      <!-- 右上角朱砂方印保存按钮 -->
      <button
        ref="closeButtonRef"
        data-dialog-initial-focus
        type="button"
        class="m3-ink-modal-save-badge-btn"
        :disabled="!isChanged"
        @click="saveChanges"
      >
        存
      </button>
    </template>

    <div v-if="editableChapter" class="space-y-6 pt-4">
      <div>
        <label for="chapter-title" class="md-text-field-label mb-2">章节标题</label>
        <!-- 乌丝栏下划线输入 -->
        <input
          type="text"
          id="chapter-title"
          v-model="editableChapter.title"
          class="m3-underline-input w-full"
          placeholder="请输入章节标题"
        />
      </div>
      <div>
        <label for="chapter-summary" class="md-text-field-label mb-2">章节摘要</label>
        <!-- 直角墨描边 textarea -->
        <textarea
          id="chapter-summary"
          v-model="editableChapter.summary"
          rows="5"
          class="m3-textarea-ink w-full"
          placeholder="请输入章节摘要"
        ></textarea>
      </div>
    </div>
  </GlobalModalContainer>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import type { ChapterOutline } from '@/api/novel'
import GlobalModalContainer from '@/components/shared/GlobalModalContainer.vue'

interface Props {
  show: boolean
  chapter: ChapterOutline | null
}

const props = defineProps<Props>()
const emit = defineEmits(['close', 'save'])

const editableChapter = ref<ChapterOutline | null>(null)
const closeButtonRef = ref<HTMLElement | null>(null)

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
</script>

<style scoped>
/* 乌丝栏下划线输入框 */
.m3-underline-input {
  width: 100%;
  border: none;
  border-bottom: 1.5px solid var(--md-outline);
  background: transparent;
  color: var(--md-on-surface);
  padding: 8px 4px;
  font-size: 16px;
  font-family: var(--md-font-serif);
  outline: none;
  transition: border-bottom-color 0.25s ease;
}

.m3-underline-input:focus {
  border-bottom-color: var(--md-secondary);
}

/* 直角墨线 textarea */
.m3-textarea-ink {
  width: 100%;
  min-height: 120px;
  resize: vertical;
  padding: 12px;
  border: 1.5px solid var(--md-outline-variant);
  border-radius: 0 !important;
  background-color: transparent;
  color: var(--md-on-surface);
  font-family: var(--md-font-serif);
  font-size: var(--md-body-large);
  line-height: 1.8;
  outline: none;
  transition: border-color 0.25s ease, box-shadow 0.25s ease;
}

.m3-textarea-ink:focus {
  border-color: var(--md-outline);
  box-shadow: 2px 2px 0px var(--md-outline);
}

.md-text-field-label {
  font-family: var(--md-font-serif);
  font-weight: 600;
  color: var(--md-on-surface-variant);
}
</style>
