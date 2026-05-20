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
        <div class="md-progress-linear">
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

// 使用后端预计算的进度数据
const progress = computed(() => {
  const { completed_chapters, total_chapters } = props.project
  return total_chapters > 0 ? Math.round((completed_chapters / total_chapters) * 100) : 0
})
const progressScale = computed(() => Math.max(0, Math.min(100, progress.value)) / 100)

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
  border-radius: var(--md-radius-lg);
  box-shadow: none;
  touch-action: manipulation;
  transition:
    border-color var(--md-duration-short) var(--md-easing-standard),
    box-shadow var(--md-duration-short) var(--md-easing-standard),
    background-color var(--md-duration-short) var(--md-easing-standard);
}

.project-card:hover,
.project-card:focus-within {
  border-color: color-mix(in srgb, var(--md-primary) 42%, var(--md-outline-variant));
  box-shadow: var(--md-elevation-1);
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
  display: -webkit-box;
  overflow: hidden;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--md-on-surface);
  font: inherit;
  font-size: var(--md-title-medium);
  font-weight: 600;
  line-height: 1.35;
  text-align: left;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-clamp: 2;
}

.project-card__title-button:hover {
  color: var(--md-primary-dark);
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
}

.project-card__action svg,
.project-card__delete svg {
  width: 20px;
  height: 20px;
}

.project-card__delete {
  color: var(--md-error);
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
