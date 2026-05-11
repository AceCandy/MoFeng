<!-- AIMETA P=小说工作区_小说列表管理|R=小说列表_创建|NR=不含章节编辑|E=route:/workspace#component:NovelWorkspace|X=ui|A=工作区|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div class="app-page workspace-page">
    <transition
      enter-active-class="transition-opacity duration-200"
      leave-active-class="transition-opacity duration-200"
      enter-from-class="opacity-0 translate-y-4"
      leave-to-class="opacity-0 translate-y-4"
    >
      <div v-if="workspaceMessage" class="md-snackbar" role="status">
        <svg
          v-if="workspaceMessage.type === 'success'"
          class="w-5 h-5"
          style="color: var(--md-success)"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
        >
          <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
        </svg>
        <svg
          v-else
          class="w-5 h-5"
          style="color: var(--md-error)"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
        <span class="md-snackbar-text">{{ workspaceMessage.text }}</span>
      </div>
    </transition>

    <section
      v-if="!novelStore.isLoading && !novelStore.error && continueProject"
      class="workspace-continue"
    >
      <div class="workspace-continue__copy">
        <p class="workspace-kicker">最近项目</p>
        <h2>{{ continueProject.title }}</h2>
        <p>
          {{ continueProject.genre || '未设置类型' }} · {{ continueProject.completed_chapters }}/{{
            continueProject.total_chapters
          }}
          章 ·
          {{ formatProjectDate(continueProject.last_edited) }}
        </p>
      </div>
      <div class="workspace-continue__actions">
        <button
          type="button"
          class="md-btn md-btn-filled md-ripple"
          @click="enterProject(continueProject)"
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
              d="M15.232 5.232l3.536 3.536M4 20h4l11-11a2.5 2.5 0 10-3.536-3.536L4 16.928V20z"
            />
          </svg>
          继续写作
        </button>
        <button
          type="button"
          class="md-btn md-btn-outlined md-ripple"
          @click="viewProjectDetail(continueProject.id)"
        >
          小说档案
        </button>
      </div>
    </section>

    <section class="workspace-actions" aria-label="项目操作">
      <button type="button" class="workspace-action" @click="goToInspiration">
        <span class="workspace-action__icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M12 3l1.6 5.4L19 10l-5.4 1.6L12 17l-1.6-5.4L5 10l5.4-1.6L12 3z"
            />
          </svg>
        </span>
        <span>
          <strong>新灵感</strong>
          <small>从对话开始整理故事蓝图</small>
        </span>
      </button>
      <button type="button" class="workspace-action" :disabled="isImporting" @click="triggerImport">
        <span class="workspace-action__icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1M8 8l4-4m0 0l4 4m-4-4v12"
            />
          </svg>
        </span>
        <span>
          <strong>{{ isImporting ? '正在导入' : '导入小说' }}</strong>
          <small>上传 .txt 并进入写作台</small>
        </span>
      </button>
      <router-link v-if="authStore.user?.is_admin" to="/admin" class="workspace-action">
        <span class="workspace-action__icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M4 7h16M6 7v12h12V7M9 11h6M9 15h6"
            />
          </svg>
        </span>
        <span>
          <strong>管理</strong>
          <small>查看平台与项目管理入口</small>
        </span>
      </router-link>
      <input type="file" ref="fileInput" accept=".txt" class="hidden" @change="handleFileImport" />
    </section>

    <section class="workspace-panel">
      <div class="workspace-panel__header">
        <div>
          <p class="workspace-kicker">项目列表</p>
          <h2>我的小说项目</h2>
        </div>
        <span class="md-chip md-chip-assist">{{ sortedProjects.length }} 个项目</span>
      </div>

      <div v-if="novelStore.isLoading" class="workspace-grid" aria-label="项目加载中">
        <article v-for="index in 3" :key="index" class="workspace-skeleton">
          <div class="workspace-skeleton__header">
            <span class="workspace-skeleton__avatar"></span>
            <span class="workspace-skeleton__lines">
              <span></span>
              <span></span>
            </span>
          </div>
          <span class="workspace-skeleton__bar"></span>
          <span class="workspace-skeleton__chips"></span>
        </article>
      </div>

      <div v-else-if="novelStore.error" class="workspace-state">
        <div class="workspace-state__icon is-error">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
        </div>
        <p class="md-body-large" style="color: var(--md-error)">{{ novelStore.error }}</p>
        <button @click="loadProjects" class="md-btn md-btn-filled md-ripple">重试</button>
      </div>

      <div v-else-if="sortedProjects.length === 0" class="workspace-state">
        <div class="workspace-state__icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"
            />
          </svg>
        </div>
        <h3>还没有项目</h3>
        <p>创建一个项目后，这里会显示最近写作进度。</p>
        <button @click="goToInspiration" class="md-btn md-btn-filled md-ripple">开始新灵感</button>
      </div>

      <div v-else class="workspace-grid">
        <ProjectCard
          v-for="project in sortedProjects"
          :key="project.id"
          :project="project"
          @click="enterProject(project)"
          @detail="viewProjectDetail"
          @continue="enterProject"
          @delete="handleDeleteProject"
        />
      </div>
    </section>

    <transition
      enter-active-class="transition-opacity duration-200"
      leave-active-class="transition-opacity duration-200"
      enter-from-class="opacity-0"
      leave-to-class="opacity-0"
    >
      <div v-if="showDeleteDialog" class="md-dialog-overlay">
        <transition
          enter-active-class="transition-opacity duration-200"
          leave-active-class="transition-opacity duration-200"
          enter-from-class="opacity-0 scale-95"
          leave-to-class="opacity-0 scale-95"
        >
          <div
            class="md-dialog max-w-md w-full mx-4"
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-project-title"
          >
            <div class="md-dialog-header flex items-center gap-4">
              <div
                class="w-12 h-12 rounded-full flex items-center justify-center"
                style="background-color: var(--md-error-container)"
              >
                <svg
                  class="w-6 h-6"
                  style="color: var(--md-error)"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                  />
                </svg>
              </div>
              <div>
                <h3 id="delete-project-title" class="md-dialog-title">确认删除</h3>
                <p class="md-body-small" style="color: var(--md-on-surface-variant)">
                  此操作无法撤销
                </p>
              </div>
            </div>

            <div class="md-dialog-content">
              <p class="md-body-large" style="color: var(--md-on-surface)">
                确定要删除项目 "<strong>{{ projectToDelete?.title }}</strong
                >" 吗？所有相关数据将被永久删除。
              </p>
            </div>

            <div class="md-dialog-actions">
              <button @click="cancelDelete" class="md-btn md-btn-text md-ripple">取消</button>
              <button
                @click="confirmDelete"
                :disabled="isDeleting"
                class="md-btn md-btn-filled md-ripple"
                style="background-color: var(--md-error); color: var(--md-on-error)"
              >
                <svg v-if="isDeleting" class="w-5 h-5 animate-spin" viewBox="0 0 24 24" fill="none">
                  <circle
                    class="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    stroke-width="4"
                  ></circle>
                  <path
                    class="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  ></path>
                </svg>
                {{ isDeleting ? '删除中...' : '确认删除' }}
              </button>
            </div>
          </div>
        </transition>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useNovelStore } from '@/stores/novel'
