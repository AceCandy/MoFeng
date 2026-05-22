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
      :class="['workspace-hero', { 'workspace-hero--loading': projectsLoading }]"
      :aria-busy="projectsLoading"
      aria-label="今日创作总览"
    >
      <div class="workspace-hero__intro">
        <p class="workspace-eyebrow">今日创作</p>
        <template v-if="projectsLoading">
          <div class="workspace-hero__loading-block">
            <span class="workspace-hero__loading-line workspace-hero__loading-line--title"></span>
          </div>
          <div class="workspace-hero__loading-block workspace-hero__loading-block--summary">
            <span class="workspace-hero__loading-line workspace-hero__loading-line--summary"></span>
            <span
              class="workspace-hero__loading-line workspace-hero__loading-line--summary is-short"
            ></span>
          </div>
          <div class="workspace-hero__meta workspace-hero__loading-meta" aria-hidden="true">
            <span class="workspace-chip workspace-hero__loading-chip"></span>
            <span class="workspace-chip workspace-hero__loading-chip"></span>
          </div>
          <div class="workspace-hero__actions workspace-panel__actions workspace-hero__loading-actions" aria-hidden="true">
            <span class="workspace-hero__loading-line workspace-hero__loading-line--button"></span>
            <span
              class="workspace-hero__loading-line workspace-hero__loading-line--button is-secondary"
            ></span>
          </div>
        </template>
        <template v-else>
          <h2>{{ continueProject ? continueProject.title : '开始一段新的长篇创作' }}</h2>
          <p class="workspace-hero__summary">
            {{
              continueProject
                ? `继续推进《${continueProject.title}》，把设定、节奏和伏笔收束到同一条叙事线上。`
                : '你还没有创作中的项目，可以从灵感模式启动一个世界观草案。'
            }}
          </p>

          <div v-if="continueProject" class="workspace-hero__meta">
            <span class="workspace-chip">{{ continueProject.genre || '未设定题材' }}</span>
            <span class="workspace-chip">{{ continueProject.completed_chapters }}/{{ continueProject.total_chapters }} 章</span>
          </div>

          <div class="workspace-hero__actions workspace-panel__actions">
            <button
              v-if="continueProject"
              type="button"
              class="md-btn md-btn-filled md-ripple workspace-panel__action"
              @click="enterProject(continueProject)"
            >
              继续写作
            </button>
            <button
              type="button"
              class="md-btn md-btn-tonal md-ripple workspace-panel__action"
              @click="goToInspiration"
            >
              新建灵感项目
            </button>
          </div>
        </template>
      </div>

      <div class="workspace-hero__panel">
        <div class="workspace-hero__panel-head">
          <p>今日目标</p>
          <strong v-if="projectsLoading">
            <span class="workspace-hero__loading-line workspace-hero__loading-line--panel-title"></span>
          </strong>
          <strong v-else>{{ todayGoal.title }}</strong>
        </div>
        <p class="workspace-hero__goal-desc">
          <template v-if="projectsLoading">
            <span class="workspace-hero__loading-line workspace-hero__loading-line--goal"></span>
            <span
              class="workspace-hero__loading-line workspace-hero__loading-line--goal is-short"
            ></span>
          </template>
          <template v-else>{{ todayGoal.description }}</template>
        </p>
        <div class="workspace-hero__progress workspace-continue__progress">
          <div class="workspace-hero__progress-label">
            <span>项目推进度</span>
            <strong v-if="projectsLoading">
              <span class="workspace-hero__loading-line workspace-hero__loading-line--progress"></span>
            </strong>
            <strong v-else>{{ continueProgress }}%</strong>
          </div>
          <div
            class="md-progress-linear"
            role="progressbar"
            aria-label="最近项目进度"
            aria-valuemin="0"
            aria-valuemax="100"
            :aria-valuenow="continueProgress"
          >
            <div class="md-progress-linear-bar" :style="{ '--md-progress-scale': continueProgressScale }"></div>
          </div>
        </div>
        <div class="workspace-hero__snapshot" aria-label="创作快照">
          <template v-if="projectsLoading">
            <span class="workspace-hero__loading-line workspace-hero__loading-line--snapshot"></span>
            <span
              class="workspace-hero__loading-line workspace-hero__loading-line--snapshot is-short"
            ></span>
            <span
              class="workspace-hero__loading-line workspace-hero__loading-line--snapshot is-shorter"
            ></span>
          </template>
          <template v-else>
            <span>创作中 <strong>{{ sortedProjects.length }}</strong> 个项目</span>
            <span aria-hidden="true">·</span>
            <span>待推进 <strong>{{ pendingChapters }}</strong> 章</span>
            <span aria-hidden="true">·</span>
            <span>最近编辑 <strong>{{ recentEditedProjects.length }}</strong> 个项目</span>
          </template>
        </div>
      </div>
    </section>



    <section class="workspace-archive" aria-label="项目档案库">
      <div class="workspace-archive__head">
        <div>
          <p class="workspace-eyebrow">项目档案</p>
          <h3>小说项目库</h3>
        </div>
        <span class="workspace-chip">{{ sortedProjects.length }} 个项目</span>
      </div>

      <div
        v-if="projectsLoading"
        class="workspace-grid"
        role="status"
        aria-live="polite"
        aria-label="项目加载中"
      >
        <span class="sr-only">项目加载中</span>
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

      <div v-else-if="projectsError" class="workspace-state">
        <div class="workspace-state__icon is-error">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
        </div>
        <p class="md-body-large" style="color: var(--md-error)">{{ projectsError }}</p>
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
      <div v-if="showDeleteDialog" class="md-dialog-overlay" @click.self="cancelDelete">
        <transition
          enter-active-class="transition-opacity duration-200"
          leave-active-class="transition-opacity duration-200"
          enter-from-class="opacity-0 scale-95"
          leave-to-class="opacity-0 scale-95"
        >
          <div
            ref="deleteDialogRef"
            class="md-dialog max-w-md w-full mx-4"
            role="dialog"
            aria-modal="true"
            :aria-labelledby="deleteDialogTitleId"
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
                <h3 :id="deleteDialogTitleId" class="md-dialog-title">确认删除</h3>
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
              <button
                ref="cancelDeleteButtonRef"
                data-dialog-initial-focus
                @click="cancelDelete"
                class="md-btn md-btn-text md-ripple"
              >
                取消
              </button>
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
import { computed, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import ProjectCard from '@/components/ProjectCard.vue'
import type { NovelProjectSummary } from '@/api/novel'
import {
  useDeleteNovelsMutation,
  useImportNovelMutation,
  useNovelProjectsQuery,
} from '@/queries/novel'
import { useDialogA11y } from '@/composables/useDialogA11y'

const router = useRouter()
const projectsQuery = useNovelProjectsQuery()
const importNovelMutation = useImportNovelMutation()
const deleteNovelsMutation = useDeleteNovelsMutation()

const fileInput = ref<HTMLInputElement | null>(null)

const showDeleteDialog = ref(false)
const deleteDialogRef = ref<HTMLElement | null>(null)
const cancelDeleteButtonRef = ref<HTMLElement | null>(null)
const deleteDialogTitleId = 'workspace-delete-project-title'
const projectToDelete = ref<NovelProjectSummary | null>(null)
const workspaceMessage = ref<{ type: 'success' | 'error'; text: string } | null>(null)

let workspaceMessageTimer: number | undefined

const showWorkspaceMessage = (message: { type: 'success' | 'error'; text: string }) => {
  workspaceMessage.value = message
  window.clearTimeout(workspaceMessageTimer)
  workspaceMessageTimer = window.setTimeout(() => {
    workspaceMessage.value = null
  }, 3200)
}

const projects = computed(() => projectsQuery.data.value ?? [])
const projectsLoading = computed(() => projectsQuery.isPending.value)
const projectsError = computed(() => {
  const error = projectsQuery.error.value
  return error instanceof Error ? error.message : error ? '加载项目失败' : null
})
const isImporting = computed(() => importNovelMutation.isPending.value)
const isDeleting = computed(() => deleteNovelsMutation.isPending.value)

// 最近编辑的项目作为工作台第一优先级，帮助作者快速恢复写作上下文。
const sortedProjects = computed(() => {
  return [...projects.value].sort((left, right) => {
    return new Date(right.last_edited).getTime() - new Date(left.last_edited).getTime()
  })
})

const continueProject = computed(() => sortedProjects.value[0] ?? null)

const continueProgress = computed(() => {
  const project = continueProject.value
  if (!project || project.total_chapters <= 0) return 0

  return Math.round((project.completed_chapters / project.total_chapters) * 100)
})
const continueProgressScale = computed(() => Math.max(0, Math.min(100, continueProgress.value)) / 100)

const recentEditedProjects = computed(() => sortedProjects.value.slice(0, 5))

const pendingChapters = computed(() => {
  return sortedProjects.value.reduce((sum, project) => {
    const remaining = Math.max(project.total_chapters - project.completed_chapters, 0)
    return sum + remaining
  }, 0)
})

const todayGoal = computed(() => {
  if (!continueProject.value) {
    return {
      title: '建立小说蓝图',
      description: '先完成世界观、角色核心关系与章节骨架，再进入正文生成。',
    }
  }

  const remaining = Math.max(
    continueProject.value.total_chapters - continueProject.value.completed_chapters,
    0,
  )

  if (remaining === 0) {
    return {
      title: '进入收尾润色',
      description: '正文已齐备，建议逐章做节奏和伏笔回收检查。',
    }
  }

  return {
    title: '推进下一章初稿',
    description: `当前还剩 ${remaining} 章待完成，建议先推进最近卡住的一章。`,
  }
})

const aiSuggestions = computed(() => {
  const suggestions: Array<{
    title: string
    description: string
    tag: string
    tone: 'focus' | 'warning' | 'calm'
  }> = []

  if (continueProject.value) {
    if (continueProgress.value < 35) {
      suggestions.push({
        title: '补全章节骨架',
        description: '先确保前三章节奏递进清晰，再让 AI 生成正文会更稳定。',
        tag: '节奏偏慢',
        tone: 'warning',
      })
    } else {
      suggestions.push({
        title: '开始正文冲刺',
        description: '你的蓝图已具备连贯性，可以把 AI 主要用于出初稿与局部润色。',
        tag: '创作中',
        tone: 'focus',
      })
    }
  }

  suggestions.push({
    title: '检查伏笔回收路径',
    description: '在章节交界处补一轮伏笔追踪，避免后期出现剧情断层。',
    tag: '伏笔待回收',
    tone: 'calm',
  })

  suggestions.push({
    title: '做一次语气统一',
    description: '选两章相邻正文做风格比对，统一叙述视角与句式密度。',
    tag: '待润色',
    tone: 'focus',
  })

  return suggestions.slice(0, 3)
})

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
  router.push(`/projects/${projectId}/write`)
}

