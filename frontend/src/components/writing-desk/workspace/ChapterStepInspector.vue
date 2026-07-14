<template>
  <article class="chapter-console__inspector-card">
    <header class="chapter-console__inspector-header">
      <div class="chapter-console__inspector-title-group">
        <span class="chapter-console__inspector-badge">节点详情</span>
        <h4 class="chapter-console__inspector-title">{{ activeStepDetails.label }}</h4>
      </div>
      <span class="chapter-console__inspector-subtitle">{{ activeStepDetails.summary }}</span>
    </header>
    <div class="chapter-console__inspector-meta">
      <span class="chapter-console__call-type">调用类型：{{ activeStepDetails.callType }}</span>
      <span class="chapter-console__llm-usage">LLM 调用：{{ activeStepDetails.llmUsage }}</span>
      <span
        v-if="activeStepDetails.status"
        class="chapter-console__trace-status"
        :class="{ 'is-failed': activeStepDetails.status === '失败' }"
      >
        状态：{{ activeStepDetails.status }}
      </span>
      <span class="chapter-console__trace-duration">
        系统耗时：{{ activeStepDetails.systemDuration }}
      </span>
    </div>
    <div class="chapter-console__inspector-grids">
      <div class="chapter-console__inspector-panel">
        <div class="chapter-console__panel-title">
          <svg class="w-4 h-4 text-primary" viewBox="0 0 20 20" fill="currentColor" width="16" height="16">
            <path fill-rule="evenodd" d="M3 3a1 1 0 011-1h12a1 1 0 011 1v12a1 1 0 01-1 1H4a1 1 0 01-1-1V3zm2.5 1.5v3h9v-3h-9zm9 5.5h-9v3h9v-3z" clip-rule="evenodd" />
          </svg>
          输入材料
        </div>
        <div class="chapter-console__panel-code-wrapper">
          <pre class="chapter-console__panel-code"><code>{{ activeStepDetails.inputs }}</code></pre>
        </div>
      </div>
      <div class="chapter-console__inspector-panel">
        <div class="chapter-console__panel-title">
          <svg class="w-4 h-4 text-primary" viewBox="0 0 20 20" fill="currentColor" width="16" height="16">
            <path fill-rule="evenodd" d="M18 10c0 3.866-3.582 7-8 7a8.841 8.841 0 01-4.083-.98L2 17l1.338-3.123C2.493 12.767 2 11.434 2 10c0-3.866 3.582-7 8-7s8 3.134 8 7zM7 9H5v2h2V9zm8 0h-2v2h2V9zM9 9h2v2H9V9z" clip-rule="evenodd" />
          </svg>
          实际动作
        </div>
        <div class="chapter-console__panel-code-wrapper">
          <pre class="chapter-console__panel-code"><code>{{ activeStepDetails.actions }}</code></pre>
        </div>
      </div>
      <div class="chapter-console__inspector-panel">
        <div class="chapter-console__panel-title">
          <svg class="w-4 h-4 text-primary" viewBox="0 0 20 20" fill="currentColor" width="16" height="16">
            <path fill-rule="evenodd" d="M4 3a1 1 0 00-1 1v12a1 1 0 001 1h12a1 1 0 001-1V8.414a1 1 0 00-.293-.707l-4.414-4.414A1 1 0 0011.586 3H4zm7 1.5V8h3.5L11 4.5zM6 11h8v1.5H6V11zm0 3h6v1.5H6V14z" clip-rule="evenodd" />
          </svg>
          产出结果
        </div>
        <div class="chapter-console__panel-code-wrapper">
          <pre class="chapter-console__panel-code"><code>{{ activeStepDetails.outputs }}</code></pre>
        </div>
      </div>
    </div>
  </article>
</template>

<script setup lang="ts">
import type { ActiveStepDetails } from '@/utils/generationTrace'

interface Props {
  activeStepDetails: ActiveStepDetails
}

defineProps<Props>()
</script>

<style scoped>
.chapter-console__inspector-card {
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-md, 8px);
  background: color-mix(in srgb, var(--md-surface) 95%, transparent);
  padding: var(--md-spacing-4);
  display: flex;
  flex-direction: column;
  gap: var(--md-spacing-3);
  animation: fadeInInspector 0.3s ease-out;
}

.chapter-console__inspector-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px dashed var(--md-outline-variant);
  padding-bottom: var(--md-spacing-2);
  flex-wrap: wrap;
  gap: 8px;
}

.chapter-console__inspector-title-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.chapter-console__inspector-badge {
  font-size: var(--md-label-small);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  background-color: var(--md-primary-container);
  color: var(--md-on-primary-container);
  padding: 2px 6px;
  border-radius: var(--md-radius-small, 4px);
}

.chapter-console__inspector-title {
  margin: 0;
  color: var(--md-on-surface);
  font-size: var(--md-title-medium);
  font-weight: 600;
}

.chapter-console__inspector-subtitle {
  font-size: var(--md-body-small);
  color: var(--md-on-surface-variant);
}

.chapter-console__inspector-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.chapter-console__call-type,
.chapter-console__llm-usage,
.chapter-console__trace-status {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-xs);
  background-color: var(--md-surface-container-low);
  color: var(--md-on-surface-variant);
  font-size: var(--md-label-small);
  font-weight: 700;
}

.chapter-console__trace-status.is-failed {
  border-color: color-mix(in srgb, var(--md-error) 36%, var(--md-outline-variant));
  background-color: color-mix(in srgb, var(--md-error) 10%, var(--md-surface));
  color: var(--md-error);
}

.chapter-console__inspector-grids {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--md-spacing-3);
}

@media (max-width: 833px) {
  .chapter-console__inspector-grids {
    grid-template-columns: 1fr;
  }
}

.chapter-console__inspector-panel {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.chapter-console__panel-title {
  font-size: var(--md-label-medium);
  font-weight: 600;
  color: var(--md-primary-dark);
  display: flex;
  align-items: center;
  gap: 6px;
}

.chapter-console__panel-code-wrapper {
  background-color: color-mix(in srgb, var(--md-surface-container-highest) 35%, var(--md-surface-container-low));
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-md, 6px);
  padding: var(--md-spacing-3);
  height: 240px;
  overflow: auto;
}

.chapter-console__panel-code {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: ui-monospace, SFMono-Regular, SF Mono, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  font-size: 13px;
  line-height: 1.6;
  color: var(--md-on-surface);
}

@keyframes fadeInInspector {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
