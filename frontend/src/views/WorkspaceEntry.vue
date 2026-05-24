<!-- AIMETA P=工作区入口_应用主入口|R=入口导航|NR=不含具体功能|E=route:/#component:WorkspaceEntry|X=ui|A=入口页|D=vue|S=dom|RD=./README.ai -->
<template>
  <div class="workspace-entry">
    <!-- Material 3 Update Log Modal -->
    <Transition name="dialog-fade">
      <div v-if="showModal" class="md-dialog-overlay" @click.self="closeModal">
        <div
          ref="updatesDialogRef"
          class="md-dialog workspace-entry__dialog"
          role="dialog"
          aria-modal="true"
          :aria-labelledby="updatesDialogTitleId"
        >
        <!-- Header -->
        <div class="md-dialog-header border-b updates-dialog-header">
          <h1
            :id="updatesDialogTitleId"
            class="md-headline-medium text-center updates-dialog-title"
          >
            更新日志
          </h1>
        </div>

        <!-- Community Section -->
        <div v-if="renderedCommunityLog" class="px-6 pt-6">
          <div class="p-4 updates-community-box">
            <div
              class="prose max-w-none prose-sm updates-community-text"
              v-html="renderedCommunityLog.renderedContent"
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
                    class="absolute left-2.5 top-4 -ml-px h-full w-0.5 updates-timeline-connector"
                    aria-hidden="true"
                  ></span>
                  <div class="relative flex items-start space-x-4">
                    <!-- Timeline Dot -->
                    <div class="updates-timeline-dot"></div>
                    <!-- Card Content -->
                    <div class="min-w-0 flex-1">
                      <div class="md-card md-card-outlined p-4">
                        <time class="md-label-large updates-timeline-time">
                          {{ new Date(log.created_at).toLocaleDateString() }}
                        </time>
                        <div
                          class="mt-3 prose max-w-none prose-sm updates-timeline-content"
                          v-html="log.renderedContent"
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
        <div class="md-dialog-actions border-t updates-dialog-actions">
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
        <span class="workspace-entry__icon-txt">[ 設 ]</span>
        设置
      </router-link>
      <button @click="handleLogout" class="md-btn md-btn-text md-ripple">
        <span class="workspace-entry__icon-txt">[ 歸 ]</span>
        退出登录
      </button>
    </div>

    <!-- Main Content -->
    <div class="workspace-entry__main">
      <div class="workspace-entry__hero fade-in">
        <!-- Title -->
        <h1 class="md-display-small mb-4 hero-title">墨风：创作中心</h1>
        <p class="md-body-large mb-12 hero-subtitle">
          从一个新灵感开始，或继续打磨你的世界。
        </p>

        <!-- Entry Actions -->
        <div class="entry-actions">
          <button
            type="button"
            @click="goToWorkspace"
            class="md-btn md-btn-filled md-ripple entry-actions__primary"
          >
            <span class="entry-actions__stamp">[ 啟 ]</span>
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
    </Transition>
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

// 【逻辑解耦】：在 computed 中缓存社区日志 Markdown 渲染产物，防 template 高频重绘性能滑坡
const renderedCommunityLog = computed(() => {
  if (!communityLog.value) return null
  return {
    ...communityLog.value,
    renderedContent: renderMarkdown(communityLog.value.content),
  }
})