const enterProject = (project: NovelProjectSummary) => {
  if (project.title === '未命名灵感') {
    router.push(`/inspiration?project_id=${project.id}`)
  } else {
    router.push(`/projects/${project.id}/write`)
  }
}

const openProjectFromActivity = (project: NovelProjectSummary) => {
  enterProject(project)
}

const loadProjects = async () => {
  await projectsQuery.refetch()
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
  try {
    const response = await importNovelMutation.mutateAsync(file)
    router.push(`/projects/${response.id}/write`)
  } catch (error: any) {
    showWorkspaceMessage({ type: 'error', text: error.message || '导入失败，请重试' })
  } finally {
    target.value = ''
  }
}

const handleDeleteProject = (projectId: string) => {
  const project = projects.value.find((p) => p.id === projectId)
  if (project) {
    projectToDelete.value = project
    showDeleteDialog.value = true
  }
}

const cancelDelete = () => {
  showDeleteDialog.value = false
  projectToDelete.value = null
}

useDialogA11y({
  active: showDeleteDialog,
  dialogRef: deleteDialogRef,
  onClose: cancelDelete,
  initialFocusRef: cancelDeleteButtonRef,
})

const confirmDelete = async () => {
  if (!projectToDelete.value) return

  const deletingProject = projectToDelete.value
  try {
    await deleteNovelsMutation.mutateAsync([deletingProject.id])
    showWorkspaceMessage({
      type: 'success',
      text: `项目 "${deletingProject.title}" 已成功删除`,
    })
    showDeleteDialog.value = false
    projectToDelete.value = null
  } catch (error) {
    console.error('删除项目失败:', error)
    showWorkspaceMessage({ type: 'error', text: '删除项目失败，请重试' })
  }
}

