// AIMETA P=Vue应用入口_创建和挂载应用|R=应用初始化_插件注册|NR=不含组件实现|E=main.ts|X=ui|A=createApp_use_mount|D=vue,pinia,vue-router|S=dom|RD=./README.ai
import './assets/main.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { VueQueryPlugin } from '@tanstack/vue-query'

import App from './App.vue'
import router from './router'
import { useAuthStore } from './stores/auth'
import { queryClient } from './lib/queryClient'

type ThemePreference = 'light' | 'dark' | 'system'

const THEME_STORAGE_KEY = 'mofeng-theme-preference'

const resolveThemePreference = (value: string | null): ThemePreference => {
  if (value === 'light' || value === 'dark' || value === 'system') {
    return value
  }
  return 'system'
}

// 统一在应用启动时解析主题偏好，支持 light/dark 固定值与 system 自动跟随。
const setupTheme = () => {
  const root = document.documentElement
  const media = window.matchMedia('(prefers-color-scheme: dark)')
  const preference = resolveThemePreference(window.localStorage.getItem(THEME_STORAGE_KEY))

  const applyResolvedTheme = () => {
    const resolvedTheme = preference === 'system' ? (media.matches ? 'dark' : 'light') : preference
    root.dataset.theme = resolvedTheme
  }

  applyResolvedTheme()

  if (preference !== 'system') {
    return
  }

  const syncThemeWithSystem = () => {
    applyResolvedTheme()
  }

  if (typeof media.addEventListener === 'function') {
    media.addEventListener('change', syncThemeWithSystem)
    return
  }

  media.addListener(syncThemeWithSystem)
}

setupTheme()

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
