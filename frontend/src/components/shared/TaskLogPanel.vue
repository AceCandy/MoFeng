<!-- AIMETA P=后台任务日志面板_查看当前任务日志|R=任务列表_日志详情_进度|NR=不含任务提交|E=component:TaskLogPanel|X=ui|A=task_logs|D=vue|S=dom|RD=./README.ai -->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import type { BackgroundTask } from '@/api/tasks'

const props = defineProps<{
  tasks: BackgroundTask[]
  loading?: boolean
}>()

const activeStatuses = new Set(['queued', 'running'])
const selectedTaskId = ref<string | null>(null)

const sortedTasks = computed(() => {
  return [...props.tasks].sort((left, right) => {
    const leftActive = activeStatuses.has(left.status) ? 0 : 1
    const rightActive = activeStatuses.has(right.status) ? 0 : 1
    if (leftActive !== rightActive) return leftActive - rightActive
    return new Date(right.created_at).getTime() - new Date(left.created_at).getTime()
  })
})

const selectedTask = computed(() => {
  return sortedTasks.value.find((task) => task.id === selectedTaskId.value) ?? sortedTasks.value[0] ?? null
})

const statusText = (status: string) => {
  if (status === 'queued') return '排队中'
  if (status === 'running') return '执行中'
  if (status === 'succeeded') return '已完成'
  if (status === 'failed') return '失败'
  return status
}

const statusClass = (status: string) => `is-${status}`

const formatTime = (value?: string | null) => {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

watch(
  sortedTasks,
  (tasks) => {
    if (!tasks.length) {
      selectedTaskId.value = null
      return
    }
    if (!tasks.some((task) => task.id === selectedTaskId.value)) {
      selectedTaskId.value = tasks[0].id
    }
  },
  { immediate: true },
)
</script>

<template>
  <section class="task-log-panel" aria-label="任务日志">
    <aside class="task-log-panel__list" aria-label="任务列表">
      <div class="task-log-panel__summary">
        <strong>{{ sortedTasks.length }}</strong>
        <span>{{ props.loading ? '同步中' : '最近任务' }}</span>
      </div>

      <button
        v-for="task in sortedTasks"
        :key="task.id"
        type="button"
        class="task-log-panel__task"
        :class="{ 'is-selected': selectedTask?.id === task.id }"
        @click="selectedTaskId = task.id"
      >
        <span class="task-log-panel__task-title">{{ task.title }}</span>
        <span class="task-log-panel__task-meta">
          <span class="task-log-panel__status" :class="statusClass(task.status)">
            {{ statusText(task.status) }}
          </span>
          <span>{{ formatTime(task.updated_at) }}</span>
        </span>
      </button>

      <p v-if="!sortedTasks.length" class="task-log-panel__empty">暂无后台任务</p>
    </aside>

    <article class="task-log-panel__detail">
      <template v-if="selectedTask">
        <header class="task-log-panel__header">
          <div>
            <p class="task-log-panel__eyebrow">任务日志</p>
            <h3>{{ selectedTask.title }}</h3>
          </div>
          <span class="task-log-panel__status" :class="statusClass(selectedTask.status)">
            {{ statusText(selectedTask.status) }}
          </span>
        </header>

        <div class="task-log-panel__progress" aria-label="任务进度">
          <span :style="{ transform: `scaleX(${selectedTask.progress / 100})` }"></span>
        </div>
        <p class="task-log-panel__progress-copy">当前进度 {{ selectedTask.progress }}%</p>

        <ol class="task-log-panel__logs">
          <li
            v-for="entry in selectedTask.log_entries ?? []"
            :key="`${entry.timestamp}-${entry.message}`"
            class="task-log-panel__log"
            :class="statusClass(entry.level)"
          >
            <time>{{ formatTime(entry.timestamp) }}</time>
            <p>{{ entry.message }}</p>
          </li>
        </ol>

        <p v-if="selectedTask.error" class="task-log-panel__error">{{ selectedTask.error }}</p>
      </template>

      <p v-else class="task-log-panel__empty-detail">后台任务会在这里显示执行日志。</p>
    </article>
  </section>
</template>

<style scoped>
.task-log-panel {
  display: grid;
  grid-template-columns: minmax(220px, 280px) minmax(0, 1fr);
  min-height: min(62vh, 620px);
  border: 1px solid var(--md-outline-variant);
  background: var(--md-surface);
}

.task-log-panel__list {
  border-right: 1px solid var(--md-outline-variant);
  background: var(--md-surface-container-low);
  overflow-y: auto;
}

.task-log-panel__summary {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 16px;
  border-bottom: 1px solid var(--md-outline-variant);
  color: var(--md-on-surface-variant);
  font-size: 13px;
}

.task-log-panel__summary strong {
  color: var(--md-on-surface);
  font-size: 22px;
  font-family: var(--md-font-serif);
}

.task-log-panel__task {
  width: 100%;
  display: grid;
  gap: 8px;
  padding: 14px 16px;
  border: 0;
  border-bottom: 1px solid var(--md-outline-variant);
  background: transparent;
  color: var(--md-on-surface);
  text-align: left;
  cursor: pointer;
}

.task-log-panel__task:hover,
.task-log-panel__task.is-selected {
  background: var(--md-surface-container);
}

.task-log-panel__task:focus-visible {
  outline: 2px solid var(--md-primary);
  outline-offset: -2px;
}

.task-log-panel__task-title {
  font-size: 14px;
  font-weight: 600;
}

.task-log-panel__task-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  color: var(--md-on-surface-variant);
  font-size: 12px;
}

