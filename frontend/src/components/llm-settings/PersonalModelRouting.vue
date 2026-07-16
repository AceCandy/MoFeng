<template>
  <section class="model-routing">
    <div class="model-routing__topbar">
      <div class="model-routing__section-copy">
        <p class="md-label-medium model-routing__eyebrow">{{ sectionEyebrow }}</p>
        <h3 class="md-title-medium">{{ sectionHeading }}</h3>
        <p class="model-routing__hint">{{ sectionDescription }}</p>
      </div>
      <div class="model-routing__topbar-actions">
        <button
          v-if="!props.isModal"
          type="button"
          class="md-btn md-btn-outlined md-ripple"
          :disabled="isLoading"
          @click="loadBundle"
        >
          {{ isLoading ? '刷新中...' : '刷新' }}
        </button>
        <button
          v-if="activeSection === 'routes' && !props.isModal"
          type="button"
          class="md-btn md-btn-tonal md-ripple"
          :disabled="isSavingRoutes"
          @click="saveRoutes"
        >
          {{ isSavingRoutes ? '保存中...' : '保存阶段路由' }}
        </button>
        <button
          v-else-if="activeSection !== 'routes'"
          type="button"
          class="md-btn md-btn-filled md-ripple"
          @click="beginCreateProvider"
        >
          新增供应商
        </button>
      </div>
    </div>

    <div
      v-if="feedback.message"
      :class="['model-routing__feedback', `is-${feedback.type}`]"
      :role="feedback.type === 'error' ? 'alert' : 'status'"
      aria-live="polite"
    >
      {{ feedback.message }}
    </div>

    <ReadinessPanel :summary="sectionReadinessSummary" />

    <template v-if="activeSection === 'routes'">
      <RoutingStagesPanel
        :route-selections="routeSelections"
        :chat-stage-groups="chatStageGroups"
        :enabled-chat-models="enabledChatModels"
        :provider-name="providerName"
        @navigate="emit('navigate', $event)"
        @update-selection="(stageKey, value) => (routeSelections[stageKey] = value)"
      />
    </template>

    <template v-else>
      <ProviderFormPanel
        v-if="providerFormMode === 'create'"
        mode="create"
        :provider-form="providerForm"
        :is-saving-provider="isSavingProvider"
        @update-field="updateProviderField"
        @save="saveProviderForm"
        @cancel="cancelProviderForm"
      />

      <PrimaryModelPanel
        v-if="activeSection === 'llm'"
        :enabled-chat-models="enabledChatModels"
        :primary-chat-model="primaryChatModel"
        :provider-name="providerName"
        @set-primary="setPrimaryChatModelById"
      />

      <div class="model-routing__provider-grid">
        <template v-for="provider in activeProviders" :key="provider.id">
          <ProviderCard
            :provider="provider"
            :is-editing="providerFormMode === 'edit' && editingProviderId === provider.id"
            :active-section="activeSection"
            :provider-form="providerForm"
            :is-saving-provider="isSavingProvider"
            :provider-fetch-state="providerFetchState"
            :is-model-picker-open="isModelPickerOpen"
            :selected-model-chips-for-provider="selectedModelChipsForProvider"
            @update-field="updateProviderField"
            @save-provider="saveProviderForm"
            @cancel-provider="cancelProviderForm"
            @toggle="toggleProviderEnabled(provider)"
            @delete="deleteProviderFromCard(provider)"
            @edit="beginEditProvider(provider)"
            @open-picker="(event) => openProviderModelPicker(provider, event)"
            @delete-model="(modelName) => deleteModelForActiveSection(provider, modelName)"
          />
          <ModelPickerDialog
            v-if="isModelPickerOpen(provider.id) && !(providerFormMode === 'edit' && editingProviderId === provider.id)"
            :provider="provider"
            :active-section="activeSection"
            :model-picker-style="modelPickerStyle"
            :is-saving-picker="isSavingPicker"
            :is-chat-picker-dirty="isChatPickerDirty"
            :model-picker-query="modelPickerQuery"
            :pending-chat-model-names="pendingChatModelNames"
            :pending-tts-model-name="pendingTTSModelName"
            :filtered-model-names-for-provider="filteredModelNamesForProvider"
            :is-model-selected-for-active-section="isModelSelectedForActiveSection"
            :active-model-state-label="activeModelStateLabel"
            :saved-model-for-active-section="savedModelForActiveSection"
            :provider-fetch-state="providerFetchState"
            :set-model-picker-dialog-ref="setModelPickerDialogRef"
            :set-model-picker-search-input-ref="setModelPickerSearchInputRef"
            @update-query="(value) => { modelPickerQuery = value }"
            @toggle-chat="(modelName, event) => togglePendingChatModel(provider, modelName, event)"
            @select-embedding="(modelName) => selectEmbeddingModel(provider, modelName)"
            @select-tts="(modelName) => selectPendingTTSModel(provider, modelName)"
            @save="() => savePickerSelections(provider)"
            @close="closeModelPicker"
          />
        </template>
      </div>

      <div v-if="activeProviders.length === 0" class="model-routing__empty-state">
        <p class="md-title-small">尚未配置供应商</p>
        <p class="model-routing__empty">
          先新增一个{{
            activeSection === 'llm'
              ? '文本生成'
              : activeSection === 'embedding'
                ? '记忆检索'
                : '语音朗读'
          }}供应商，再拉取并启用模型。
        </p>
        <button type="button" class="md-btn md-btn-filled md-ripple" @click="beginCreateProvider">
          新增供应商
        </button>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import {
  computed,
  onMounted,
} from 'vue'
import { useModelBundle } from '@/composables/useModelBundle'
import { useSectionMeta } from './useSectionMeta'
import { useStageRoutes } from './useStageRoutes'
import { useProviderForm } from './useProviderForm'
import { useModelPicker } from './useModelPicker'
import { useModelSelection } from './useModelSelection'
import { ReadinessPanel } from './ReadinessPanel'
import { RoutingStagesPanel } from './RoutingStagesPanel'
import { ProviderFormPanel } from './ProviderFormPanel'
import { PrimaryModelPanel } from './PrimaryModelPanel'
import { ModelPickerDialog } from './ModelPickerDialog'
import { SelectedModelChips } from './SelectedModelChips'
import { ProviderCard } from './ProviderCard'
import type {
  ProviderForm,
  RoutingSection,
} from './modelRoutingTypes'