import { useAuthStore } from '@/stores/auth'
import ProjectCard from '@/components/ProjectCard.vue'
import type { NovelProjectSummary } from '@/api/novel'
import { NovelAPI } from '@/api/novel'

const router = useRouter()
const novelStore = useNovelStore()
const authStore = useAuthStore()

const fileInput = ref<HTMLInputElement | null>(null)
const isImporting = ref(false)

const showDeleteDialog = ref(false)
const projectToDelete = ref<NovelProjectSummary | null>(null)
const isDeleting = ref(false)
const workspaceMessage = ref<{ type: 'success' | 'error'; text: string } | null>(null)

let workspaceMessageTimer: number | undefined

const showWorkspaceMessage = (message: { type: 'success' | 'error'; text: string }) => {
  workspaceMessage.value = message
  window.clearTimeout(workspaceMessageTimer)
  workspaceMessageTimer = window.setTimeout(() => {
    workspaceMessage.value = null
  }, 3200)
}

// 最近编辑的项目作为工作台第一优先级，帮助作者快速恢复写作上下文。
const sortedProjects = computed(() => {
  return [...novelStore.projects].sort((left, right) => {
    return new Date(right.last_edited).getTime() - new Date(left.last_edited).getTime()
  })
})

const continueProject = computed(() => sortedProjects.value[0] ?? null)

