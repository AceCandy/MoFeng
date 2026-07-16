<template>
  <div
    :class="['model-routing__readiness', `is-${summary.tone}`]"
    :title="summary.description"
    aria-label="模型配置状态"
  >
    <span class="model-routing__readiness-label">{{ summary.label }}</span>
    <strong class="model-routing__readiness-value">{{ summary.value }}</strong>
    <span class="model-routing__readiness-detail">{{ summary.description }}</span>
  </div>
</template>

<script setup lang="ts">
import type { ReadinessSummary } from './modelRoutingTypes'

defineProps<{ summary: ReadinessSummary }>()
</script>

<style scoped>
.model-routing__readiness {
  display: flex;
  min-width: 0;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--md-spacing-2) var(--md-spacing-4);
  padding: var(--md-spacing-3) var(--md-spacing-4) var(--md-spacing-4);
  border-bottom: 1px solid var(--md-outline-variant);
  color: var(--md-on-surface-variant);
}

.model-routing__readiness.is-success .model-routing__readiness-value {
  color: var(--md-success);
}

.model-routing__readiness.is-warning .model-routing__readiness-value {
  color: var(--md-on-warning-container);
}

.model-routing__readiness-label {
  color: var(--md-on-surface-variant);
  font-size: var(--md-label-small);
  font-weight: 600;
}

.model-routing__readiness-value {
  min-width: 0;
  overflow: hidden;
  color: var(--md-on-surface);
  font-size: var(--md-title-medium);
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.model-routing__readiness-detail {
  min-width: min(100%, 240px);
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
}
</style>
