<!-- AIMETA P=工作区入口_应用主入口|R=入口导航|NR=不含具体功能|E=route:/#component:WorkspaceEntry|X=ui|A=入口页|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="workspace-entry md-surface-dim">
    <!-- Material 3 Update Log Modal -->
    <div v-if="showModal" class="md-dialog-overlay" @click.self="closeModal">
      <div
        ref="updatesDialogRef"
        class="md-dialog workspace-entry__dialog"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="updatesDialogTitleId"
      >
        <!-- Header -->
        <div class="md-dialog-header border-b" style="border-color: var(--md-outline-variant)">
          <h1
            :id="updatesDialogTitleId"
            class="md-headline-medium text-center"
            style="color: var(--md-on-surface)"
          >
            更新日志
          </h1>
        </div>

        <!-- Community Section -->
        <div v-if="communityLog" class="px-6 pt-6">
          <div class="p-4 rounded-lg" style="background-color: var(--md-primary-container)">
            <div
              class="prose max-w-none prose-sm"
              style="color: var(--md-on-primary-container)"
              v-html="renderMarkdown(communityLog.content)"
            ></div>
          </div>
        </div>

        <!-- Timeline Content -->
        <div class="workspace-entry__dialog-timeline px-6 py-6 overflow-y-auto flex-1">
          <div class="flow-root">
            <ul role="list" class="-mb-8">
              <li v-for="(log, index) in filteredUpdateLogs" :key="log.id">
                <div class="relative pb-8">
                  <!-- Connector Line -->
                  <span
                    v-if="index < filteredUpdateLogs.length - 1"
                    class="absolute left-2.5 top-4 -ml-px h-full w-0.5"
                    style="background-color: var(--md-outline-variant)"
                    aria-hidden="true"
                  ></span>
                  <div class="relative flex items-start space-x-4">
                    <!-- Timeline Dot -->
                    <div
                      class="h-5 w-5 rounded-full flex items-center justify-center ring-8 mt-1"
                      style="background-color: var(--md-primary); ring-color: var(--md-surface)"
                    ></div>
                    <!-- Card Content -->
                    <div class="min-w-0 flex-1">
                      <div class="md-card md-card-outlined p-4">
                        <time class="md-label-large" style="color: var(--md-on-surface-variant)">
                          {{ new Date(log.created_at).toLocaleDateString() }}
                        </time>
                        <div
                          class="mt-3 prose max-w-none prose-sm"
                          style="color: var(--md-on-surface)"
                          v-html="renderMarkdown(log.content)"
                        ></div>
                      </div>
                    </div>
                  </div>
                </div>
              </li>
            </ul>
          </div>
        </div>

        <!-- Footer Actions -->
        <div
          class="md-dialog-actions border-t"
          style="
            border-color: var(--md-outline-variant);
            background-color: var(--md-surface-container-low);
          "
        >
          <button @click="hideModalToday" class="md-btn md-btn-text md-ripple">今日不再显示</button>
          <button
            ref="updatesCloseButtonRef"
            data-dialog-initial-focus
            @click="closeModal"
            class="md-btn md-btn-filled md-ripple"
          >
            关闭
          </button>
        </div>
      </div>
    </div>

    <!-- Top Right Actions -->
    <div class="workspace-entry__actions-top">
      <router-link to="/settings" class="md-btn md-btn-text md-ripple">
        <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
          />
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
          />
        </svg>
        设置
      </router-link>
      <button @click="handleLogout" class="md-btn md-btn-text md-ripple">
        <svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
          />
        </svg>
        退出登录
      </button>
    </div>

    <!-- Main Content -->
    <div class="workspace-entry__main">
      <div class="workspace-entry__hero fade-in">
        <!-- Title -->
        <h1 class="md-display-small mb-4" style="color: var(--md-on-surface)">墨风：创作中心</h1>
        <p class="md-body-large mb-12" style="color: var(--md-on-surface-variant)">
          从一个新灵感开始，或继续打磨你的世界。
        </p>

        <!-- Entry Actions -->
        <div class="entry-actions">
          <button
            type="button"
            @click="goToWorkspace"
            class="md-btn md-btn-filled md-ripple entry-actions__primary"
          >
            <svg
              class="w-5 h-5"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
              />
            </svg>
            进入小说工作台
          </button>
          <button
            type="button"
            @click="goToInspiration"
            class="md-btn md-btn-outlined md-ripple entry-actions__secondary"
          >
            从零开始，用灵感模式构建故事雏形
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { useRouter } from 'vue-router'
import { useQueryClient } from '@tanstack/vue-query'
import { useAuthStore } from '../stores/auth'
import { clearAuthQueryCache } from '@/queries/auth'
import { useLatestUpdatesQuery } from '@/queries/updates'
import { useDialogA11y } from '@/composables/useDialogA11y'

marked.setOptions({
  gfm: true,
  breaks: true,
})

