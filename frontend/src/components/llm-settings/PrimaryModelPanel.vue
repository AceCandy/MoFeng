<!-- AIMETA P=主模型面板_文本生成主模型选择|R=主模型 select 切换|NR=不含主模型状态与切换副作用|E=component:PrimaryModelPanel|X=internal|A=主模型面板|D=vue|S=dom|RD=./README.ai -->
<template>
  <!-- 主模型选择面板（仅 llm 分区）：未设置阶段路由时的默认文本生成模型 -->
  <section class="model-routing__panel model-routing__primary-panel">
    <div class="model-routing__primary-copy">
      <h3 class="md-title-medium">主模型</h3>
      <p class="model-routing__hint">未设置阶段路由时，所有文本生成任务会使用这里的模型。</p>
    </div>
    <label class="md-text-field model-routing__primary-field">
      <span class="md-text-field-label">主模型</span>
      <select
        class="md-text-field-input"
        :value="primaryChatModel ? String(primaryChatModel.id) : ''"
        :disabled="enabledChatModels.length === 0"
        @change="emit('set-primary', $event)"
      >
        <option value="">请先勾选一个文本生成模型</option>
        <option v-for="model in enabledChatModels" :key="model.id" :value="String(model.id)">
          {{ model.display_name }} · {{ providerName(model.provider_id) }}
        </option>
      </select>
    </label>
  </section>
</template>

<script setup lang="ts">
import type { UserAIModel } from '@/api/llm'

defineProps<{
  enabledChatModels: UserAIModel[]
  primaryChatModel: UserAIModel | undefined
  providerName: (providerId: number) => string
}>()

const emit = defineEmits<{
  (event: 'set-primary', e: Event): void
}>()
</script>

<style scoped>
/* 面板外观（原父 .model-routing__panel 随本子组件迁入；父已无 .panel 消费） */
.model-routing__panel {
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-sm);
  padding: var(--md-spacing-4);
  background: var(--md-surface);
}

.model-routing__primary-panel {
  display: grid;
  grid-template-columns: minmax(180px, 0.65fr) minmax(260px, 1fr);
  align-items: end;
  gap: var(--md-spacing-4);
  background: color-mix(in srgb, var(--md-surface) 88%, var(--md-surface-dim));
}

.model-routing__primary-copy h3 {
  margin: 0;
  color: var(--md-on-surface);
}

.model-routing__primary-field {
  margin: 0;
}

/* hint 共用样式（复制自父；父多处仍消费） */
.model-routing__hint {
  margin: 4px 0 0;
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
}

@media (max-width: 860px) {
  .model-routing__primary-panel {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
