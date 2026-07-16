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

    <div
      :class="['model-routing__readiness', `is-${sectionReadinessSummary.tone}`]"
      :title="sectionReadinessSummary.description"
      aria-label="模型配置状态"
    >
      <span class="model-routing__readiness-label">{{ sectionReadinessSummary.label }}</span>
      <strong class="model-routing__readiness-value">{{ sectionReadinessSummary.value }}</strong>
      <span class="model-routing__readiness-detail">{{ sectionReadinessSummary.description }}</span>
    </div>

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
      <section v-if="providerFormMode === 'create'" class="model-routing__panel model-routing__provider-form">
        <div class="model-routing__form-head">
          <h3 class="md-title-medium">新增供应商</h3>
          <button type="button" class="model-routing__link" @click="cancelProviderForm">
            取消
          </button>
        </div>

        <div class="model-routing__form">
          <label class="md-text-field">
            <span class="md-text-field-label">名称</span>
            <input
              v-model="providerForm.name"
              class="md-text-field-input"
              type="text"
              placeholder="如 OpenAI / Anthropic / DeepSeek / 本地 Ollama"
            />
          </label>

          <label class="md-text-field">
            <span class="md-text-field-label">类型</span>
            <select v-model="providerForm.provider_type" class="md-text-field-input">
              <option value="openai_compatible">OpenAI 兼容</option>
              <option value="anthropic">Anthropic</option>
              <option value="ollama">Ollama</option>
              <option value="custom">自定义</option>
            </select>
          </label>

          <label class="md-text-field">
            <span class="md-text-field-label">API URL</span>
            <input
              v-model="providerForm.base_url"
              class="md-text-field-input"
              type="text"
              placeholder="https://api.example.com/v1"
            />
          </label>

          <label class="md-text-field">
            <span class="md-text-field-label">API Key</span>
            <input
              v-model="providerForm.api_key"
              class="md-text-field-input"
              type="password"
              placeholder="请输入 API Key，Ollama 可留空"
            />
          </label>

          <label class="model-routing__check">
            <input v-model="providerForm.is_enabled" type="checkbox" />
            <span>启用供应商</span>
          </label>

          <button
            type="button"
            class="md-btn md-btn-filled md-ripple"
            :disabled="isSavingProvider"
            @click="saveProviderForm"
          >
            {{ isSavingProvider ? '保存中...' : '保存供应商' }}
          </button>
        </div>
      </section>

      <section
        v-if="activeSection === 'llm'"
        class="model-routing__panel model-routing__primary-panel"
      >
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
            @change="setPrimaryChatModelById"
          >
            <option value="">请先勾选一个文本生成模型</option>
            <option v-for="model in enabledChatModels" :key="model.id" :value="String(model.id)">
              {{ model.display_name }} · {{ providerName(model.provider_id) }}
            </option>
          </select>
        </label>
      </section>

      <div class="model-routing__provider-grid">
        <article
          v-for="provider in activeProviders"
          :key="provider.id"
          :class="[
            'model-routing__provider-card',
            { 'is-editing': providerFormMode === 'edit' && editingProviderId === provider.id }
          ]"
        >
          <!-- 行内编辑表单模式 -->
          <template v-if="providerFormMode === 'edit' && editingProviderId === provider.id">
            <div class="model-routing__inline-form-head">
              <h4 class="md-title-medium">编辑供应商</h4>
              <button type="button" class="model-routing__inline-cancel" @click="cancelProviderForm">
                取消
              </button>
            </div>

            <div class="model-routing__inline-form">
              <label class="md-text-field">
                <span class="md-text-field-label">名称</span>
                <input
                  v-model="providerForm.name"
                  class="md-text-field-input"
                  type="text"
                  placeholder="如 OpenAI / Anthropic / DeepSeek"
                />
              </label>

              <label class="md-text-field">
                <span class="md-text-field-label">类型</span>
                <select v-model="providerForm.provider_type" class="md-text-field-input">
                  <option value="openai_compatible">OpenAI 兼容</option>
                  <option value="anthropic">Anthropic</option>
                  <option value="ollama">Ollama</option>
                  <option value="custom">自定义</option>
                </select>
              </label>

              <label class="md-text-field">
                <span class="md-text-field-label">API URL</span>
                <input
                  v-model="providerForm.base_url"
                  class="md-text-field-input"
                  type="text"
                  placeholder="https://api.example.com/v1"
                />
              </label>

              <label class="md-text-field">
                <span class="md-text-field-label">API Key</span>
                <input
                  v-model="providerForm.api_key"
                  class="md-text-field-input"
                  type="password"
                  placeholder="留空则保留已保存 Key"
                />
              </label>

              <div class="model-routing__inline-form-footer">
                <label class="model-routing__check">
                  <input v-model="providerForm.is_enabled" type="checkbox" />
                  <span>启用供应商</span>
                </label>

                <button
                  type="button"
                  class="md-btn md-btn-filled md-ripple"
                  :disabled="isSavingProvider"
                  @click="saveProviderForm"
                >
                  {{ isSavingProvider ? '保存中...' : '保存供应商' }}
                </button>
              </div>
            </div>
          </template>

          <!-- 常态展示模式 -->
          <template v-else>
            <header class="model-routing__provider-head">
              <div class="model-routing__provider-main">
                <div class="model-routing__provider-title-row">
                  <h3 class="md-title-medium">{{ provider.name }}</h3>
                  <span
                    :class="[
                      'model-routing__provider-state',
                      provider.is_enabled ? 'is-enabled' : 'is-disabled',
                    ]"
                  >
                    {{ provider.is_enabled ? '已启用' : '已停用' }}
                  </span>
                </div>
                <div class="model-routing__provider-meta">
                  <span class="model-routing__provider-type">
                    {{ providerTypeLabel(provider.provider_type) }}
                  </span>
                  <span>{{ providerKeyLabel(provider) }}</span>
                </div>
                <p class="model-routing__provider-url">{{ provider.base_url }}</p>
              </div>
              <div class="model-routing__provider-card-actions">
                <button
                  type="button"
                  :class="['model-routing__toggle', provider.is_enabled ? 'is-on' : 'is-off']"
                  :disabled="isSavingProvider"
                  @click="toggleProviderEnabled(provider)"
                >
                  {{ provider.is_enabled ? '停用' : '启用' }}
                </button>
                <button
                  type="button"
                  class="model-routing__provider-delete"
                  :disabled="isSavingProvider"
                  :aria-label="`删除供应商 ${provider.name}`"
                  @click="deleteProviderFromCard(provider)"
                >
                  删除供应商
                </button>
              </div>
            </header>

            <div class="model-routing__provider-actions">
              <button
                type="button"
                class="md-btn md-btn-text md-ripple"
                @click="beginEditProvider(provider)"
              >
                编辑供应商
              </button>
              <button
                type="button"
                class="md-btn md-btn-tonal md-ripple"
                :disabled="!provider.is_enabled || providerFetchState(provider.id).isLoading"
                aria-haspopup="dialog"
                :aria-expanded="isModelPickerOpen(provider.id)"
                :aria-controls="`model-picker-${provider.id}`"
                @click="openProviderModelPicker(provider, $event)"
              >
                {{ providerFetchState(provider.id).isLoading ? '拉取中...' : '拉取模型' }}
              </button>
            </div>

          <Teleport to="body">
            <div
              v-if="isModelPickerOpen(provider.id)"
              :id="`model-picker-${provider.id}`"
              :ref="setModelPickerDialogRef"
              class="model-routing__model-picker"
              role="dialog"
              aria-modal="false"
              :style="modelPickerStyle"
              :aria-labelledby="`model-picker-title-${provider.id}`"
              @keydown.esc.stop.prevent="!isSavingPicker && closeModelPicker()"
              @click.stop
            >
              <div class="model-routing__picker-head">
                <div>
                  <strong :id="`model-picker-title-${provider.id}`">{{
                    activeSection === 'llm'
                      ? '选择文本生成模型'
                      : activeSection === 'embedding'
                        ? '选择记忆检索模型'
                        : '选择语音朗读模型'
                  }}</strong>
                  <p class="model-routing__hint">
                    {{
                      activeSection === 'llm'
                        ? '勾选后点右上角"保存"生效。'
                        : activeSection === 'embedding'
                          ? '单选后作为当前检索模型。'
                          : '选择默认语音朗读模型；音色与倍速在朗读控件里调整。'
                    }}
                  </p>
                </div>
                <button
                  v-if="activeSection === 'tts' || !isChatPickerDirty"
                  type="button"
                  class="model-routing__link"
                  :disabled="isSavingPicker"
                  @click="closeModelPicker"
                >
                  关闭
                </button>
                <button
                  v-if="activeSection === 'tts' || isChatPickerDirty"
                  type="button"
                  class="md-btn md-btn-filled md-ripple model-routing__picker-save"
                  :disabled="isSavingPicker"
                  @click="savePickerSelections(provider)"
                >
                  {{ isSavingPicker ? '保存中...' : '保存' }}
                </button>
              </div>

              <label class="md-text-field model-routing__picker-search">
                <span class="md-text-field-label">搜索模型</span>
                <input
                  :ref="setModelPickerSearchInputRef"
                  data-dialog-initial-focus
                  v-model="modelPickerQuery"
                  class="md-text-field-input"
                  type="search"
                  placeholder="输入模型名过滤"
                />
              </label>

              <p v-if="providerFetchState(provider.id).isLoading" class="model-routing__empty">
                正在拉取模型...
              </p>
              <p
                v-else-if="filteredModelNamesForProvider(provider.id).length === 0"
                class="model-routing__empty"
              >
                没有可选模型。
              </p>
              <div v-else class="model-routing__picker-list">
                <label
                  v-for="modelName in filteredModelNamesForProvider(provider.id)"
                  :key="`${provider.id}-${modelName}`"
                  :class="[
                    'model-routing__picker-row',
                    {
                      'is-selected': isModelSelectedForActiveSection(provider.id, modelName),
                    },
                  ]"
                >
                  <span class="model-routing__picker-model-name">
                    {{ modelName }}
                    <small v-if="activeModelStateLabel(provider.id, modelName)">
                      {{ activeModelStateLabel(provider.id, modelName) }}
                    </small>
                  </span>
                  <input
                    v-if="activeSection === 'llm'"
                    type="checkbox"
                    :checked="pendingChatModelNames.has(modelName)"
                    :disabled="!provider.is_enabled"
                    :aria-label="`启用文本生成模型 ${modelName}`"
                    @change="togglePendingChatModel(provider, modelName, $event)"
                  />
                  <input
                    v-else-if="activeSection === 'embedding'"
                    name="embedding-model"
                    type="radio"
                    :checked="
                      Boolean(
                        embeddingModelForName(provider.id, modelName)?.is_enabled &&
                        embeddingModelForName(provider.id, modelName)?.is_default_embedding,
                      )
                    "
                    :disabled="!provider.is_enabled"
                    :aria-label="`选择向量模型 ${modelName}`"
                    @change="selectEmbeddingModel(provider, modelName)"
                  />
                  <input
                    v-else
                    name="tts-model"
                    type="radio"
                    :checked="pendingTTSModelName === modelName"
                    :disabled="!provider.is_enabled || isSavingPicker"
                    :aria-label="`选择语音朗读模型 ${modelName}`"
                    @change="selectPendingTTSModel(provider, modelName)"
                  />
                </label>
              </div>

            </div>
          </Teleport>

            <p v-if="!provider.is_enabled" class="model-routing__hint">
              启用供应商后才能使用里面的模型。
            </p>
            <p v-if="providerFetchState(provider.id).error" class="model-routing__hint is-error">
              {{ providerFetchState(provider.id).error }}
            </p>

            <div class="model-routing__selected-models">
              <p class="md-label-medium model-routing__model-list-title">
                {{
                  activeSection === 'llm'
                    ? '已选文本生成模型'
                    : activeSection === 'embedding'
                      ? '已选检索模型'
                      : '已选语音朗读模型'
                }}
              </p>
              <p
                v-if="selectedModelChipsForProvider(provider.id).length === 0"
                class="model-routing__empty"
              >
                点击"拉取模型"后勾选模型。
              </p>
              <div v-else class="model-routing__selected-chip-list">
                <span
                  v-for="chip in selectedModelChipsForProvider(provider.id)"
                  :key="chip.id"
                  class="model-routing__selected-chip"
                >
                  <span class="model-routing__chip-name">{{ chip.display_name || chip.model_name }}</span>
                  <small v-if="activeSection === 'llm' && chip.is_default_chat" class="model-routing__stamp-label">主</small>
                  <small v-else-if="activeSection === 'embedding' && chip.is_default_embedding" class="model-routing__stamp-label">用</small>
                  <small v-else-if="activeSection === 'tts' && chip.is_default_tts" class="model-routing__stamp-label">读</small>
                  <button
                    type="button"
                    class="model-routing__delete-btn"
                    :aria-label="`删除模型 ${chip.display_name || chip.model_name}`"
                    :title="`删除模型 ${chip.display_name || chip.model_name}`"
                    @click="deleteModelForActiveSection(provider, chip.model_name)"
                  >
                    删除
                  </button>
                </span>
              </div>
            </div>
          </template>
        </article>
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
import type {
  UserModelProvider,
} from '@/api/llm'
import { useModelBundle } from '@/composables/useModelBundle'
import { useSectionMeta } from './useSectionMeta'
import { useStageRoutes } from './useStageRoutes'
import { useProviderForm } from './useProviderForm'
import { useModelPicker } from './useModelPicker'
import { useModelSelection } from './useModelSelection'
import { RoutingStagesPanel } from './RoutingStagesPanel'
import type {
  RoutingSection,
} from './modelRoutingTypes'
import {
  providerTypeLabel,
} from './modelRoutingHelpers'

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

