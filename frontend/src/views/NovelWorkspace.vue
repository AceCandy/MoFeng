<!-- AIMETA P=小说工作区_小说列表管理|R=小说列表_创建|NR=不含章节编辑|E=route:/workspace#component:NovelWorkspace|X=ui|A=工作区|D=vue|S=dom,net|RD=./README.ai -->
<template>
  <div class="app-page workspace-page">
    <transition name="ink-fade">
      <div v-if="workspaceMessage" class="md-snackbar" role="status">
        <svg
          v-if="workspaceMessage.type === 'success'"
          class="w-5 h-5 snackbar-success-icon"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
        >
          <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
        </svg>
        <svg
          v-else
          class="w-5 h-5 snackbar-error-icon"
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
      <!-- 墨碑底纹：夜色里的巨型低透明排印（当前书名首字，无项目落「墨」），右下出血裁切，纯装饰 -->
      <div class="workspace-hero__backdrop" aria-hidden="true">
        <span class="workspace-hero__monolith">{{ heroMonolithChar }}</span>
      </div>
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
          <div class="workspace-hero__title-row">
            <h2>{{ continueProject ? continueProject.title : '开始一段新的长篇创作' }}</h2>
            <!-- 空状态引首章：灯下米字格衬底 + 夜色钤印「著」字，只作卷首留白装饰 -->
            <span v-if="!continueProject" class="workspace-hero__empty-seal" aria-hidden="true">著</span>
          </div>
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
              class="md-btn md-btn-primary md-ripple workspace-panel__action"
              @click="enterProject(continueProject)"
            >
              {{ projectEntryLabel(continueProject) }}
            </button>
            <button
              type="button"
              class="md-btn md-btn-primary md-ripple workspace-panel__action"
              @click="goToInspiration"
            >
              新建灵感项目
            </button>
          </div>
        </template>
      </div>

      <div class="workspace-hero__panel">
        <div class="workspace-hero__panel-head">
          <p class="workspace-hero__goal-tag">今日目标</p>
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
      </div>

      <!-- 墨进度：通栏夜色发线轨道，灯下走墨填充，条头缀朱砂方印点 -->
      <div class="workspace-hero__progress workspace-continue__progress">
        <div class="workspace-hero__progress-label">
          <span>墨进度</span>
          <strong v-if="projectsLoading">
            <span class="workspace-hero__loading-line workspace-hero__loading-line--progress"></span>
          </strong>
          <strong v-else>
            {{ continueProgress }}%
            <span v-if="continueProject" class="workspace-hero__progress-chapters">
              {{ continueProject.completed_chapters }}/{{ continueProject.total_chapters }} 章
            </span>
          </strong>
        </div>
        <div
          class="md-progress-linear"
          role="progressbar"
          aria-label="最近项目进度"
          aria-valuemin="0"
          aria-valuemax="100"
          :aria-valuenow="continueProgress"
          :style="{ '--md-progress-scale': continueProgressScale }"
        >
          <div class="md-progress-linear-bar"></div>
          <span
            v-if="continueProgressScale > 0"
            class="workspace-hero__progress-seal"
            aria-hidden="true"
          ></span>
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
        <p class="md-body-large state-error-text">{{ projectsError }}</p>
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
        <button @click="goToInspiration" class="md-btn md-btn-primary md-ripple">开始新灵感</button>
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

    <transition name="md-dialog-overlay">
      <div v-if="showDeleteDialog" class="md-dialog-overlay" @click.self="cancelDelete">
          <div
            ref="deleteDialogRef"
            class="md-dialog max-w-md w-full mx-4"
            role="dialog"
            aria-modal="true"
            :aria-labelledby="deleteDialogTitleId"
          >
            <div class="md-dialog-header flex items-center gap-4">
              <div class="w-12 h-12 flex items-center justify-center delete-alert-icon-container">
                <svg
                  class="w-6 h-6 delete-alert-icon"
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
                <p class="md-body-small delete-dialog-subtitle">
                  此操作无法撤销
                </p>
              </div>
            </div>

            <div class="md-dialog-content">
              <p class="md-body-large delete-dialog-content-text">
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
                class="md-btn md-btn-filled md-ripple delete-confirm-btn"
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
  useNovelProjectsQuery,
} from '@/queries/novel'
import { useDialogA11y } from '@/composables/useDialogA11y'

const router = useRouter()
const projectsQuery = useNovelProjectsQuery()
const deleteNovelsMutation = useDeleteNovelsMutation()

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
const isDeleting = computed(() => deleteNovelsMutation.isPending.value)