const emit = defineEmits<{
  (event: 'saved'): void
  (event: 'navigate', section: RoutingSection): void
}>()

const props = withDefaults(
  defineProps<{
    activeSection?: RoutingSection
    isModal?: boolean
  }>(),
  {
    activeSection: 'llm',
    isModal: false,
  }
)

const activeSection = computed<RoutingSection>(() => props.activeSection || 'llm')

const {
  bundleQuery,
  saveProviderMutation,
  toggleProviderMutation,
  deleteProviderMutation,
  saveUserModelMutation,
  updateUserModelMutation,
  deleteUserModelMutation,
  saveStageRoutesMutation,
  providers,
  models,
  isLoading,
  isSavingProvider,
  isSavingRoutes,
  feedback,
  setFeedback,
  loadBundle,
} = useModelBundle({
  onLoaded: () => syncRouteSelectionsFromBundle(),
})
const {
  providerForm,
  providerFormMode,
  editingProviderId,
  providerFetchStates,
  providerFetchState,
  beginCreateProvider,
  beginEditProvider,
  cancelProviderForm,
  saveProviderForm,
  toggleProviderEnabled,
  deleteProviderFromCard,
} = useProviderForm({
  providers,
  activeSection,
  saveProviderMutation,
  toggleProviderMutation,
  deleteProviderMutation,
  loadBundle,
  setFeedback,
  onSaved: () => emit('saved'),
})

/** 供应商表单字段回写（ProviderFormPanel emit update-field；cast 规避 reactive 索引写入的 union 缩窄） */
const updateProviderField = (field: keyof ProviderForm, value: string | boolean) => {
  ;(providerForm as Record<string, string | boolean>)[field] = value
}

const {
  routeSelections,
  chatStageGroups,
  allStageKeys,
  syncRouteSelectionsFromBundle,
  saveRoutes,
  isDirty,
} = useStageRoutes({
  bundleQuery,
  saveStageRoutesMutation,
  providerFormMode,
  setFeedback,
  onSaved: () => emit('saved'),
})
const {
  enabledChatModels,
  primaryChatModel,
  enabledEmbeddingModels,
  defaultEmbeddingModel,
  enabledTTSModels,
  defaultTTSModel,
  configuredRouteCount,
  chatModelsByProvider,
  embeddingModelsByProvider,
  ttsModelsByProvider,
  activeProviders,
  sectionEyebrow,
  sectionHeading,
  sectionDescription,
  sectionReadinessSummary,
} = useSectionMeta({
  providers,
  models,
  activeSection,
  routeSelections,
  allStageKeys,
})
const {
  activeModelPickerProviderId,
  modelPickerQuery,
  pendingChatModelNames,
  pendingTTSModelName,
  isSavingPicker,
  isModelPickerOpen,
  modelPickerStyle,
  isChatPickerDirty,
  setModelPickerDialogRef,
  setModelPickerSearchInputRef,
  openProviderModelPicker,
  closeModelPicker,
} = useModelPicker({
  models,
  activeSection,
  providerFetchState,
  defaultTTSModel,
  ttsModelsByProvider,
  activeProviders,
})

const {
  modelNamesForProvider,
  filteredModelNamesForProvider,
  selectedModelChipsForProvider,
  savedModelForActiveSection,
  isModelSelectedForActiveSection,
  activeModelStateLabel,
  upsertModelForCapability,
  togglePendingChatModel,
  saveChatSelections,
  savePickerSelections,
  setPrimaryChatModel,
  setPrimaryChatModelById,
  selectEmbeddingModel,
  selectPendingTTSModel,
  saveTTSSelection,
  deleteModelForActiveSection,
} = useModelSelection({
  models,
  activeSection,
  chatModelsByProvider,
  embeddingModelsByProvider,
  ttsModelsByProvider,
  primaryChatModel,
  providerFetchState,
  modelPickerQuery,
  activeModelPickerProviderId,
  pendingChatModelNames,
  pendingTTSModelName,
  isSavingPicker,
  closeModelPicker,
  saveUserModelMutation,
  updateUserModelMutation,
  deleteUserModelMutation,
  loadBundle,
  setFeedback,
  onSaved: () => emit('saved'),
})

