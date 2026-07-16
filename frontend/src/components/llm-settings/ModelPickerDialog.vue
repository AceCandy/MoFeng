<template>
  <!-- 模型拉取弹窗（Teleport to body）：按能力勾选/单选模型，含搜索过滤；外部点击与视口关闭由父级 useModelPicker 的 document/window 监听处理 -->
  <Teleport to="body">
    <div
      :id="`model-picker-${provider.id}`"
      :ref="setModelPickerDialogRef"
      class="model-routing__model-picker"
      role="dialog"
      aria-modal="false"
      :style="modelPickerStyle"
      :aria-labelledby="`model-picker-title-${provider.id}`"
      @keydown.esc.stop.prevent="!isSavingPicker && emit('close')"
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

      <label class="md-text-field model-routing__picker-search">
        <span class="md-text-field-label">搜索模型</span>
        <input
          :ref="setModelPickerSearchInputRef"
          data-dialog-initial-focus
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
            @change="emit('toggle-chat', modelName, $event)"
          />
          <input
            v-else-if="activeSection === 'embedding'"
            name="embedding-model"
            type="radio"
            :checked="
              Boolean(
                savedModelForActiveSection(provider.id, modelName)?.is_enabled &&
                savedModelForActiveSection(provider.id, modelName)?.is_default_embedding,
              )
            "
            :disabled="!provider.is_enabled"
            :aria-label="`选择向量模型 ${modelName}`"
            @change="emit('select-embedding', modelName)"
          />
          <input
            v-else
            name="tts-model"
            type="radio"
            :checked="pendingTTSModelName === modelName"
            :disabled="!provider.is_enabled || isSavingPicker"
            :aria-label="`选择语音朗读模型 ${modelName}`"
            @change="emit('select-tts', modelName)"
          />
        </label>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import type { ComponentPublicInstance, StyleValue } from 'vue'
import type { UserAIModel, UserModelProvider } from '@/api/llm'
import type { ProviderFetchState, RoutingSection } from './modelRoutingTypes'

defineProps<{
  provider: UserModelProvider
  activeSection: RoutingSection
  modelPickerStyle: StyleValue
  isSavingPicker: boolean
  isChatPickerDirty: boolean
  modelPickerQuery: string
  pendingChatModelNames: Set<string>
  pendingTTSModelName: string
  filteredModelNamesForProvider: (providerId: number) => string[]
  isModelSelectedForActiveSection: (providerId: number, modelName: string) => boolean
  activeModelStateLabel: (providerId: number, modelName: string) => string
  savedModelForActiveSection: (providerId: number, modelName: string) => UserAIModel | undefined
  providerFetchState: (providerId: number) => ProviderFetchState
  setModelPickerDialogRef: (el: Element | ComponentPublicInstance | null) => void
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
.model-routing__picker-row {
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

/* picker-row 内 input 尺寸（原父 .model-controls input,.picker-row input 混合选择器拆分；.model-controls 留父属既有死代码） */
.model-routing__picker-row input {
  width: 20px;
  height: 20px;
  flex: 0 0 auto;
}

/* 关闭链接按钮（原父 .model-routing__link 随弹窗迁入；父已无 .link 消费） */
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
.model-routing__picker-row:focus-within {
  outline: 2px solid var(--md-primary);
  outline-offset: 2px;
}

/* hint/empty 共用样式（复制自父 .provider-head p,.hint,.empty 混合规则；父多处仍消费） */
.model-routing__hint,
.model-routing__empty {
  margin: 4px 0 0;
  color: var(--md-on-surface-variant);
  font-size: var(--md-body-small);
}

@media (max-width: 640px) {
  .model-routing__model-picker {
    max-height: 360px;
  }
}
</style>