// 最近编辑的项目作为工作台第一优先级，帮助作者快速恢复写作上下文。
const sortedProjects = computed(() => {
  return [...projects.value].sort((left, right) => {
    return new Date(right.last_edited).getTime() - new Date(left.last_edited).getTime()
  })
})

const continueProject = computed(() => sortedProjects.value[0] ?? null)

// 墨碑底纹取当前书名首字，无项目时落「墨」字，纯装饰不参与数据流。
const heroMonolithChar = computed(() => {
  const title = continueProject.value?.title?.trim()
  return title ? title.charAt(0) : '墨'
})

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

  // 章节骨架尚未建立（0/0 章）的项目不能落入“收尾润色”分支
  if (continueProject.value.total_chapters <= 0) {
    return {
      title: '建立小说蓝图',
      description: '先完成世界观、角色核心关系与章节骨架，再进入正文生成。',
    }
  }

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

const goToInspiration = () => {
  router.push('/inspiration')
}

const viewProjectDetail = (projectId: string) => {
  router.push(`/projects/${projectId}/write`)
}

const isInspirationProject = (project: NovelProjectSummary) => project.title === '未命名灵感'
const projectEntryLabel = (project: NovelProjectSummary) =>
  isInspirationProject(project) ? '继续灵感对话' : '继续写作'

const enterProject = (project: NovelProjectSummary) => {
  if (isInspirationProject(project)) {
    router.push(`/inspiration?project_id=${project.id}`)
  } else {
    router.push(`/projects/${project.id}/write`)
  }
}

const loadProjects = async () => {
  await projectsQuery.refetch()
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

/* 夜色长卷：夜案深底 + 书名区后方暖灯光晕 + 四缘向夜深处压暗，多层 background 一次绘成；行线不长在夜色里。
   构图：底缘下方预留落款签骑缝位（padding-bottom 加破带量，margin-bottom 预留签条下半身的落纸空间） */
.workspace-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(320px, 0.8fr);
  gap: var(--md-spacing-5) var(--md-spacing-8);
  padding: clamp(var(--md-spacing-6), 3vw, var(--md-spacing-8)) clamp(var(--md-spacing-8), 5vw, var(--md-spacing-10)); /* 左右 ≥32px，案头内缩留白 */
  padding-bottom: calc(clamp(var(--md-spacing-6), 3vw, var(--md-spacing-8)) + 40px); /* 夜色带底缘内让出骑缝签条上半身 */
  margin-bottom: 32px; /* 签条破带下半身落纸的预留空位，防压档案区 */
  border-radius: var(--md-radius-xs) !important; /* 微直角方章 */
  background:
    /* 书名区后方一团暖灯晕（暖纸色径向光，大面积低透明） */
    radial-gradient(58% 82% at 24% 30%, var(--md-night-glow-warm), transparent 70%),
    /* 四周边缘向夜深处压暗 */
    radial-gradient(125% 155% at 50% 42%, var(--md-night-bg) 52%, var(--md-night-bg-deep) 100%);
  background-color: var(--md-night-bg);
  box-shadow: var(--md-night-elevation-1); /* 夜案纯黑深影，长卷浮于案上（影边二选一，取影） */
  position: relative;
}

/* 墨碑衬底层：只负责出血裁切，hero 本体保持 overflow 可见以放行破带签条 */
.workspace-hero__backdrop {
  position: absolute;
  inset: 0;
  border-radius: inherit;
  overflow: hidden;
  pointer-events: none;
  user-select: none;
}

/* 墨碑：真实字符排印，夜色暖纸白 6% 透明度，右下出血裁切，压在最底不抢字 */
.workspace-hero__monolith {
  position: absolute;
  right: -0.16em;
  bottom: -0.3em;
  color: color-mix(in srgb, var(--md-night-on) 6%, transparent);
  font-family: var(--md-font-display);
  font-size: clamp(160px, 22vw, 300px);
  font-weight: 600;
  line-height: 1;
  letter-spacing: 0;
  white-space: nowrap;
}

.workspace-hero--loading .workspace-hero__intro {
  min-height: 244px;
}

.workspace-hero--loading .workspace-hero__panel {
  min-height: 160px; /* 课签骨架小于旧面板，按新体量稳定占位 */
}

/* 题签：宋体小签，不用 eyebrow 式 uppercase 小字眉（夜色里压为暖纸辅文色） */
.workspace-eyebrow {
  margin: 0;
  color: var(--md-on-surface-variant);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
}

