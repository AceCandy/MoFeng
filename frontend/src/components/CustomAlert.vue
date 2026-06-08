<!-- AIMETA P=自定义提示_提示消息组件|R=提示弹窗|NR=不含业务逻辑|E=component:CustomAlert|X=internal|A=提示组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <Teleport to="body">
    <transition
      enter-active-class="transition-opacity duration-200"
      leave-active-class="transition-opacity duration-200"
      enter-from-class="opacity-0"
      leave-to-class="opacity-0"
    >
      <div
        v-if="visible"
        class="md-dialog-overlay"
        @click.self="handleClose"
      >
        <transition
          enter-active-class="transition-[opacity,transform] duration-300"
          leave-active-class="transition-[opacity,transform] duration-200"
          enter-from-class="opacity-0 scale-95"
          leave-to-class="opacity-0 scale-95"
        >
          <div
            ref="dialogRef"
            class="md-dialog max-w-md w-full mx-4"
            role="dialog"
            aria-modal="true"
            :aria-labelledby="dialogTitleId"
            :aria-describedby="dialogMessageId"
          >
            <!-- 国风印章标题头部 -->
            <div class="md-dialog-header flex items-center gap-4">
              <!-- 朱砂/金石印章 -->
              <div
                class="w-10 h-10 flex items-center justify-center flex-shrink-0 custom-alert-seal"
                :class="`custom-alert-seal--${type}`"
              >
                <span class="custom-alert-seal-text">{{ sealText }}</span>
              </div>
              <div>
                <h3 :id="dialogTitleId" class="md-dialog-title">{{ titleText }}</h3>
              </div>
            </div>

            <!-- 红丝栏分割线 -->
            <div class="custom-alert-divider"></div>

            <!-- 笺格写字板内容区 -->
            <div class="md-dialog-content">
              <p :id="dialogMessageId" class="md-body-large dialog-message-content">{{ message }}</p>
              <label v-if="showInput" class="custom-alert__input-field">
                <span class="custom-alert-input-label">{{ inputLabel }}</span>
                <input
                  v-model="inputValue"
                  class="custom-alert-underline-input"
                  type="text"
                  :placeholder="inputPlaceholder"
                  autocomplete="off"
                />
              </label>
            </div>

            <!-- 国风金石钤印按钮区 -->
            <div class="md-dialog-actions">
              <button
                v-if="showCancel"
                @click="handleCancel"
                class="md-btn md-btn-text md-ripple custom-alert-btn-cancel"
              >
                {{ cancelText }}
              </button>
              <button
                ref="confirmButtonRef"
                data-dialog-initial-focus
                @click="handleConfirm"
                class="md-btn md-ripple custom-alert-btn-confirm"
                :class="`custom-alert-btn-confirm--${type}`"
              >
                {{ confirmText }}
              </button>
            </div>
          </div>
        </transition>
      </div>
    </transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, ref, toRef } from 'vue'
import { useDialogA11y } from '@/composables/useDialogA11y'

interface Props {
  visible: boolean
  type?: 'success' | 'error' | 'warning' | 'info' | 'confirmation'
  title?: string
  message: string
  showCancel?: boolean
  confirmText?: string
  cancelText?: string
  showInput?: boolean
  inputLabel?: string
  inputPlaceholder?: string
}

const props = withDefaults(defineProps<Props>(), {
  type: 'info',
  title: '',
  showCancel: false,
  confirmText: '确定',
  cancelText: '取消',
  showInput: false,
  inputLabel: '',
  inputPlaceholder: ''
})

const emit = defineEmits<{
  confirm: [inputValue?: string]
  cancel: []
  close: []
}>()

const dialogRef = ref<HTMLElement | null>(null)
const confirmButtonRef = ref<HTMLElement | null>(null)
const inputValue = ref('')
const dialogInstanceId = `custom-alert-${Math.random().toString(36).slice(2, 10)}`
const dialogTitleId = `${dialogInstanceId}-title`
const dialogMessageId = `${dialogInstanceId}-message`

const titleText = computed(() => {
  if (props.title) return props.title

  switch (props.type) {
    case 'success': return '操作成功'
    case 'error': return '出现错误'
    case 'warning': return '警告提示'
    case 'confirmation': return '请确认'
    default: return '提示信息'
  }
})

// 金石印章文字计算
const sealText = computed(() => {
  switch (props.type) {
    case 'success': return '捷'
    case 'error': return '误'
    case 'warning': return '警'
    case 'confirmation': return '慎'
    default: return '信'
  }
})

const handleConfirm = () => {
  emit('confirm', props.showInput ? inputValue.value : undefined)
  emit('close')
}

const handleCancel = () => {
  emit('cancel')
  emit('close')
}

const handleClose = () => {
  emit('close')
}

useDialogA11y({
  active: toRef(props, 'visible'),
  dialogRef,
  onClose: handleClose,
  initialFocusRef: confirmButtonRef,
})
</script>