onUnmounted(() => {
  window.clearTimeout(workspaceMessageTimer)
})
</script>

<style scoped>
.workspace-page {
  display: flex;
  flex-direction: column;
  gap: clamp(var(--md-spacing-6), 4vw, var(--md-spacing-10));
}

.workspace-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(320px, 0.8fr);
  gap: var(--md-spacing-5);
  padding: clamp(var(--md-spacing-5), 4vw, var(--md-spacing-8));
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-xl);
  background:
    linear-gradient(
      140deg,
      color-mix(in srgb, var(--md-surface) 92%, transparent),
      color-mix(in srgb, var(--md-primary-container) 32%, var(--md-surface-container-low))
    );
  box-shadow: var(--md-elevation-1);
}

.workspace-hero--loading .workspace-hero__intro,
.workspace-hero--loading .workspace-hero__panel {
  min-height: 244px;
}

.workspace-eyebrow {
  margin: 0;
  color: var(--md-primary);
  font-size: var(--md-label-medium);
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.workspace-hero h2 {
  margin: 10px 0 0;
  color: var(--md-on-surface);
  font-size: clamp(1.45rem, 2vw, 2rem);
  line-height: 1.35;
}

.workspace-hero__summary {
  margin: var(--md-spacing-3) 0 0;
  color: var(--md-on-surface-variant);
  line-height: 1.7;
  max-width: 64ch;
}

.workspace-hero__meta {
  margin-top: var(--md-spacing-4);
  display: flex;
  flex-wrap: wrap;
  gap: var(--md-spacing-2);
}

.workspace-chip {
  display: inline-flex;
  align-items: center;
  height: 30px;
  padding: 0 11px;
  border-radius: var(--md-radius-full);
  border: 1px solid var(--md-outline-variant);
  background-color: color-mix(in srgb, var(--md-surface-container-low) 70%, transparent);
  color: var(--md-on-surface-variant);
  font-size: var(--md-label-medium);
  font-weight: 600;
}

.workspace-hero__actions {
  margin-top: var(--md-spacing-5);
  display: flex;
  flex-wrap: wrap;
  gap: var(--md-spacing-3);
}

.workspace-hero__loading-block {
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-3);
}