.workspace-hero .workspace-eyebrow {
  color: var(--md-night-on-variant);
}

.workspace-hero__title-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--md-spacing-4);
}

/* 书名破顶展示级：clamp(44px, 6.5vw, 88px)，夜色暖纸白，追踪微收，灯下碑拓骨力 */
.workspace-hero h2 {
  margin: var(--md-spacing-2) 0 0;
  min-width: 0;
  color: var(--md-night-on);
  font-size: clamp(44px, 6.5vw, 88px);
  font-weight: 600;
  line-height: 1.18;
  letter-spacing: -0.02em;
}

/* 空状态引首章：放大一格成为空态主角——灯下米字格 + 夜色钤印「著」字，只作卷首留白装饰 */
.workspace-hero__empty-seal {
  flex: none;
  display: grid;
  place-items: center;
  width: clamp(104px, 12vw, 148px);
  aspect-ratio: 1;
  border: 1px solid var(--md-night-outline);
  border-radius: var(--md-radius-xs); /* 微直角方章 */
  background-image:
    linear-gradient(to right, transparent calc(50% - 0.5px), var(--md-night-outline) calc(50% - 0.5px), var(--md-night-outline) calc(50% + 0.5px), transparent calc(50% + 0.5px)),
    linear-gradient(to bottom, transparent calc(50% - 0.5px), var(--md-night-outline) calc(50% - 0.5px), var(--md-night-outline) calc(50% + 0.5px), transparent calc(50% + 0.5px)),
    linear-gradient(to top right, transparent calc(50% - 0.5px), var(--md-night-outline) calc(50% - 0.5px), var(--md-night-outline) calc(50% + 0.5px), transparent calc(50% + 0.5px)),
    linear-gradient(to top left, transparent calc(50% - 0.5px), var(--md-night-outline) calc(50% - 0.5px), var(--md-night-outline) calc(50% + 0.5px), transparent calc(50% + 0.5px)),
    /* 字后一团朱砂微光，灯下印色不闷 */
    radial-gradient(circle at 50% 50%, var(--md-night-glow-seal), transparent 72%);
  color: var(--md-night-seal); /* 夜色钤印，待作家落墨覆写 */
  font-family: var(--md-font-kai); /* 楷体只给描红 */
  font-size: clamp(48px, 5.6vw, 68px);
  line-height: 1;
  box-shadow: none; /* 印不浮 */
  user-select: none;
}

.workspace-hero__summary {
  margin: var(--md-spacing-3) 0 0;
  color: var(--md-night-on-variant);
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
  border-radius: var(--md-radius-xs);
  border: 1px solid var(--md-outline-variant);
  background-color: color-mix(in srgb, var(--md-surface-container-low) 70%, transparent);
  color: var(--md-on-surface-variant);
  font-size: var(--md-label-medium);
  font-weight: 600;
}

