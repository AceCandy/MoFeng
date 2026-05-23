<!-- AIMETA P=评审详情弹窗_章节评审展示|R=评审结果展示|NR=不含评审逻辑|E=component:WDEvaluationDetailModal|X=ui|A=评审弹窗|D=vue|S=dom|RD=./README.ai -->
<template>
  <div v-if="show" class="md-dialog-overlay" @click.self="handleClose">
    <div
      ref="dialogRef"
      class="md-dialog w-full max-w-4xl m3-eval-dialog flex flex-col"
      role="dialog"
      aria-modal="true"
      :aria-labelledby="dialogTitleId"
    >
      <!-- 弹窗头部 -->
      <div class="flex items-center justify-between p-6 border-b m3-eval-dialog__header">
        <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 m3-eval-icon-wrapper">
                <svg class="w-6 h-6 m3-eval-icon" fill="currentColor" viewBox="0 0 20 20">
                    <path d="M10 2a6 6 0 00-6 6v3.586l-1.707 1.707A1 1 0 003 15v1a1 1 0 001 1h12a1 1 0 001-1v-1a1 1 0 00-.293-.707L16 11.586V8a6 6 0 00-6-6zM8.05 17a2 2 0 103.9 0H8.05z"></path>
                </svg>
            </div>
            <h3 :id="dialogTitleId" class="md-headline-small font-semibold">AI 评审详情</h3>
        </div>
        <button
          ref="closeButtonRef"
          data-dialog-initial-focus
          @click="handleClose"
          class="md-icon-btn md-ripple"
          aria-label="关闭 AI 评审详情弹窗"
        >
          <svg class="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"></path>
          </svg>
        </button>
      </div>

      <!-- 弹窗内容 -->
      <div class="p-6 overflow-y-auto max-h-[calc(80vh-130px)]">
        <div v-if="parsedEvaluation" class="space-y-6 text-sm">
            <div class="md-card md-card-filled p-4 m3-eval-best-choice-card">
              <p class="md-title-small font-semibold m3-eval-best-choice-title">🏆 最佳选择：版本 {{ parsedEvaluation.best_choice }}</p>
              <p class="md-body-small mt-2 m3-eval-best-choice-reason">{{ parsedEvaluation.reason_for_choice }}</p>
            </div>
            <div class="space-y-4">
              <div v-for="(evalResult, versionName) in parsedEvaluation.evaluation" :key="versionName" class="md-card md-card-outlined p-4 m3-eval-version-card">
                <h5 class="md-title-medium font-semibold mb-2">版本 {{ String(versionName).replace('version', '') }} 评估</h5>
                <div class="prose prose-sm max-w-none md-on-surface space-y-3">
                  <div>
                    <p class="font-semibold">综合评价:</p>
                    <p>{{ evalResult.overall_review }}</p>
                  </div>
                  <div>
                    <p class="font-semibold">优点:</p>
                    <ul class="list-disc pl-5 space-y-1">
                      <li v-for="(pro, i) in evalResult.pros" :key="`pro-${i}`">{{ pro }}</li>
                    </ul>
                  </div>
                  <div>
                    <p class="font-semibold">缺点:</p>
                    <ul class="list-disc pl-5 space-y-1">
                      <li v-for="(con, i) in evalResult.cons" :key="`con-${i}`">{{ con }}</li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div
            v-else
            class="prose prose-sm max-w-none prose-headings:mt-2 prose-headings:mb-1 prose-p:my-1 prose-ul:my-1 prose-ol:my-1 prose-li:my-0 m3-eval-markdown-container"
            v-html="parseMarkdown(evaluation)"
          ></div>
      </div>

      <!-- 弹窗底部操作按钮 -->
      <div class="flex items-center justify-end gap-3 p-6 border-t m3-eval-dialog__footer">
        <button
          @click="$emit('optimizeRecommendedVersion')"
          :disabled="!canOptimizeRecommendedVersion || isOptimizingRecommendedVersion"
          class="md-btn md-btn-tonal md-ripple disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
        >
          <svg v-if="isOptimizingRecommendedVersion" class="w-4 h-4 animate-spin" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd"></path>
          </svg>
          {{ isOptimizingRecommendedVersion ? '优化中...' : '优化建议采用版本' }}
        </button>
        <button
            @click="handleClose"
            class="md-btn md-btn-filled md-ripple"
        >
            关闭
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, toRef } from 'vue'
import DOMPurify from 'dompurify'
import { useDialogA11y } from '@/composables/useDialogA11y'

