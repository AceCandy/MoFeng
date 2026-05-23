<!-- AIMETA P=对话输入_用户输入组件|R=输入框_发送|NR=不含消息展示|E=component:ConversationInput|X=internal|A=输入组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="fade-in">
    <!-- 加载状态 -->
    <div v-if="loading || !uiControl" class="flex justify-center items-center gap-4 p-4" role="status" aria-live="polite">
      <!-- 极致国风水墨/朱砂双色洇染等待器 -->
      <div class="ink-bloom-loader" aria-hidden="true">
        <div class="ink-bloom-dot ink-bloom-dot--black"></div>
        <div class="ink-bloom-dot ink-bloom-dot--red"></div>
      </div>
      <span class="inspiration-loading-text">文思正提笔研墨，恭候阁主落座起笔...</span>
    </div>

    <!-- 单选题 -->
    <div v-else-if="uiControl.type === 'single_choice'">
      <div class="flex flex-wrap gap-2 mb-3 max-h-[110px] overflow-y-auto pr-1 conv-input__options-scroll">
        <button
          v-for="option in uiControl.options"
          :key="option.id"
          type="button"
          @click="handleOptionSelect(option.id, option.label)"
          class="conv-input__option conv-input__option--primary"
        >
          {{ option.label }}
        </button>
        <button
          type="button"
          @click="isManualInput = true"
          class="conv-input__option conv-input__option--neutral"
        >
          我要输入
        </button>
      </div>
      <form @submit.prevent="handleTextSubmit" class="flex items-center gap-3">
        <label :for="manualTextareaId" class="sr-only">输入你的想法</label>
        <textarea
          :id="manualTextareaId"
          v-model="textInput"
          :placeholder="isManualInput ? '请输入您的想法...' : '选择上方选项或点击「我要输入」'"
          class="conv-input__textarea"
          :disabled="!isManualInput"
          rows="2"
          ref="textInputRef"
          @input="handleTextareaInput"
        ></textarea>
        <button
          type="submit"
          class="conv-input__send"
          :disabled="!isManualInput"
          aria-label="发送"
        >
          <svg
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <line x1="22" y1="2" x2="11" y2="13"></line>
            <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
          </svg>
        </button>
      </form>
    </div>

    <!-- 文本输入 -->
    <form v-else-if="uiControl.type === 'text_input'" @submit.prevent="handleTextSubmit" class="flex items-center gap-3">
      <label :for="textInputTextareaId" class="sr-only">输入内容</label>
      <textarea
        :id="textInputTextareaId"
        v-model="textInput"
        :placeholder="uiControl.placeholder || '请输入...'"
        class="conv-input__textarea"
        required
        ref="textInputRef"
        rows="2"
        @input="handleTextareaInput"
      ></textarea>
      <button
        type="submit"
        class="conv-input__send"
        aria-label="发送"
      >
        <svg
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <line x1="22" y1="2" x2="11" y2="13"></line>
          <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
        </svg>
      </button>
    </form>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import type { UIControl } from '@/api/novel'

