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
          <div class="whitespace-pre-wrap leading-relaxed" style="color: var(--md-on-surface)">
            <p
              v-for="(paragraph, index) in optimizedParagraphs"
              :key="`recommended-optimized-${index}`"
              class="mb-4 last:mb-0"
            >
              {{ paragraph }}
            </p>
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
            class="md-btn md-btn-filled md-ripple disabled:opacity-50 flex items-center gap-2"
            style="background-color: var(--md-success); color: var(--md-on-success)"
          >
            <svg
              v-if="isApplying"
              class="w-4 h-4 animate-spin"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fill-rule="evenodd"
                d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z"
                clip-rule="evenodd"
              ></path>
            </svg>
            {{ isApplying ? '应用中...' : '应用优化' }}
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

const optimizedParagraphs = computed(() => {
  if (!props.optimizedContent.trim()) return []
  return props.optimizedContent
    .split(/\n{2,}/)
    .map((paragraph) => paragraph.trim())
    .filter(Boolean)
})

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
  border-radius: var(--md-radius-xl);
}
</style>