const providerKeyLabel = (provider: UserModelProvider): string =>
  provider.api_key_preview ? `Key ${provider.api_key_preview}` : '未保存 Key'

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

.model-routing__topbar,
.model-routing__form-head,
.model-routing__provider-head,
.model-routing__model-row {
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

.model-routing__panel {
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-sm);
  padding: var(--md-spacing-4);
  background: var(--md-surface);
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


.model-routing__form,
.model-routing__model-list,
.model-routing__selected-models {
  display: grid;
  gap: var(--md-spacing-3);
}

.model-routing__provider-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 400px), 1fr));
  gap: var(--md-spacing-3);
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

.model-routing__provider-head h3,
.model-routing__form-head h3 {
  margin: 0;
  color: var(--md-on-surface);
}

.model-routing__provider-head p,
.model-routing__hint,
.model-routing__empty {
  margin: 4px 0 0;
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
}

.model-routing__provider-url {
  display: block;
  max-width: 100%;
  margin-top: var(--md-spacing-2);
  color: var(--md-on-surface-variant);
  font-family: var(--md-font-mono);
  font-size: var(--md-body-small);
  word-break: break-all;
}

.model-routing__provider-main {
  min-width: 0;
}

.model-routing__provider-title-row,
.model-routing__provider-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--md-spacing-2);
}

