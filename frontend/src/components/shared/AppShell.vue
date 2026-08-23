<!-- AIMETA P=应用布局_认证后共享外壳|R=全局导航_页面容器|NR=不含业务页面逻辑|E=component:AppShell|X=ui|A=布局组件|D=vue,vue-router,pinia|S=dom|RD=./README.ai -->
<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted, defineAsyncComponent, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { useQueryClient } from '@tanstack/vue-query'

import { clearAuthQueryCache } from '@/queries/auth'
import { useAuthStore } from '@/stores/auth'
import {
  novelQueryKeys,
  useNovelProjectsQuery,
  useNovelProjectQuery,
  useImportNovelMutation,
} from '@/queries/novel'
import { useTasksQuery, useTaskStream } from '@/queries/tasks'
import { useNovelStore } from '@/stores/novel'
import GlobalModalContainer from '@/components/shared/GlobalModalContainer.vue'
import { globalAlert } from '@/composables/useAlert'

const SettingsView = defineAsyncComponent(() => import('@/views/SettingsView.vue'))
const AdminView = defineAsyncComponent(() => import('@/views/AdminView.vue'))
const PromptUsageMap = defineAsyncComponent(() => import('@/components/admin/PromptUsageMap.vue'))
const PasswordManagement = defineAsyncComponent(() => import('@/components/admin/PasswordManagement.vue'))
const TaskLogPanel = defineAsyncComponent(() => import('@/components/shared/TaskLogPanel.vue'))

const showSettingsModal = ref(false)
const showAdminModal = ref(false)
const showPromptUsageModal = ref(false)
const showPasswordModal = ref(false)
const showTaskLogModal = ref(false)
const adminInitialTab = ref('statistics')

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const queryClient = useQueryClient()
const isDropdownOpen = ref(false)
const toggleDropdown = () => {
  isDropdownOpen.value = !isDropdownOpen.value
}
const { data: rawBackgroundTasks, isFetching: isFetchingTasks } = useTasksQuery()
const { sseBackgroundTasks, isTaskStreamActive } = useTaskStream(() => authStore.user?.id)
const completedOutlineTaskIds = new Set<string>()
const taskReadStoragePrefix = 'mofeng-task-read:'
const viewedCompletedTaskIds = ref<Set<string>>(new Set())

const taskReadStorageKey = computed(() => {
  const userId = authStore.user?.id
  return userId == null ? null : `${taskReadStoragePrefix}${userId}`
})

const loadViewedCompletedTaskIds = () => {
  const storageKey = taskReadStorageKey.value
  if (!storageKey) {
    viewedCompletedTaskIds.value = new Set()
    return
  }

  try {
    const stored = window.localStorage.getItem(storageKey)
    const ids = stored ? JSON.parse(stored) : []
    viewedCompletedTaskIds.value = new Set(
      Array.isArray(ids) ? ids.filter((id): id is string => typeof id === 'string') : [],
    )
  } catch {
    viewedCompletedTaskIds.value = new Set()
  }
}

const markCompletedTasksViewed = () => {
  const storageKey = taskReadStorageKey.value
  if (!storageKey) return

  const completedTaskIds = backgroundTasks.value
    .filter((task) => task.status === 'succeeded' || task.status === 'failed')
    .map((task) => task.id)
  if (completedTaskIds.length === 0) return

  const nextViewedIds = new Set(viewedCompletedTaskIds.value)
  completedTaskIds.forEach((id) => nextViewedIds.add(id))
  viewedCompletedTaskIds.value = nextViewedIds
  try {
    window.localStorage.setItem(storageKey, JSON.stringify([...nextViewedIds]))
  } catch {
    // 本地存储不可用时仍允许查看日志，并保留当前会话内的已读状态。
  }
}

const handleTaskButtonClick = () => {
  markCompletedTasksViewed()
  showTaskLogModal.value = true
}

watch(taskReadStorageKey, loadViewedCompletedTaskIds, { immediate: true })

