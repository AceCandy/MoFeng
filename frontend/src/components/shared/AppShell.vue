<!-- AIMETA P=应用布局_认证后共享外壳|R=全局导航_页面容器|NR=不含业务页面逻辑|E=component:AppShell|X=ui|A=布局组件|D=vue,vue-router,pinia|S=dom|RD=./README.ai -->
<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted, defineAsyncComponent } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useQueryClient } from '@tanstack/vue-query'

import { clearAuthQueryCache } from '@/queries/auth'
import { useAuthStore } from '@/stores/auth'
import {
  useNovelProjectsQuery,
  useNovelProjectQuery,
  useImportNovelMutation,
} from '@/queries/novel'
import { useNovelStore } from '@/stores/novel'
import GlobalModalContainer from '@/components/shared/GlobalModalContainer.vue'
import { globalAlert } from '@/composables/useAlert'

const SettingsView = defineAsyncComponent(() => import('@/views/SettingsView.vue'))
const AdminView = defineAsyncComponent(() => import('@/views/AdminView.vue'))
const PromptUsageMap = defineAsyncComponent(() => import('@/components/admin/PromptUsageMap.vue'))

const showSettingsModal = ref(false)
const showAdminModal = ref(false)
const showPromptUsageModal = ref(false)
const adminInitialTab = ref('statistics')

// 昼夜主题中式切换逻辑
const isDarkTheme = ref(false)

const syncThemeState = () => {
  const currentTheme = document.documentElement.dataset.theme
  isDarkTheme.value = currentTheme === 'dark'
}

const toggleTheme = () => {
  const nextTheme = isDarkTheme.value ? 'light' : 'dark'
  document.documentElement.dataset.theme = nextTheme
  window.localStorage.setItem('mofeng-theme-preference', nextTheme)
  isDarkTheme.value = nextTheme === 'dark'

  // 向外抛出全局事件，方便其他组件同步
  window.dispatchEvent(new Event('theme-changed'))
}


const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const queryClient = useQueryClient()
const isDropdownOpen = ref(false)

const novelStore = useNovelStore()
const isAssistantOpen = computed(() => novelStore.isAssistantPanelVisible)
const toggleWorkspaceAssistant = () => {
  novelStore.isAssistantPanelVisible = !novelStore.isAssistantPanelVisible
}

const importMutation = useImportNovelMutation()
const fileInputRef = ref<HTMLInputElement | null>(null)
const capsuleRef = ref<HTMLElement | null>(null)

const currentProjectId = computed(() => {
  return (route.params.id as string) || null
})

const { data: currentProject } = useNovelProjectQuery(currentProjectId)
const { data: rawProjects } = useNovelProjectsQuery()
const projects = computed(() => rawProjects.value || [])

const projectTags = computed(() => {
  if (!currentProject.value) return ''
  const bp = currentProject.value.blueprint
  let genreText = ''
  
  if (bp?.genre) {
    genreText = bp.genre
  } else {
    const summary = projects.value.find(p => p.id === currentProjectId.value)
    if (summary?.genre) {
      genreText = summary.genre
    }
  }
  
  if (!genreText) {
    return '山水写意'
  }
  
  return genreText
})

const projectStats = computed(() => {
  if (!currentProject.value) return null
  const total = currentProject.value.chapters?.length || 0
  const completed = currentProject.value.chapters?.filter(c => c.content && c.content.length > 0).length || 0
  const percent = total > 0 ? Math.round((completed / total) * 100) : 0
  return {
    completed,
    total,
    percent
  }
})

const triggerImport = () => {
  fileInputRef.value?.click()
}

const isUserDropdownOpen = ref(false)
const userTagRef = ref<HTMLElement | null>(null)

const handleFileChange = async (event: Event) => {
  const input = event.target as HTMLInputElement
  if (input.files && input.files[0]) {
    const file = input.files[0]
    try {
      const res = await importMutation.mutateAsync(file)
      isDropdownOpen.value = false
      if (res && res.id) {
        router.push(`/projects/${res.id}/write`)
      } else {
        router.push('/workspace')
      }
    } catch (err) {
      console.error('导入卷轴失败:', err)
    }
  }
}

