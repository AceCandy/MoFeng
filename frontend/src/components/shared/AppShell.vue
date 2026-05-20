<!-- AIMETA P=应用布局_认证后共享外壳|R=全局导航_页面容器|NR=不含业务页面逻辑|E=component:AppShell|X=ui|A=布局组件|D=vue,vue-router,pinia|S=dom|RD=./README.ai -->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useQueryClient } from '@tanstack/vue-query'

import { useResponsiveViewport } from '@/composables/useResponsiveViewport'
import { clearAuthQueryCache } from '@/queries/auth'
import { useAuthStore } from '@/stores/auth'
import {
  buildShellNavigation,
  type ShellNavIcon,
} from '@/components/shared/shellNavigation'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const queryClient = useQueryClient()
const viewport = useResponsiveViewport()
const isDrawerOpen = ref(false)

const navigation = computed(() => buildShellNavigation(Boolean(authStore.user?.is_admin)))
const isCompactShell = computed(() => viewport.tier.value !== 'desktop')
const isMobileShell = computed(() => viewport.isMobile.value)

const pageLabel = computed(() => String(route.meta.label || '工作台'))
const pageDescription = computed(() => String(route.meta.description || ''))
const isProjectContext = computed(() =>
  ['project-detail', 'project-write', 'admin-project-detail'].includes(String(route.name || '')),
)

const navIconPaths: Record<ShellNavIcon, string[]> = {
  desk: ['M4 5h16v14H4z', 'M4 10h16', 'M9 19v-9'],
  spark: ['M12 3l1.9 4.8L19 10l-5.1 2.2L12 17l-1.9-4.8L5 10l5.1-2.2L12 3z'],
  settings: [
    'M12 15.5a3.5 3.5 0 100-7 3.5 3.5 0 000 7z',
    'M19.4 15a1.7 1.7 0 00.34 1.87l.06.06a2 2 0 01-2.83 2.83l-.06-.06A1.7 1.7 0 0015 19.4a1.7 1.7 0 00-1 .6 1.7 1.7 0 00-.4 1.1V21a2 2 0 01-4 0v-.09A1.7 1.7 0 009 19.4a1.7 1.7 0 00-1.87.34l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.7 1.7 0 004.6 15a1.7 1.7 0 00-.6-1 1.7 1.7 0 00-1.1-.4H3a2 2 0 010-4h.09A1.7 1.7 0 004.6 9a1.7 1.7 0 00-.34-1.87l-.06-.06a2 2 0 012.83-2.83l.06.06A1.7 1.7 0 009 4.6a1.7 1.7 0 001-.6 1.7 1.7 0 00.4-1.1V3a2 2 0 014 0v.09A1.7 1.7 0 0015 4.6a1.7 1.7 0 001.87-.34l.06-.06a2 2 0 012.83 2.83l-.06.06A1.7 1.7 0 0019.4 9a1.7 1.7 0 00.6 1 1.7 1.7 0 001.1.4H21a2 2 0 010 4h-.09A1.7 1.7 0 0019.4 15z',
  ],
  admin: ['M4 7h16', 'M6 7v12h12V7', 'M9 11h6', 'M9 15h6'],
}

const closeDrawer = () => {
  isDrawerOpen.value = false
}

const toggleDrawer = () => {
  isDrawerOpen.value = !isDrawerOpen.value
}

const logout = () => {
  authStore.logout()
  clearAuthQueryCache(queryClient)
  closeDrawer()
  router.push('/login')
}

watch(
  () => route.fullPath,
  () => {
    closeDrawer()
  },
)

watch(
  isCompactShell,
  (compact) => {
    if (!compact) {
      closeDrawer()
    }
  },
  { immediate: true },
)
</script>

<template>
  <div class="app-shell" :class="{ 'app-shell--project-context': isProjectContext }">
    <a class="skip-link" href="#main-content">跳到主内容</a>

    <aside
      id="app-primary-navigation"
      class="app-shell__sidebar"
      :class="{ 'is-open': isCompactShell && isDrawerOpen }"
      :aria-hidden="isCompactShell && !isDrawerOpen ? 'true' : undefined"
      :inert="isCompactShell && !isDrawerOpen"
    >
      <div class="app-shell__brand">
        <div class="app-shell__brand-mark" aria-hidden="true">墨</div>
        <div class="app-shell__brand-copy">
          <p class="app-shell__brand-title">墨风</p>
          <p class="app-shell__account-role">AI 小说创作中控台</p>
        </div>
        <button
          v-if="isCompactShell"
          type="button"
          class="md-icon-btn app-shell__close"
          aria-label="关闭导航"
          @click="closeDrawer"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <nav class="app-shell__nav" aria-label="主导航">
        <RouterLink
          v-for="item in navigation.sidebarItems"
          :key="item.key"
          :to="item.path"
          class="app-shell__nav-item"
          :class="{ 'is-active': item.match(route.path) }"
          :aria-current="item.match(route.path) ? 'page' : undefined"
          :aria-label="item.label"
          :title="item.label"
        >
          <span class="app-shell__nav-icon" aria-hidden="true">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <path
                v-for="(path, index) in navIconPaths[item.icon]"
                :key="`${item.key}-${index}`"
                :d="path"
              />
            </svg>
          </span>
          <span class="app-shell__nav-text">{{ item.label }}</span>
        </RouterLink>
      </nav>

      <div class="app-shell__account">
        <div class="app-shell__account-copy">
          <p class="app-shell__account-name">{{ authStore.user?.username || '当前用户' }}</p>
          <p class="app-shell__account-role">{{ authStore.user?.is_admin ? '管理模式' : '作者模式' }}</p>
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
      v-if="isCompactShell && isDrawerOpen"
      type="button"
      class="app-shell__mobile-backdrop"
      aria-label="关闭导航"
      @click="closeDrawer"
    ></button>

    <div class="app-shell__main">
      <header class="app-shell__topbar">
        <button
          v-if="isCompactShell"
          type="button"
          class="md-icon-btn app-shell__menu"
          aria-label="打开导航"
          aria-controls="app-primary-navigation"
          :aria-expanded="isDrawerOpen"
          @click="toggleDrawer"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
        <div class="app-shell__workspace-context">
          <div class="app-shell__title-block">
            <h1>{{ pageLabel }}</h1>
            <p v-if="pageDescription" class="app-shell__title-description">
              {{ pageDescription }}
            </p>
          </div>
        </div>
      </header>

      <main id="main-content" class="app-shell__content" tabindex="-1">
        <slot />
      </main>
    </div>

    <nav v-if="isMobileShell" class="app-shell__bottom-tabs" aria-label="移动主导航">
      <RouterLink
        v-for="item in navigation.mobileTabs"
        :key="item.key"
        :to="item.path"
        class="app-shell__bottom-tab"
        :class="{ 'is-active': item.match(route.path) }"
        :aria-current="item.match(route.path) ? 'page' : undefined"
        :aria-label="item.mobileLabel || item.label"
        :title="item.mobileLabel || item.label"
      >
        <span class="app-shell__bottom-tab-icon" aria-hidden="true">
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <path
              v-for="(path, index) in navIconPaths[item.icon]"
              :key="`${item.key}-mobile-${index}`"
              :d="path"
            />
          </svg>
        </span>
        <span class="app-shell__bottom-tab-text">{{ item.mobileLabel || item.label }}</span>
      </RouterLink>
    </nav>
  </div>
</template>
