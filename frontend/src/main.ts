// AIMETA P=Vue应用入口_创建和挂载应用|R=应用初始化_插件注册|NR=不含组件实现|E=main.ts|X=ui|A=createApp_use_mount|D=vue,pinia,vue-router|S=dom|RD=./README.ai
import './assets/main.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { VueQueryPlugin } from '@tanstack/vue-query'

import App from './App.vue'
import router from './router'
import { useAuthStore } from './stores/auth'
import { queryClient } from './lib/queryClient'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(VueQueryPlugin, { queryClient })
app.use(router)

const bootstrapUrlToken = async () => {
  const urlParams = new URLSearchParams(window.location.search)
  const token = urlParams.get('token')

  if (!token) {
    return
  }

  // 只有第三方登录回跳携带 token 时，才加载认证恢复查询。
  const { currentUserQueryOptions } = await import('./queries/auth')
  const authStore = useAuthStore()
  authStore.setToken(token)
  window.history.replaceState({}, document.title, '/workspace')

  try {
    const user = await queryClient.fetchQuery(currentUserQueryOptions(token))
    authStore.setUser(user)
  } catch {
    authStore.logout()
  }
}

void bootstrapUrlToken().finally(() => {
  app.mount('#app')
})
