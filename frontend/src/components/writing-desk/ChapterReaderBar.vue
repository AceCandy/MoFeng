<template>
    <div class="reader-float" role="region" aria-label="章节朗读">
      <button
        type="button"
        class="md-btn md-btn-text md-ripple reader-float__btn reader-float__btn--main"
        :aria-label="mainLabel"
        :title="mainLabel"
        @click="onMainClick"
      >
        <svg
          v-if="status === 'idle'"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"
        >
          <path d="M11 5 6 9H3v6h3l5 4z" />
          <path d="M15.5 8.5a5 5 0 0 0 0 7" />
          <path d="M18.5 5.5a9 9 0 0 0 0 13" />
        </svg>
        <svg
          v-else-if="status === 'generating'"
          class="reader-float__spin"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          aria-hidden="true"
        >
          <path d="M21 12a9 9 0 1 1-6.22-8.56" />
        </svg>
        <svg
          v-else-if="status === 'playing'"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2.5"
          stroke-linecap="round"
          aria-hidden="true"
        >
          <path d="M9 5v14" />
          <path d="M15 5v14" />
        </svg>
        <svg
          v-else
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linejoin="round"
          aria-hidden="true"
        >
          <path d="M7 5l12 7-12 7z" />
        </svg>
      </button>

      <span class="reader-float__status">{{ statusLabel }}</span>

      <select
        v-if="useModelVoice"
        class="reader-float__select"
        aria-label="模型朗读音色"
        title="模型朗读音色"
        :value="modelVoice"
        @change="emit('model-voice-change', ($event.target as HTMLSelectElement).value)"
      >
        <option v-for="option in modelVoiceOptions" :key="option.voice" :value="option.voice">
          {{ option.label }}
        </option>
      </select>
      <select
        v-else-if="showVoiceControl"
        class="reader-float__select"
        aria-label="朗读音色"
        title="朗读音色"
        :value="voiceURI"
        @change="emit('voice-change', ($event.target as HTMLSelectElement).value)"
      >
        <option value="">默认音色</option>
        <option v-for="voice in voiceOptions" :key="voice.uri" :value="voice.uri">
          {{ voice.label }}
        </option>
      </select>
      <button
        v-if="useModelVoice || showVoiceControl"
        type="button"
        class="md-btn md-btn-text md-ripple reader-float__btn reader-float__btn--preview"
        :disabled="status !== 'idle'"
        :aria-label="status !== 'idle' ? '朗读中无法试听' : '试听音色'"
        :title="status !== 'idle' ? '朗读中无法试听，请先停止' : '试听当前音色'"
        @click="emit('preview-voice')"
      >
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"
        >
          <path d="M2 12h2" />
          <path d="M6 9v6" />
          <path d="M10 5v14" />
          <path d="M14 8v8" />
          <path d="M18 10v4" />
          <path d="M20 12h2" />
        </svg>
      </button>

      <select
        class="reader-float__select reader-float__select--rate"
        aria-label="朗读倍速"
        title="朗读倍速"
        :value="rate"
        @change="emit('rate-change', Number(($event.target as HTMLSelectElement).value))"
      >
        <option v-for="option in rateOptions" :key="option" :value="option">
          {{ option }}x
        </option>
      </select>

      <button
        v-if="status !== 'idle'"
        type="button"
        class="md-btn md-btn-text md-ripple reader-float__btn reader-float__btn--reset"
        aria-label="停止朗读"
        title="停止朗读"
        @click="emit('reset')"
      >
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2.5"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"
        >
          <rect x="6" y="6" width="12" height="12" rx="1.5" />
        </svg>
      </button>
    </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import type { ReaderStatus } from '@/composables/useChapterReader'

interface Props {
  status: ReaderStatus
  isBrowserFallback: boolean
  hasModelTTS: boolean
  modelVoice: string
  modelVoiceOptions: { voice: string; label: string }[]
  currentParagraphIndex: number
  paragraphCount: number
  voiceURI: string
  rate: number
  voiceOptions: { uri: string; label: string }[]
  rateOptions: number[]
}