const backgroundTasks = computed(() => sseBackgroundTasks.value ?? rawBackgroundTasks.value ?? [])
const isTaskSyncing = computed(() => isFetchingTasks.value || isTaskStreamActive.value)
const runningBackgroundTasks = computed(() =>
  backgroundTasks.value.filter((task) => task.status === 'running'),
)
const unviewedSucceededTasks = computed(() =>
  backgroundTasks.value.filter(
    (task) => task.status === 'succeeded' && !viewedCompletedTaskIds.value.has(task.id),
  ),
)
const unviewedFailedTasks = computed(() =>
  backgroundTasks.value.filter(
    (task) => task.status === 'failed' && !viewedCompletedTaskIds.value.has(task.id),
  ),
)
const completedTaskReminder = computed<'success' | 'failed' | null>(() => {
  if (!taskReadStorageKey.value) return null
  if (unviewedFailedTasks.value.length > 0) return 'failed'
  if (unviewedSucceededTasks.value.length > 0) return 'success'
  return null
})
const taskButtonLabel = computed(() => {
  if (runningBackgroundTasks.value.length > 0) {
    return `查看任务日志，${runningBackgroundTasks.value.length} 个任务执行中`
  }
  if (completedTaskReminder.value === 'failed') return '查看任务日志，有任务执行失败'
  if (completedTaskReminder.value === 'success') return '查看任务日志，有任务执行完成'
  return '查看任务日志'
})

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

watch(backgroundTasks, (tasks) => {
  for (const task of tasks) {
    if (
      task.task_type === 'chapter_outline' &&
      task.status === 'succeeded' &&
      task.project_id &&
      !completedOutlineTaskIds.has(task.id)
    ) {
      completedOutlineTaskIds.add(task.id)
      void queryClient.invalidateQueries({ queryKey: novelQueryKeys.projects() })
      void queryClient.invalidateQueries({ queryKey: novelQueryKeys.detail(task.project_id) })
    }
  }
})

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
const userTagTriggerRef = ref<HTMLButtonElement | null>(null)

const closeUserDropdown = (restoreFocus = false) => {
  isUserDropdownOpen.value = false
  if (restoreFocus) userTagTriggerRef.value?.focus()
}

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
// 仅「存」按钮触发的保存才关闭弹窗；删除模型、改定价等行内自动保存也会冒泡 saved，不得关窗
const closeSettingsOnSaved = ref(false)

const triggerSettingsSave = async () => {
  if (settingsViewRef.value) {
    isSavingSettings.value = true
    closeSettingsOnSaved.value = true
    try {
      await settingsViewRef.value.save()
    } catch (err) {
      console.error('配置保存失败:', err)
    } finally {
      isSavingSettings.value = false
      closeSettingsOnSaved.value = false
    }
  }
}