.workspace-hero__loading-block--summary {
  margin-top: var(--md-spacing-3);
}

.workspace-hero__loading-meta {
  margin-top: var(--md-spacing-4);
}

.workspace-hero__loading-actions {
  margin-top: var(--md-spacing-5);
}

.workspace-hero__loading-chip {
  width: 92px;
  min-width: 92px;
  border-color: transparent;
  background-color: color-mix(in srgb, var(--md-surface-container-low) 82%, var(--md-outline-variant));
}

.workspace-hero__loading-chip:last-child {
  width: 112px;
  min-width: 112px;
}

.workspace-hero__loading-line {
  display: block;
  border-radius: var(--md-radius-full);
  background: linear-gradient(
    90deg,
    color-mix(in srgb, var(--md-surface-container-low) 88%, transparent) 0%,
    color-mix(in srgb, var(--md-surface-container-high) 96%, transparent) 48%,
    color-mix(in srgb, var(--md-surface-container-low) 88%, transparent) 100%
  );
  background-size: 220% 100%;
  animation: workspace-hero-loading-pulse 1.5s var(--md-easing-standard) infinite;
}

.workspace-hero__loading-line--title {
  width: min(18rem, 78%);
  height: 2.5rem;
}

.workspace-hero__loading-line--summary {
  width: min(30rem, 92%);
  height: 1rem;
}

.workspace-hero__loading-line--summary.is-short {
  width: min(21rem, 68%);
}

.workspace-hero__loading-line--button {
  width: 126px;
  height: 42px;
}

.workspace-hero__loading-line--button.is-secondary {
  width: 144px;
}

.workspace-hero__loading-line--panel-title {
  width: min(12rem, 72%);
  height: 1.5rem;
}

.workspace-hero__loading-line--goal {
  width: 100%;
  height: 1rem;
}

.workspace-hero__loading-line--goal.is-short {
  width: 76%;
}

.workspace-hero__loading-line--progress {
  width: 3.2rem;
  height: 1rem;
}

.workspace-hero__loading-line--snapshot {
  width: min(18rem, 100%);
  height: 2rem;
}

.workspace-hero__loading-line--snapshot.is-short {
  width: min(14rem, 86%);
}

.workspace-hero__loading-line--snapshot.is-shorter {
  width: min(11rem, 72%);
}

@keyframes workspace-hero-loading-pulse {
  from {
    background-position: 100% 0;
  }

  to {
    background-position: -100% 0;
  }
}

.workspace-panel__action:focus-visible {
  outline: 2px solid var(--md-primary);
  outline-offset: 2px;
}

