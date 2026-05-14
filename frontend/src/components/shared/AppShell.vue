<!-- AIMETA P=应用布局_认证后共享外壳|R=全局导航_页面容器|NR=不含业务页面逻辑|E=component:AppShell|X=ui|A=布局组件|D=vue,vue-router,pinia|S=dom|RD=./README.ai -->
<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useQueryClient } from '@tanstack/vue-query'
import { useAuthStore } from '@/stores/auth'
import { clearAuthQueryCache } from '@/queries/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const queryClient = useQueryClient()
const isMobileNavOpen = ref(false)
const isMobileShell = ref(false)

let mobileMediaQuery: MediaQueryList | null = null

const syncMobileShell = () => {
  isMobileShell.value = Boolean(mobileMediaQuery?.matches)
}

const navigationItems = computed(() => {
  const items = [
    {
      label: '工作台',
      path: '/workspace',
      match: (path: string) => path === '/workspace' || path.startsWith('/projects/'),
      icon: 'desk',
    },
    {
      label: '模型设置',
      path: '/settings',
      match: (path: string) => path.startsWith('/settings'),
      icon: 'settings',
    },
  ]

  if (authStore.user?.is_admin) {
    items.push({
      label: '管理',
      path: '/admin',
      match: (path: string) => path.startsWith('/admin'),
      icon: 'admin',
    })
  }

  return items
})

const pageLabel = computed(() => String(route.meta.label || '工作台'))
const isProjectContext = computed(() =>
  ['project-detail', 'project-write', 'admin-project-detail'].includes(String(route.name || '')),
)

const closeMobileNav = () => {
  isMobileNavOpen.value = false
}

const logout = () => {
  authStore.logout()
  clearAuthQueryCache(queryClient)
  router.push('/login')
}

watch(
  () => route.fullPath,
  () => {
    closeMobileNav()
  },
)

onMounted(() => {
  mobileMediaQuery = window.matchMedia('(max-width: 1023px)')
  syncMobileShell()
  mobileMediaQuery.addEventListener('change', syncMobileShell)
})

onUnmounted(() => {
  mobileMediaQuery?.removeEventListener('change', syncMobileShell)
  mobileMediaQuery = null
})
</script>

<template>
  <div class="app-shell" :class="{ 'app-shell--project-context': isProjectContext }">
    <a class="skip-link" href="#main-content">跳到主内容</a>

    <aside
      id="app-primary-navigation"
      class="app-shell__sidebar"
      :class="{ 'is-open': isMobileNavOpen }"
      :aria-hidden="isMobileShell && !isMobileNavOpen ? 'true' : undefined"
      :inert="isMobileShell && !isMobileNavOpen"
    >
      <div class="app-shell__brand">
        <div class="app-shell__brand-mark" aria-hidden="true">A</div>
        <div class="app-shell__brand-copy">
          <p class="app-shell__brand-title">Arboris Novel</p>
        </div>
        <button
          type="button"
          class="md-icon-btn app-shell__close"
          aria-label="关闭导航"
          @click="closeMobileNav"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <nav class="app-shell__nav" aria-label="主导航">
        <RouterLink
          v-for="item in navigationItems"
          :key="item.path"
          :to="item.path"
          class="app-shell__nav-item"
          :class="{ 'is-active': item.match(route.path) }"
          :aria-current="item.match(route.path) ? 'page' : undefined"
          :aria-label="item.label"
          :title="item.label"
        >
          <span class="app-shell__nav-icon" aria-hidden="true">
            <svg
              v-if="item.icon === 'desk'"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M4 5h16v14H4zM4 10h16M9 19v-9"
              />
            </svg>
            <svg
              v-else-if="item.icon === 'settings'"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M12 15.5a3.5 3.5 0 100-7 3.5 3.5 0 000 7z"
              />
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M19.4 15a1.7 1.7 0 00.34 1.87l.06.06a2 2 0 01-2.83 2.83l-.06-.06A1.7 1.7 0 0015 19.4a1.7 1.7 0 00-1 .6 1.7 1.7 0 00-.4 1.1V21a2 2 0 01-4 0v-.09A1.7 1.7 0 009 19.4a1.7 1.7 0 00-1.87.34l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.7 1.7 0 004.6 15a1.7 1.7 0 00-.6-1 1.7 1.7 0 00-1.1-.4H3a2 2 0 010-4h.09A1.7 1.7 0 004.6 9a1.7 1.7 0 00-.34-1.87l-.06-.06a2 2 0 012.83-2.83l.06.06A1.7 1.7 0 009 4.6a1.7 1.7 0 001-.6 1.7 1.7 0 00.4-1.1V3a2 2 0 014 0v.09A1.7 1.7 0 0015 4.6a1.7 1.7 0 001.87-.34l.06-.06a2 2 0 012.83 2.83l-.06.06A1.7 1.7 0 0019.4 9a1.7 1.7 0 00.6 1 1.7 1.7 0 001.1.4H21a2 2 0 010 4h-.09A1.7 1.7 0 0019.4 15z"
              />
            </svg>
            <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M4 7h16M6 7v12h12V7M9 11h6M9 15h6"
              />
            </svg>
          </span>
          <span class="app-shell__nav-text">{{ item.label }}</span>
        </RouterLink>
      </nav>

      <div class="app-shell__account">
        <div class="app-shell__account-copy">
          <p class="app-shell__account-name">{{ authStore.user?.username || '当前用户' }}</p>
          <p class="app-shell__account-role">{{ authStore.user?.is_admin ? '管理员' : '作者' }}</p>
        </div>
        <button
          type="button"
          class="md-btn md-btn-text app-shell__logout"
          aria-label="退出登录"
          title="退出登录"
          @click="logout"
        >
          退出
        </button>
      </div>
    </aside>

    <button
      v-if="isMobileNavOpen"
      type="button"
      class="app-shell__mobile-backdrop"
      aria-label="关闭导航"
      @click="closeMobileNav"
    ></button>

    <div class="app-shell__main">
      <header class="app-shell__topbar">
        <button
          type="button"
          class="md-icon-btn app-shell__menu"
          aria-label="打开导航"
          aria-controls="app-primary-navigation"
          :aria-expanded="isMobileNavOpen"
          @click="isMobileNavOpen = true"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
        <div class="app-shell__workspace-context">
          <div class="app-shell__title-block">
            <h1>{{ pageLabel }}</h1>
          </div>
        </div>
      </header>

      <main id="main-content" class="app-shell__content" tabindex="-1">
        <slot />
      </main>
    </div>
  </div>
</template>