/* 夜色里的元信息签：夜色浮层底 + 夜色发线边 */
.workspace-hero .workspace-chip {
  border-color: var(--md-night-outline);
  background-color: var(--md-night-surface);
  color: var(--md-night-on-variant);
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

/* 内容层压过墨碑衬底 */
.workspace-hero__intro {
  position: relative;
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

/* 夜色骨架签：夜色上浮层，不带边线（须后于 chip 夜色覆写出场） */
.workspace-hero .workspace-hero__loading-chip {
  width: 92px;
  min-width: 92px;
  border-color: transparent;
  background-color: var(--md-night-surface-high);
}

.workspace-hero .workspace-hero__loading-chip:last-child {
  width: 112px;
  min-width: 112px;
}

.workspace-hero__loading-line {
  display: block;
  border-radius: var(--md-radius-xs) !important; /* 纸条微直角 */
  background: var(--md-night-surface-high) !important; /* 夜色上浮层，暗骨架呼吸 */
  animation: ink-skeleton-breath 2.2s cubic-bezier(0.22, 1, 0.36, 1) infinite !important;
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

@keyframes ink-skeleton-breath {
  0%, 100% {
    opacity: 0.38;
  }
  50% {
    opacity: 0.85;
  }
}

.workspace-panel__action:focus-visible {
  outline: 2px solid var(--md-night-on);
  outline-offset: 2px;
}

/* 课签：夜色浮层 + dashed 夜色强发线边，压案不浮；微斜半度并右探贴住夜色带右缘，如随手别上的手作签 */
.workspace-hero__panel {
  grid-column: 2;
  grid-row: 1;
  align-self: start;
  position: relative; /* 压过墨碑衬底 */
  margin-right: -10px; /* 右探咬住夜色带右缘（右 padding ≥32px 吸收，不出血） */
  transform: rotate(-0.8deg); /* 手作微斜，静定不晃 */
  border: 1px dashed var(--md-night-outline-strong);
  border-radius: var(--md-radius-xs) !important; /* 微直角方章 */
  background-color: var(--md-night-surface); /* 夜色浮层 */
  padding: var(--md-spacing-5);
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-4);
  box-shadow: none; /* 课签压案不浮 */
}

.workspace-hero__panel-head {
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-2);
}

/* 「今日目标」夜色小签：朱砂微光 wash 底 + 夜色钤印字，12px/600、字距 0.3em */
.workspace-hero__goal-tag {
  margin: 0;
  align-self: flex-start;
  padding: 4px 10px;
  border-radius: var(--md-radius-xs);
  background-color: var(--md-night-glow-seal);
  color: var(--md-night-on);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.3em;
}

.workspace-hero__panel-head strong {
  color: var(--md-night-on);
  font-size: var(--md-title-large);
}

.workspace-hero__goal-desc {
  margin: 0;
  color: var(--md-night-on-variant);
  line-height: 1.6;
}

/* 墨进度：通栏灯下行墨，横贯夜色带底部；压过墨碑衬底 */
.workspace-hero__progress {
  grid-column: 1 / -1;
  position: relative;
}

.workspace-hero__progress-label {
  margin-bottom: var(--md-spacing-2);
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--md-spacing-3);
  color: var(--md-night-on-variant);
  font-size: var(--md-label-medium);
}

/* 百分比升展示级字级落在夜端，章数保持辅文 */
.workspace-hero__progress-label strong {
  color: var(--md-night-on);
  font-size: clamp(24px, 2.6vw, 34px);
  font-weight: 600;
  letter-spacing: 0.02em;
  line-height: 1.2;
}

.workspace-hero__progress-chapters {
  margin-left: var(--md-spacing-2);
  font-size: var(--md-label-medium);
  font-weight: 400;
  color: var(--md-night-on-variant);
}

/* 通栏夜色发线轨道，灯下行墨填充，条头带暖光 */
.workspace-hero .md-progress-linear {
  height: 3px;
  background-color: var(--md-night-outline);
  border-radius: 0; /* 发线轨道不收圆 */
  overflow: visible; /* 让条头朱砂印点得以压线而立 */
  position: relative;
}

.workspace-hero .md-progress-linear-bar {
  background-color: var(--md-night-on); /* 灯下走墨，不借石青 */
  border-radius: 0;
  box-shadow: 0 0 8px color-mix(in srgb, var(--md-night-on) 22%, transparent); /* 灯下微光，静定 */
}

/* 数据就绪后只出场一次：填充条自左铺墨 1.2s */
.workspace-hero:not(.workspace-hero--loading) .md-progress-linear-bar {
  animation: workspace-hero-ink-progress 1.2s cubic-bezier(0.22, 1, 0.36, 1) both;
}

@keyframes workspace-hero-ink-progress {
  from {
    transform: scaleX(0);
  }
  to {
    transform: scaleX(var(--md-progress-scale, 0));
  }
}

/* 条头朱砂方印点：12px 微直角，缀一枚静态微光，随铺墨同步到位 */
.workspace-hero__progress-seal {
  position: absolute;
  top: 50%;
  left: calc(var(--md-progress-scale, 0) * 100%);
  width: 12px;
  height: 12px;
  margin: -6px 0 0 -6px; /* 以条头为中心钤下 */
  border-radius: var(--md-radius-xs);
  background-color: var(--md-night-seal); /* 夜色钤印 */
  box-shadow:
    0 0 0 3px var(--md-night-glow-seal), /* 印周薄晕 */
    0 0 8px color-mix(in srgb, var(--md-night-seal) 45%, transparent); /* 灯下微光，≤8px 弥散 */
}

.workspace-hero:not(.workspace-hero--loading) .workspace-hero__progress-seal {
  animation: workspace-hero-ink-seal 1.2s cubic-bezier(0.22, 1, 0.36, 1) both;
}

@keyframes workspace-hero-ink-seal {
  from {
    left: 0;
  }
  to {
    left: calc(var(--md-progress-scale, 0) * 100%);
  }
}