.workspace-hero__panel {
  border: 1px solid color-mix(in srgb, var(--md-primary) 20%, var(--md-outline-variant));
  border-radius: var(--md-radius-lg);
  background: color-mix(in srgb, var(--md-surface) 92%, transparent);
  padding: var(--md-spacing-5);
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-4);
}

.workspace-hero__panel-head {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.workspace-hero__panel-head p {
  margin: 0;
  color: var(--md-on-surface-variant);
  font-size: var(--md-label-medium);
}

.workspace-hero__panel-head strong {
  color: var(--md-on-surface);
  font-size: var(--md-title-large);
}

.workspace-hero__goal-desc {
  margin: 0;
  color: var(--md-on-surface-variant);
  line-height: 1.6;
}

.workspace-hero__progress-label {
  margin-bottom: var(--md-spacing-2);
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: var(--md-on-surface-variant);
  font-size: var(--md-label-medium);
}

.workspace-hero__progress-label strong {
  color: var(--md-on-surface);
}

.workspace-hero__snapshot {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--md-spacing-2);
  padding: var(--md-spacing-3);
  border-radius: var(--md-radius-md);
  border: 1px dashed color-mix(in srgb, var(--md-primary) 28%, var(--md-outline-variant));
  background-color: color-mix(in srgb, var(--md-surface-container-low) 86%, var(--md-tint-cool));
  color: var(--md-on-surface-variant);
  font-size: var(--md-label-medium);
  line-height: 1.5;
}

.workspace-hero__snapshot strong {
  color: var(--md-on-surface);
  font-size: var(--md-title-small);
}

.workspace-canvas {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--md-spacing-4);
}

.workspace-module,
.workspace-archive {
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-lg);
  background-color: color-mix(in srgb, var(--md-surface) 95%, transparent);
}

.workspace-module {
  padding: var(--md-spacing-5);
}

.workspace-module--tools {
  grid-column: span 2;
}

.workspace-module__head h3 {
  margin: 0;
  color: var(--md-on-surface);
  font-size: var(--md-title-large);
}

.workspace-module__head p {
  margin: 8px 0 0;
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
}

.workspace-activity {
  list-style: none;
  margin: var(--md-spacing-4) 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-2);
}

.workspace-activity__item {
  width: 100%;
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-md);
  background-color: var(--md-surface-container-low);
  padding: var(--md-spacing-3);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--md-spacing-3);
  text-align: left;
  cursor: pointer;
}

.workspace-activity__item:hover {
  border-color: color-mix(in srgb, var(--md-primary) 28%, var(--md-outline-variant));
}

.workspace-activity__item strong,
.workspace-activity__item span,
.workspace-activity__item em {
  display: block;
}

.workspace-activity__item strong {
  color: var(--md-on-surface);
  font-size: var(--md-label-large);
  font-style: normal;
}

.workspace-activity__item span {
  margin-top: 3px;
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
}

.workspace-activity__item em {
  color: var(--md-on-surface-variant);
  font-size: var(--md-label-small);
  font-style: normal;
  white-space: nowrap;
}

.workspace-ai-list {
  list-style: none;
  margin: var(--md-spacing-3) 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-3);
}

.workspace-insights[open] {
  display: block;
}

.workspace-insights__summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--md-spacing-2);
  min-height: 44px;
  padding: var(--md-spacing-2) 0;
  cursor: pointer;
  list-style: none;
  color: var(--md-on-surface);
  font-size: var(--md-title-medium);
  font-weight: 600;
  transition:
    color var(--md-duration-short) var(--md-easing-standard),
    opacity var(--md-duration-short) var(--md-easing-standard);
}

.workspace-insights__summary::-webkit-details-marker {
  display: none;
}

.workspace-insights__summary::after {
  content: '';
  width: 9px;
  height: 9px;
  border-right: 1.5px solid currentColor;
  border-bottom: 1.5px solid currentColor;
  transform: rotate(45deg);
  transform-origin: center;
  transition: transform var(--md-duration-short) var(--md-easing-standard);
}

.workspace-insights[open] .workspace-insights__summary::after {
  transform: rotate(-135deg) translate(-1px, -1px);
}

.workspace-insights__summary:hover {
  color: var(--md-primary-dark);
}

.workspace-insights__summary:active {
  opacity: 0.78;
}

