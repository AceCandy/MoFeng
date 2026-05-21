<!-- AIMETA P=对话输入_用户输入组件|R=输入框_发送|NR=不含消息展示|E=component:ConversationInput|X=internal|A=输入组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="fade-in">
    <!-- 加载状态 -->
    <div v-if="loading || !uiControl" class="flex justify-center items-center p-4" role="status" aria-live="polite">
      <div class="loader"></div>
      <span class="sr-only">正在加载输入控件</span>
    </div>

    <!-- 单选题 -->
    <div v-else-if="uiControl.type === 'single_choice'">
      <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
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
          rows="5"
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
        rows="5"
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

const MIN_ROWS = 5
const MAX_ROWS = 5

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
  padding: var(--md-spacing-3) var(--md-spacing-4);
  border-radius: var(--md-radius-sm);
  font-weight: 500;
  font-size: var(--md-body-medium);
  transition: background-color 0.15s, color 0.15s;
  cursor: pointer;
  border: none;
}

.conv-input__option--primary {
  background-color: var(--md-primary-container);
  color: var(--md-on-primary-container);
}

.conv-input__option--primary:hover {
  background-color: var(--md-primary);
  color: var(--md-on-primary);
}

.conv-input__option--neutral {
  background-color: var(--md-surface-container);
  color: var(--md-on-surface-variant);
}

.conv-input__option--neutral:hover {
  background-color: var(--md-surface-container-high);
  color: var(--md-on-surface);
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
</style>
