<!-- AIMETA P=项目卡片_小说项目展示|R=项目信息卡片|NR=不含编辑功能|E=component:ProjectCard|X=internal|A=卡片组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <article
    class="md-card md-card-outlined project-card"
    :aria-label="`${project.title}，${getStatusText}`"
  >
    <div>
      <div class="project-card__header">
        <div class="project-card__summary">
          <button
            type="button"
            class="project-card__title-button"
            @click.stop="$emit('detail', project.id)"
          >
            {{ project.title }}
          </button>
          <p>{{ project.genre || '未知类型' }} · {{ getStatusText }}</p>
          <p class="project-card__meta">最后编辑: {{ formatDateTime(project.last_edited) }}</p>
        </div>
      </div>

      <div class="project-card__progress">
        <div class="project-card__progress-label">
          <span>完成进度</span>
          <strong>{{ progress }}%</strong>
        </div>
        <div
          class="md-progress-linear"
          role="progressbar"
          aria-label="项目完成进度"
          aria-valuemin="0"
          aria-valuemax="100"
          :aria-valuenow="progress"
        >
          <div class="md-progress-linear-bar" :style="{ '--md-progress-scale': progressScale }"></div>
        </div>
      </div>
    </div>

    <div class="project-card__actions project-card__actions--compact">
      <button
        type="button"
        @click.stop="$emit('continue', project)"
        class="md-btn md-btn-filled md-ripple project-card__action"
      >
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          aria-hidden="true"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"
          />
        </svg>
        创作
      </button>
      <button
        type="button"
        @click.stop="handleDelete"
        class="md-icon-btn md-ripple project-card__delete"
        :aria-label="`删除项目 ${project.title}`"
        title="删除项目"
      >
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          aria-hidden="true"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
          />
        </svg>
      </button>
    </div>
  </article>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { NovelProjectSummary } from '@/api/novel'
import { formatDateTime } from '@/utils/date'

interface Props {
  project: NovelProjectSummary
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'detail', id: string): void
  (e: 'continue', project: NovelProjectSummary): void
  (e: 'delete', id: string): void
}>()

// 使用后端预计算的进度数据，并夹紧异常值，避免视觉进度和读屏值分叉。
const rawProgress = computed(() => {
  const { completed_chapters, total_chapters } = props.project
  return total_chapters > 0 ? Math.round((completed_chapters / total_chapters) * 100) : 0
})
const progress = computed(() => Math.max(0, Math.min(100, rawProgress.value)))
const progressScale = computed(() => progress.value / 100)

const getStatusText = computed(() => {
  const { completed_chapters, total_chapters } = props.project

  if (completed_chapters > 0) {
    return `已完成 ${completed_chapters}/${total_chapters} 章`
  } else if (total_chapters > 0) {
    return '准备创作'
  } else {
    return '蓝图完成'
  }
})

const handleDelete = () => {
  emit('delete', props.project.id)
}
</script>

<style scoped>
.project-card {
  min-height: 260px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: var(--md-spacing-5);
  padding: var(--md-spacing-5);
  border-radius: var(--md-radius-xs) !important; /* 去 SaaS 大圆角，木刻方直微圆角 */
  border: 3px double var(--md-outline) !important; /* 古籍线装双边，书架书本仪式感 */
  background-color: var(--md-surface) !important;
  box-shadow: none;
  touch-action: manipulation;
  position: relative !important;
  transition:
    border-color var(--md-duration-short) var(--md-easing-standard),
    box-shadow var(--md-duration-short) var(--md-easing-standard),
    background-color var(--md-duration-short) var(--md-easing-standard);
}

/* Hover 态右下角金石阳刻“卷”朱砂钤印渐显，点睛之笔 */
.project-card::after {
  content: '卷' !important;
  position: absolute !important;
  right: 16px !important;
  bottom: 60px !important;
  font-family: var(--md-font-serif) !important;
  font-size: 10px !important;
  font-weight: bold !important;
  color: var(--md-secondary) !important;
  border: 1px solid var(--md-secondary) !important;
  border-radius: 2px !important; /* 朱砂小方印 */
  width: 15px !important;
  height: 15px !important;
  display: grid !important;
  place-items: center !important;
  line-height: 1 !important;
  box-shadow: none !important; /* 印面压纸不浮起 */
  opacity: 0;
  transform: scale(0.7) rotate(-8deg);
  transition:
    background-color 0.3s cubic-bezier(0.22, 1, 0.36, 1),
    border-color 0.3s cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 0.3s cubic-bezier(0.22, 1, 0.36, 1),
    color 0.3s cubic-bezier(0.22, 1, 0.36, 1),
    opacity 0.3s cubic-bezier(0.22, 1, 0.36, 1),
    transform 0.3s cubic-bezier(0.22, 1, 0.36, 1) !important;
  pointer-events: none;
}

