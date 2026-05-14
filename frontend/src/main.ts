// AIMETA P=Vue应用入口_创建和挂载应用|R=应用初始化_插件注册|NR=不含组件实现|E=main.ts|X=ui|A=createApp_use_mount|D=vue,pinia,vue-router|S=dom|RD=./README.ai
import '@fontsource/noto-sans-sc/400.css'
import '@fontsource/noto-sans-sc/500.css'

import './assets/main.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { VueQueryPlugin } from '@tanstack/vue-query'

import App from './App.vue'
import router from './router'
import { useAuthStore } from './stores/auth'
import { queryClient } from './lib/queryClient'
import { currentUserQueryOptions } from './queries/auth'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(VueQueryPlugin, { queryClient })
app.use(router)

// Handle token from URL
const urlParams = new URLSearchParams(window.location.search)
const token = urlParams.get('token')

if (token) {
  const authStore = useAuthStore()
  authStore.setToken(token)
  // Clean the URL
  window.history.replaceState({}, document.title, '/workspace')
  queryClient.fetchQuery(currentUserQueryOptions(token))
    .then((user) => {
      authStore.setUser(user)
    })
    .catch(() => {
      authStore.logout()
    })
}

app.mount('#app')
