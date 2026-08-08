<template>
  <Teleport to="body">
    <div
      v-if="show"
      class="md-dialog-overlay"
      @click.self="$emit('close')"
    >
      <div
        ref="dialogRef"
        class="md-dialog m3-result-dialog flex flex-col"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="dialogTitleId"
      >
        <div class="p-6 border-b" style="border-bottom-color: var(--md-outline-variant)">
          <div class="flex items-center justify-between gap-4">
            <div>
              <h3 :id="dialogTitleId" class="md-headline-small font-semibold">
                评审优化结果预览
              </h3>
              <p class="md-body-small md-on-surface-variant mt-1">
                {{ notes }}
              </p>
            </div>
            <button
              ref="closeButtonRef"
              data-dialog-initial-focus
              type="button"
              @click="$emit('close')"
              :disabled="isApplying"
              class="md-icon-btn md-ripple disabled:opacity-50"
              aria-label="关闭评审优化结果弹窗"
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
        </div>
        <div class="flex-1 overflow-y-auto p-6">
          <!-- 优化稿 = AI 描红稿:只读呈现,三信号由编辑器内核渲染(规格 §4) -->
          <div class="mofeng-miaohong-review" data-provenance="ai">
            <p class="mofeng-miaohong-review__label">描红稿 · 待落墨</p>
            <MofengEditor
              :model-value="optimizedContent"
              provenance="ai"
              readonly
            />
          </div>
        </div>
        <div
          class="p-6 border-t flex items-center justify-end gap-3"
          style="
            border-top-color: var(--md-outline-variant);
            background-color: var(--md-surface-container-low);
          "
        >
          <div class="md-body-small md-on-surface-variant mr-auto">
            {{ optimizedWordCount }} 字
          </div>
          <button
            type="button"
            @click="$emit('close')"
            :disabled="isApplying"
            class="md-btn md-btn-outlined md-ripple disabled:opacity-50"
          >
            取消
          </button>
          <button
            type="button"
            @click="$emit('apply')"
            :disabled="isApplying"
            class="md-btn md-btn-primary mofeng-seal-btn md-ripple disabled:opacity-50 flex items-center gap-2"
          >
            <svg
              v-if="isApplying"
              class="w-4 h-4 animate-spin"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fill-rule="evenodd"
                d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 01-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z"
                clip-rule="evenodd"
              ></path>
            </svg>
            {{ isApplying ? '应用中...' : '落墨成稿' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, ref, toRef } from 'vue'
import { useDialogA11y } from '@/composables/useDialogA11y'
import { countNonWhitespaceChars } from '@/utils/text'
import MofengEditor from '@/components/writing-desk/editor/MofengEditor.vue'

interface Props {
  show: boolean
  optimizedContent: string
  isApplying: boolean
  notes: string
}

const props = defineProps<Props>()
const emit = defineEmits(['close', 'apply'])

const dialogRef = ref<HTMLElement | null>(null)
const closeButtonRef = ref<HTMLElement | null>(null)
const dialogTitleId = 'writing-desk-recommended-optimize-title'

const optimizedWordCount = computed(() => countNonWhitespaceChars(props.optimizedContent))

useDialogA11y({
  active: toRef(props, 'show'),
  dialogRef,
  onClose: () => emit('close'),
  initialFocusRef: closeButtonRef,
})
</script>

<style scoped>
.m3-result-dialog {
  max-width: min(900px, calc(100vw - 32px));
  max-height: calc(var(--app-viewport-unit) - 32px);
  border-radius: var(--md-radius-md);
}

/* 描红审阅容器:语义钩子 data-provenance="ai"(规格 §4) */
.mofeng-miaohong-review {
  /* 同 MofengEditor:全局 --md-font-kai 暂为宋体别名,描红域内局部落地真楷体栈 */
  --md-font-kai: 'Kaiti SC', 'STKaiti', 'KaiTi', 'AR PL UKai CN', 'AR PL KaitiM GB', 'TW-Kai', serif;
}

.mofeng-miaohong-review__label {
  margin: 0 0 8px;
  font-family: var(--md-font-kai);
  font-size: 12px;
  line-height: 1.6;
  color: var(--md-miaohong, #b8402f);
}

/* 落印主按钮(规格 §5):朱砂印纽,方章微圆角 2px、朱砂底、熟宣字 */
.mofeng-seal-btn {
  border: none;
  border-radius: 2px;
  background-color: var(--md-miaohong, #b8402f);
  color: var(--md-surface);
  font-family: var(--md-font-serif);
  letter-spacing: 0.08em;
  text-indent: 0.08em;
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
  cursor: not-allowed;
}
</style>
