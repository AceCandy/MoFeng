<!-- AIMETA P=正文节点模型路由面板|R=工作流节点展示_stage选择_默认模型|NR=不持有路由状态与保存|E=component:RoutingStagesPanel|X=internal|A=model-routing|D=vue|S=dom|RD=./README.ai -->
<template>
  <section class="model-routing__stages" aria-label="阶段路由配置">
    <div v-if="missingCapabilities.length" class="model-routing__route-notices">
      <div
        v-for="capability in missingCapabilities"
        :key="capability"
        class="model-routing__route-notice"
      >
        <span>
          {{ capability === 'chat' ? '文本生成模型尚未配置' : '向量检索模型尚未配置' }}
        </span>
        <button
          type="button"
          class="md-btn md-btn-text md-ripple"
          @click="emit('navigate', capability === 'chat' ? 'llm' : 'embedding')"
        >
          去配置
        </button>
      </div>
    </div>

    <section class="model-routing__route-section" aria-labelledby="chapter-workflow-routes-title">
      <header class="model-routing__route-section-header">
        <h4 id="chapter-workflow-routes-title" class="md-title-small">正文工作流</h4>
        <p>与生成正文的节点顺序一致；相同 stage 的节点共用一个模型选择。</p>
      </header>

      <div class="model-routing__workflow-groups">
        <details
          v-for="group in workflowGroups"
          :key="group.key"
          class="model-routing__workflow-group"
          :data-group="group.key"
          :data-mode="group.mode"
          :open="isGroupOpen(`workflow:${group.key}`)"
          @toggle="onGroupToggle(`workflow:${group.key}`, $event)"
        >
          <summary class="model-routing__workflow-group-header" :tabindex="isMobile ? 0 : -1">
            <h5>{{ group.label }}</h5>
            <span v-if="group.mode === 'parallel'" class="model-routing__route-badge">并行</span>
          </summary>
          <ol class="model-routing__workflow-list">
            <li
              v-for="node in group.steps"
              :key="node.key"
              class="model-routing__workflow-node"
              :class="{ 'is-local': !node.routeStage }"
              :data-node="node.key"
            >
              <div class="model-routing__node-copy">
                <div class="model-routing__node-title">
                  <strong>{{ node.label }}</strong>
                  <span v-if="node.routeStage" class="model-routing__route-badge">
                    {{ node.routeCapability === 'embedding' ? '向量模型' : '聊天模型' }}
                  </span>
                  <span
                    v-if="node.routeStage && sharedStageCount(node.routeStage) > 1"
                    class="model-routing__route-badge"
                  >
                    共用路由
                  </span>
                  <span v-if="node.optional" class="model-routing__route-badge">按需</span>
                </div>
                <small v-if="node.routeStage">
                  {{ routeDescription(node.routeStage) }} · <code>{{ node.routeStage }}</code>
                </small>
                <small v-else>{{ nodeKindLabel(node.kind) }} · 无模型调用</small>
              </div>

              <select
                v-if="node.routeStage && node.routeCapability"
                :value="routeSelections[node.routeStage]"
                class="md-text-field-input model-routing__route-select"
                :data-stage="node.routeStage"
                :aria-label="`${node.label} 模型路由`"
                @change="onSelectStage(node.routeStage, $event)"
              >
                <option value="">{{ fallbackModelLabel(node.routeCapability) }}</option>
                <option
                  v-for="model in modelsForCapability(node.routeCapability)"
                  :key="model.id"
                  :value="String(model.id)"
                >
                  {{ model.display_name }} · {{ providerName(model.provider_id) }}
                </option>
              </select>
            </li>
          </ol>
        </details>
      </div>
    </section>

    <section class="model-routing__route-section" aria-labelledby="other-stage-routes-title">
      <header class="model-routing__route-section-header">
        <h4 id="other-stage-routes-title" class="md-title-small">其他功能</h4>
        <p>通用调用、导入、灵感、蓝图和独立分析等不属于正文工作流的路由。</p>
      </header>

      <div class="model-routing__other-groups">
        <details
          v-for="group in otherStageGroups"
          :key="group.title"
          class="model-routing__other-group"
          :open="isGroupOpen(`other:${group.title}`)"
          @toggle="onGroupToggle(`other:${group.title}`, $event)"
        >
          <summary class="model-routing__other-group-header" :tabindex="isMobile ? 0 : -1">
            <h5>{{ group.title }}</h5>
          </summary>
          <div class="model-routing__other-list">
            <label v-for="stage in group.stages" :key="stage.key" class="model-routing__other-row">
              <span class="model-routing__node-copy">
                <strong>{{ stage.label }}</strong>
                <small
                  >{{ stage.description }} · <code>{{ stage.key }}</code></small
                >
              </span>
              <select
                :value="routeSelections[stage.key]"
                class="md-text-field-input model-routing__route-select"
                :aria-label="`${stage.label} 模型路由`"
                @change="onSelectStage(stage.key, $event)"
              >
                <option value="">{{ fallbackModelLabel(stage.capability) }}</option>
                <option
                  v-for="model in modelsForCapability(stage.capability)"
                  :key="model.id"
                  :value="String(model.id)"
                >
                  {{ model.display_name }} · {{ providerName(model.provider_id) }}
                </option>
              </select>
            </label>
          </div>
        </details>
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { UserAIModel } from '@/api/llm'
import { useResponsiveViewport } from '@/composables/useResponsiveViewport'
import { mobileMax } from '@/constants/responsive'
import { CHAPTER_WORKFLOW_STEPS, type PipelineStepKind } from '@/utils/generationTrace'
import { otherStageGroups, stageDefinitionByKey } from './stageDefinitions'
import type { Capability, RoutingSection } from './modelRoutingTypes'