.model-routing__provider-state,
.model-routing__provider-type {
  display: inline-flex;
  align-items: center;
  min-height: 26px;
  border-radius: var(--md-radius-xs);
  padding: 0 10px;
  font-size: var(--md-label-small);
  font-weight: 600;
  white-space: nowrap;
}

.model-routing__provider-state.is-enabled {
  background: var(--md-success-container);
  color: var(--md-on-success-container);
}

.model-routing__provider-state.is-disabled {
  background: var(--md-surface-container-high);
  color: var(--md-on-surface-variant);
}

.model-routing__provider-type {
  border: 1px solid var(--md-outline-variant);
  background: var(--md-surface);
  color: var(--md-on-surface);
}

.model-routing__provider-meta {
  margin-top: var(--md-spacing-2);
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
}

.model-routing__provider-card-actions {
  display: inline-flex;
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: var(--md-spacing-2);
}

.model-routing__model-list-title {
  margin: 0;
  color: var(--md-on-surface-variant);
}

.model-routing__model-picker {
  position: fixed;
  z-index: 1050;
  width: min(420px, calc(100vw - 16px));
  max-height: 420px;
  overflow: auto;
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-sm);
  padding: var(--md-spacing-3);
  background: var(--md-surface);
  box-shadow: 2px 2px 0px rgba(28, 32, 34, 0.15);
}

