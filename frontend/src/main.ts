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

// 监听全局滚动，实现“滚动时显示滚动条，静止后隐藏”的水墨交互效果
const setupScrollbarBehavior = () => {
  const scrollTimeoutMap = new WeakMap<HTMLElement, number>()

  window.addEventListener(
    'scroll',
    (event) => {
      const target = event.target
      if (!target) return

      // 确定触发滚动的元素：如果是 document，则应用在 documentElement 上
      const scrollEl = (target === document || target === window || (target as any).tagName === 'BODY')
        ? document.documentElement
        : target as HTMLElement

      // 添加正在滚动类名
      scrollEl.classList.add('is-scrolling')

      // 使用 WeakMap 记录和管理定时器，避免全局污染与内存泄漏
      const existingTimeout = scrollTimeoutMap.get(scrollEl)
      if (existingTimeout) {
        clearTimeout(existingTimeout)
      }

      const timeoutId = window.setTimeout(() => {
        scrollEl.classList.remove('is-scrolling')
        scrollTimeoutMap.delete(scrollEl)
      }, 1000) // 停止滚动1秒后平滑淡出

      scrollTimeoutMap.set(scrollEl, timeoutId)
    },
    { capture: true, passive: true }
  )
}

setupScrollbarBehavior()

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
