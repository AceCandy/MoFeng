<!-- AIMETA P=模型选择面板_供应商模型拉取|R=模型搜索与勾选|NR=不含picker状态与保存副作用|E=component:ModelPickerPanel|X=internal|A=模型选择面板|D=vue|S=dom|RD=./README.ai -->
<template>
  <section
    :id="`model-picker-${provider.id}`"
    class="model-routing__model-picker"
    :aria-labelledby="`model-picker-title-${provider.id}`"
    @keydown.esc.stop.prevent="!isSavingPicker && emit('close')"
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
              ? '勾选后保存生效。'
              : activeSection === 'embedding'
                ? '选择后作为当前检索模型。'
                : '选择默认朗读模型；音色与倍速在朗读控件里调整。'
          }}
        </p>
      </div>
      <div class="model-routing__picker-actions">
        <button
          type="button"
          class="model-routing__link"
          :disabled="isSavingPicker"
          @click="emit('close')"
        >
          关闭
        </button>
        <button
          v-if="activeSection === 'tts' || isChatPickerDirty"
          type="button"
          class="md-btn md-btn-filled md-ripple model-routing__picker-save"
          :disabled="isSavingPicker"
          @click="emit('save')"
        >
          {{ isSavingPicker ? '保存中...' : '保存' }}
        </button>
      </div>
    </div>

    <label class="md-text-field model-routing__picker-search">
      <span class="md-text-field-label">搜索模型</span>
      <input
        :ref="setModelPickerSearchInputRef"
        :value="modelPickerQuery"
        class="md-text-field-input"
        type="search"
        placeholder="输入模型名过滤"
        @input="onSearchInput"
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
          { 'is-selected': isModelSelectedForActiveSection(provider.id, modelName) },
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
          @change="emit('toggle-chat', modelName, $event)"
        />
        <input
          v-else-if="activeSection === 'embedding'"
          name="embedding-model"
          type="radio"
          :checked="Boolean(
            savedModelForActiveSection(provider.id, modelName)?.is_enabled &&
            savedModelForActiveSection(provider.id, modelName)?.is_default_embedding
          )"
          :disabled="!provider.is_enabled"
          :aria-label="`选择向量模型 ${modelName}`"
          @change="emit('select-embedding', modelName)"
        />
        <input
          v-else
          name="tts-model"
          type="radio"
          :checked="isModelSelectedForActiveSection(provider.id, modelName)"
          :disabled="!provider.is_enabled || isSavingPicker"
          :aria-label="`选择语音朗读模型 ${modelName}`"
          @change="emit('select-tts', modelName)"
        />
      </label>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { ComponentPublicInstance } from 'vue'
import type { UserAIModel, UserModelProvider } from '@/api/llm'
import type { ProviderFetchState, RoutingSection } from './modelRoutingTypes'

defineProps<{
  provider: UserModelProvider
  activeSection: RoutingSection
  isSavingPicker: boolean
  isChatPickerDirty: boolean
  modelPickerQuery: string
  pendingChatModelNames: Set<string>
  filteredModelNamesForProvider: (providerId: number) => string[]
  isModelSelectedForActiveSection: (providerId: number, modelName: string) => boolean
  activeModelStateLabel: (providerId: number, modelName: string) => string
  savedModelForActiveSection: (providerId: number, modelName: string) => UserAIModel | undefined
  providerFetchState: (providerId: number) => ProviderFetchState
  setModelPickerSearchInputRef: (el: Element | ComponentPublicInstance | null) => void
}>()

const emit = defineEmits<{
  (event: 'update-query', value: string): void
  (event: 'toggle-chat', modelName: string, changeEvent: Event): void
  (event: 'select-embedding', modelName: string): void
  (event: 'select-tts', modelName: string): void
  (event: 'save'): void
  (event: 'close'): void
}>()

const onSearchInput = (event: Event) => {
  emit('update-query', (event.target as HTMLInputElement).value)
}
</script>

<style scoped>
.model-routing__model-picker {
  grid-column: 1 / -1;
  width: 100%;
  padding: var(--md-spacing-4);
  border: 1px solid var(--md-outline);
  border-radius: var(--md-radius-xs);
  background: var(--md-surface-container-low);
}

.model-routing__picker-head,
.model-routing__picker-row,
.model-routing__picker-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--md-spacing-3);
}

.model-routing__picker-head {
  margin-bottom: var(--md-spacing-3);
  color: var(--md-on-surface);
}

.model-routing__picker-actions {
  flex: 0 0 auto;
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
  padding: var(--md-spacing-2) var(--md-spacing-3);
  border: 1px solid transparent;
  border-radius: var(--md-radius-xs);
  color: var(--md-on-surface);
  cursor: pointer;
}

.model-routing__picker-row:hover,
.model-routing__picker-row.is-selected {
  border-color: var(--md-primary);
  background: var(--md-surface-container);
}

.model-routing__picker-model-name {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: var(--md-spacing-2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.model-routing__picker-model-name > small {
  flex: 0 0 auto;
  padding: 2px 6px;
  border-radius: var(--md-radius-xs);
  background: var(--md-surface);
  color: var(--md-primary-dark);
  font-size: var(--md-label-small);
  font-weight: 600;
}

.model-routing__picker-row input {
  width: 20px;
  height: 20px;
  flex: 0 0 auto;
}

.model-routing__link:focus-visible,
.model-routing__picker-row:focus-within {
  outline: 2px solid var(--md-primary);
  outline-offset: 2px;
}

@media (max-width: 600px) {
  .model-routing__picker-head {
    align-items: flex-start;
    flex-direction: column;
  }

  .model-routing__picker-actions {
    width: 100%;
    justify-content: flex-end;
  }
}
</style>
