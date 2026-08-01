<!-- AIMETA P=供应商表单_新增编辑供应商|R=供应商字段表单|NR=不含表单状态与提交副作用|E=component:ProviderFormPanel|X=internal|A=供应商表单|D=vue|S=dom|RD=./README.ai -->
<template>
  <!-- 供应商新建/编辑表单：create 为独立面板，edit 为卡片内行内表单，字段共用 -->
  <section :class="isCreate ? 'model-routing__panel model-routing__provider-form' : 'model-routing__provider-form-edit'">
    <div :class="isCreate ? 'model-routing__form-head' : 'model-routing__inline-form-head'">
      <component :is="isCreate ? 'h3' : 'h4'" class="md-title-medium">
        {{ isCreate ? '新增供应商' : '编辑供应商' }}
      </component>
      <button
        type="button"
        :class="isCreate ? 'model-routing__link' : 'model-routing__inline-cancel'"
        @click="emit('cancel')"
      >
        取消
      </button>
    </div>

    <div :class="isCreate ? 'model-routing__form' : 'model-routing__inline-form'">
      <label class="md-text-field">
        <span class="md-text-field-label">名称</span>
        <input
          :value="providerForm.name"
          class="md-text-field-input"
          type="text"
          :placeholder="isCreate ? '如 OpenAI / Anthropic / DeepSeek / 本地 Ollama' : '如 OpenAI / Anthropic / DeepSeek'"
          @input="onTextInput('name', $event)"
        />
      </label>

      <label class="md-text-field">
        <span class="md-text-field-label">类型</span>
        <select
          :value="providerForm.provider_type"
          class="md-text-field-input"
          @change="onTextInput('provider_type', $event)"
        >
          <option value="openai_compatible">OpenAI 兼容</option>
          <option value="anthropic">Anthropic</option>
          <option value="ollama">Ollama</option>
          <option value="custom">自定义</option>
        </select>
      </label>

      <label class="md-text-field">
        <span class="md-text-field-label">API URL</span>
        <input
          :value="providerForm.base_url"
          class="md-text-field-input"
          type="text"
          placeholder="https://api.example.com/v1"
          @input="onTextInput('base_url', $event)"
        />
      </label>

      <label class="md-text-field">
        <span class="md-text-field-label">API Key</span>
        <input
          :value="providerForm.api_key"
          class="md-text-field-input"
          type="password"
          :placeholder="isCreate ? '请输入 API Key，Ollama 可留空' : '留空则保留已保存 Key'"
          @input="onTextInput('api_key', $event)"
        />
      </label>

      <!-- 启用开关 + 保存：edit 包在 inline-form-footer（flex 两端对齐），create 平铺为 .form 的 grid 项 -->
      <div v-if="!isCreate" class="model-routing__inline-form-footer">
        <label class="model-routing__check">
          <input
            :checked="providerForm.is_enabled"
            type="checkbox"
            @change="onCheck('is_enabled', $event)"
          />
          <span>启用供应商</span>
        </label>
        <button
          type="button"
          class="md-btn md-btn-filled md-ripple"
          :disabled="isSavingProvider"
          @click="emit('save')"
        >
          {{ isSavingProvider ? '保存中...' : '保存供应商' }}
        </button>
      </div>
      <template v-else>
        <label class="model-routing__check">
          <input
            :checked="providerForm.is_enabled"
            type="checkbox"
            @change="onCheck('is_enabled', $event)"
          />
          <span>启用供应商</span>
        </label>
        <button
          type="button"
          class="md-btn md-btn-filled md-ripple"
          :disabled="isSavingProvider"
          @click="emit('save')"
        >
          {{ isSavingProvider ? '保存中...' : '保存供应商' }}
        </button>
      </template>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ProviderForm } from './modelRoutingTypes'

const props = defineProps<{
  /** 供应商表单数据（reactive 对象；字段改动经 update-field 事件回写父组件，规避 vue/no-mutating-props） */
  providerForm: ProviderForm
  /** 表单模式：create=独立新增面板，edit=卡片内行内编辑 */
  mode: 'create' | 'edit'
  isSavingProvider: boolean
}>()

const emit = defineEmits<{
  (event: 'update-field', field: keyof ProviderForm, value: string | boolean): void
  (event: 'save'): void
  (event: 'cancel'): void
}>()

const isCreate = computed(() => props.mode === 'create')

const onTextInput = (field: keyof ProviderForm, event: Event) => {
  emit('update-field', field, (event.target as HTMLInputElement).value)
}

const onCheck = (field: keyof ProviderForm, event: Event) => {
  emit('update-field', field, (event.target as HTMLInputElement).checked)
}
</script>

<style scoped>
/* .model-routing__panel 与 .model-routing__link 已收口至
   styles/components/model-routing.css，组件内不再重复定义 */
.model-routing__provider-form-edit {
  display: grid;
  gap: var(--md-spacing-3);
}

.model-routing__form-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--md-spacing-3);
}

.model-routing__form {
  display: grid;
  gap: var(--md-spacing-3);
}

.model-routing__form-head h3 {
  margin: 0;
  color: var(--md-on-surface);
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

.model-routing__check input {
  width: 20px;
  height: 20px;
  flex: 0 0 auto;
}

/* edit 行内表单 */
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
  color: var(--md-primary); /* hover 用焦墨字，不用朱砂 */
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

@media (min-width: 768px) {
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
</style>