const formatProjectDate = (value: string) => {
  if (!value) return '暂无更新时间'
  return new Date(value).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const goToInspiration = () => {
  router.push('/inspiration')
}

const viewProjectDetail = (projectId: string) => {
  router.push(`/projects/${projectId}`)
}

const enterProject = (project: NovelProjectSummary) => {
  if (project.title === '未命名灵感') {
    router.push(`/inspiration?project_id=${project.id}`)
  } else {
    router.push(`/projects/${project.id}/write`)
  }
}

const loadProjects = async () => {
  await novelStore.loadProjects()
}

const triggerImport = () => {
  if (isImporting.value) return
  fileInput.value?.click()
}

const handleFileImport = async (event: Event) => {
  const target = event.target as HTMLInputElement
  if (!target.files || target.files.length === 0) return

  const file = target.files[0]
  if (!file.name.endsWith('.txt')) {
    showWorkspaceMessage({ type: 'error', text: '请上传 .txt 格式的文件' })
    target.value = ''
    return
  }

  // 导入成功后直接进入写作台，避免作者再从列表中寻找新项目。
  isImporting.value = true
  try {
    const response = await NovelAPI.importNovel(file)
    await loadProjects()
    router.push(`/projects/${response.id}/write`)
  } catch (error: any) {
    showWorkspaceMessage({ type: 'error', text: error.message || '导入失败，请重试' })
  } finally {
    isImporting.value = false
    target.value = ''
  }
}

const handleDeleteProject = (projectId: string) => {
  const project = novelStore.projects.find((p) => p.id === projectId)
  if (project) {
    projectToDelete.value = project
    showDeleteDialog.value = true
  }
}

const cancelDelete = () => {
  showDeleteDialog.value = false
  projectToDelete.value = null
}

const confirmDelete = async () => {
  if (!projectToDelete.value) return

  isDeleting.value = true
  try {
    await novelStore.deleteProjects([projectToDelete.value.id])
    showWorkspaceMessage({
      type: 'success',
      text: `项目 "${projectToDelete.value.title}" 已成功删除`,
    })
    showDeleteDialog.value = false
    projectToDelete.value = null
  } catch (error) {
    console.error('删除项目失败:', error)
    showWorkspaceMessage({ type: 'error', text: '删除项目失败，请重试' })
  } finally {
    isDeleting.value = false
  }
}

onMounted(() => {
  loadProjects()
})

onUnmounted(() => {
  window.clearTimeout(workspaceMessageTimer)
})
</script>

<style scoped>
.workspace-page {
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-6);
}

.workspace-continue,
.workspace-panel,
.workspace-action {
  border: 1px solid var(--md-outline-variant);
  background-color: var(--md-surface);
  box-shadow: var(--md-elevation-1);
}

.workspace-continue {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--md-spacing-6);
  padding: clamp(var(--md-spacing-5), 4vw, var(--md-spacing-8));
  border-radius: var(--md-radius-xl);
}

.workspace-continue__copy {
  min-width: 0;
}

.workspace-kicker {
  margin: 0 0 6px;
  color: var(--md-primary-dark);
  font-size: var(--md-label-medium);
  font-weight: 600;
}

.workspace-continue h2,
.workspace-panel h2,
.workspace-state h3 {
  margin: 0;
  color: var(--md-on-surface);
  font-weight: 600;
}

.workspace-continue h2 {
  font-size: var(--md-headline-small);
  line-height: 1.25;
}

.workspace-continue p:last-child {
  margin: 8px 0 0;
  color: var(--md-on-surface-variant);
}