const providerName = (providerId: number): string =>
  providers.value.find((provider) => provider.id === providerId)?.name || `供应商 ${providerId}`

onMounted(() => {
  void loadBundle()
})

defineExpose({
  isDirty,
  save: async () => {
    if (activeSection.value === 'routes') {
      await saveRoutes()
    } else if (providerFormMode.value) {
      await saveProviderForm()
    } else {
      setFeedback('success', '所有模型配置已同步自动保存，案头大吉。')
    }
  }
})
</script>

<style scoped>
.model-routing {
  display: grid;
  gap: var(--md-spacing-5);
}

.model-routing__topbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--md-spacing-3);
}

.model-routing__topbar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: start;
  gap: var(--md-spacing-4);
}

.model-routing__section-copy {
  min-width: 0;
}

.model-routing__eyebrow {
  margin: 0 0 var(--md-spacing-1);
  color: var(--md-primary-dark);
}

.model-routing__section-copy h3 {
  margin: 0;
  color: var(--md-on-surface);
}

.model-routing__topbar-actions {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: var(--md-spacing-2);
  flex: 0 0 auto;
}


.model-routing__provider-card {
  border: 3px double var(--md-outline);
  border-radius: var(--md-radius-xs);
  padding: var(--md-spacing-4);
  background: var(--md-surface);
  position: relative;
  display: grid;
  gap: var(--md-spacing-3);
  overflow: hidden;
  box-shadow: 2px 2px 0px rgba(28, 32, 34, 0.08);
  transition: box-shadow var(--md-duration-short) var(--md-easing-standard);
}

.model-routing__provider-card::after {
  content: '';
  position: absolute;
  right: -10px;
  bottom: -10px;
  width: 140px;
  height: 160px;
  pointer-events: none;
  z-index: 1;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 120' fill='none' stroke='%231C2022' stroke-width='1' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M70,120 Q65,80 62,40 M62,39 Q60,20 59,0 M63,50 Q45,45 35,55 M61,30 Q80,25 90,32' stroke-width='1.2' opacity='0.035'/%3E%3Cpath d='M35,55 Q20,62 10,68 Q25,60 33,56 Z' fill='%231C2022' opacity='0.025' stroke='none'/%3E%3Cpath d='M33,56 Q15,55 5,50 Q18,53 30,55 Z' fill='%231C2022' opacity='0.025' stroke='none'/%3E%3Cpath d='M90,32 Q105,30 115,35 Q100,33 88,32 Z' fill='%231C2022' opacity='0.025' stroke='none'/%3E%3Cpath d='M88,32 Q102,24 110,18 Q96,25 87,31 Z' fill='%231C2022' opacity='0.025' stroke='none'/%3E%3C/svg%3E");
  background-size: contain;
  background-repeat: no-repeat;
  background-position: right bottom;
}

.model-routing__provider-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 400px), 1fr));
  gap: var(--md-spacing-3);
}

.model-routing__hint,
.model-routing__empty {
  margin: 4px 0 0;
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
}
.model-routing__feedback {
  border-radius: var(--md-radius-md);
  padding: var(--md-spacing-3);
  font-size: var(--md-body-medium);
}

.model-routing__feedback.is-success {
  background-color: var(--md-success-container);
  color: var(--md-on-success-container);
}

.model-routing__feedback.is-error {
  background-color: var(--md-error-container);
  color: var(--md-on-error-container);
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

@media (min-width: 768px) {
  .model-routing__provider-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
  }

  .model-routing__provider-grid > .model-routing__provider-card:only-child {
    grid-column: 1 / -1;
  }

  /* 无论是否为 only-child，只要处于编辑态，就强制跨列，100% 全宽铺满弹窗 */
  .model-routing__provider-grid > .model-routing__provider-card.is-editing {
    grid-column: 1 / -1 !important;
  }
}

@media (max-width: 640px) {
  .model-routing__topbar {
    flex-direction: column;
    align-items: stretch;
  }

  .model-routing__topbar-actions {
    width: 100%;
  }

  .model-routing__topbar-actions .md-btn {
    flex: 1 1 140px;
  }

  .model-routing__topbar {
    grid-template-columns: minmax(0, 1fr);
  }
}

/* 正在编辑中的卡片视觉增强 */
.model-routing__provider-card.is-editing {
  border-style: solid !important;
  border-width: 2px !important;
  border-color: var(--md-primary) !important;
  background: color-mix(in srgb, var(--md-surface) 96%, var(--md-primary)) !important;
  box-shadow: 4px 4px 0px rgba(28, 32, 34, 0.12) !important;
}

.model-routing__provider-card.is-editing::after {
  opacity: 0.01 !important; /* 极度淡化背景竹影 */
}
</style>
