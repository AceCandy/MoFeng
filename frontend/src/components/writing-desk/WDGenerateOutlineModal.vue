<!-- AIMETA P=生成大纲弹窗_大纲生成界面|R=大纲生成表单|NR=不含生成逻辑|E=component:WDGenerateOutlineModal|X=ui|A=生成弹窗|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <GlobalModalContainer
    v-if="show"
    title="生成后续大纲"
    badge-text="启"
    width="min(90vw, 520px)"
    @close="handleClose"
  >
    <template #header-actions>
      <!-- 右上角朱砂“启”印签生成大纲按钮 -->
      <button
        type="button"
        class="m3-ink-modal-save-badge-btn"
        @click="handleGenerate"
      >
        启
      </button>
    </template>

    <div class="px-2 pt-2 text-left">
      <div class="flex flex-col gap-4 sm:flex-row sm:items-start mb-6">
        <div class="mx-auto flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-xs sm:mx-0 sm:h-12 sm:w-12 border border-[var(--md-outline)] m3-outline-icon-wrapper">
          <svg class="h-6 w-6 m3-outline-icon" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 6v12m6-6H6" />
          </svg>
        </div>
        <div class="text-center sm:flex-1 sm:text-left">
          <p class="md-body-medium md-on-surface-variant font-serif">请输入或选择要生成的后续章节数量。大纲生成任务将提交至后台队列异步执行。</p>
        </div>
      </div>

      <div class="mt-4">
        <label for="numChapters" class="md-text-field-label">生成数量 (章)</label>
        <!-- 乌丝栏下划线输入 -->
        <input
          type="number"
          name="numChapters"
          id="numChapters"
          v-model.number="numChapters"
          class="m3-underline-input w-full mt-2"
          min="1"
          max="20"
        />
        <div class="mt-6 flex flex-wrap justify-center gap-3">
          <button
            type="button"
            v-for="count in [1, 2, 5, 10]"
            :key="count"
            @click="setNumChapters(count)"
            :aria-pressed="numChapters === count"
            :class="['md-btn md-btn-outlined md-ripple font-serif', numChapters === count ? 'm3-count-selected' : '']"
          >
            {{ count }} 章
          </button>
        </div>
      </div>
    </div>
  </GlobalModalContainer>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import GlobalModalContainer from '@/components/shared/GlobalModalContainer.vue'

interface Props {
  show: boolean
}

const props = defineProps<Props>()
const emit = defineEmits(['close', 'generate'])

const numChapters = ref(5)

const setNumChapters = (count: number) => {
  numChapters.value = count
}

const handleClose = () => {
  emit('close')
}

const handleGenerate = () => {
  if (numChapters.value > 0) {
    emit('generate', numChapters.value)
    emit('close')
  }
}
</script>

<style scoped>
.m3-outline-icon-wrapper {
  background-color: var(--md-primary-container) !important;
  border-radius: 4px !important;
}

.m3-outline-icon {
  color: var(--md-on-primary-container) !important;
}

.m3-count-selected {
  background-color: var(--md-primary) !important;
  color: var(--md-on-primary) !important;
  border-color: transparent !important;
}

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
</style>