interface Props {
  uiControl: UIControl | null
  loading: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{
  submit: [userInput: { id: string; value: string } | null]
}>()

const controlIdPrefix = `conv-input-${Math.random().toString(36).slice(2, 10)}`
const manualTextareaId = `${controlIdPrefix}-manual-textarea`
const textInputTextareaId = `${controlIdPrefix}-text-textarea`

const textInput = ref('')
const textInputRef = ref<HTMLTextAreaElement>()
const isManualInput = ref(false)

const MIN_ROWS = 2
const MAX_ROWS = 4

const adjustTextareaHeight = () => {
  const textarea = textInputRef.value
  if (!textarea) {
    return
  }
  if (typeof window === 'undefined') {
    return
  }

  const lineHeight = parseFloat(window.getComputedStyle(textarea).lineHeight || '0') || 20
  const minHeight = lineHeight * MIN_ROWS
  const maxHeight = lineHeight * MAX_ROWS

  textarea.style.height = 'auto'
  const targetHeight = Math.min(maxHeight, Math.max(minHeight, textarea.scrollHeight))
  textarea.style.height = `${targetHeight}px`
}

const handleTextareaInput = () => {
  adjustTextareaHeight()
}

const handleOptionSelect = (id: string, label: string) => {
  emit('submit', { id, value: label })
}

const handleTextSubmit = () => {
  if (textInput.value.trim()) {
    emit('submit', { id: 'text_input', value: textInput.value.trim() })
    textInput.value = ''
    nextTick(() => adjustTextareaHeight())
  }
}

const getControlIdentity = (control: UIControl | null) => {
  if (!control) return 'empty'
  if (control.type === 'single_choice') {
    const optionIds = control.options?.map((option) => option.id).join('|') ?? ''
    return `${control.type}:${optionIds}`
  }
  return control.type
}

// 只有输入控件身份真正变化时，才重置草稿并在需要时聚焦。
watch(
  () => getControlIdentity(props.uiControl),
  async () => {
    isManualInput.value = false
    textInput.value = ''

    await nextTick()
    adjustTextareaHeight()

    if (props.uiControl?.type === 'text_input') {
      textInputRef.value?.focus()
    }
  },
)

// 监听手动输入状态的变化，以聚焦输入框
watch(isManualInput, async (newValue) => {
  if (newValue) {
    await nextTick()
    adjustTextareaHeight()
    textInputRef.value?.focus()
  }
})

</script>

<style scoped>
.conv-input__option {
  padding: 6px 12px !important;
  border-radius: var(--md-radius-xs) !important; /* 极窄 2px 微直角 */
  font-weight: 500;
  font-size: 13px !important; /* 字号缩小 */
  border: 1px solid var(--md-outline-variant) !important; /* 初始墨晕细线 */
  background-color: var(--md-surface-container-lowest) !important;
  color: var(--md-on-surface-variant) !important;
  transition: all var(--md-duration-short) var(--md-easing-standard) !important;
  cursor: pointer;
  box-shadow: 1px 1px 0px rgba(28, 32, 34, 0.03) !important;
}

.conv-input__option--primary {
  background-color: var(--md-surface-container-low) !important;
  border-color: var(--md-outline) !important; /* 干燥竹青框线 */
  color: var(--md-primary) !important;
}

.conv-input__option--primary:hover {
  background-color: rgba(184, 60, 50, 0.05) !important; /* 润以朱砂红泥 */
  border-color: var(--md-secondary) !important; /* 朱砂红 */
  color: var(--md-secondary) !important;
  box-shadow: 2px 2px 0px rgba(184, 60, 50, 0.12) !important;
}

.conv-input__option--neutral {
  background-color: var(--md-surface-dim) !important;
  border-color: var(--md-outline-variant) !important;
  color: var(--md-on-surface-variant) !important;
}

.conv-input__option--neutral:hover {
  background-color: rgba(28, 32, 34, 0.04) !important;
  border-color: var(--md-primary) !important;
  color: var(--md-primary) !important;
  box-shadow: 2px 2px 0px rgba(28, 32, 34, 0.08) !important;
}

/* 选项滚动条 */
.conv-input__options-scroll::-webkit-scrollbar {
  width: 4px;
}

.conv-input__options-scroll::-webkit-scrollbar-thumb {
  background-color: var(--md-outline-variant);
  border-radius: var(--md-radius-xs);
}

.conv-input__options-scroll::-webkit-scrollbar-thumb:hover {
  background-color: var(--md-outline);
}

.conv-input__option:focus-visible {
  outline: 2px solid var(--md-primary);
  outline-offset: 2px;
}

.conv-input__textarea {
  flex: 1;
  padding: var(--md-spacing-3) var(--md-spacing-4);
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-md);
  background-color: var(--md-surface);
  color: var(--md-on-surface);
  font-size: var(--md-body-medium);
  resize: none;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.conv-input__textarea:focus {
  outline: none;
  border-color: var(--md-primary);
  box-shadow: 0 0 0 2px color-mix(in oklch, var(--md-primary) 20%, transparent);
}

.conv-input__textarea:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.conv-input__send {
  width: 44px;
  height: 44px;
  border-radius: var(--md-radius-full);
  background-color: var(--md-primary);
  color: var(--md-on-primary);
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background-color 0.15s, opacity 0.15s;
  flex-shrink: 0;
}

.conv-input__send:hover {
  background-color: color-mix(in oklch, var(--md-primary) 82%, var(--md-primary-dark));
}

.conv-input__send:focus-visible {
  outline: 2px solid var(--md-primary);
  outline-offset: 2px;
}

.conv-input__send:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* ============================================
   极致国风水墨洇染 Loading 动效 (输入框端)
   ============================================ */
.ink-bloom-loader {
  width: 20px;
  height: 20px;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

/* 核心洇墨黑红双点，模拟松烟入墨与朱砂落印的晕染 */
.ink-bloom-dot {
  position: absolute;
  width: 8px;
  height: 8px;
  border-radius: var(--md-radius-full) !important;
  mix-blend-mode: multiply; /* 叠印色晕交融 */
}

/* 焦墨松烟 */
.ink-bloom-dot--black {
  background-color: var(--md-primary) !important;
  animation: ink-bloom-black 2.2s cubic-bezier(0.25, 1, 0.5, 1) infinite;
}

/* 润以朱砂 */
.ink-bloom-dot--red {
  background-color: var(--md-secondary) !important;
  animation: ink-bloom-red 2.2s cubic-bezier(0.25, 1, 0.5, 1) infinite;
  animation-delay: 1.1s;
}

@keyframes ink-bloom-black {
  0% {
    transform: scale(0.2) translate(0, 0);
    filter: blur(0.8px);
    opacity: 0.9;
  }
  50% {
    transform: scale(1.8) translate(-1.5px, -0.8px);
    filter: blur(4px);
    opacity: 0.35;
  }
  100% {
    transform: scale(2.6) translate(-3px, -1.5px);
    filter: blur(8px);
    opacity: 0;
  }
}

@keyframes ink-bloom-red {
  0% {
    transform: scale(0.2) translate(0, 0);
    filter: blur(0.8px);
    opacity: 0.8;
  }
  50% {
    transform: scale(1.6) translate(1.5px, 0.8px);
    filter: blur(3.5px);
    opacity: 0.3;
  }
  100% {
    transform: scale(2.3) translate(3px, 1.5px);
    filter: blur(7px);
    opacity: 0;
  }
}

/* 古风文字运墨状态呼吸 */
.inspiration-loading-text {
  font-family: var(--md-font-serif, "STSong", "Songti SC", serif) !important;
  font-size: 13.5px !important;
  font-weight: 600 !important;
  color: var(--md-on-surface-variant) !important;
  letter-spacing: 0.05em !important;
  animation: ink-text-breath 2.2s ease-in-out infinite alternate !important;
  text-shadow: 0.5px 0.5px 0px rgba(28, 32, 34, 0.04) !important;
}

@keyframes ink-text-breath {
  0% {
    opacity: 0.45;
    filter: blur(0.5px);
  }
  100% {
    opacity: 0.95;
    filter: blur(0px);
  }
}
</style>