interface Props {
  routeSelections: Record<string, string>
  enabledChatModels: UserAIModel[]
  primaryChatModel?: UserAIModel
  enabledEmbeddingModels: UserAIModel[]
  defaultEmbeddingModel?: UserAIModel
  providerName: (providerId: number) => string
}

const props = defineProps<Props>()
const viewport = useResponsiveViewport()
const isMobile = computed(() => viewport.width.value <= mobileMax)
const firstWorkflowGroup = CHAPTER_WORKFLOW_STEPS[0]?.group || 'workflow'
const openMobileGroup = ref(`workflow:${firstWorkflowGroup}`)

const emit = defineEmits<{
  (event: 'navigate', section: RoutingSection): void
  (event: 'update-selection', stageKey: string, value: string): void
}>()

const workflowGroups = computed(() => {
  const groups: Array<{
    key: string
    label: string
    mode: 'serial' | 'parallel'
    steps: (typeof CHAPTER_WORKFLOW_STEPS)[number][]
  }> = []
  for (const step of CHAPTER_WORKFLOW_STEPS) {
    const key = step.group || 'workflow'
    let group = groups[groups.length - 1]
    if (!group || group.key !== key) {
      group = {
        key,
        label: step.groupLabel || '',
        mode: step.groupMode || 'serial',
        steps: [],
      }
      groups.push(group)
    }
    group.steps.push(step)
  }
  return groups
})

const isGroupOpen = (key: string) => !isMobile.value || openMobileGroup.value === key

const onGroupToggle = (key: string, event: Event) => {
  const details = event.currentTarget as HTMLDetailsElement
  if (!isMobile.value) {
    if (!details.open) details.open = true
    return
  }
  if (!details.open) return
  openMobileGroup.value = key
  details
    .closest('.model-routing__stages')
    ?.querySelectorAll<HTMLDetailsElement>('.model-routing__workflow-group, .model-routing__other-group')
    .forEach((group) => {
      if (group !== details) group.open = false
    })
}

const stageCounts = new Map<string, number>()
for (const step of CHAPTER_WORKFLOW_STEPS) {
  if (step.routeStage) stageCounts.set(step.routeStage, (stageCounts.get(step.routeStage) || 0) + 1)
}

const missingCapabilities = computed<Array<'chat' | 'embedding'>>(() => {
  const missing: Array<'chat' | 'embedding'> = []
  if (props.enabledChatModels.length === 0) missing.push('chat')
  if (props.enabledEmbeddingModels.length === 0) missing.push('embedding')
  return missing
})

const sharedStageCount = (stage: string) => stageCounts.get(stage) || 0

const routeDescription = (stage: string) =>
  stageDefinitionByKey[stage]?.description || '使用该阶段的模型路由'

const modelsForCapability = (capability: Capability) =>
  capability === 'embedding' ? props.enabledEmbeddingModels : props.enabledChatModels

const fallbackModelLabel = (capability: Capability) => {
  const model = capability === 'embedding' ? props.defaultEmbeddingModel : props.primaryChatModel
  const prefix = capability === 'embedding' ? '当前检索模型' : '主模型'
  return model
    ? `${prefix}：${model.display_name} · ${props.providerName(model.provider_id)}`
    : `${prefix}：未配置`
}

const nodeKindLabel = (kind?: PipelineStepKind) => {
  if (kind === 'control') return '控制节点'
  if (kind === 'terminal') return '终态节点'
  return '系统节点'
}