/* 创作快照 = 破带者：一枚纸色落款签条骑跨夜色带底缘，上半身压夜色、下半身落纸，
   缝合夜色长卷与下方纸色档案区；签面纸色世界，文字回落墨/辅文色 */
.workspace-hero__snapshot {
  position: absolute;
  left: clamp(var(--md-spacing-8), 5vw, var(--md-spacing-10)); /* 与 hero 横 padding 对齐 */
  right: clamp(var(--md-spacing-8), 5vw, var(--md-spacing-10));
  bottom: 0;
  transform: translateY(50%); /* 骑缝：一半压夜色带，一半破出落纸 */
  z-index: 1;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--md-spacing-2);
  padding: 10px var(--md-spacing-4);
  border: 1px solid var(--md-jiege); /* 界格发线 */
  border-radius: var(--md-radius-xs);
  background-color: var(--md-surface); /* 熟宣签面 */
  box-shadow: var(--md-elevation-paper-1); /* 熟宣柔影 */
  color: var(--md-on-surface-variant);
  font-size: var(--md-label-medium);
  line-height: 1.5;
}

/* 骑缝签上的数字用落墨色：破带处在纸底上必须可读 */
.workspace-hero__snapshot strong {
  color: var(--md-luomo);
  font-size: var(--md-title-small);
}

/* 破带签落在纸世界，内部骨架条跟随纸面灰 */
.workspace-hero .workspace-hero__snapshot .workspace-hero__loading-line {
  background: var(--md-surface-container-high) !important;
}

.workspace-archive {
  border: 1px solid var(--md-jiege); /* 界格发线 */
  border-radius: var(--md-radius-xs) !important; /* 微直角方章 */
  background-color: var(--md-surface); /* 熟宣 */
  box-shadow: var(--md-elevation-paper-1); /* 熟宣柔影 */
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
  letter-spacing: 0.03em;
}

.workspace-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: var(--md-spacing-5);
}

.workspace-skeleton {
  min-height: 216px;
  padding: var(--md-spacing-5);
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-xs) !important; /* 骨架屏同为微直角 */
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
  border-radius: var(--md-radius-xs) !important; /* 骨架屏直角化 */
  background: var(--md-surface-container-high) !important; /* 稳定的淡墨色 */
  animation: ink-skeleton-breath 2.2s cubic-bezier(0.22, 1, 0.36, 1) infinite !important;
}

.workspace-skeleton__avatar {
  width: 48px;
  height: 48px;
  border-radius: var(--md-radius-xs) !important; /* 头像骨架重塑为篆刻方印 */
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

/* 已统一使用国风水墨洇湿脉冲动画 workspace-ink-pulse */

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
  border-radius: var(--md-radius-xs); /* 方形印鉴造型 */
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
  /* 长卷收为单列：课签回落通栏不再右探，墨进度通栏，破带签仍骑底缘 */
  .workspace-hero {
    grid-template-columns: minmax(0, 1fr);
    gap: var(--md-spacing-5);
  }

  .workspace-hero__panel {
    grid-column: 1 / -1;
    grid-row: auto;
    margin-right: 0;
  }
}

