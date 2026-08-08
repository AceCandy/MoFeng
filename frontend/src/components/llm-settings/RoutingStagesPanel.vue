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
  letter-spacing: 0.03em; /* 碑拓骨力：宋体小标题拉开字距 */
}

/* .model-routing__empty / __empty-state 已收口至
   styles/components/model-routing.css，组件内不再重复定义 */

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
  border: 1px solid var(--md-jiege);
  border-radius: var(--md-radius-xs);
  background: var(--md-surface);
}

/* 卡片由 auto-fit 决定宽度（约 280-400px），标签与选择框始终纵向堆叠；
   选择框占满卡片宽度，长模型名由全局 select 规则以省略号截断，不再溢出 */
</style>
