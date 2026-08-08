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
      <!-- 右上角朱砂方印保存按钮(落印主按钮,规格 §5) -->
      <button
        ref="closeButtonRef"
        data-dialog-initial-focus
        type="button"
        class="mofeng-seal-btn"
        :disabled="!isChanged"
        aria-label="保存章节大纲修改"
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
        <span class="md-text-field-label mb-2 block">章节摘要</span>
        <!-- 方格稿纸编辑器(作家正文,provenance=ink 落墨态) -->
        <MofengEditor
          v-model="editableChapter.summary"
          placeholder="请输入章节摘要"
        />
        <div class="md-body-small md-on-surface-variant mt-2">
          字数统计: {{ summaryWordCount }}
        </div>
      </div>
    </div>
  </GlobalModalContainer>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import type { ChapterOutline } from '@/api/novel'
import GlobalModalContainer from '@/components/shared/GlobalModalContainer.vue'
import MofengEditor from '@/components/writing-desk/editor/MofengEditor.vue'
import { countNonWhitespaceChars } from '@/utils/text'

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

const summaryWordCount = computed(() => countNonWhitespaceChars(editableChapter.value?.summary))

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

.md-text-field-label {
  font-family: var(--md-font-serif);
  font-weight: 600;
  color: var(--md-on-surface-variant);
}

/* 朱砂落印主按钮(规格 §5):方章微圆角 2px、朱砂底、熟宣字,
   hover 转 --md-miaohong-strong,按下 translateY(1px) */
.mofeng-seal-btn {
  min-width: 44px;
  height: 44px;
  padding: 0 12px;
  border: none;
  border-radius: 2px;
  background-color: var(--md-miaohong, #b8402f);
  color: var(--md-surface);
  font-family: var(--md-font-serif);
  font-size: var(--md-title-small);
  font-weight: 700;
  cursor: pointer;
  transition:
    background-color 140ms var(--md-easing-standard),
    transform 140ms var(--md-easing-standard),
    opacity 140ms var(--md-easing-standard);
}

.mofeng-seal-btn:hover:not(:disabled) {
  background-color: var(--md-miaohong-strong, #9c3323);
}

.mofeng-seal-btn:active:not(:disabled) {
  transform: translateY(1px);
}

.mofeng-seal-btn:focus-visible {
  outline: 1px solid var(--md-luomo, var(--md-on-surface));
  outline-offset: 2px;
}

.mofeng-seal-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