@media (max-width: 833px) {
  .workspace-page {
    gap: var(--md-spacing-5);
  }

  .workspace-hero--loading .workspace-hero__intro {
    min-height: 212px;
  }

  .workspace-hero--loading .workspace-hero__panel {
    min-height: 140px;
  }

  .workspace-hero,
  .workspace-archive {
    padding: var(--md-spacing-5);
    border-radius: var(--md-radius-xs) !important; /* 微直角方章 */
  }

  /* 破带预留随内缩 padding 重落 */
  .workspace-hero {
    padding-bottom: calc(var(--md-spacing-5) + 40px);
  }

  .workspace-hero__snapshot {
    left: var(--md-spacing-5);
    right: var(--md-spacing-5);
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

  /* 390px：破带成立但签条改竖排三行，破带预留加深 */
  .workspace-hero {
    padding-bottom: calc(var(--md-spacing-4) + 56px);
    margin-bottom: 56px;
  }

  .workspace-grid {
    grid-template-columns: minmax(0, 1fr);
    gap: var(--md-spacing-4);
  }

  .workspace-hero__snapshot {
    left: var(--md-spacing-4);
    right: var(--md-spacing-4);
    flex-direction: column;
    align-items: flex-start;
    gap: var(--md-spacing-2);
    padding: 10px var(--md-spacing-3);
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
    border-bottom: 1px dashed var(--md-jiege); /* 纸签各行以界格发线相隔 */
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
  .workspace-skeleton__chips,
  .workspace-hero .md-progress-linear-bar,
  .workspace-hero__progress-seal {
    animation: none; /* 铺墨与钤印直落终态 */
    background-position: 0 0;
  }
}

.snackbar-success-icon {
  color: var(--md-success);
}

.snackbar-error-icon {
  color: var(--md-error);
}

.state-error-text {
  color: var(--md-error);
}

.delete-alert-icon-container {
  border-radius: var(--md-radius-xs) !important; /* 方直印鉴 */
  border: 1px solid var(--md-error) !important; /* 丹砂警示细边 */
  background-color: var(--md-error-container) !important;
}

.delete-alert-icon {
  color: var(--md-error);
}

.delete-dialog-subtitle {
  color: var(--md-error-text);
}

.delete-dialog-content-text strong {
  color: var(--md-error-text);
}

.delete-confirm-btn {
  background-color: var(--md-error) !important; /* 丹砂警示底 */
  color: var(--md-on-error) !important; /* 高对比宣白字 */
  border: 1px solid var(--md-error-strong) !important;
  box-shadow: none !important; /* 静息无影 */
  transition:
    background-color var(--md-duration-short) var(--md-easing-standard),
    box-shadow var(--md-duration-short) var(--md-easing-standard),
    color var(--md-duration-short) var(--md-easing-standard),
    transform var(--md-duration-short) var(--md-easing-standard);
}

.delete-confirm-btn:hover {
  background-color: var(--md-error-strong) !important; /* 丹砂加深 */
  color: var(--md-on-error) !important;
  box-shadow: var(--md-elevation-paper-1) !important; /* 纸影微浮 */
}

.delete-confirm-btn:active {
  transform: translate(1px, 1px); /* 钤印按压微沉 */
  box-shadow: none !important;
}

/* 删除确认对话框：双线框 + 熟宣柔影（弹层 paper-2） */
.md-dialog {
  border: 3px double var(--md-outline) !important;
  border-radius: var(--md-radius-xs) !important; /* 微直角方章 */
  background-color: var(--md-surface-bright) !important; /* 熟宣竹纸 */
  box-shadow: var(--md-elevation-paper-2) !important;
}

.md-dialog-overlay {
  background-color: var(--md-scrim) !important;
}

/* 级联 Transition：阻尼回弹的金石印章落纸曲线，模拟钤印动作 */
.md-dialog-overlay-enter-active {
  transition: opacity 0.3s cubic-bezier(0.22, 1, 0.36, 1) !important;
}
.md-dialog-overlay-enter-active .md-dialog {
  transition: 
    transform 0.38s cubic-bezier(0.22, 1, 0.36, 1), /* 平滑起笔入宣，告别AI弹跳 */
    opacity 0.3s cubic-bezier(0.22, 1, 0.36, 1),
    filter 0.3s cubic-bezier(0.22, 1, 0.36, 1) !important;
}
.md-dialog-overlay-leave-active {
  transition: opacity 0.25s cubic-bezier(0.22, 1, 0.36, 1) !important;
}
.md-dialog-overlay-leave-active .md-dialog {
  transition: 
    transform 0.3s cubic-bezier(0.22, 1, 0.36, 1),
    opacity 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    filter 0.25s cubic-bezier(0.22, 1, 0.36, 1) !important;
}

/* 进场状态：微弱放大并带有模糊，呈现印章从空中扣下的过程 */
.md-dialog-overlay-enter-from {
  opacity: 0 !important;
}
.md-dialog-overlay-enter-from .md-dialog {
  transform: scale(1.04) translateY(-12px) !important;
  opacity: 0 !important;
}

/* 出场状态：微缩并淡出 */
.md-dialog-overlay-leave-to {
  opacity: 0 !important;
}
.md-dialog-overlay-leave-to .md-dialog {
  transform: scale(0.97) translateY(6px) !important;
  opacity: 0 !important;
}

/* SnackBar 清水慢显 */
.ink-fade-enter-active,
.ink-fade-leave-active {
  transition: 
    opacity 0.38s cubic-bezier(0.22, 1, 0.36, 1),
    filter 0.38s cubic-bezier(0.22, 1, 0.36, 1),
    transform 0.38s cubic-bezier(0.22, 1, 0.36, 1) !important;
}

.ink-fade-enter-from {
  opacity: 0 !important;
  transform: translateY(8px) !important;
}

.ink-fade-leave-to {
  opacity: 0 !important;
  transform: translateY(-4px) !important;
}
</style>