const renderMarkdown = (md: string) => {
  const parsed = marked.parse(md)
  const html = typeof parsed === 'string' ? parsed : ''
  return DOMPurify.sanitize(html, {
    USE_PROFILES: { html: true },
  })
}

const router = useRouter()
const authStore = useAuthStore()
const queryClient = useQueryClient()

const showModal = ref(false)
const updatesDialogRef = ref<HTMLElement | null>(null)
const updatesCloseButtonRef = ref<HTMLElement | null>(null)
const updatesDialogTitleId = 'workspace-entry-updates-title'
const shouldCheckUpdates = ref(false)
const updatesQuery = useLatestUpdatesQuery(() => shouldCheckUpdates.value)
const updateLogs = computed(() => updatesQuery.data.value ?? [])

// 查找包含"交流群"的日志
const communityLog = computed(() => {
  return updateLogs.value.find((log) => /交流群/.test(log.content))
})

// 过滤掉包含"交流群"的日志，用于时间线显示
const filteredUpdateLogs = computed(() => {
  if (!communityLog.value) {
    return updateLogs.value
  }
  return updateLogs.value.filter((log) => log.id !== communityLog.value!.id)
})

watch(
  () => updatesQuery.data.value,
  (logs) => {
    if (shouldCheckUpdates.value && logs && logs.length > 0) {
      showModal.value = true
    }
  },
)

watch(
  () => updatesQuery.error.value,
  (error) => {
    if (error) {
      console.error('Failed to fetch update logs:', error)
    }
  },
)

onMounted(() => {
  const hideUntil = localStorage.getItem('hideAnnouncement')
  if (hideUntil !== new Date().toDateString()) {
    shouldCheckUpdates.value = true
  }
})

const closeModal = () => {
  showModal.value = false
}

const hideModalToday = () => {
  localStorage.setItem('hideAnnouncement', new Date().toDateString())
  closeModal()
}

useDialogA11y({
  active: showModal,
  dialogRef: updatesDialogRef,
  onClose: closeModal,
  initialFocusRef: updatesCloseButtonRef,
})

const handleLogout = () => {
  authStore.logout()
  clearAuthQueryCache(queryClient)
  router.push('/login')
}

const goToInspiration = () => {
  router.push('/inspiration')
}

const goToWorkspace = () => {
  router.push('/workspace')
}
</script>

<style scoped>
.workspace-entry {
  position: relative;
  min-height: var(--app-viewport-unit);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: clamp(var(--md-spacing-4), 3vw, var(--md-spacing-8));
}

.workspace-entry__actions-top {
  position: absolute;
  top: var(--md-spacing-4);
  right: var(--md-spacing-4);
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: var(--md-spacing-2);
}

.workspace-entry__main {
  width: min(100%, 960px);
  margin: 0 auto;
}

.workspace-entry__hero {
  text-align: center;
  padding: clamp(var(--md-spacing-6), 4vw, var(--md-spacing-10));
}

.workspace-entry__dialog {
  width: min(100%, 960px);
  max-height: min(90vh, 900px);
  margin: 0 var(--md-spacing-4);
  display: flex;
  flex-direction: column;
}

.workspace-entry__dialog-timeline {
  min-height: 0;
}

.entry-actions {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: min(100%, 560px);
  margin: 0 auto;
  gap: var(--md-spacing-4);
}

.entry-actions__primary {
  min-height: 52px;
  min-width: min(100%, 320px);
  padding: 0 var(--md-spacing-8);
  font-size: var(--md-body-large);
  gap: var(--md-spacing-3);
}

.entry-actions__secondary {
  min-height: 44px;
  padding: 0 var(--md-spacing-6);
  font-size: var(--md-body-medium);
  color: var(--md-on-surface-variant);
  border-color: var(--md-outline-variant);
}

.entry-actions__secondary:hover {
  color: var(--md-primary-dark);
  border-color: var(--md-primary);
}

@media (max-width: 833px) {
  .workspace-entry {
    align-items: flex-start;
    justify-content: flex-start;
    padding: max(var(--md-spacing-4), env(safe-area-inset-top)) var(--md-spacing-3)
      max(var(--md-spacing-4), env(safe-area-inset-bottom));
  }

  .workspace-entry__actions-top {
    position: static;
    width: 100%;
    margin-bottom: var(--md-spacing-2);
  }

  .workspace-entry__actions-top > * {
    flex: 1 1 0;
    min-width: 0;
  }

  .workspace-entry__hero {
    padding: var(--md-spacing-6) 0 var(--md-spacing-4);
  }

  .workspace-entry__dialog {
    width: 100%;
    max-height: calc(var(--app-viewport-unit) - var(--md-spacing-6));
    margin: 0;
  }

  .workspace-entry__dialog-timeline {
    padding: var(--md-spacing-4);
  }

  .entry-actions {
    width: 100%;
  }

  .entry-actions__primary,
  .entry-actions__secondary {
    width: 100%;
    padding-inline: var(--md-spacing-4);
  }
}
</style>