const props = defineProps<Props>()

const emit = defineEmits<{
  start: []
  'play-pause': []
  reset: []
  'voice-change': [uri: string]
  'model-voice-change': [voice: string]
  'rate-change': [rate: number]
  'preview-voice': []
}>()

// idle 也露出音色+试听，供朗读前预选预听；模型 TTS 播放中隐藏
const showVoiceControl = computed(() => props.isBrowserFallback || props.status === 'idle')
// 配了默认 TTS 模型且未回退浏览器时，音色由后端模型决定，控件只读展示模型音色
const useModelVoice = computed(() => props.hasModelTTS && !props.isBrowserFallback)

const statusLabel = computed(() => {
  const idx = props.currentParagraphIndex
  const total = props.paragraphCount
  const position = idx >= 0 && total > 0 ? ` · 第 ${idx + 1}/${total} 段` : ''
  if (props.status === 'idle') return '准备朗读'
  if (props.status === 'generating') return '准备朗读…'
  if (props.status === 'paused') return `已暂停${position}`
  return `朗读中${position}`
})

const mainLabel = computed(() => {
  if (props.status === 'playing') return '暂停'
  if (props.status === 'paused') return '继续'
  if (props.status === 'generating') return '停止'
  return '朗读'
})

const onMainClick = () => {
  if (props.status === 'idle') emit('start')
  else emit('play-pause')
}
</script>

<style scoped>
.reader-float {
  position: absolute;
  top: 8px;
  right: 12px;
  z-index: 30;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px 8px 12px;
  background-color: var(--md-surface);
  border: 1.5px solid var(--md-outline);
  border-left: 3px solid #9c2720; /* 朱砂引首竖线 */
  border-radius: 2px;
  box-shadow: 3px 3px 0px rgba(28, 32, 34, 0.85); /* 硬偏移水墨阴影 */
  font-family: var(--md-font-serif);
}

.reader-float__btn {
  height: 32px;
  min-height: 32px;
  width: 32px;
  padding-inline: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 0;
  border: 1px solid var(--md-outline);
  box-shadow: 1.5px 1.5px 0px var(--md-outline);
  color: var(--md-on-surface-variant);
  background-color: var(--md-surface);
  transition:
    color 0.2s ease,
    border-color 0.2s ease,
    box-shadow 0.2s ease,
    transform 0.2s ease;
}

.reader-float__btn svg {
  width: 18px;
  height: 18px;
}

.reader-float__btn:hover:not(:disabled) {
  color: var(--md-primary-container);
  border-color: var(--md-primary-container);
}

.reader-float__btn:active:not(:disabled) {
  transform: translate(1px, 1px);
  box-shadow: 0 0 0 var(--md-outline);
}

.reader-float__btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.reader-float__btn--main {
  color: var(--md-primary-container);
  border-color: var(--md-primary-container);
}

.reader-float__btn--reset svg {
  color: var(--md-primary-container);
}

.reader-float__spin {
  animation: reader-float-spin 1s linear infinite;
}

@keyframes reader-float-spin {
  to {
    transform: rotate(360deg);
  }
}

.reader-float__status {
  font-size: 13px;
  color: var(--md-on-surface-variant);
  letter-spacing: 0.02em;
  white-space: nowrap;
  max-width: 16ch;
  overflow: hidden;
  text-overflow: ellipsis;
}

.reader-float__select {
  height: 28px;
  max-width: 9em;
  padding-inline: 6px;
  font-size: 12px;
  color: var(--md-on-surface-variant);
  background-color: var(--md-surface);
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-xs);
  cursor: pointer;
}

@media (max-width: 1199px) {
  .reader-float {
    flex-wrap: wrap;
  }
}

@media (max-width: 640px) {
  .reader-float__status {
    max-width: 10ch;
  }
}
</style>