const handleSettingsSaved = () => {
  if (closeSettingsOnSaved.value) {
    showSettingsModal.value = false
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

const passwordManagementRef = ref<any>(null)
const isSavingPassword = computed(() => passwordManagementRef.value?.submitting ?? false)
const triggerPasswordSave = () => {
  passwordManagementRef.value?.submit()
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
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
        <!-- 左侧项目名 -->
        <RouterLink to="/" class="app-shell__brand-top">
          <p class="app-shell__brand-title">墨風</p>
        </RouterLink>

        <!-- 作品空间双胶囊选择器 (砚海阁案头中枢) -->
        <div class="app-shell__top-nav app-shell__project-capsule-container">
          <!-- 胶囊一：选择作品空间 -->
          <div 
            ref="capsuleRef"
            class="app-shell__project-capsule is-select"
            :class="{ 'is-active': isDropdownOpen }"
          >
            <button
              type="button"
              class="app-shell__project-trigger"
              :aria-expanded="isDropdownOpen"
              :aria-controls="isDropdownOpen ? 'app-shell-project-menu' : undefined"
              @click="toggleDropdown"
            >
              <span class="app-shell__project-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                </svg>
              </span>
              <span class="app-shell__project-title">
                {{ currentProject ? (currentProject.title || '未命名书卷') : '选择书卷' }}
              </span>
              <span class="app-shell__project-arrow" :class="{ 'is-open': isDropdownOpen }">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
                </svg>
              </span>
            </button>
 
             <!-- 水墨风微粒下拉菜单 -->
             <transition name="fade">
              <div 
                v-if="isDropdownOpen" 
                id="app-shell-project-menu"
                class="app-shell__project-dropdown" 
                @click.stop
              >
                 <div class="app-shell__dropdown-header">阁主已存书卷</div>
                 <div class="app-shell__dropdown-list">
                   <div 
                     v-for="proj in projects" 
                     :key="proj.id" 
                     class="app-shell__dropdown-item"
                     :class="{ 'is-active': proj.id === currentProjectId }"
                     @click="selectProject(proj)"
                   >
                     <span class="item-mark"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" /></svg></span>
                     <span class="item-title">{{ proj.title || '未命名书卷' }}</span>
                   </div>
                   <div v-if="projects.length === 0" class="app-shell__dropdown-empty">
                     案头尚无书卷，请点击下方开启创作
                   </div>
                 </div>
                 <div class="app-shell__dropdown-divider"></div>
                 <div class="app-shell__dropdown-actions">
                  <button
                    type="button"
                    class="app-shell__dropdown-action"
                    @click="selectInspiration"
                  >
                    <span class="action-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18h6" /><path d="M10 22h4" /><path d="M15.09 14c.18-.98.65-1.74 1.41-2.5A4.65 4.65 0 0 0 18 8 6 6 0 0 0 6 8c0 1 .23 2.23 1.5 3.5.76.76 1.23 1.52 1.41 2.5z" /></svg></span>
                    <span>灵感启航</span>
                  </button>
                  <button
                    type="button"
                    class="app-shell__dropdown-action"
                    @click="triggerImport"
                  >
                    <span class="action-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 16 12 14 15 10 15 8 12 2 12" /><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z" /></svg></span>
                    <span>导入卷轴</span>
                  </button>
                 </div>
               </div>
             </transition>
           </div>

          <!-- 胶囊二：当前作品的多维成就与状态 (始终保留常驻展示；写作台 is-writing-mode 下收敛为「N/M 章」，见 topbar.css) -->
          <div
            v-if="currentProject && projectStats"
            class="app-shell__project-capsule is-status"
            :class="{ 'is-writing-mode': route.name === 'project-write' }"
          >
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
            <span class="welcome-spark"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9" /><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" /></svg></span>
            <span class="welcome-text">笔底生墨，风动砚海。阁主，吾静待汝执笔。</span>
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
          <button
            type="button"
            class="app-shell__task-button"
            :title="taskButtonLabel"
            :aria-label="taskButtonLabel"
            @click="handleTaskButtonClick"
          >
            <svg
              class="app-shell__task-icon"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              aria-hidden="true"
            >
              <rect x="5" y="3" width="14" height="18" rx="2" />
              <path stroke-linecap="round" d="M9 8h6M9 12h6M9 16h4" />
            </svg>
            <span v-if="runningBackgroundTasks.length > 0" class="app-shell__task-count">
              {{ runningBackgroundTasks.length > 9 ? '9+' : runningBackgroundTasks.length }}
            </span>
            <span
              v-else-if="completedTaskReminder"
              class="app-shell__task-status-dot"
              :class="{ 'is-success': completedTaskReminder === 'success' }"
              aria-hidden="true"
            ></span>
          </button>

          <!-- 阁主身份菜单 -->
          <div
            ref="userTagRef"
            class="app-shell__user-menu"
            @keydown.esc.stop.prevent="closeUserDropdown(true)"
          >
            <button
              ref="userTagTriggerRef"
              type="button"
              class="app-shell__user-tag is-trigger"
              :class="{ 'is-active': isUserDropdownOpen }"
              :aria-expanded="isUserDropdownOpen"
              aria-controls="app-shell-user-menu"
              title="查看阁主菜单"
              @click="isUserDropdownOpen = !isUserDropdownOpen"
            >
              <span class="app-shell__user-role-dot" :class="{ 'is-admin-dot': authStore.user?.is_admin }"></span>
              <span class="app-shell__user-name">{{ authStore.user?.username || '阁主' }}</span>
              <span class="app-shell__user-arrow" :class="{ 'is-open': isUserDropdownOpen }">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
                </svg>
              </span>
            </button>

            <transition name="fade">
              <div
                v-if="isUserDropdownOpen"
                id="app-shell-user-menu"
                class="app-shell__user-dropdown"
                @click.stop
              >
                <div class="app-shell__user-dropdown-header">账户</div>
                <div class="app-shell__user-dropdown-list">
                  <!-- 系统管理配置 -->
                  <button
                    v-if="authStore.user?.is_admin"
                    type="button"
                    class="app-shell__user-dropdown-item"
                    :class="{ 'is-active': showAdminModal }"
                    @click="openAdminModal()"
                  >
                    <span class="app-shell__action-badge is-admin">司</span>
                    <div class="item-text">
                      <span class="item-title">系统管理</span>
                      <span class="item-desc">配置全局与用户权限</span>
                    </div>
                  </button>

                  <!-- 提示词阶段关系 -->
                  <button
                    v-if="authStore.user?.is_admin"
                    type="button"
                    class="app-shell__user-dropdown-item"
                    :class="{ 'is-active': showPromptUsageModal }"
                    @click="openPromptUsageModal"
                  >
                    <span class="app-shell__action-badge is-prompt">妙</span>
                    <div class="item-text">
                      <span class="item-title">提示词用量</span>
                      <span class="item-desc">查看阶段与 Prompt 关系</span>
                    </div>
                  </button>

                  <!-- 配置个人 AI 模型 -->
                  <button
                    type="button"
                    class="app-shell__user-dropdown-item"
                    :class="{ 'is-active': showSettingsModal }"
                    @click="showSettingsModal = true; isUserDropdownOpen = false"
                  >
                    <span class="app-shell__action-badge is-settings">乾</span>
                    <div class="item-text">
                      <span class="item-title">个人设置</span>
                      <span class="item-desc">配置个人 AI 模型</span>
                    </div>
                  </button>

                  <!-- 修改个人密码 -->
                  <button
                    type="button"
                    class="app-shell__user-dropdown-item"
                    :class="{ 'is-active': showPasswordModal }"
                    @click="showPasswordModal = true; isUserDropdownOpen = false"
                  >
                    <span class="app-shell__action-badge is-password">密</span>
                    <div class="item-text">
                      <span class="item-title">修改密码</span>
                      <span class="item-desc">更新登录密码</span>
                    </div>
                  </button>

                  <div class="app-shell__user-dropdown-divider"></div>

                  <!-- 离席退出系统 -->
                  <button
                    type="button"
                    class="app-shell__user-dropdown-item is-logout-action"
                    @click="logout"
                  >
                    <span class="app-shell__action-badge is-logout">离</span>
                    <div class="item-text">
                      <span class="item-title">退出登录</span>
                      <span class="item-desc">保存草稿并安全退出</span>
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
        v-if="showTaskLogModal"
        title="任务日志"
        badge-text="务"
        width="min(94vw, 960px)"
        @close="showTaskLogModal = false"
      >
        <TaskLogPanel :tasks="backgroundTasks" :loading="isTaskSyncing" />
      </GlobalModalContainer>

      <GlobalModalContainer
        v-if="showSettingsModal"
        title="个人设置"
        badge-text="乾"
        @close="handleCloseSettingsModal"
      >
        <template #header-actions>
          <!-- 极具金石质感的「存」字朱红方章保存按钮 -->
          <button
            type="button"
            class="m3-ink-modal-save-badge-btn"
            :title="isSavingSettings ? '正在保存中...' : '保存当前案头配置'"
            :disabled="isSavingSettings"
            @click="triggerSettingsSave"
          >
            存
          </button>
        </template>
        <SettingsView ref="settingsViewRef" :is-modal="true" @saved="handleSettingsSaved" />
      </GlobalModalContainer>

      <GlobalModalContainer
        v-if="showAdminModal"
        title="系统管理"
        badge-text="司"
        @close="showAdminModal = false"
      >
        <AdminView :is-modal="true" :initial-tab="adminInitialTab" />
      </GlobalModalContainer>

      <GlobalModalContainer
        v-if="showPromptUsageModal"
        title="提示词用量"
        badge-text="妙"
        width="min(94vw, 1180px)"
        @close="showPromptUsageModal = false"
      >
        <PromptUsageMap @open-prompt-editor="openPromptEditor" />
      </GlobalModalContainer>

      <GlobalModalContainer
        v-if="showPasswordModal"
        title="修改密码"
        badge-text="密"
        width="min(90vw, 540px)"
        @close="showPasswordModal = false"
      >
        <template #header-actions>
          <!-- 极具金石质感的「契」字朱红方章保存按钮 -->
          <button
            type="button"
            class="m3-ink-modal-save-badge-btn"
            title="确认更替密契"
            :disabled="isSavingPassword"
            @click="triggerPasswordSave"
          >
            契
          </button>
        </template>
        <PasswordManagement ref="passwordManagementRef" :is-modal="true" @saved="showPasswordModal = false" />
      </GlobalModalContainer>
    </Teleport>


  </div>
</template>

<style scoped>
.app-shell__task-button {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  min-height: 44px;
  padding: 0;
  border: 0;
  border-radius: var(--md-radius-full);
  background: transparent;
  color: var(--md-on-surface-variant);
  cursor: pointer;
  transition:
    color 160ms cubic-bezier(0.2, 0, 0, 1),
    transform 160ms cubic-bezier(0.2, 0, 0, 1);
}

.app-shell__task-button:hover {
  color: var(--md-primary);
  transform: translateY(-1px);
}

.app-shell__task-button:focus-visible {
  outline: 2px solid var(--md-primary);
  outline-offset: 2px;
}

.app-shell__task-icon {
  width: 20px;
  height: 20px;
  color: currentColor;
}

.app-shell__task-count {
  position: absolute;
  top: -5px;
  right: -5px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 3px;
  border: 1px solid var(--md-outline);
  border-radius: var(--md-radius-full);
  background: var(--md-warning-container);
  color: var(--md-on-surface);
  font-size: 12px;
  font-weight: 700;
  line-height: 1;
}

.app-shell__task-status-dot {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 7px;
  height: 7px;
  border: 1px solid var(--md-surface-container-low);
  border-radius: var(--md-radius-full);
  background: var(--md-error);
}

.app-shell__task-status-dot.is-success {
  background: var(--md-success);
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
  white-space: nowrap; /* 治「蓝图概览」等四字竖断折行 */
  border-radius: var(--md-radius-xs) !important;
  border: 1px solid var(--md-outline) !important;
  /* 导航钮保持安静：透明底焦墨字，不抢朱砂承诺钮的权责 */
  background-color: transparent !important;
  color: var(--md-on-surface) !important;
  font-family: var(--md-font-serif);
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.08em;
  cursor: pointer;
  box-shadow: none; /* 纸页柔影是唯一的影：硬偏置投影已退役 */
  transition:
    background-color 0.2s cubic-bezier(0.2, 0, 0, 1),
    box-shadow 0.2s cubic-bezier(0.2, 0, 0, 1),
    transform 0.2s cubic-bezier(0.2, 0, 0, 1);
}

.app-shell__top-action-btn:hover {
  background-color: var(--md-surface-container) !important;
  border-color: var(--md-on-surface-variant) !important;
  box-shadow: var(--md-elevation-paper-1) !important;
}

/* 项目上下文顶栏的金石导航钮沿用纸色层级 */
.app-shell--project-context .app-shell__top-action-btn {
  border-color: var(--md-outline-variant) !important;
  color: var(--md-on-surface) !important;
}

.app-shell--project-context .app-shell__top-action-btn:hover {
  background-color: var(--md-state-layer-hover) !important;
  border-color: var(--md-outline) !important;
  box-shadow: none !important;
}

.app-shell--project-context .app-shell__task-button {
  color: var(--md-on-surface-variant);
}

.app-shell--project-context .app-shell__task-button:hover {
  color: var(--md-on-surface);
}

.app-shell--project-context .app-shell__task-button:focus-visible {
  outline-color: var(--md-miaohong);
}

.app-shell__top-action-btn svg {
  width: 14px;
  height: 14px;
}

/* 菜单 hover 回归平净：旧世界扫墨 SVG 纹理已焚稿 */
.app-shell__dropdown-item:hover {
  background-color: var(--md-surface-container) !important;
}

.app-shell__project-welcome-message {
  /* 空态寄语保持素纸，不再叠泼墨纹理 */
}

/* 品牌链接与胶囊触发器样式（自模板内联样式收编） */
.app-shell__user-menu {
  position: relative;
}

.app-shell__user-dropdown-item {
  font: inherit;
  text-align: left;
}

.app-shell__brand-top {
  text-decoration: none;
}

.app-shell__project-trigger {
  display: flex;
  align-items: center;
  width: 100%;
  height: 100%;
  padding: 0;
  border: none;
  background: none;
  color: inherit;
  font: inherit;
  cursor: pointer;
  outline: none;
}

/* 下拉条目与寄语的 SVG 图标尺寸（替代原 emoji） */
.item-mark,
.action-icon,
.welcome-spark {
  display: inline-flex;
  align-items: center;
  flex-shrink: 0;
}

.item-mark svg,
.action-icon svg,
.welcome-spark svg {
  width: 15px;
  height: 15px;
}

</style>
