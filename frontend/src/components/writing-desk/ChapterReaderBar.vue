<template>
  <div
    ref="readerFloatRef"
    class="reader-float"
    :class="{
      'reader-float--expanded': isExpanded,
      'reader-float--playing': status === 'playing',
    }"
    role="region"
    aria-label="章节朗读"
    @mouseenter="expandReader"
    @mouseleave="collapseFromPointer"
    @focusin="expandFromFocus"
    @focusout="collapseFromFocus"
    @keydown.esc.stop.prevent="collapseReader"
  >
    <button
      ref="mainButtonRef"
      type="button"
      class="md-btn md-btn-text md-ripple reader-float__btn reader-float__btn--main"
      :aria-label="mainLabel"
      :title="mainLabel"
      :aria-expanded="isExpanded ? 'true' : 'false'"
      aria-controls="chapter-reader-controls"
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

    <div v-if="isExpanded" id="chapter-reader-controls" class="reader-float__panel">
      <span class="reader-float__status" aria-live="polite">
        {{ statusLabel }}
      </span>

      <label
        v-if="hasModelTTS"
        class="reader-float__engine"
        title="勾选后即使配了模型，也用浏览器内置语音朗读"
      >
        <input
          type="checkbox"
          class="reader-float__checkbox"
          :checked="forceBrowser"
          @change="emit('force-browser-change', ($event.target as HTMLInputElement).checked)"
        />
        <span>兼容</span>
      </label>

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
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <path d="M2 12h2M6 9v6M10 5v14M14 8v8M18 10v4M20 12h2" />
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
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true">
          <rect x="6" y="6" width="12" height="12" rx="1.5" />
        </svg>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'

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
  forceBrowser: boolean
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
  'force-browser-change': [force: boolean]
  'rate-change': [rate: number]
  'preview-voice': []
}>()
const readerFloatRef = ref<HTMLElement | null>(null)
const mainButtonRef = ref<HTMLButtonElement | null>(null)
const isExpanded = ref(false)
let suppressFocusExpansion = false

const showVoiceControl = computed(
  () => props.forceBrowser || props.isBrowserFallback || props.status === 'idle',
)
const useModelVoice = computed(
  () => props.hasModelTTS && !props.isBrowserFallback && !props.forceBrowser,
)

const statusLabel = computed(() => {
  const position =
    props.currentParagraphIndex >= 0 && props.paragraphCount > 0
      ? ` · 第 ${props.currentParagraphIndex + 1}/${props.paragraphCount} 段`
      : ''
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

const expandReader = () => {
  isExpanded.value = true
}

const expandFromFocus = () => {
  if (suppressFocusExpansion) return
  expandReader()
}

const collapseReader = () => {
  isExpanded.value = false
  suppressFocusExpansion = true
  void nextTick(() => {
    mainButtonRef.value?.focus()
    suppressFocusExpansion = false
  })
}

const collapseFromPointer = () => {
  if (readerFloatRef.value?.contains(document.activeElement)) return
  isExpanded.value = false
}

const collapseFromFocus = (event: FocusEvent) => {
  const nextTarget = event.relatedTarget
  if (nextTarget instanceof Node && readerFloatRef.value?.contains(nextTarget)) return
  isExpanded.value = false
}

const onMainClick = () => {
  isExpanded.value = true
  if (props.status === 'idle') emit('start')
  else emit('play-pause')
}
</script>

<style scoped>
.reader-float {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 30;
  display: flex;
  flex-direction: row-reverse;
  align-items: center;
  max-width: calc(100% - 24px);
  color: var(--md-on-surface-variant);
  font-family: var(--md-font-family);
}

.reader-float--expanded {
  gap: 6px;
  padding-left: 8px;
  border: 1px solid var(--md-outline-variant);
  border-radius: 23px var(--md-radius-sm) var(--md-radius-sm) 23px;
  background-color: var(--md-surface);
  box-shadow: var(--md-elevation-paper-2);
}

.reader-float__panel {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 6px;
  overflow-x: auto;
  animation: reader-panel-reveal 0.2s cubic-bezier(0.22, 1, 0.36, 1) both;
}

.reader-float__btn {
  display: inline-flex;
  flex: 0 0 44px;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  min-height: 44px;
  padding: 0;
  border: 1px solid var(--md-outline-variant);
  border-radius: 50%;
  background-color: color-mix(in srgb, var(--md-surface) 76%, transparent);
  color: var(--md-on-surface);
  box-shadow: var(--md-elevation-paper-1);
  transition:
    background-color 0.2s var(--md-easing-standard),
    border-color 0.2s var(--md-easing-standard),
    color 0.2s var(--md-easing-standard);
}

.reader-float--expanded .reader-float__btn--main,
.reader-float__btn:hover:not(:disabled) {
  border-color: var(--md-outline);
  background-color: var(--md-surface-container-high);
}

.reader-float--playing .reader-float__btn--main {
  border-color: var(--md-primary-container);
  background-color: var(--md-primary-container);
  color: var(--md-on-primary-container);
}

.reader-float__btn:focus-visible,
.reader-float__select:focus-visible,
.reader-float__checkbox:focus-visible {
  outline: 2px solid var(--md-on-surface);
  outline-offset: 2px;
}

.reader-float__btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.reader-float__btn svg {
  width: 18px;
  height: 18px;
}

.reader-float__status {
  max-width: 16ch;
  overflow: hidden;
  color: var(--md-on-surface-variant);
  font-size: 13px;
  letter-spacing: 0.02em;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.reader-float__engine {
  display: inline-flex;
  min-height: 44px;
  align-items: center;
  gap: 4px;
  color: var(--md-on-surface-variant);
  font-size: 12px;
  cursor: pointer;
  user-select: none;
}

.reader-float__checkbox {
  width: 16px;
  height: 16px;
  accent-color: var(--md-secondary);
}

.reader-float__select {
  height: 44px;
  max-width: 12em;
  padding-inline: 8px;
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-xs);
  background-color: var(--md-surface);
  color: var(--md-on-surface-variant);
  font-size: 12px;
}

.reader-float__select--rate {
  width: 68px;
}

.reader-float__spin {
  animation: reader-float-spin 1s linear infinite;
}

@keyframes reader-panel-reveal {
  from {
    opacity: 0;
    transform: translateX(8px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

@keyframes reader-float-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 640px) {
  .reader-float__status {
    display: none;
  }
}

@media (prefers-reduced-motion: reduce) {
  .reader-float__panel,
  .reader-float__spin {
    animation: none;
  }
}
</style>