const onSelectStage = (stageKey: string, event: Event) => {
  emit('update-selection', stageKey, (event.target as HTMLSelectElement).value)
}
</script>

<style scoped>
.model-routing__stages,
.model-routing__route-section,
.model-routing__workflow-groups,
.model-routing__other-groups {
  display: grid;
}

.model-routing__stages {
  gap: var(--md-spacing-6);
}

.model-routing__route-section {
  gap: var(--md-spacing-4);
}

.model-routing__route-section-header {
  display: grid;
  gap: var(--md-spacing-1);
}

.model-routing__route-section-header h4,
.model-routing__route-section-header p,
.model-routing__workflow-group-header h5,
.model-routing__other-group h5 {
  margin: 0;
}

.model-routing__route-section-header h4,
.model-routing__workflow-group-header h5,
.model-routing__other-group h5 {
  color: var(--md-on-surface);
  letter-spacing: 0.03em;
}

.model-routing__route-section-header p {
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
}

.model-routing__workflow-groups,
.model-routing__other-groups {
  gap: var(--md-spacing-4);
}

.model-routing__workflow-group,
.model-routing__other-group {
  display: grid;
  gap: var(--md-spacing-2);
}

.model-routing__workflow-group-header,
.model-routing__other-group-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--md-spacing-2);
}

.model-routing__workflow-group-header,
.model-routing__other-group-header {
  list-style: none;
}

.model-routing__workflow-group-header::-webkit-details-marker,
.model-routing__other-group-header::-webkit-details-marker {
  display: none;
}

@media (min-width: 834px) {
  .model-routing__workflow-group-header,
  .model-routing__other-group-header {
    pointer-events: none;
  }
}

.model-routing__workflow-list,
.model-routing__other-list {
  margin: 0;
  padding: 0;
  border: 1px solid var(--md-jiege);
  border-radius: var(--md-radius-xs);
  background: var(--md-surface);
  list-style: none;
}

.model-routing__workflow-node,
.model-routing__other-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(240px, 360px);
  gap: var(--md-spacing-3);
  align-items: center;
  min-width: 0;
  padding: var(--md-spacing-3);
}

.model-routing__workflow-node + .model-routing__workflow-node,
.model-routing__other-row + .model-routing__other-row {
  border-top: 1px solid var(--md-jiege);
}

.model-routing__workflow-node.is-local {
  background: var(--md-surface-container-low);
}

.model-routing__node-copy,
.model-routing__node-copy strong,
.model-routing__node-copy small {
  min-width: 0;
}

.model-routing__node-copy strong,
.model-routing__node-copy small {
  display: block;
}

.model-routing__node-copy strong {
  color: var(--md-on-surface);
  font-size: var(--md-body-medium);
}

.model-routing__node-copy small {
  margin-top: var(--md-spacing-1);
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
  overflow-wrap: anywhere;
}

.model-routing__node-copy code {
  font-family: inherit;
  font-size: inherit;
}

.model-routing__node-title {
  display: flex;
  flex-wrap: wrap;
  gap: var(--md-spacing-1) var(--md-spacing-2);
  align-items: center;
}

.model-routing__route-badge {
  padding: 2px var(--md-spacing-2);
  border: 1px solid var(--md-jiege);
  border-radius: var(--md-radius-xs);
  color: var(--md-on-surface-variant);
  font-size: var(--md-label-small);
  line-height: 1.4;
}

.model-routing__route-select {
  width: 100%;
  min-width: 0;
}

.model-routing__route-notices {
  display: grid;
  gap: var(--md-spacing-2);
}

.model-routing__route-notice {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--md-spacing-3);
  padding: var(--md-spacing-2) var(--md-spacing-3);
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-xs);
  color: var(--md-on-surface-variant);
  background: var(--md-surface-container-low);
}

@media (max-width: 833px) {
  .model-routing__workflow-group-header,
  .model-routing__other-group-header {
    min-height: 44px;
    cursor: pointer;
    align-items: center;
  }

  .model-routing__workflow-group-header::after,
  .model-routing__other-group-header::after {
    content: '展开';
    margin-left: auto;
    color: var(--md-on-surface-variant);
    font-size: var(--md-label-small);
  }

  .model-routing__workflow-group[open] > .model-routing__workflow-group-header::after,
  .model-routing__other-group[open] > .model-routing__other-group-header::after {
    content: '收起';
  }

  .model-routing__workflow-node,
  .model-routing__other-row {
    grid-template-columns: minmax(0, 1fr);
  }

  .model-routing__route-notice {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
