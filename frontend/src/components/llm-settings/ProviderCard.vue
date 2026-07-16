<!-- AIMETA P=供应商卡片_单个供应商展示与操作|R=卡片展示+编辑/拉取/启停/删除|NR=不含供应商状态与操作副作用|E=component:ProviderCard|X=internal|A=供应商卡片|D=vue|S=dom|RD=./README.ai -->
<template>
  <!-- 单个供应商卡片：常态展示（标题/状态/类型/Key/URL + 启用·删除 + 编辑·拉取 + 已选模型）与行内编辑表单两态切换 -->
  <article
    :class="[
      'model-routing__provider-card',
      { 'is-editing': isEditing }
    ]"
  >
    <!-- 行内编辑表单模式 -->
    <template v-if="isEditing">
      <ProviderFormPanel
        mode="edit"
        :provider-form="providerForm"
        :is-saving-provider="isSavingProvider"
        @update-field="(field, value) => emit('update-field', field, value)"
        @save="emit('save-provider')"
        @cancel="emit('cancel-provider')"
      />
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
            @click="emit('toggle')"
          >
            {{ provider.is_enabled ? '停用' : '启用' }}
          </button>
          <button
            type="button"
            class="model-routing__provider-delete"
            :disabled="isSavingProvider"
            :aria-label="`删除供应商 ${provider.name}`"
            @click="emit('delete')"
          >
            删除供应商
          </button>
        </div>
      </header>

      <div class="model-routing__provider-actions">
        <button
          type="button"
          class="md-btn md-btn-text md-ripple"
          @click="emit('edit')"
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
          @click="emit('open-picker', $event)"
        >
          {{ providerFetchState(provider.id).isLoading ? '拉取中...' : '拉取模型' }}
        </button>
      </div>

      <p v-if="!provider.is_enabled" class="model-routing__hint">
        启用供应商后才能使用里面的模型。
      </p>
      <p v-if="providerFetchState(provider.id).error" class="model-routing__hint is-error">
        {{ providerFetchState(provider.id).error }}
      </p>

      <SelectedModelChips
        :chips="selectedModelChipsForProvider(provider.id)"
        :active-section="activeSection"
        @delete="(modelName) => emit('delete-model', modelName)"
      />
    </template>
  </article>
</template>

<script setup lang="ts">
import type { UserAIModel, UserModelProvider } from '@/api/llm'
import type { ProviderFetchState, ProviderForm, RoutingSection } from './modelRoutingTypes'
import { providerTypeLabel } from './modelRoutingHelpers'
import { ProviderFormPanel } from './ProviderFormPanel'
import { SelectedModelChips } from './SelectedModelChips'

defineProps<{
  provider: UserModelProvider
  isEditing: boolean
  activeSection: RoutingSection
  providerForm: ProviderForm
  isSavingProvider: boolean
  providerFetchState: (providerId: number) => ProviderFetchState
  isModelPickerOpen: (providerId: number) => boolean
  selectedModelChipsForProvider: (providerId: number) => UserAIModel[]
}>()

const emit = defineEmits<{
  (event: 'update-field', field: keyof ProviderForm, value: string | boolean): void
  (event: 'save-provider'): void
  (event: 'cancel-provider'): void
  (event: 'toggle'): void
  (event: 'delete'): void
  (event: 'edit'): void
  (event: 'open-picker', e: Event): void
  (event: 'delete-model', modelName: string): void
}>()

/** 供应商 Key 预览标签（无 Key 时提示未保存） */
const providerKeyLabel = (provider: UserModelProvider): string =>
  provider.api_key_preview ? `Key ${provider.api_key_preview}` : '未保存 Key'
</script>

<style scoped>
/* provider-head 共享 flex（从父 topbar/provider-head/model-row 混合拆出；topbar/model-row 仍留父） */
.model-routing__provider-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--md-spacing-3);
}

.model-routing__provider-head h3 {
  margin: 0;
  color: var(--md-on-surface);
}

/* provider-head p / hint 共享排版（从父 provider-head p/hint/empty 混合拆出；empty 仍留父） */
.model-routing__provider-head p,
.model-routing__hint {
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

.model-routing__toggle:focus-visible,
.model-routing__provider-delete:focus-visible {
  outline: 2px solid var(--md-primary);
  outline-offset: 2px;
}

/* hint.is-error（从父 feedback.is-error/hint.is-error 混合拆出；feedback.is-error 仍留父） */
.model-routing__hint.is-error {
  background-color: var(--md-error-container);
  color: var(--md-on-error-container);
  border-radius: var(--md-radius-md);
  padding: var(--md-spacing-2);
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

@media (max-width: 640px) {
  .model-routing__provider-head,
  .model-routing__provider-actions {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