const selectProject = (proj: { id: string; title?: string }) => {
  isDropdownOpen.value = false
  const titleStr = (proj.title || '').trim()
  if (titleStr === '未命名灵感') {
    router.push(`/inspiration?project_id=${proj.id}`)
  } else {
    router.push(`/projects/${proj.id}/write`)
  }
}

const goToWritingDesk = () => {
  const project = currentProject.value
  if (!project) return
  const path =
    project.title === '未命名灵感'
      ? `/inspiration?project_id=${project.id}`
      : `/projects/${project.id}/write`
  router.push(path)
}

const goToBlueprint = () => {
  if (currentProjectId.value) {
    router.push(`/projects/${currentProjectId.value}`)
  }
}

const selectInspiration = () => {
  isDropdownOpen.value = false
  router.push('/inspiration')
}

const isProjectContext = computed(() =>
  ['project-detail', 'project-write', 'admin-project-detail'].includes(String(route.name || '')),
)

const logout = () => {
  authStore.logout()
  clearAuthQueryCache(queryClient)
  router.push('/login')
}

const handleClickOutside = (event: MouseEvent) => {
  if (isDropdownOpen.value && capsuleRef.value && !capsuleRef.value.contains(event.target as Node)) {
    isDropdownOpen.value = false
  }
  if (isUserDropdownOpen.value && userTagRef.value && !userTagRef.value.contains(event.target as Node)) {
    isUserDropdownOpen.value = false
  }
}

const settingsViewRef = ref<any>(null)
const isSavingSettings = ref(false)

const triggerSettingsSave = async () => {
  if (settingsViewRef.value) {
    isSavingSettings.value = true
    try {
      await settingsViewRef.value.save()
    } catch (err) {
      console.error('配置保存失败:', err)
    } finally {
      isSavingSettings.value = false
    }
  }
}

const handleCloseSettingsModal = async () => {
  const isDirty = settingsViewRef.value?.isDirty
  if (isDirty) {
    const confirmed = await globalAlert.showConfirm(
      '案头仍有未保存的配置底墨，此时离席将丢弃修改，是否确定关闭？',
      '未保存确认'
    )
    if (!confirmed) {
      return
    }
  }
  showSettingsModal.value = false
}

const openAdminModal = (tab: string = 'statistics') => {
  adminInitialTab.value = tab
  showAdminModal.value = true
  showPromptUsageModal.value = false
  isUserDropdownOpen.value = false
}

const openPromptUsageModal = () => {
  showPromptUsageModal.value = true
  showAdminModal.value = false
  isUserDropdownOpen.value = false
}

