<!-- AIMETA P=通用组件_水墨大弹窗容器|R=弹窗容器_水墨遮罩_中式边框|NR=不含具体业务逻辑|E=component:GlobalModalContainer|X=ui|A=弹窗容器|D=vue|S=dom|RD=./README.ai -->
<script setup lang="ts">
import { ref, useId } from 'vue'
import { useDialogA11y } from '@/composables/useDialogA11y'

const props = withDefaults(
  defineProps<{
    title?: string
    width?: string
    hideCloseButton?: boolean
    badgeText?: string
  }>(),
  {
    title: '能力配置',
    width: 'min(92vw, 1100px)',
    hideCloseButton: false,
  }
)

const emit = defineEmits<{
  (e: 'close'): void
}>()

const modalBoxRef = ref<HTMLElement | null>(null)
const closeButtonRef = ref<HTMLElement | null>(null)
const active = ref(true)
const titleId = useId()

const handleClose = () => {
  emit('close')
}

useDialogA11y({
  active,
  dialogRef: modalBoxRef,
  initialFocusRef: closeButtonRef,
  onClose: handleClose,
})
</script>

<template>
  <div class="m3-ink-modal-overlay" @click.self="handleClose">
    <div
      ref="modalBoxRef"
      class="m3-ink-modal-box"
      :style="{ width: props.width }"
      role="dialog"
      aria-modal="true"
      :aria-labelledby="titleId"
      tabindex="-1"
    >
      <!-- 四角黄铜古角扣 -->
      <div class="m3-ink-modal-corner is-top-left" aria-hidden="true"></div>
      <div class="m3-ink-modal-corner is-top-right" aria-hidden="true"></div>
      <div class="m3-ink-modal-corner is-bottom-left" aria-hidden="true"></div>
      <div class="m3-ink-modal-corner is-bottom-right" aria-hidden="true"></div>

      <!-- 弹窗头部：宣纸印签标题 -->
      <header class="m3-ink-modal-header">
        <div class="m3-ink-modal-header__brand">
          <span v-if="props.badgeText !== '' && props.title" class="m3-ink-modal-header__badge">
            {{ props.badgeText || props.title.slice(0, 1) }}
          </span>
          <h2 :id="titleId" class="m3-ink-modal-header__title">
            {{ props.title }}
          </h2>
        </div>

        <div class="m3-ink-modal-header__actions">
          <slot name="header-actions" />

          <!-- 朱砂钤印风格关闭按钮 -->
          <button
            v-if="!props.hideCloseButton"
            ref="closeButtonRef"
            type="button"
            class="m3-ink-modal-close-btn"
            :aria-label="`关闭${props.title}`"
            :title="`关闭${props.title}`"
            @click="handleClose"
          >
            <span class="m3-ink-modal-close-badge">閉</span>
            <span class="m3-ink-modal-close-text">关闭</span>
          </button>
        </div>
      </header>

      <!-- 弹窗主体：古籍双线滚动区域 -->
      <div class="m3-ink-modal-body">
        <slot />
      </div>
    </div>
  </div>
</template>

<style scoped>
/* 核心 CSS 都直接写入 scoped，少量全局水墨动效由 main.css 覆盖 */
.m3-ink-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--md-spacing-4);
  background-color: color-mix(in srgb, var(--md-primary-dark) 76%, transparent);
  animation: inkFadeIn 0.3s cubic-bezier(0.25, 0.8, 0.25, 1) forwards;
}

.m3-ink-modal-box {
  position: relative;
  max-height: 88vh;
  display: flex;
  flex-direction: column;
  background-color: var(--md-surface-bright);
  border: 1px solid var(--md-jiege); /* 1px 界格发线 */
  border-radius: var(--md-radius-xs);
  box-shadow: var(--md-elevation-paper-2); /* 弹层上浮 */
  outline: none;
  animation: scrollFoldOpen 0.35s cubic-bezier(0.22, 1, 0.36, 1) forwards;
}

