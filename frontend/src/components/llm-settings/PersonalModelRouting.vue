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

    <FeedbackPanel v-if="feedback.message" :feedback="feedback" />

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
            :save-model-pricing="saveModelPricing"
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
            @update-query="modelPickerQuery = $event"
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
import FeedbackPanel from './FeedbackPanel.vue'
import ReadinessPanel from './ReadinessPanel.vue'
import RoutingStagesPanel from './RoutingStagesPanel.vue'
import ProviderFormPanel from './ProviderFormPanel.vue'
import PrimaryModelPanel from './PrimaryModelPanel.vue'
import ModelPickerDialog from './ModelPickerDialog.vue'
import SelectedModelChips from './SelectedModelChips.vue'
import ProviderCard from './ProviderCard.vue'
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
  saveModelPricing,
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
  color: var(--md-on-surface-variant); /* 宋体题签 */
}

.model-routing__section-copy h3 {
  margin: 0;
  color: var(--md-on-surface);
  letter-spacing: 0.03em; /* 碑拓骨力：宋体小标题拉开字距 */
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
  border: 1px solid var(--md-jiege); /* 1px 界格发线 */
  border-radius: var(--md-radius-xs);
  padding: var(--md-spacing-4);
  background: var(--md-surface);
  position: relative;
  display: grid;
  gap: var(--md-spacing-3);
  transition: box-shadow var(--md-duration-short) var(--md-easing-standard);
}

.model-routing__provider-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 400px), 1fr));
  gap: var(--md-spacing-3);
}

.model-routing__provider-grid > .model-routing__provider-card:only-child {
  grid-column: 1 / -1;
}

/* 处于编辑态的卡片强制跨列，100% 全宽铺满 */
.model-routing__provider-grid > .model-routing__provider-card.is-editing {
  grid-column: 1 / -1;
}

@media (max-width: 640px) {
  .model-routing__topbar {
    grid-template-columns: minmax(0, 1fr);
  }

  .model-routing__topbar-actions {
    width: 100%;
  }

  .model-routing__topbar-actions .md-btn {
    flex: 1 1 140px;
  }
}

/* 正在编辑中的卡片视觉增强：焦墨发线 + 浮起纸页 */
.model-routing__provider-card.is-editing {
  border-style: solid !important;
  border-width: 1px !important;
  border-color: var(--md-primary) !important;
  background: color-mix(in srgb, var(--md-surface) 96%, var(--md-primary)) !important;
  box-shadow: var(--md-elevation-paper-1) !important;
}
</style>