.model-routing__picker-head,
.model-routing__picker-row,
.model-routing__selected-chip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--md-spacing-3);
}

.model-routing__picker-head {
  margin-bottom: var(--md-spacing-3);
  color: var(--md-on-surface);
}

.model-routing__picker-search {
  margin-bottom: var(--md-spacing-3);
}

.model-routing__picker-list {
  display: grid;
  gap: var(--md-spacing-1);
}

.model-routing__picker-row {
  min-height: 44px;
  border: 1px solid transparent;
  border-radius: var(--md-radius-xs);
  padding: var(--md-spacing-2) var(--md-spacing-3);
  color: var(--md-on-surface);
  cursor: pointer;
  transition:
    background-color var(--md-duration-short) var(--md-easing-standard),
    border-color var(--md-duration-short) var(--md-easing-standard);
}

.model-routing__picker-row:hover {
  background: var(--md-surface-container);
}

.model-routing__picker-row.is-selected {
  border-color: var(--md-primary);
  background: var(--md-primary-container);
  color: var(--md-on-primary-container);
}

.model-routing__picker-model-name {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: var(--md-spacing-2);
}

.model-routing__picker-model-name,
.model-routing__picker-model-name > small {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.model-routing__picker-model-name > small {
  flex: 0 0 auto;
  border-radius: var(--md-radius-xs);
  padding: 2px 6px;
  background: var(--md-surface);
  color: var(--md-primary-dark);
  font-size: var(--md-label-small);
  font-weight: 600;
}

.model-routing__selected-chip-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: var(--md-spacing-2);
}