.workspace-continue__actions,
.workspace-actions {
  display: flex;
  align-items: center;
  gap: var(--md-spacing-3);
}

.workspace-actions {
  flex-wrap: wrap;
}

.workspace-action {
  min-height: 76px;
  flex: 1 1 240px;
  display: flex;
  align-items: center;
  gap: var(--md-spacing-3);
  padding: var(--md-spacing-4);
  border-radius: var(--md-radius-lg);
  color: var(--md-on-surface);
  text-align: left;
  text-decoration: none;
  transition:
    border-color var(--md-duration-short) var(--md-easing-standard),
    background-color var(--md-duration-short) var(--md-easing-standard);
}

.workspace-action:hover:not(:disabled) {
  border-color: var(--md-primary);
  background-color: var(--md-surface-container-low);
}

.workspace-action:disabled {
  opacity: 0.62;
  cursor: not-allowed;
}

.workspace-action__icon {
  width: 44px;
  height: 44px;
  display: grid;
  place-items: center;
  border-radius: var(--md-radius-md);
  background-color: var(--md-primary-container);
  color: var(--md-on-primary-container);
}

.workspace-action__icon svg {
  width: 22px;
  height: 22px;
}

.workspace-action strong,
.workspace-action small {
  display: block;
}

.workspace-action strong {
  font-size: var(--md-title-small);
}

.workspace-action small {
  margin-top: 2px;
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
}

.workspace-panel {
  padding: clamp(var(--md-spacing-5), 4vw, var(--md-spacing-8));
  border-radius: var(--md-radius-xl);
}

.workspace-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--md-spacing-4);
  margin-bottom: var(--md-spacing-6);
}

.workspace-panel h2 {
  font-size: var(--md-title-large);
}

.workspace-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--md-spacing-5);
}

.workspace-skeleton {
  min-height: 216px;
  padding: var(--md-spacing-5);
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-lg);
  background-color: var(--md-surface);
}

.workspace-skeleton__header {
  display: flex;
  gap: var(--md-spacing-3);
  margin-bottom: var(--md-spacing-6);
}

.workspace-skeleton__avatar,
.workspace-skeleton__lines span,
.workspace-skeleton__bar,
.workspace-skeleton__chips {
  display: block;
  border-radius: var(--md-radius-full);
  background: linear-gradient(
    90deg,
    var(--md-surface-container-low) 0%,
    var(--md-surface-container-high) 48%,
    var(--md-surface-container-low) 100%
  );
  background-size: 220% 100%;
  animation: workspace-skeleton-pulse 1.4s var(--md-easing-standard) infinite;
}

.workspace-skeleton__avatar {
  width: 48px;
  height: 48px;
  border-radius: var(--md-radius-full);
}

.workspace-skeleton__lines {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: var(--md-spacing-2);
  justify-content: center;
}

.workspace-skeleton__lines span:first-child {
  width: 72%;
  height: 18px;
}

.workspace-skeleton__lines span:last-child {
  width: 48%;
  height: 12px;
}

.workspace-skeleton__bar {
  width: 100%;
  height: 8px;
  margin-bottom: var(--md-spacing-5);
}

.workspace-skeleton__chips {
  width: 46%;
  height: 32px;
}

@keyframes workspace-skeleton-pulse {
  from {
    background-position: 100% 0;
  }

  to {
    background-position: -100% 0;
  }
}

.workspace-state {
  min-height: 260px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--md-spacing-4);
  text-align: center;
}

.workspace-state p {
  margin: 0;
  color: var(--md-on-surface-variant);
}

.workspace-state__icon {
  width: 64px;
  height: 64px;
  display: grid;
  place-items: center;
  border-radius: var(--md-radius-full);
  background-color: var(--md-primary-container);
  color: var(--md-on-primary-container);
}

.workspace-state__icon.is-error {
  background-color: var(--md-error-container);
  color: var(--md-error);
}

.workspace-state__icon svg {
  width: 32px;
  height: 32px;
}

@media (max-width: 720px) {
  .workspace-continue,
  .workspace-panel__header {
    align-items: stretch;
    flex-direction: column;
  }

  .workspace-continue__actions {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