.project-card:hover::after {
  opacity: 0.85 !important;
  transform: scale(1) rotate(0deg) !important;
}

.project-card:hover,
.project-card:focus-within {
  border-color: color-mix(in srgb, var(--md-primary) 50%, var(--md-outline-variant)) !important;
  /* 熟宣柔影微浮 */
  box-shadow: var(--md-elevation-paper-1) !important;
  background-color: var(--md-surface-dim) !important; /* 宣纸微暖色 */
}

.project-card__header {
  display: flex;
  align-items: flex-start;
  gap: var(--md-spacing-4);
  margin-bottom: var(--md-spacing-5);
}

.project-card__summary {
  min-width: 0;
  flex: 1;
}

.project-card__title-button {
  max-width: 100%;
  min-height: 44px;
  display: -webkit-box;
  overflow: hidden;
  padding: var(--md-spacing-1) 0;
  border: 0;
  background: transparent;
  color: var(--md-on-surface);
  /* 使用碑拓宋体 */
  font-family: var(--md-font-serif) !important;
  font-size: var(--md-title-medium);
  font-weight: 700;
  line-height: 1.35;
  letter-spacing: 0.03em; /* 碑拓骨力：宋体标题拉开字距 */
  text-align: left;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-clamp: 2;
}

.project-card__title-button:hover {
  color: var(--md-primary) !important;
  text-decoration: underline;
  text-underline-offset: 4px;
}

.project-card__title-button:focus-visible {
  outline: 2px solid var(--md-primary);
  outline-offset: 3px;
  border-radius: var(--md-radius-xs);
}

.project-card__summary p {
  margin: var(--md-spacing-1) 0 0;
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
}

.project-card__meta {
  font-weight: 500;
}

.project-card__progress {
  margin-bottom: var(--md-spacing-4);
}

.project-card__progress-label {
  display: flex;
  justify-content: space-between;
  gap: var(--md-spacing-3);
  margin-bottom: var(--md-spacing-2);
  color: var(--md-on-surface-variant);
  font-size: var(--md-label-medium);
  font-weight: 600;
}

.project-card__progress-label strong {
  color: var(--md-on-surface);
  font-weight: 600;
}

.project-card__actions {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 44px;
  gap: var(--md-spacing-2);
  padding-top: var(--md-spacing-4);
  border-top: 1px solid var(--md-outline-variant);
}

.project-card__action {
  min-width: 0;
  padding-inline: var(--md-spacing-3);
  white-space: nowrap;
  transition:
    background-color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    border-color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    opacity 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    transform 0.25s cubic-bezier(0.22, 1, 0.36, 1) !important;
}

/* 执笔创作按钮 active 钤印微沉 */
.project-card__action:active {
  transform: translate(1px, 1px) !important;
  opacity: 0.9 !important;
}

.project-card__action svg,
.project-card__delete svg {
  width: 20px;
  height: 20px;
}

.project-card__delete {
  color: var(--md-error);
  transition:
    background-color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    border-color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    color 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    opacity 0.25s cubic-bezier(0.22, 1, 0.36, 1),
    transform 0.25s cubic-bezier(0.22, 1, 0.36, 1) !important;
}

.project-card__delete:hover {
  color: var(--md-error-strong) !important;
  background-color: var(--md-error-container) !important;
}

/* 删除按钮 active 钤印微沉 */
.project-card__delete:active {
  transform: translate(1.5px, 1.5px) !important;
  opacity: 0.8 !important;
}

@media (max-width: 420px) {
  .project-card__actions {
    grid-template-columns: 1fr;
  }

  .project-card__delete {
    width: 100%;
  }
}
</style>