.model-routing__selected-chip {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 38px;
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-xs);
  padding: 6px 8px 6px 12px;
  background: var(--md-surface-container);
  color: var(--md-on-surface);
  box-shadow: 1px 1px 0px rgba(28, 32, 34, 0.04);
  transition:
    background-color var(--md-duration-short) var(--md-easing-standard),
    border-color var(--md-duration-short) var(--md-easing-standard),
    box-shadow var(--md-duration-short) var(--md-easing-standard),
    color var(--md-duration-short) var(--md-easing-standard),
    opacity var(--md-duration-short) var(--md-easing-standard),
    transform var(--md-duration-short) var(--md-easing-standard);
  cursor: default;
}

.model-routing__selected-chip:hover {
  background: var(--md-surface-container-high);
  border-color: var(--md-outline);
  box-shadow: 2px 2px 0px rgba(28, 32, 34, 0.1);
}

.model-routing__selected-chip > span.model-routing__chip-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--md-body-small);
  padding-right: 18px; /* 固定右内边距，为删除按钮预留空间，静止稳定且无 layout-transition 隐患 */
  flex: 1 1 0%;
}

.model-routing__selected-chip .model-routing__stamp-label {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 1px;
  padding: 1px 4px;
  background: var(--md-secondary);
  color: var(--md-on-primary);
  font-family: var(--md-font-display);
  font-size: 10px;
  font-weight: 700;
  line-height: 1;
  letter-spacing: 0.03em;
  white-space: nowrap;
  border: 1px solid rgba(184, 60, 50, 0.2);
  margin-left: 4px;
  box-shadow: 1px 1px 0px rgba(184, 60, 50, 0.15);
  flex-shrink: 0;
}