interface Props {
  show: boolean
  evaluation: string | null
  isOptimizingRecommendedVersion?: boolean
}

const props = defineProps<Props>()

const emit = defineEmits(['close', 'optimizeRecommendedVersion'])
const dialogRef = ref<HTMLElement | null>(null)
const closeButtonRef = ref<HTMLElement | null>(null)
const dialogInstanceId = `evaluation-detail-${Math.random().toString(36).slice(2, 10)}`
const dialogTitleId = `${dialogInstanceId}-title`

const handleClose = () => {
  emit('close')
}

const parsedEvaluation = computed(() => {
  if (!props.evaluation) return null
  try {
    let data = JSON.parse(props.evaluation)
    if (typeof data === 'string') {
      data = JSON.parse(data)
    }
    return data
  } catch (error) {
    console.error('Failed to parse evaluation JSON:', error)
    return null
  }
})

const canOptimizeRecommendedVersion = computed(() => {
  const bestChoice = Number(parsedEvaluation.value?.best_choice)
  return Number.isInteger(bestChoice) && bestChoice > 0
})

const parseMarkdown = (text: string | null): string => {
  if (!text) return ''
  let parsed = text
    .replace(/\\n/g, '\n')
    .replace(/\\"/g, '"')
    .replace(/\\'/g, "'")
    .replace(/\\\\/g, '\\')
  parsed = parsed.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
  parsed = parsed.replace(/(?<!\*)\*([^*]+)\*(?!\*)/g, '<em>$1</em>')
  parsed = parsed.replace(
    /^([A-Z])\)\s*\*\*(.*?)\*\*(.*)/gm,
    '<div class="mb-2"><span class="inline-flex items-center justify-center w-6 h-6 text-sm font-bold rounded-full mr-2 m3-eval-badge">$1</span><strong>$2</strong>$3</div>'
  )
  parsed = parsed.replace(/\n/g, '<br>')
  parsed = parsed.replace(/(<br\s*\/?>\s*){2,}/g, '</p><p class="mt-2">')
  if (!parsed.includes('<p>')) {
    parsed = `<p>${parsed}</p>`
  }
  return DOMPurify.sanitize(parsed, {
    USE_PROFILES: { html: true },
  })
}

useDialogA11y({
  active: toRef(props, 'show'),
  dialogRef,
  onClose: handleClose,
  initialFocusRef: closeButtonRef,
})
</script>

<style scoped>
.m3-eval-dialog {
  max-width: min(960px, calc(100vw - 32px));
  max-height: calc(var(--app-viewport-unit) - 32px);
  border-radius: var(--md-radius-md);
  border: 3px double var(--md-outline);
  background-color: var(--md-surface);
  box-shadow: 3px 3px 0px rgba(28, 32, 34, 0.15);
}

.m3-eval-dialog__header {
  border-bottom-color: var(--md-outline-variant) !important;
}

.m3-eval-icon-wrapper {
  background-color: var(--md-secondary) !important;
}

.m3-eval-icon {
  color: var(--md-on-secondary) !important;
}

/* 最佳选择卡片：熟宣底色 + 朱砂红细边框，圆角为 sm(4px) */
.m3-eval-best-choice-card {
  border-radius: var(--md-radius-sm) !important;
  border: 1px solid var(--md-secondary) !important;
  background-color: var(--md-surface-container-lowest) !important;
  box-shadow: 2px 2px 0px rgba(184, 60, 50, 0.08) !important;
}

.m3-eval-best-choice-title {
  color: var(--md-secondary) !important;
  font-family: STSong, Songti SC, serif;
}

.m3-eval-best-choice-reason {
  color: var(--md-on-surface) !important;
}

/* 评审卡片：圆角为 sm(4px)，使用竹青框线 */
.m3-eval-version-card {
  border-radius: var(--md-radius-sm) !important;
  border-color: var(--md-outline) !important;
  background-color: var(--md-surface-container-low) !important;
}

.m3-eval-markdown-container {
  color: var(--md-on-surface) !important;
}

.m3-eval-dialog__footer {
  border-top-color: var(--md-outline-variant) !important;
  background-color: var(--md-surface-container-low) !important;
}

.m3-eval-badge {
  background-color: var(--md-primary-container) !important;
  color: var(--md-on-primary-container) !important;
}
</style>
