<!-- AIMETA P=模型路由阶段覆盖面板_阶段路由配置|R=stage select 路由选择|NR=不含路由状态归属与保存|E=component:RoutingStagesPanel|X=internal|A=模型路由阶段面板|D=vue|S=dom|RD=./README.ai -->
<template>
  <!-- 阶段路由分区（routes）：为各创作阶段指定使用的文本生成模型 -->
  <section class="model-routing__stages">
    <div v-if="enabledChatModels.length === 0" class="model-routing__empty-state">
      <p class="md-title-small">还不能配置阶段路由</p>
      <p class="model-routing__empty">请先在文本生成里启用至少一个模型，并指定主模型。</p>
      <button
        type="button"
        class="md-btn md-btn-tonal md-ripple"
        @click="emit('navigate', 'llm')"
      >
        去配置文本生成
      </button>
    </div>

    <div v-else class="model-routing__stage-groups">
      <div
        v-for="group in chatStageGroups"
        :key="group.title"
        class="model-routing__stage-group"
      >
        <h4 class="md-title-small">{{ group.title }}</h4>
        <div class="model-routing__stage-list">
          <label
            v-for="stage in group.stages"
            :key="stage.key"
            class="model-routing__stage-row"
          >
            <span>
              <strong>{{ stage.label }}</strong>
              <small>{{ stage.description }}</small>
            </span>
            <select
              :value="routeSelections[stage.key]"
              class="md-text-field-input"
              :aria-label="`${stage.label} 模型路由`"
              @change="onSelectStage(stage.key, $event)"
            >
              <option value="">使用主模型</option>
              <option
                v-for="model in enabledChatModels"
                :key="model.id"
                :value="String(model.id)"
              >
                {{ model.display_name }} · {{ providerName(model.provider_id) }}
              </option>
            </select>
          </label>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { UserAIModel } from '@/api/llm'
import type { RoutingSection, StageGroup } from './modelRoutingTypes'

defineProps<{
  /** 阶段路由选择（reactive 对象，select 改动经 update-selection 事件回写父组件） */
  routeSelections: Record<string, string>
  chatStageGroups: StageGroup[]
  enabledChatModels: UserAIModel[]
  providerName: (providerId: number) => string
}>()

const emit = defineEmits<{
  (event: 'navigate', section: RoutingSection): void
  (event: 'update-selection', stageKey: string, value: string): void
}>()

const onSelectStage = (stageKey: string, event: Event) => {
  emit('update-selection', stageKey, (event.target as HTMLSelectElement).value)
}
</script>

<style scoped>
.model-routing__stage-groups {
  display: grid;
  gap: var(--md-spacing-3);
}

.model-routing__stage-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: var(--md-spacing-3);
}

.model-routing__stage-group h4 {
  margin: 0;
  color: var(--md-on-surface);
}

.model-routing__empty {
  margin: 4px 0 0;
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
}

.model-routing__stage-row strong {
  display: block;
  font-size: var(--md-body-medium);
}

.model-routing__stage-row small {
  display: block;
  margin-top: 2px;
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
}

.model-routing__empty-state {
  display: grid;
  justify-items: start;
  gap: var(--md-spacing-2);
  padding: var(--md-spacing-5);
  border: 1px dashed var(--md-outline);
  border-radius: var(--md-radius-sm);
  background: var(--md-surface);
}

.model-routing__empty-state p {
  margin: 0;
}

.model-routing__stage-group {
  display: grid;
  gap: var(--md-spacing-3);
}

.model-routing__stage-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--md-spacing-2);
  align-items: center;
  padding: var(--md-spacing-3);
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-md);
  background: var(--md-surface);
}

@media (min-width: 960px) {
  .model-routing__stage-row {
    grid-template-columns: minmax(220px, 0.8fr) minmax(240px, 1fr);
  }
}

@media (min-width: 768px) {
  .model-routing__stage-list {
    grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
  }
}
</style>