.model-routing__model-row {
  width: 100%;
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-sm);
  background: var(--md-surface);
  color: var(--md-on-surface);
  padding: var(--md-spacing-3);
  text-align: left;
  cursor: pointer;
}

.model-routing__model-row:hover:not(.is-disabled) {
  border-color: var(--md-primary);
  background: var(--md-primary-container);
  color: var(--md-on-primary-container);
}

.model-routing__model-row.is-disabled {
  cursor: not-allowed;
  opacity: 0.7;
}

.model-routing__model-row strong {
  display: block;
  font-size: var(--md-body-medium);
}

.model-routing__model-row small {
  display: block;
  margin-top: 2px;
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
}

.model-routing__model-controls {
  display: inline-flex;
  align-items: center;
  gap: var(--md-spacing-2);
}

.model-routing__delete-btn {
  position: absolute;
  right: 6px;
  top: 50%;
  transform: translateY(-50%) scale(0.8);
  border: none;
  background: transparent;
  color: var(--md-secondary);
  cursor: pointer;
  font-size: 16px;
  line-height: 1;
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  pointer-events: none;
  transition:
    background-color var(--md-duration-short) var(--md-easing-standard),
    border-color var(--md-duration-short) var(--md-easing-standard),
    box-shadow var(--md-duration-short) var(--md-easing-standard),
    color var(--md-duration-short) var(--md-easing-standard),
    opacity var(--md-duration-short) var(--md-easing-standard),
    transform var(--md-duration-short) var(--md-easing-standard);
  border-radius: var(--md-radius-xs);
}

.model-routing__delete-btn::before {
  content: '';
  position: absolute;
  top: -11px;
  bottom: -11px;
  left: -11px;
  right: -11px;
}

.model-routing__selected-chip:hover .model-routing__delete-btn {
  opacity: 1;
  transform: translateY(-50%) scale(1);
  pointer-events: auto;
}

.model-routing__delete-btn:hover {
  color: var(--md-error);
  transform: translateY(-50%) scale(1.15) !important;
  text-shadow: 1px 1px 0px rgba(184, 60, 50, 0.2);
}

.model-routing__toggle {
  position: relative;
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-xs);
  min-width: 48px;
  min-height: 28px;
  padding: 0 8px;
  cursor: pointer;
  font-size: var(--md-label-small);
  font-weight: 600;
  white-space: nowrap;
  opacity: 0.35;
  transition:
    background-color var(--md-duration-short) var(--md-easing-standard),
    border-color var(--md-duration-short) var(--md-easing-standard),
    box-shadow var(--md-duration-short) var(--md-easing-standard),
    color var(--md-duration-short) var(--md-easing-standard),
    opacity var(--md-duration-short) var(--md-easing-standard),
    transform var(--md-duration-short) var(--md-easing-standard);
  background: transparent;
  color: var(--md-on-surface-variant);
  z-index: 2;
}

.model-routing__toggle::before {
  content: '';
  position: absolute;
  top: -8px;
  bottom: -8px;
  left: -4px;
  right: -4px;
}

.model-routing__toggle:disabled,
.model-routing__provider-delete:disabled {
  cursor: not-allowed;
  opacity: 0.15 !important;
}

.model-routing__toggle.is-on {
  border: 1px solid var(--md-outline);
  background: var(--md-surface-container);
  color: var(--md-primary-dark);
}

.model-routing__toggle.is-off {
  background: var(--md-surface-container-high);
  color: var(--md-on-surface-variant);
}

