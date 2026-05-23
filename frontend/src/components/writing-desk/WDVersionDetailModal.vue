<!-- AIMETA P=版本详情弹窗_版本信息展示|R=版本对比_历史|NR=不含版本管理|E=component:WDVersionDetailModal|X=ui|A=版本弹窗|D=vue|S=dom|RD=./README.ai -->
<template>
  <div v-if="show" class="md-dialog-overlay" @click.self="handleClose">
    <div
      ref="dialogRef"
      class="md-dialog w-full max-w-4xl m3-detail-dialog"
      role="dialog"
      aria-modal="true"
      :aria-labelledby="dialogTitleId"
    >
      <!-- 弹窗头部 -->
      <div class="flex items-center justify-between p-6 border-b m3-detail-dialog__header">
        <div>
          <h3 :id="dialogTitleId" class="md-headline-small font-semibold">版本详情</h3>
          <p class="md-body-small md-on-surface-variant mt-1">
            版本 {{ detailVersionIndex + 1 }}
            <span class="md-on-surface-variant">•</span>
            {{ version?.style || '标准' }}风格
            <span class="md-on-surface-variant">•</span>
            {{ getVersionWordCount(version?.content || '') }} 字
          </p>
        </div>
        <button
          ref="closeButtonRef"
          data-dialog-initial-focus
          @click="handleClose"
          class="md-icon-btn md-ripple"
          aria-label="关闭版本详情弹窗"
        >
          <svg class="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"></path>
          </svg>
        </button>
      </div>

      <!-- 弹窗内容 -->
      <div class="p-6 overflow-y-auto max-h-[60vh]">
        <div class="prose max-w-none">
          <div class="whitespace-pre-wrap leading-relaxed m3-detail-dialog__content">
            {{ cleanVersionContent(version?.content || '') }}
          </div>
        </div>
      </div>

      <!-- 弹窗底部操作按钮 -->
      <div class="flex items-center justify-between p-6 border-t m3-detail-dialog__footer">
        <div class="md-body-small md-on-surface-variant">
          <span v-if="isCurrent" class="md-chip m3-version-active-stamp">
            <svg class="w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"></path>
            </svg>
            当前选中版本
          </span>
          <span v-else class="md-on-surface-variant">未选中版本</span>
        </div>

        <div class="flex gap-3">
          <button
            @click="handleClose"
            class="md-btn md-btn-outlined md-ripple"
          >
            关闭
          </button>
          <button
            v-if="!isCurrent"
            @click="$emit('selectVersion')"
            class="md-btn md-btn-filled md-ripple"
          >
            选择此版本
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, toRef } from 'vue'
import type { ChapterVersion } from '@/api/novel'
import { countNonWhitespaceChars } from '@/utils/text'
import { useDialogA11y } from '@/composables/useDialogA11y'

interface Props {
  show: boolean
  detailVersionIndex: number
  version: ChapterVersion | null
  isCurrent: boolean
}

const props = defineProps<Props>()

const emit = defineEmits(['close', 'selectVersion'])
const dialogRef = ref<HTMLElement | null>(null)
const closeButtonRef = ref<HTMLElement | null>(null)
const dialogInstanceId = `version-detail-${Math.random().toString(36).slice(2, 10)}`
const dialogTitleId = `${dialogInstanceId}-title`

const handleClose = () => {
  emit('close')
}

const cleanVersionContent = (content: string): string => {
  if (!content) return ''
  try {
    const parsed = JSON.parse(content)
    const extractContent = (value: any): string | null => {
      if (!value) return null
      if (typeof value === 'string') return value
      if (Array.isArray(value)) {
        for (const item of value) {
          const nested = extractContent(item)
          if (nested) return nested
        }
        return null
      }
      if (typeof value === 'object') {
        for (const key of ['content', 'chapter_content', 'chapter_text', 'text', 'body', 'story']) {
          if (value[key]) {
            const nested = extractContent(value[key])
            if (nested) return nested
          }
        }
      }
      return null
    }
    const extracted = extractContent(parsed)
    if (extracted) {
      content = extracted
    }
  } catch (error) {
    // not a json
  }
  let cleaned = content.replace(/^"|"$/g, '')
  cleaned = cleaned.replace(/\\n/g, '\n')
  cleaned = cleaned.replace(/\\"/g, '"')
  cleaned = cleaned.replace(/\\t/g, '\t')
  cleaned = cleaned.replace(/\\\\/g, '\\')
  return cleaned
}

const getVersionWordCount = (content: string): number => {
  return countNonWhitespaceChars(cleanVersionContent(content))
}

useDialogA11y({
  active: toRef(props, 'show'),
  dialogRef,
  onClose: handleClose,
  initialFocusRef: closeButtonRef,
})
</script>

<style scoped>
.m3-detail-dialog {
  max-width: min(900px, calc(100vw - 32px));
  max-height: calc(var(--app-viewport-unit) - 32px);
  border-radius: var(--md-radius-md);
  border: 3px double var(--md-outline);
  background-color: var(--md-surface);
  box-shadow: 3px 3px 0px rgba(28, 32, 34, 0.15);
}

.m3-detail-dialog__header {
  border-bottom-color: var(--md-outline-variant) !important;
}

.m3-detail-dialog__content {
  color: var(--md-on-surface) !important;
  font-family: var(--md-font-family);
}

.m3-detail-dialog__footer {
  border-top-color: var(--md-outline-variant) !important;
  background-color: var(--md-surface-container-low) !important;
}

.m3-version-active-stamp {
  background-color: var(--md-secondary) !important;
  color: var(--md-on-secondary) !important;
  border-radius: var(--md-radius-xs) !important;
  border: 1px solid var(--md-secondary-dark) !important;
  font-family: STSong, Songti SC, serif;
  font-weight: bold;
  letter-spacing: 0.05em;
  padding: 2px 6px;
  box-shadow: 1px 1px 0px rgba(28, 32, 34, 0.15) !important;
}
</style>