// 【逻辑解耦】：过滤日志，并预先在 computed 中进行 Markdown 渲染，保证只在数据流变更时触发解析
const filteredUpdateLogs = computed(() => {
  const logsToFilter = communityLog.value
    ? updateLogs.value.filter((log) => log.id !== communityLog.value!.id)
    : updateLogs.value
  return logsToFilter.map(log => ({
    ...log,
    renderedContent: renderMarkdown(log.content),
  }))
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
  /* 采用平铺温暖熟宣纸与干燥木骨网格 */
  background-color: var(--md-background) !important;
  background-image: radial-gradient(var(--md-outline-variant) 1px, transparent 1px) !important;
  background-size: 24px 24px !important;
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

.workspace-entry__actions-top .md-btn {
  font-family: var(--md-font-serif) !important;
  font-weight: 600;
  color: var(--md-primary-light) !important;
  transition:
    background-color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    border-color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    opacity 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    transform 0.25s cubic-bezier(0.22, 1, 0.36, 1) !important;
}

.workspace-entry__actions-top .md-btn:hover {
  color: var(--md-secondary) !important; /* Hover 时变为朱砂红 */
}

/* 右上角朱砂小落款印章字标样式 */
.workspace-entry__icon-txt {
  font-family: var(--md-font-serif) !important;
  font-weight: 600;
  color: var(--md-secondary) !important; /* 朱砂红，像一枚落款小印章点醒页面 */
  margin-right: 4px;
}

.workspace-entry__main {
  width: min(100%, 720px); /* 适度收窄，更具书卷聚拢感 */
  margin: 0 auto;
}

/* 将普通的看板区域，重构为宣纸折页线装卡片 */
.workspace-entry__hero {
  text-align: center;
  padding: clamp(var(--md-spacing-8), 6vw, var(--md-spacing-12)) !important;
  border-radius: var(--md-radius-sm) !important;
  border: 3px double var(--md-outline) !important;
  background: var(--md-surface) !important;
  box-shadow: 5px 5px 0px rgba(28, 32, 34, 0.15) !important;
  position: relative;
  overflow: hidden;
}



.hero-title {
  font-family: var(--md-font-serif) !important;
  color: var(--md-on-surface) !important;
  letter-spacing: 0.08em !important;
  font-weight: 600 !important;
  font-size: 32px !important;
}

.hero-subtitle {
  color: var(--md-on-surface-variant) !important;
  font-family: var(--md-font-kai) !important;
  font-size: 16px !important;
  letter-spacing: 0.03em !important;
}

.workspace-entry__dialog {
  width: min(100%, 720px);
  max-height: min(85vh, 750px);
  margin: 0 var(--md-spacing-4);
  display: flex;
  flex-direction: column;
  background-color: var(--md-surface) !important;
  border-radius: var(--md-radius-sm) !important;
  border: 3px double var(--md-outline) !important;
  box-shadow: 4px 4px 0px rgba(28, 32, 34, 0.18) !important;
  padding: 2px !important;
}

.workspace-entry__dialog-timeline {
  min-height: 0;
}

.entry-actions {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: min(100%, 480px);
  margin: 0 auto;
  gap: var(--md-spacing-5);
}

/* 焦墨动作大按钮，钤印下沉微动效 */
.entry-actions__primary {
  min-height: 52px;
  min-width: min(100%, 320px);
  padding: 0 var(--md-spacing-8);
  font-size: var(--md-body-large) !important;
  gap: var(--md-spacing-3);
  border-radius: var(--md-radius-xs) !important;
  border: 1px solid var(--md-outline) !important;
  background-color: var(--md-primary) !important;
  color: var(--md-on-primary) !important;
  font-family: var(--md-font-serif) !important;
  font-weight: 600 !important;
  letter-spacing: 0.05em;
  box-shadow: 2px 2px 0px rgba(28, 32, 34, 0.15) !important;
  transition:
    background-color 0.3s cubic-bezier(0.22, 1, 0.36, 1),
    border-color 0.3s cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 0.3s cubic-bezier(0.22, 1, 0.36, 1),
    color 0.3s cubic-bezier(0.22, 1, 0.36, 1),
    opacity 0.3s cubic-bezier(0.22, 1, 0.36, 1),
    transform 0.3s cubic-bezier(0.22, 1, 0.36, 1) !important;
  cursor: pointer;
  position: relative;
  overflow: hidden;
}

.entry-actions__primary::before {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  width: 250px;
  height: 250px;
  background: radial-gradient(circle, var(--md-primary-light) 0%, transparent 70%);
  border-radius: 50%;
  transform: translate(-50%, -50%) scale(0);
  transition: 
    transform 0.6s cubic-bezier(0.22, 1, 0.36, 1), 
    opacity 0.6s cubic-bezier(0.22, 1, 0.36, 1) !important;
  pointer-events: none;
  opacity: 0;
}

.entry-actions__primary:hover:not(:disabled)::before {
  transform: translate(-50%, -50%) scale(1.5);
  opacity: 0.3;
}

.entry-actions__primary:hover:not(:disabled) {
  background-color: var(--md-primary-light) !important;
  box-shadow: 3px 3px 0px rgba(184, 60, 50, 0.25) !important; /* 获得朱砂压章硬投影 */
}

.entry-actions__primary:active:not(:disabled) {
  transform: translate(1.5px, 1.5px) !important;
  box-shadow: 0.5px 0.5px 0px rgba(184, 60, 50, 0.25) !important; /* 点击下陷，缩回阴影 */
}

/* 辅动作用虚线竹青钮 */
.entry-actions__secondary {
  min-height: 48px;
  padding: 0 var(--md-spacing-6);
  font-size: var(--md-body-medium);
  border-radius: var(--md-radius-xs) !important;
  border: 1px dashed var(--md-outline) !important;
  background-color: transparent !important;
  color: var(--md-on-surface-variant) !important;
  font-family: var(--md-font-serif) !important;
  font-weight: 600 !important;
  box-shadow: 1px 1px 0px rgba(28, 32, 34, 0.05) !important;
  transition:
    background-color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    border-color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    opacity 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    transform 0.25s cubic-bezier(0.22, 1, 0.36, 1) !important;
  cursor: pointer;
}

.entry-actions__secondary:hover {
  background-color: var(--md-surface-container-low) !important;
  color: var(--md-secondary) !important; /* 变为朱砂红 */
  border-color: var(--md-secondary) !important;
  box-shadow: 2px 2px 0px rgba(184, 60, 50, 0.15) !important;
}

.entry-actions__secondary:active {
  transform: translate(1px, 1px) !important;
  box-shadow: 0.5px 0.5px 0px rgba(184, 60, 50, 0.15) !important;
}

/* Modal 样式国风微调 */
.updates-dialog-header {
  border-color: var(--md-outline-variant) !important;
}

.updates-dialog-title {
  color: var(--md-on-surface) !important;
  font-family: var(--md-font-serif) !important;
  font-weight: 600;
  letter-spacing: 0.05em;
}

.updates-community-box {
  background-color: var(--md-surface-container-high) !important;
  border: 1px dashed var(--md-secondary) !important;
  border-radius: var(--md-radius-xs) !important;
}

.updates-community-text {
  color: var(--md-on-surface) !important;
  font-family: var(--md-font-kai) !important;
}

.updates-timeline-connector {
  background-color: var(--md-outline-variant) !important;
}

.updates-timeline-dot {
  width: 10px;
  height: 10px;
  background-color: var(--md-secondary) !important; /* 朱砂方点 */
  border-radius: var(--md-radius-xs) !important;
  transform: rotate(45deg);
  margin-top: 6px;
  box-shadow: 0 0 0 6px var(--md-surface) !important;
}

.updates-timeline-time {
  color: var(--md-secondary) !important;
  font-family: var(--md-font-serif) !important;
  font-weight: 600;
}

.updates-timeline-content {
  color: var(--md-on-surface) !important;
}

.workspace-entry__dialog-timeline .md-card {
  border-radius: var(--md-radius-xs) !important;
  border: 1px solid var(--md-outline) !important;
  background-color: var(--md-surface-container-low) !important;
}

.updates-dialog-actions .md-btn {
  font-family: var(--md-font-serif) !important;
  font-weight: 600;
}

/* 首屏宣纸润墨淡入动画 */
.fade-in {
  animation: ink-fade-in 0.75s cubic-bezier(0.22, 1, 0.36, 1) forwards;
}

@keyframes ink-fade-in {
  0% {
    opacity: 0;
    transform: translateY(8px);
    filter: blur(8px); /* 起笔淡墨模糊 */
  }
  100% {
    opacity: 1;
    transform: translateY(0);
    filter: blur(0);
  }
}

/* 主动作按钮朱砂印章样式 */
.entry-actions__stamp {
  font-family: var(--md-font-serif) !important;
  font-weight: 600;
  color: var(--md-secondary) !important;
  margin-right: var(--md-spacing-2);
  user-select: none;
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

/* 遮罩背景水墨漫润般变深 */
.dialog-fade-enter-active,
.dialog-fade-leave-active {
  transition: opacity 0.5s cubic-bezier(0.22, 1, 0.36, 1);
}

.dialog-fade-enter-from,
.dialog-fade-leave-to {
  opacity: 0;
}

/* 弹窗实体如折页书卷般舒展开来 */
.dialog-fade-enter-active .workspace-entry__dialog,
.dialog-fade-leave-active .workspace-entry__dialog {
  transition: 
    transform 0.5s cubic-bezier(0.22, 1, 0.36, 1),
    filter 0.5s cubic-bezier(0.22, 1, 0.36, 1),
    opacity 0.5s cubic-bezier(0.22, 1, 0.36, 1);
}

.dialog-fade-enter-from .workspace-entry__dialog {
  transform: scale(0.96) translateY(10px);
  filter: blur(4px); /* 刚出现时微模糊 */
  opacity: 0;
}

.dialog-fade-leave-to .workspace-entry__dialog {
  transform: scale(0.98) translateY(-6px);
  filter: blur(2px);
  opacity: 0;
}
</style>