.model-routing__toggle:hover:not(:disabled) {
  opacity: 1;
  border-color: var(--md-primary);
  background: var(--md-primary);
  color: var(--md-on-primary);
  box-shadow: 1px 1px 0px rgba(28, 32, 34, 0.15);
}

.model-routing__provider-delete {
  position: relative;
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-xs);
  min-width: 48px;
  min-height: 28px;
  padding: 0 8px;
  background: transparent;
  color: var(--md-on-surface-variant);
  cursor: pointer;
  font-size: var(--md-label-small);
  font-weight: 600;
  white-space: nowrap;
  opacity: 0.25;
  transition:
    background-color var(--md-duration-short) var(--md-easing-standard),
    border-color var(--md-duration-short) var(--md-easing-standard),
    box-shadow var(--md-duration-short) var(--md-easing-standard),
    color var(--md-duration-short) var(--md-easing-standard),
    opacity var(--md-duration-short) var(--md-easing-standard),
    transform var(--md-duration-short) var(--md-easing-standard);
  z-index: 2;
}

.model-routing__provider-delete::before {
  content: '';
  position: absolute;
  top: -8px;
  bottom: -8px;
  left: -4px;
  right: -4px;
}

.model-routing__provider-delete:hover:not(:disabled) {
  opacity: 1;
  background: var(--md-secondary);
  color: var(--md-on-primary);
  border-color: rgba(184, 60, 50, 0.3);
  box-shadow: 1px 1px 0px rgba(184, 60, 50, 0.2);
}

.model-routing__check {
  display: inline-flex;
  align-items: center;
  gap: var(--md-spacing-2);
  color: var(--md-on-surface);
  font-size: var(--md-body-medium);
  min-height: 44px;
  cursor: pointer;
}

.model-routing__check input,
.model-routing__model-controls input,
.model-routing__picker-row input {
  width: 20px;
  height: 20px;
  flex: 0 0 auto;
}

.model-routing__link {
  border: none;
  background: transparent;
  color: var(--md-primary-dark);
  cursor: pointer;
  font-weight: 600;
  min-height: 44px;
  padding: 0 var(--md-spacing-2);
}