.task-log-panel__detail {
  padding: 22px 24px;
  overflow-y: auto;
}

.task-log-panel__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
}

.task-log-panel__eyebrow {
  margin: 0 0 4px;
  color: var(--md-on-surface-variant);
  font-size: 12px;
  font-weight: 600;
}

.task-log-panel__header h3 {
  margin: 0;
  color: var(--md-on-surface);
  font-family: var(--md-font-serif);
  font-size: 19px;
  letter-spacing: 0.03em;
}

.task-log-panel__status {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 8px;
  border: 1px solid var(--md-outline);
  border-radius: var(--md-radius-xs);
  background: var(--md-surface-container);
  color: var(--md-on-surface-variant);
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

.task-log-panel__status.is-running,
.task-log-panel__status.is-queued {
  background: var(--md-warning-container);
  color: var(--md-on-surface);
}

.task-log-panel__status.is-succeeded {
  background: var(--md-success-container);
  color: var(--md-success);
}

.task-log-panel__status.is-failed,
.task-log-panel__status.is-error {
  background: var(--md-error-container);
  color: var(--md-error);
}

.task-log-panel__progress {
  height: 6px;
  margin-top: 20px;
  overflow: hidden;
  border: 1px solid var(--md-outline-variant);
  background: var(--md-surface-container);
}

.task-log-panel__progress span {
  display: block;
  height: 100%;
  transform-origin: left center;
  background: var(--md-primary);
  transition: transform 180ms cubic-bezier(0.2, 0, 0, 1);
}

.task-log-panel__progress-copy {
  margin: 8px 0 0;
  color: var(--md-on-surface-variant);
  font-size: 12px;
}

.task-log-panel__logs {
  display: grid;
  gap: 10px;
  margin: 22px 0 0;
  padding: 0;
  list-style: none;
}

.task-log-panel__log {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr);
  gap: 12px;
  padding: 12px;
  border: 1px solid var(--md-outline-variant);
  background: var(--md-surface-container-lowest);
}

.task-log-panel__log time {
  color: var(--md-on-surface-variant);
  font-size: 12px;
}

.task-log-panel__log p {
  margin: 0;
  color: var(--md-on-surface);
  font-size: 13px;
  line-height: 1.7;
}

.task-log-panel__error,
.task-log-panel__empty,
.task-log-panel__empty-detail {
  margin: 16px;
  color: var(--md-on-surface-variant);
  font-size: 13px;
}

.task-log-panel__error {
  margin: 18px 0 0;
  color: var(--md-error);
}

@media (max-width: 720px) {
  .task-log-panel {
    grid-template-columns: 1fr;
  }

  .task-log-panel__list {
    max-height: 220px;
    border-right: 0;
    border-bottom: 1px solid var(--md-outline-variant);
  }
}
</style>