/* 深色模式（深夜书房）适配 */
:global([data-theme='dark']) .m3-ink-modal-box,
:global(.dark) .m3-ink-modal-box {
  background-color: var(--md-surface);
  border-color: var(--md-jiege);
  box-shadow: var(--md-elevation-paper-2);
}

/* 四角古黄铜包角扣 */
.m3-ink-modal-corner {
  position: absolute;
  width: 14px;
  height: 14px;
  border: 2.5px solid var(--md-warning); /* 仿古黄铜金 */
  pointer-events: none;
  z-index: 10;
  opacity: 0.85;
}

.is-top-left {
  top: -2px;
  left: -2px;
  border-right: none;
  border-bottom: none;
  border-top-left-radius: var(--md-radius-md, 6px);
}

.is-top-right {
  top: -2px;
  right: -2px;
  border-left: none;
  border-bottom: none;
  border-top-right-radius: var(--md-radius-md, 6px);
}

.is-bottom-left {
  bottom: -2px;
  left: -2px;
  border-right: none;
  border-top: none;
  border-bottom-left-radius: var(--md-radius-md, 6px);
}

.is-bottom-right {
  bottom: -2px;
  right: -2px;
  border-left: none;
  border-top: none;
  border-bottom-right-radius: var(--md-radius-md, 6px);
}

:global([data-theme='dark']) .m3-ink-modal-corner,
:global(.dark) .m3-ink-modal-corner {
  border-color: var(--md-warning); /* 深色下古铜色略微低调些 */
}

/* 头部样式 */
.m3-ink-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--md-spacing-4) var(--md-spacing-5);
  border-bottom: 1.5px solid var(--md-outline-variant);
  background-color: color-mix(in srgb, var(--md-surface-container-low) 54%, transparent);
  border-top-left-radius: var(--md-radius-md);
  border-top-right-radius: var(--md-radius-md);
}

:global([data-theme='dark']) .m3-ink-modal-header,
:global(.dark) .m3-ink-modal-header {
  border-bottom-color: var(--md-outline-variant) !important;
  background-color: var(--md-surface-dim) !important;
}

:global([data-theme='dark']) .m3-ink-modal-header__title {
  color: var(--md-on-surface) !important;
}

:global([data-theme='dark']) .m3-ink-modal-close-btn {
  border-color: var(--md-outline) !important;
  color: var(--md-on-surface-variant) !important;
}

:global([data-theme='dark']) .m3-ink-modal-close-btn:hover {
  background-color: var(--md-state-layer-hover) !important;
  color: var(--md-on-surface) !important;
}

:global([data-theme='dark']) .m3-ink-modal-close-badge {
  background-color: color-mix(in srgb, var(--md-secondary) 16%, transparent) !important;
  border-color: color-mix(in srgb, var(--md-secondary) 50%, transparent) !important;
  color: var(--md-secondary-light) !important;
}

.m3-ink-modal-header__brand {
  display: flex;
  align-items: center;
  gap: 2px; /* 让无框描边首字更紧贴后面的标题文字 */
}

.m3-ink-modal-header__badge {
  display: inline-block;
  vertical-align: middle;
  background-color: transparent !important; /* 去除底色 */
  color: var(--md-secondary) !important; /* 白天：经典朱砂红（朱批色） */
  -webkit-text-stroke: none !important; /* 彻底去除描边 */
  font-family: "STXinwei", "华文新魏", "STLiti", "华文隶书", "LiSu", "隶书", var(--md-font-serif), serif;
  font-weight: 800; /* 字重适度减小，更显清秀 */
  font-size: 24px; /* 字号保持 24px，使字形显得清秀 */
  line-height: 1;
  border: none !important; /* 彻底去除边框 */
  box-shadow: none !important;
}

.m3-ink-modal-header__title {
  margin: 0;
  font-family: var(--md-font-serif);
  font-weight: 700;
  font-size: var(--md-title-medium);
  color: var(--md-on-surface);
}