.model-routing__link:focus-visible,
.model-routing__delete-btn:focus-visible,
.model-routing__toggle:focus-visible,
.model-routing__provider-delete:focus-visible,
.model-routing__picker-row:focus-within {
  outline: 2px solid var(--md-primary);
  outline-offset: 2px;
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

.model-routing__feedback.is-error,
.model-routing__hint.is-error {
  background-color: var(--md-error-container);
  color: var(--md-on-error-container);
}

.model-routing__hint.is-error {
  border-radius: var(--md-radius-md);
  padding: var(--md-spacing-2);
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

@media (max-width: 860px) {
  .model-routing__primary-panel {
    grid-template-columns: minmax(0, 1fr);
  }
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

  /* 原地编辑表单内部排版升级：名称与类型并排，API 地址和 API Key 独占一行，空间拉满 */
  .model-routing__inline-form {
    grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
    gap: var(--md-spacing-3) var(--md-spacing-4) !important;
  }

  .model-routing__inline-form > .md-text-field:nth-child(1),
  .model-routing__inline-form > .md-text-field:nth-child(2) {
    grid-column: span 1;
  }

  .model-routing__inline-form > .md-text-field:nth-child(3), /* API URL */
  .model-routing__inline-form > .md-text-field:nth-child(4), /* API Key */
  .model-routing__inline-form-footer {
    grid-column: 1 / -1 !important;
  }
}

@media (max-width: 640px) {
  .model-routing__topbar,
  .model-routing__form-head,
  .model-routing__provider-head,
  .model-routing__provider-actions,
  .model-routing__model-row {
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

  .model-routing__model-picker {
    max-height: 360px;
  }
}

.model-routing__provider-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--md-spacing-2);
  margin-top: var(--md-spacing-1);
  position: relative;
  z-index: 2;
}

/* 拉取模型：朱砂印章主按钮 */
.model-routing__provider-actions .md-btn-tonal {
  position: relative;
  border: 1px solid rgba(184, 60, 50, 0.35);
  border-radius: var(--md-radius-xs) !important;
  background: var(--md-secondary) !important;
  color: var(--md-on-primary) !important;
  font-family: var(--md-font-label);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.05em;
  height: 34px;
  padding: 0 16px;
  box-shadow: 2px 2px 0px rgba(184, 60, 50, 0.25);
  transition:
    background-color var(--md-duration-short) var(--md-easing-standard),
    border-color var(--md-duration-short) var(--md-easing-standard),
    box-shadow var(--md-duration-short) var(--md-easing-standard),
    color var(--md-duration-short) var(--md-easing-standard),
    opacity var(--md-duration-short) var(--md-easing-standard),
    transform var(--md-duration-short) var(--md-easing-standard);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.model-routing__provider-actions .md-btn-tonal::before {
  content: '';
  position: absolute;
  top: -5px;
  bottom: -5px;
  left: -4px;
  right: -4px;
}

.model-routing__provider-actions .md-btn-tonal:hover:not(:disabled) {
  background: var(--md-error-strong) !important;
  box-shadow: 3px 3px 0px rgba(184, 60, 50, 0.35);
}

.model-routing__provider-actions .md-btn-tonal:active:not(:disabled) {
  transform: translate(1px, 1px);
  box-shadow: 1px 1px 0px rgba(184, 60, 50, 0.15);
}

.model-routing__provider-actions .md-btn-tonal:disabled {
  background: var(--md-surface-container-high) !important;
  color: var(--md-on-surface-variant) !important;
  border-color: var(--md-outline-variant);
  box-shadow: none;
  cursor: not-allowed;
}

/* 编辑供应商：次级古籍框线按钮 */
.model-routing__provider-actions .md-btn-text {
  position: relative;
  border: 1px solid var(--md-outline);
  border-radius: var(--md-radius-xs) !important;
  background: transparent !important;
  color: var(--md-primary) !important;
  font-family: var(--md-font-label);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.02em;
  height: 34px;
  padding: 0 16px;
  transition:
    background-color var(--md-duration-short) var(--md-easing-standard),
    border-color var(--md-duration-short) var(--md-easing-standard),
    box-shadow var(--md-duration-short) var(--md-easing-standard),
    color var(--md-duration-short) var(--md-easing-standard),
    opacity var(--md-duration-short) var(--md-easing-standard),
    transform var(--md-duration-short) var(--md-easing-standard);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.model-routing__provider-actions .md-btn-text::before {
  content: '';
  position: absolute;
  top: -5px;
  bottom: -5px;
  left: -4px;
  right: -4px;
}

.model-routing__provider-actions .md-btn-text:hover {
  background: var(--md-surface-container-high) !important;
  border-color: var(--md-primary);
}

.model-routing__provider-actions .md-btn-text:active {
  transform: translate(1px, 1px);
}

/* 卡片原地编辑表单样式 */
.model-routing__inline-form-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px dashed var(--md-outline-variant);
  padding-bottom: var(--md-spacing-2);
  margin-bottom: var(--md-spacing-2);
}

.model-routing__inline-form-head h4 {
  margin: 0;
  color: var(--md-primary-dark);
}

.model-routing__inline-cancel {
  border: none;
  background: transparent;
  color: var(--md-on-surface-variant);
  cursor: pointer;
  font-size: var(--md-label-small);
  font-weight: 600;
  transition: color var(--md-duration-short) var(--md-easing-standard);
  min-height: 28px;
  padding: 0 var(--md-spacing-2);
}

.model-routing__inline-cancel:hover {
  color: var(--md-secondary);
}

.model-routing__inline-form {
  display: grid;
  gap: var(--md-spacing-3);
  z-index: 2;
  position: relative;
}

.model-routing__inline-form-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: var(--md-spacing-2);
  gap: var(--md-spacing-3);
  flex-wrap: wrap;
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