.workspace-insights__summary:focus-visible {
  outline: 2px solid var(--md-primary);
  outline-offset: 2px;
  border-radius: var(--md-radius-xs);
}

.workspace-insights__summary em {
  color: var(--md-on-surface-variant);
  font-size: var(--md-label-medium);
  font-style: normal;
  font-weight: 500;
}

.workspace-insights[open] .workspace-ai-list {
  padding-top: var(--md-spacing-3);
  border-top: 1px solid var(--md-outline-variant);
}

.workspace-ai-list li {
  padding: var(--md-spacing-3);
  border-radius: var(--md-radius-md);
  border: 1px solid var(--md-outline-variant);
  background-color: var(--md-surface-container-low);
}

.workspace-ai-list__title {
  margin: 0;
  color: var(--md-on-surface);
  font-weight: 600;
}

.workspace-ai-list__desc {
  margin: 6px 0 0;
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
  line-height: 1.6;
}

.workspace-ai-list__tag {
  margin-top: var(--md-spacing-2);
  display: inline-flex;
  align-items: center;
  height: 26px;
  padding: 0 10px;
  border-radius: var(--md-radius-full);
  font-size: var(--md-label-small);
  font-weight: 600;
}

.workspace-ai-list__tag.is-focus {
  background-color: var(--md-primary-container);
  color: var(--md-on-primary-container);
}

.workspace-ai-list__tag.is-warning {
  background-color: var(--md-warning-container);
  color: var(--md-on-warning-container);
}

.workspace-ai-list__tag.is-calm {
  background-color: var(--md-success-container);
  color: var(--md-on-success-container);
}

.workspace-tools {
  margin-top: var(--md-spacing-4);
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-3);
}

.workspace-empty-hint {
  margin: var(--md-spacing-5) 0 0;
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
}

.workspace-archive {
  padding: clamp(var(--md-spacing-5), 4vw, var(--md-spacing-8));
}

.workspace-archive__head {
  margin-bottom: var(--md-spacing-5);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--md-spacing-3);
}

.workspace-archive__head h3,
.workspace-state h3 {
  margin: 8px 0 0;
  color: var(--md-on-surface);
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

@media (max-width: 960px) {
  .workspace-hero {
    grid-template-columns: minmax(0, 1fr);
    gap: var(--md-spacing-5);
  }
}

@media (max-width: 833px) {
  .workspace-page {
    gap: var(--md-spacing-5);
  }

  .workspace-hero--loading .workspace-hero__intro,
  .workspace-hero--loading .workspace-hero__panel {
    min-height: 212px;
  }

  .workspace-hero,
  .workspace-archive {
    padding: var(--md-spacing-5);
    border-radius: var(--md-radius-lg);
  }

  .workspace-hero__snapshot {
    font-size: var(--md-label-small);
  }
}

@media (max-width: 600px) {
  .workspace-page {
    gap: var(--md-spacing-4);
  }

  .workspace-hero,
  .workspace-archive {
    padding: var(--md-spacing-4);
  }

  .workspace-grid {
    grid-template-columns: minmax(0, 1fr);
    gap: var(--md-spacing-4);
  }

  .workspace-hero__snapshot {
    flex-direction: column;
    align-items: flex-start;
    gap: var(--md-spacing-2);
    padding: var(--md-spacing-4);
  }

  .workspace-hero__snapshot [aria-hidden="true"] {
    display: none;
  }

  .workspace-hero__snapshot span:not([aria-hidden="true"]) {
    display: flex;
    align-items: center;
    width: 100%;
    justify-content: space-between;
    padding-bottom: var(--md-spacing-2);
    border-bottom: 1px dashed color-mix(in srgb, var(--md-primary) 12%, var(--md-outline-variant));
  }

  .workspace-hero__snapshot span:not([aria-hidden="true"]):last-child {
    border-bottom: none;
    padding-bottom: 0;
  }

  .workspace-hero__panel {
    padding: var(--md-spacing-4);
  }
}

@media (max-width: 480px) {
  .workspace-hero__actions .md-btn {
    flex: 1 1 100%;
  }
}

@media (prefers-reduced-motion: reduce) {
  .workspace-hero__loading-line,
  .workspace-skeleton__avatar,
  .workspace-skeleton__lines span,
  .workspace-skeleton__bar,
  .workspace-skeleton__chips {
    animation: none;
    background-position: 0 0;
  }
}
</style>
