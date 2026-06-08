<!-- AIMETA P=根组件_应用根节点|R=全局布局_RouterView|NR=不含页面逻辑|E=component:App|X=ui|A=RouterView|D=vue-router|S=dom|RD=./README.ai -->
<script setup lang="ts">
import { computed, defineAsyncComponent } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import { globalAlert } from '@/composables/useAlert'

const route = useRoute()

// 布局壳与弹窗只在实际渲染时加载，避免登录首屏带上认证后导航和焦点陷阱代码。
const AppShell = defineAsyncComponent(() => import('@/components/shared/AppShell.vue'))
const AuthLayout = defineAsyncComponent(() => import('@/components/shared/AuthLayout.vue'))
const CustomAlert = defineAsyncComponent(() => import('@/components/CustomAlert.vue'))

const layoutComponent = computed(() => route.meta.layout === 'auth' ? AuthLayout : AppShell)
</script>

<template>
  <RouterView v-slot="{ Component }">
    <component :is="layoutComponent">
      <component :is="Component" />
    </component>
  </RouterView>

  <!-- 全局提示框 -->
  <CustomAlert
    v-for="alert in globalAlert.alerts.value"
    :key="alert.id"
    :visible="alert.visible"
    :type="alert.type"
    :title="alert.title"
    :message="alert.message"
    :show-cancel="alert.showCancel"
    :confirm-text="alert.confirmText"
    :cancel-text="alert.cancelText"
    :show-input="alert.showInput"
    :input-label="alert.inputLabel"
    :input-placeholder="alert.inputPlaceholder"
    @confirm="(inputValue) => globalAlert.closeAlert(alert.id, inputValue ?? true)"
    @cancel="globalAlert.closeAlert(alert.id, false)"
    @close="globalAlert.closeAlert(alert.id, false)"
  />

  <!-- 全局轻量 Tips (Toast) -->
  <div class="global-toast-container" aria-live="polite">
    <transition-group name="toast-fade">
      <div
        v-for="toast in globalAlert.toasts.value"
        :key="toast.id"
        class="global-toast"
        :class="`global-toast--${toast.type}`"
      >
        <!-- 竹青色成功图标 -->
        <svg
          v-if="toast.type === 'success'"
          class="global-toast-icon"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2.5"
        >
          <path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <!-- 朱砂红错误图标 -->
        <svg
          v-else-if="toast.type === 'error'"
          class="global-toast-icon"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2.5"
        >
          <path stroke-linecap="round" stroke-linejoin="round" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <!-- 黛色/水墨色提示图标 -->
        <svg
          v-else
          class="global-toast-icon"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2.5"
        >
          <path stroke-linecap="round" stroke-linejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <span class="global-toast-message">{{ toast.message }}</span>
      </div>
    </transition-group>
  </div>
</template>

<style scoped>
.global-toast-container {
  position: fixed;
  top: 24px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 9999;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  pointer-events: none;
  width: max-content;
  max-width: 90vw;
}

.global-toast {
  pointer-events: auto;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 20px;
  border-radius: 6px;
  font-family: var(--md-font-serif), var(--md-font-family);
  font-size: var(--md-body-medium);
  font-weight: 500;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.08), 0 1px 3px rgba(0, 0, 0, 0.02);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1.5px solid transparent;
  /* 极致国风：宣纸帘纹背景 */
  background-image:
    linear-gradient(to right, rgba(247, 245, 240, 0.95), rgba(247, 245, 240, 0.95)),
    repeating-linear-gradient(90deg, rgba(28, 32, 34, 0.005) 0px, rgba(28, 32, 34, 0.005) 1px, transparent 1px, transparent 12px);
  background-blend-mode: overlay;
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.global-toast-icon {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
}

.global-toast-message {
  line-height: 1.4;
  letter-spacing: 0.02em;
}

/* 成功 - 竹青色调 */
.global-toast--success {
  border-color: rgba(63, 108, 93, 0.35);
  color: #2b5043;
  background-color: rgba(247, 245, 240, 0.95);
}
.global-toast--success .global-toast-icon {
  color: #3f6c5d;
}

/* 错误 - 朱砂红色调 */
.global-toast--error {
  border-color: rgba(201, 64, 54, 0.35);
  color: #9c2720;
  background-color: rgba(247, 245, 240, 0.95);
}
.global-toast--error .global-toast-icon {
  color: #c94036;
}

/* 普通提示 - 水墨黛色调 */
.global-toast--info {
  border-color: rgba(28, 32, 34, 0.25);
  color: #1c2022;
  background-color: rgba(247, 245, 240, 0.95);
}
.global-toast--info .global-toast-icon {
  color: #5c6265;
}

/* 动画效果：toast-fade */
.toast-fade-enter-from {
  opacity: 0;
  transform: translateY(-20px) scale(0.9);
}
.toast-fade-leave-to {
  opacity: 0;
  transform: translateY(-10px) scale(0.95);
}
.toast-fade-enter-active,
.toast-fade-leave-active {
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
.toast-fade-leave-active {
  position: absolute;
}
</style>