<style scoped>
/* 国风笺纸手札弹窗本体 */
.md-dialog {
  border-radius: 0 !important;
  border: 3px double var(--md-outline) !important;
  box-shadow: 4px 4px 0px rgba(28, 32, 34, 0.15) !important;
  background-color: var(--md-surface) !important;
  /* 熟宣帘纹背景 */
  background-image: repeating-linear-gradient(90deg, rgba(28, 32, 34, 0.005) 0px, rgba(28, 32, 34, 0.005) 1px, transparent 1px, transparent 20px);
}

/* 朱砂/金石印章本体 */
.custom-alert-seal {
  border: 1.5px solid var(--md-outline-variant);
  background-color: transparent;
  font-family: var(--md-font-serif);
  font-size: 18px;
  font-weight: bold;
  line-height: 1;
  transform: rotate(-4deg); /* 盖印的随机倾斜感 */
  transition: all 0.3s ease;
}

/* 印章配色体系 */
.custom-alert-seal--success {
  border-color: rgba(63, 108, 93, 0.8) !important;
  color: #3f6c5d !important;
  background-color: rgba(63, 108, 93, 0.05);
}

.custom-alert-seal--error,
.custom-alert-seal--warning {
  border-color: rgba(184, 60, 50, 0.8) !important;
  color: #c94036 !important;
  background-color: rgba(184, 60, 50, 0.05);
}

.custom-alert-seal--confirmation {
  border-color: rgba(200, 123, 46, 0.8) !important;
  color: #c87b2e !important;
  background-color: rgba(200, 123, 46, 0.05);
}

.custom-alert-seal--info {
  border-color: rgba(28, 32, 34, 0.6) !important;
  color: #5c6265 !important;
  background-color: rgba(28, 32, 34, 0.03);
}

/* 红丝栏分割线 */
.custom-alert-divider {
  height: 1px;
  background-image: linear-gradient(to right, rgba(184, 60, 50, 0.25) 0%, rgba(184, 60, 50, 0.25) 80%, transparent 100%);
  margin: 12px 24px 0;
}

/* 信笺写字格子内容 */
.dialog-message-content {
  color: var(--md-on-surface-variant) !important;
  font-family: var(--md-font-serif), var(--md-font-family);
  line-height: 1.65;
  letter-spacing: 0.02em;
}

.custom-alert__input-field {
  display: grid;
  gap: 8px;
  margin-top: 16px;
}

.custom-alert-input-label {
  color: var(--md-on-surface);
  font-size: var(--md-label-medium);
  font-weight: 600;
  font-family: var(--md-font-serif);
}

/* 乌丝栏下划线输入框 */
.custom-alert-underline-input {
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

.custom-alert-underline-input:focus {
  border-bottom-color: var(--md-secondary);
}

/* 按钮微调 */
.custom-alert-btn-cancel {
  font-family: var(--md-font-serif);
  font-weight: 600;
  color: var(--md-on-surface-variant) !important;
  transition: all 0.2s ease;
}

.custom-alert-btn-cancel:hover {
  color: var(--md-secondary) !important;
  background-color: rgba(184, 60, 50, 0.03) !important;
}

.custom-alert-btn-confirm {
  font-family: var(--md-font-serif);
  font-weight: bold;
  border-radius: 0 !important;
  border: 1px solid var(--md-outline);
  background-color: transparent !important;
  color: var(--md-on-surface) !important;
  box-shadow: 1.5px 1.5px 0px var(--md-outline);
  transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

.custom-alert-btn-confirm:hover {
  transform: translate(-0.5px, -0.5px);
  box-shadow: 2px 2px 0px var(--md-outline);
  background-color: var(--md-surface-container-low) !important;
}

.custom-alert-btn-confirm:active {
  transform: translate(1px, 1px) !important;
  box-shadow: 0px 0px 0px var(--md-outline) !important;
}

/* 确认按钮中式色彩映射 */
.custom-alert-btn-confirm--error,
.custom-alert-btn-confirm--warning {
  border-color: var(--md-secondary) !important;
  color: var(--md-secondary) !important;
  box-shadow: 1.5px 1.5px 0px var(--md-secondary);
}

.custom-alert-btn-confirm--error:hover,
.custom-alert-btn-confirm--warning:hover {
  background-color: rgba(184, 60, 50, 0.05) !important;
  box-shadow: 2.5px 2.5px 0px var(--md-secondary);
}

.custom-alert-btn-confirm--error:active,
.custom-alert-btn-confirm--warning:active {
  box-shadow: 0px 0px 0px var(--md-secondary) !important;
}

.custom-alert-btn-confirm--success {
  border-color: #3f6c5d !important;
  color: #3f6c5d !important;
  box-shadow: 1.5px 1.5px 0px #3f6c5d;
}

.custom-alert-btn-confirm--success:hover {
  background-color: rgba(63, 108, 93, 0.05) !important;
  box-shadow: 2.5px 2.5px 0px #3f6c5d;
}

.custom-alert-btn-confirm--success:active {
  box-shadow: 0px 0px 0px #3f6c5d !important;
}
</style>
