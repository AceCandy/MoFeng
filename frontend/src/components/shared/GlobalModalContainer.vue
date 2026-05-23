<!-- AIMETA P=通用组件_水墨大弹窗容器|R=弹窗容器_水墨遮罩_中式边框|NR=不含具体业务逻辑|E=component:GlobalModalContainer|X=ui|A=弹窗容器|D=vue|S=dom|RD=./README.ai -->
<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'

const props = withDefaults(
  defineProps<{
    title?: string
    width?: string
    hideCloseButton?: boolean
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

const modalBoxRef = ref<HTMLElement | null>(Reflect.get(window, 'undefined') || null)

const handleClose = () => {
  emit('close')
}

// 支持 ESC 键优雅关闭
const handleKeyDown = (event: KeyboardEvent) => {
  if (event.key === 'Escape') {
    handleClose()
  }
}

onMounted(() => {
  document.addEventListener('keydown', handleKeyDown)
  // 阻止外层页面滚动，保持弹窗内部独立滚动
  document.body.style.overflow = 'hidden'
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeyDown)
  document.body.style.overflow = ''
})
</script>

<template>
  <div class="m3-ink-modal-overlay" @click.self="handleClose" role="dialog" aria-modal="true">
    <div
      ref="modalBoxRef"
      class="m3-ink-modal-box"
      :style="{ width: props.width }"
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
          <span class="m3-ink-modal-header__badge">配置</span>
          <h2 class="m3-ink-modal-header__title">{{ props.title }}</h2>
        </div>

        <div class="m3-ink-modal-header__actions">
          <slot name="header-actions" />

          <!-- 朱砂钤印风格关闭按钮 -->
          <button
            v-if="!props.hideCloseButton"
            type="button"
            class="m3-ink-modal-close-btn"
            title="关闭本案头配置"
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
  background-color: rgba(18, 22, 23, 0.75);
  animation: inkFadeIn 0.3s cubic-bezier(0.25, 0.8, 0.25, 1) forwards;
}

.m3-ink-modal-box {
  position: relative;
  max-height: 88vh;
  display: flex;
  flex-direction: column;
  background-color: var(--md-surface-bright, #faf9f2);
  background-image: radial-gradient(rgba(0, 0, 0, 0.03) 1px, transparent 0);
  background-size: 4px 4px; /* 模拟宣纸极细砂感 */
  border: 3px double #1c2022; /* 古籍经典焦墨双线 */
  border-radius: var(--md-radius-md, 6px);
  box-shadow: 4px 4px 0px rgba(28, 32, 34, 0.15);
  outline: none;
  animation: scrollFoldOpen 0.35s cubic-bezier(0.34, 1.56, 0.64, 1) forwards;
}

/* 深色模式（深夜书房）适配 */
:global(.dark) .m3-ink-modal-box {
  background-color: #1a1e20;
  background-image: radial-gradient(rgba(255, 255, 255, 0.015) 1px, transparent 0);
  border-color: #3b4245;
  box-shadow: 4px 4px 0px rgba(0, 0, 0, 0.5);
}

/* 四角古黄铜包角扣 */
.m3-ink-modal-corner {
  position: absolute;
  width: 14px;
  height: 14px;
  border: 2.5px solid #d4af37; /* 仿古黄铜金 */
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

:global(.dark) .m3-ink-modal-corner {
  border-color: #bfa14c; /* 深色下古铜色略微低调些 */
}

/* 头部样式 */
.m3-ink-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--md-spacing-4) var(--md-spacing-5);
  border-bottom: 1.5px solid #e7e5d9;
  background-color: rgba(246, 245, 236, 0.5);
  border-top-left-radius: var(--md-radius-md, 6px);
  border-top-right-radius: var(--md-radius-md, 6px);
}

:global(.dark) .m3-ink-modal-header {
  border-bottom-color: #2b3032;
  background-color: rgba(28, 32, 34, 0.5);
}

.m3-ink-modal-header__brand {
  display: flex;
  align-items: center;
  gap: var(--md-spacing-3);
}

.m3-ink-modal-header__badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 4px;
  background-color: var(--md-primary, #b83c32);
  color: #ffffff;
  font-family: 'Noto Serif SC', '思源宋体', serif;
  font-weight: 700;
  font-size: var(--md-label-large);
  box-shadow: 0 1px 3px rgba(184, 60, 50, 0.2);
}

.m3-ink-modal-header__title {
  margin: 0;
  font-family: 'Noto Serif SC', '思源宋体', serif;
  font-weight: 700;
  font-size: var(--md-title-medium, 1.25rem);
  color: var(--md-on-surface, #1c2022);
}

/* 朱砂钤印关闭按钮 */
.m3-ink-modal-close-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 38px;
  padding: 0 12px 0 6px;
  border: 1px dashed var(--md-outline-variant, #e7e5d9);
  border-radius: var(--md-radius-xs, 2px);
  background-color: transparent;
  color: var(--md-on-surface-variant, #5b6264);
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.25, 0.8, 0.25, 1);
}

.m3-ink-modal-close-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: var(--md-radius-xs, 2px);
  background-color: rgba(184, 60, 50, 0.08);
  border: 1px solid rgba(184, 60, 50, 0.35);
  color: #b83c32; /* 朱砂红 */
  font-family: 'Noto Serif SC', '思源宋体', serif;
  font-weight: 700;
  font-size: var(--md-label-large);
  box-shadow: inset 0 1px 2px rgba(184, 60, 50, 0.1);
  transition: all 0.25s cubic-bezier(0.25, 0.8, 0.25, 1);
}

.m3-ink-modal-close-text {
  font-size: var(--md-label-medium);
  font-weight: 600;
}

.m3-ink-modal-close-btn:hover {
  background-color: rgba(184, 60, 50, 0.03);
  border-color: rgba(184, 60, 50, 0.3);
  color: #b83c32;
}

.m3-ink-modal-close-btn:hover .m3-ink-modal-close-badge {
  transform: rotate(-10deg) scale(1.05);
  background-color: #b83c32;
  color: #ffffff;
  box-shadow: 0 3px 6px rgba(184, 60, 50, 0.2);
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
  border-bottom-left-radius: var(--md-radius-md, 6px);
  border-bottom-right-radius: var(--md-radius-md, 6px);
}

/* 极精细水墨滚动条 */
.m3-ink-modal-body::-webkit-scrollbar {
  width: 6px;
}

.m3-ink-modal-body::-webkit-scrollbar-track {
  background: transparent;
}

.m3-ink-modal-body::-webkit-scrollbar-thumb {
  background-color: rgba(28, 32, 34, 0.15);
  border-radius: var(--md-radius-full);
}

.m3-ink-modal-body::-webkit-scrollbar-thumb:hover {
  background-color: rgba(28, 32, 34, 0.35);
}

:global(.dark) .m3-ink-modal-body::-webkit-scrollbar-thumb {
  background-color: rgba(255, 255, 255, 0.12);
}

:global(.dark) .m3-ink-modal-body::-webkit-scrollbar-thumb:hover {
  background-color: rgba(255, 255, 255, 0.25);
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