/* 朱砂钤印关闭按钮 */
.m3-ink-modal-close-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 44px;
  padding: 0 12px 0 6px;
  border: 1px dashed var(--md-outline-variant);
  border-radius: var(--md-radius-xs);
  background-color: transparent;
  color: var(--md-on-surface-variant);
  cursor: pointer;
  transition:
    background-color 0.25s cubic-bezier(0.25, 0.8, 0.25, 1),
    border-color 0.25s cubic-bezier(0.25, 0.8, 0.25, 1),
    color 0.25s cubic-bezier(0.25, 0.8, 0.25, 1),
    transform 0.25s cubic-bezier(0.25, 0.8, 0.25, 1);
}

.m3-ink-modal-close-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: var(--md-radius-xs);
  background-color: color-mix(in srgb, var(--md-secondary) 8%, transparent);
  border: 1px solid color-mix(in srgb, var(--md-secondary) 35%, transparent);
  color: var(--md-secondary); /* 朱砂红 */
  font-family: var(--md-font-serif);
  font-weight: 700;
  font-size: var(--md-label-large);
  box-shadow: inset 0 1px 2px color-mix(in srgb, var(--md-secondary) 10%, transparent);
  transition:
    background-color 0.25s cubic-bezier(0.25, 0.8, 0.25, 1),
    box-shadow 0.25s cubic-bezier(0.25, 0.8, 0.25, 1),
    color 0.25s cubic-bezier(0.25, 0.8, 0.25, 1),
    transform 0.25s cubic-bezier(0.25, 0.8, 0.25, 1);
}

.m3-ink-modal-close-text {
  font-size: var(--md-label-medium);
  font-weight: 600;
}

.m3-ink-modal-close-btn:hover {
  background-color: color-mix(in srgb, var(--md-secondary) 3%, transparent);
  border-color: color-mix(in srgb, var(--md-secondary) 30%, transparent);
  color: var(--md-secondary);
}

.m3-ink-modal-close-btn:hover .m3-ink-modal-close-badge {
  transform: rotate(-10deg) scale(1.05);
  background-color: var(--md-secondary);
  color: var(--md-on-secondary);
  /* 印章无影 */
}

/* 按钮物理按压交互 */
.m3-ink-modal-close-btn:active {
  transform: translateY(1.5px);
}

/* 滚动主体区域 */
.m3-ink-modal-body {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
  padding: var(--md-spacing-4) var(--md-spacing-5) var(--md-spacing-5);
  /* 使用古典淡宣线分隔 */
  border-bottom-left-radius: var(--md-radius-md);
  border-bottom-right-radius: var(--md-radius-md);
}

/* 极精细水墨滚动条 */
.m3-ink-modal-body::-webkit-scrollbar {
  width: 6px;
}

.m3-ink-modal-body::-webkit-scrollbar-track {
  background: transparent;
}

.m3-ink-modal-body::-webkit-scrollbar-thumb {
  background-color: color-mix(in srgb, var(--md-primary) 15%, transparent);
  border-radius: var(--md-radius-full);
}

.m3-ink-modal-body::-webkit-scrollbar-thumb:hover {
  background-color: color-mix(in srgb, var(--md-primary) 35%, transparent);
}

:global([data-theme='dark']) .m3-ink-modal-body::-webkit-scrollbar-thumb,
:global(.dark) .m3-ink-modal-body::-webkit-scrollbar-thumb {
  background-color: color-mix(in srgb, var(--md-on-surface) 12%, transparent);
}

:global([data-theme='dark']) .m3-ink-modal-body::-webkit-scrollbar-thumb:hover,
:global(.dark) .m3-ink-modal-body::-webkit-scrollbar-thumb:hover {
  background-color: color-mix(in srgb, var(--md-on-surface) 25%, transparent);
}

/* 动效：水墨淡入与卷轴缓缓弹开 */
@keyframes inkFadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@keyframes scrollFoldOpen {
  from {
    opacity: 0;
    transform: scale(0.96) translateY(12px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}
</style>
