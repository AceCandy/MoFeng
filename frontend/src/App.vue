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
</template>

<style scoped>
</style>