const openPromptEditor = () => {
  openAdminModal('prompts')
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
  syncThemeState()

  // 监听系统的偏好改变
  const media = window.matchMedia('(prefers-color-scheme: dark)')
  const preference = window.localStorage.getItem('mofeng-theme-preference')
  if (preference === 'system' || !preference) {
    if (typeof media.addEventListener === 'function') {
      media.addEventListener('change', syncThemeState)
    } else {
      media.addListener(syncThemeState)
    }
  }
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>

<template>
  <div class="app-shell" :class="{ 'app-shell--project-context': isProjectContext }">
    <a class="skip-link" href="#main-content">跳到主内容</a>

    <div class="app-shell__main">
      <header class="app-shell__topbar">
        <!-- 左侧墨风金石Logo -->
        <RouterLink to="/" class="app-shell__brand-top" style="text-decoration: none;">
          <div class="app-shell__brand-mark" aria-hidden="true">墨</div>
          <div class="app-shell__brand-copy">
            <p class="app-shell__brand-title">墨風</p>
            <p class="app-shell__account-role">AI 小说创作中控台</p>
          </div>
        </RouterLink>

        <!-- 作品空间双胶囊选择器 (砚海阁案头中枢) -->
        <div class="app-shell__top-nav app-shell__project-capsule-container">
          <!-- 胶囊一：选择作品空间 -->
          <div 
            ref="capsuleRef"
            class="app-shell__project-capsule is-select"
            :class="{ 'is-active': isDropdownOpen }"
            @click="isDropdownOpen = !isDropdownOpen"
          >
            <span class="app-shell__project-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
              </svg>
            </span>
            <span class="app-shell__project-title">
              {{ currentProject ? (currentProject.title || '未命名书卷') : '选择案头画卷...' }}
            </span>
            <span class="app-shell__project-arrow" :class="{ 'is-open': isDropdownOpen }">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
            </span>

            <!-- 水墨风微粒下拉菜单 -->
            <transition name="fade">
              <div v-if="isDropdownOpen" class="app-shell__project-dropdown" @click.stop>
                <div class="app-shell__dropdown-header">阁主已存书卷</div>
                <div class="app-shell__dropdown-list">
                  <div 
                    v-for="proj in projects" 
                    :key="proj.id" 
                    class="app-shell__dropdown-item"
                    :class="{ 'is-active': proj.id === currentProjectId }"
                    @click="selectProject(proj)"
                  >
                    <span class="item-mark">📖</span>
                    <span class="item-title">{{ proj.title || '未命名书卷' }}</span>
                  </div>
                  <div v-if="projects.length === 0" class="app-shell__dropdown-empty">
                    案头尚无书卷，请点击下方开启创作
                  </div>
                </div>
                <div class="app-shell__dropdown-divider"></div>
                <div class="app-shell__dropdown-actions">
                  <div class="app-shell__dropdown-action" @click="selectInspiration">
                    <span class="action-icon">💡</span>
                    <span>灵感启航</span>
                  </div>
                  <div class="app-shell__dropdown-action" @click="triggerImport">
                    <span class="action-icon">📥</span>
                    <span>导入卷轴</span>
                  </div>
                </div>
              </div>
            </transition>
          </div>

          <!-- 胶囊二：当前作品的多维成就与状态 (始终保留常驻展示) -->
          <div v-if="currentProject && projectStats" class="app-shell__project-capsule is-status">
            <span class="app-shell__project-tag-info">{{ projectTags }}</span>
            <span class="app-shell__project-divider">•</span>
            <span class="app-shell__project-progress-info">
              <strong class="app-shell__number">{{ projectStats.percent }}%</strong> 完成
            </span>
            <span class="app-shell__project-divider">•</span>
            <span class="app-shell__project-chapter-info">
              <strong class="app-shell__number">{{ projectStats.completed }}/{{ projectStats.total }}</strong> 章
            </span>
          </div>

          <!-- 当处于项目总览页 (project-detail) 时，在旁边紧贴着并列呈现“继续创作”顶栏金石按钮 -->
          <div v-if="currentProject && route.name === 'project-detail'" class="app-shell__top-action-wrap">
            <button 
              type="button"
              class="app-shell__top-action-btn md-ripple" 
              title="点击继续创作正文"
              @click="goToWritingDesk"
            >
              <svg
                class="w-4 h-4"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2.5"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"
                />
              </svg>
              <span>继续创作</span>
            </button>
          </div>

          <!-- 当处于项目写作页 (project-write) 时，在旁边紧贴着并列呈现“蓝图概览”顶栏金石按钮 -->
          <div v-if="currentProject && route.name === 'project-write'" class="app-shell__top-action-wrap">
            <button 
              type="button"
              class="app-shell__top-action-btn md-ripple" 
              title="点击回到故事蓝图"
              @click="goToBlueprint"
            >
              <svg
                class="w-4 h-4"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2.5"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  d="M9 15L3 9m0 0l6-6M3 9h12a6 6 0 010 12h-3"
                />
              </svg>
              <span>蓝图概览</span>
            </button>
          </div>

          <!-- 空白状态：山水泼墨励志寄语 (仅在未选定工作空间前渲染) -->
          <div v-if="!currentProjectId" class="app-shell__project-welcome-message">
            <span class="welcome-spark">✍️</span>
            <span class="welcome-text">笔底生墨，风动砚海。阁主，今天又是新的元气的一天，快来尽情创作吧！</span>
          </div>

          <!-- 隐藏的导入文件 Input -->
          <input 
            ref="fileInputRef" 
            type="file" 
            accept=".txt,.json,.md,.zip" 
            style="display: none" 
            @change="handleFileChange" 
          />
        </div>

        <!-- 右侧操作控制台 (辅助信息印章与水墨折叠下拉) -->
        <div class="app-shell__actions-right">
          <!-- 昼夜切换中式印章 -->
          <button
            type="button"
            class="app-shell__action-btn theme-toggle-btn"
            :title="isDarkTheme ? '换至：昼模式 (熟宣暖白)' : '换至：夜模式 (深夜书房)'"
            @click="toggleTheme"
          >
            <span class="app-shell__action-badge" :class="isDarkTheme ? 'is-theme-light' : 'is-theme-dark'">
              {{ isDarkTheme ? '晝' : '夜' }}
            </span>
          </button>



          <!-- 阁主身份名牌 (金石印章折叠中枢) -->
          <div 
            ref="userTagRef"
            class="app-shell__user-tag is-trigger"
            :class="{ 'is-active': isUserDropdownOpen }"
            @click="isUserDropdownOpen = !isUserDropdownOpen"
            role="button"
            aria-haspopup="true"
            :aria-expanded="isUserDropdownOpen"
            title="查看阁主菜单"
          >
            <span class="app-shell__user-role-dot" :class="{ 'is-admin-dot': authStore.user?.is_admin }"></span>
            <span class="app-shell__user-name">{{ authStore.user?.username || '阁主' }}</span>
            <span class="app-shell__user-arrow" :class="{ 'is-open': isUserDropdownOpen }">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
            </span>

            <!-- 水墨信笺下拉菜单 -->
            <transition name="fade">
              <div v-if="isUserDropdownOpen" class="app-shell__user-dropdown" @click.stop>
                <div class="app-shell__user-dropdown-header">阁主案头起居</div>
                <div class="app-shell__user-dropdown-list">
                  <!-- 系统管理配置 -->
                  <a
                    v-if="authStore.user?.is_admin"
                    href="javascript:void(0)"
                    class="app-shell__user-dropdown-item"
                    :class="{ 'is-active': showAdminModal }"
                    @click.prevent="openAdminModal()"
                  >
                    <span class="app-shell__action-badge is-admin">管</span>
                    <div class="item-text">
                      <span class="item-title">系统管理</span>
                      <span class="item-desc">配置全局与用户权限</span>
                    </div>
                  </a>

                  <!-- 提示词阶段关系 -->
                  <a
                    v-if="authStore.user?.is_admin"
                    href="javascript:void(0)"
                    class="app-shell__user-dropdown-item"
                    :class="{ 'is-active': showPromptUsageModal }"
                    @click.prevent="openPromptUsageModal"
                  >
                    <span class="app-shell__action-badge is-prompt">词</span>
                    <div class="item-text">
                      <span class="item-title">提示词管理</span>
                      <span class="item-desc">查看阶段与 Prompt 关系</span>
                    </div>
                  </a>

                  <!-- 配置个人 AI 模型 -->
                  <a
                    href="javascript:void(0)"
                    class="app-shell__user-dropdown-item"
                    :class="{ 'is-active': showSettingsModal }"
                    @click.prevent="showSettingsModal = true; isUserDropdownOpen = false"
                  >
                    <span class="app-shell__action-badge is-settings">設</span>
                    <div class="item-text">
                      <span class="item-title">模型设置</span>
                      <span class="item-desc">配置个人大语言模型</span>
                    </div>
                  </a>

                  <div class="app-shell__user-dropdown-divider"></div>

                  <!-- 离席退出系统 -->
                  <button
                    type="button"
                    class="app-shell__user-dropdown-item is-logout-action"
                    @click="logout"
                  >
                    <span class="app-shell__action-badge is-logout">离</span>
                    <div class="item-text">
                      <span class="item-title">离席登出</span>
                      <span class="item-desc">保存草稿并安全离线</span>
                    </div>
                  </button>
                </div>
              </div>
            </transition>
          </div>
        </div>

        <!-- 全局水墨宣纸写作进度条 (仅在写作台页面展示) -->
        <div 
          v-if="currentProject && projectStats && route.name === 'project-write'" 
          class="app-shell__global-progress" 
          role="progressbar"
          :aria-valuenow="projectStats.percent"
          aria-valuemin="0"
          aria-valuemax="100"
          :aria-label="`写作进度 ${projectStats.percent}%`"
        >
          <span :style="{ transform: `scaleX(${projectStats.percent / 100})` }"></span>
        </div>
      </header>

      <main id="main-content" class="app-shell__content" tabindex="-1">
        <slot />
      </main>
    </div>

    <!-- 全局模型设置与系统管理大弹窗 (案头折纸折子戏) -->
    <Teleport to="body">
      <GlobalModalContainer
        v-if="showSettingsModal"
        title="模型与能力中枢"
        hide-close-button
        @close="handleCloseSettingsModal"
      >
        <template #header-actions>
          <!-- 极具金石质感的「存」字朱红方章保存按钮 -->
          <button
            type="button"
            class="m3-ink-modal-save-btn"
            title="保存当前配置"
            :disabled="isSavingSettings"
            @click="triggerSettingsSave"
          >
            <span class="m3-ink-modal-save-badge">存</span>
            <span class="m3-ink-modal-save-text">{{ isSavingSettings ? '保存中...' : '保存' }}</span>
          </button>
        </template>
        <SettingsView ref="settingsViewRef" :is-modal="true" @saved="showSettingsModal = false" />
      </GlobalModalContainer>

      <GlobalModalContainer
        v-if="showAdminModal"
        title="系统运营控制台"
        hide-close-button
        @close="showAdminModal = false"
      >
        <AdminView :is-modal="true" :initial-tab="adminInitialTab" />
      </GlobalModalContainer>

      <GlobalModalContainer
        v-if="showPromptUsageModal"
        title="提示词关系总览"
        width="min(94vw, 1180px)"
        @close="showPromptUsageModal = false"
      >
        <PromptUsageMap @open-prompt-editor="openPromptEditor" />
      </GlobalModalContainer>
    </Teleport>
  </div>
</template>

<style scoped>
/* 昼夜切换中式印章专属样式 */
.theme-toggle-btn {
  margin-right: 4px;
}

/* 昼模式印章：翠玉竹青色，彰显清新白昼 */
.app-shell__action-badge.is-theme-light {
  background-color: var(--md-success, #3b7a57) !important;
  color: var(--md-on-success) !important;
  border: 1px solid var(--md-outline) !important;
  box-shadow: 1.5px 1.5px 0px rgba(59, 122, 87, 0.25) !important;
  transform: rotate(2deg) !important;
}

/* 夜模式印章：深沉朱砂红，代表静谧深夜 */
.app-shell__action-badge.is-theme-dark {
  background-color: var(--md-secondary, #b83c32) !important;
  color: var(--md-on-secondary) !important;
  border: 1px solid var(--md-outline) !important;
  box-shadow: 1.5px 1.5px 0px rgba(184, 60, 50, 0.25) !important;
  transform: rotate(-1.5deg) !important;
}

/* 悬浮微升，产生毛笔书写的弹跳动感 */
.theme-toggle-btn:hover .app-shell__action-badge {
  transform: scale(1.08) rotate(5deg) !important;
  box-shadow: 2px 2px 0px rgba(28, 32, 34, 0.2) !important;
}

/* 顶栏继续创作方正金石按钮样式 */
.app-shell__top-action-wrap {
  display: flex;
  align-items: center;
  margin-left: 8px;
}

.app-shell__top-action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 44px;
  padding: 0 16px;
  border-radius: var(--md-radius-xs) !important;
  border: 1px solid var(--md-outline) !important;
  background-color: var(--md-primary) !important; /* 焦墨底色 */
  color: var(--md-on-primary) !important; /* 熟宣字色 */
  font-family: var(--md-font-serif);
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.08em;
  cursor: pointer;
  box-shadow: 1.5px 1.5px 0px rgba(28, 32, 34, 0.2);
  transition:
    background-color 0.2s cubic-bezier(0.2, 0, 0, 1),
    box-shadow 0.2s cubic-bezier(0.2, 0, 0, 1),
    transform 0.2s cubic-bezier(0.2, 0, 0, 1);
}

.app-shell__top-action-btn:hover {
  background-color: var(--md-primary-dark) !important;
  box-shadow: 2.5px 2.5px 0px rgba(184, 60, 50, 0.25) !important; /* 朱批红印重影 */
  transform: translate(-1px, -1px);
}

.app-shell__top-action-btn svg {
  width: 14px;
  height: 14px;
}
</style>
