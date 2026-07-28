<!-- AIMETA P=已选模型列表_模型状态与行内定价|R=模型展示_定价编辑_删除入口|NR=不拥有模型持久化与删除副作用|E=component:SelectedModelChips|X=internal|A=模型列表|D=vue|S=dom|RD=./README.ai -->
<template>
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
    <p v-if="chips.length === 0" class="model-routing__empty">
      点击"拉取模型"后勾选模型。
    </p>
    <div v-else class="model-routing__model-list">
      <section v-for="chip in chips" :key="chip.id" class="model-routing__model-row">
        <div class="model-routing__model-summary">
          <div class="model-routing__model-identity">
            <span class="model-routing__model-name">{{ chip.display_name || chip.model_name }}</span>
            <small
              v-if="activeSection === 'llm' && chip.is_default_chat"
              class="model-routing__stamp-label"
            >主</small>
            <small
              v-else-if="activeSection === 'embedding' && chip.is_default_embedding"
              class="model-routing__stamp-label"
            >用</small>
            <small
              v-else-if="activeSection === 'tts' && chip.is_default_tts"
              class="model-routing__stamp-label"
            >读</small>
          </div>
          <span v-if="activeSection !== 'tts'" class="model-routing__pricing-status">
            {{ pricingSummary(chip) }}
          </span>
        </div>

        <div class="model-routing__model-actions">
          <button
            v-if="activeSection !== 'tts'"
            type="button"
            class="model-routing__text-action"
            :aria-expanded="editingModelId === chip.id"
            :aria-controls="`model-pricing-${chip.id}`"
            @click="togglePricing(chip)"
          >
            {{ editingModelId === chip.id ? '收起' : '定价' }}
          </button>
          <button
            type="button"
            class="model-routing__text-action is-danger"
            :aria-label="`删除模型 ${chip.display_name || chip.model_name}`"
            @click="emit('delete', chip.model_name)"
          >
            删除
          </button>
        </div>

        <form
          v-if="editingModelId === chip.id && pricingForms[chip.id]"
          :id="`model-pricing-${chip.id}`"
          class="model-routing__pricing-form"
          @submit.prevent="savePricing(chip)"
        >
          <div class="model-routing__pricing-grid">
            <label class="model-routing__pricing-field">
              <span>输入 / 1M</span>
              <input
                v-model="pricingForms[chip.id].inputPrice"
                inputmode="decimal"
                autocomplete="off"
                placeholder="0.00"
              />
            </label>
            <template v-if="activeSection === 'llm'">
              <label class="model-routing__pricing-field">
                <span>输出 / 1M</span>
                <input
                  v-model="pricingForms[chip.id].outputPrice"
                  inputmode="decimal"
                  autocomplete="off"
                  placeholder="0.00"
                />
              </label>
              <label class="model-routing__pricing-field">
                <span>缓存读取 / 1M</span>
                <input
                  v-model="pricingForms[chip.id].cachedInputPrice"
                  inputmode="decimal"
                  autocomplete="off"
                  placeholder="0.00"
                />
              </label>
              <label class="model-routing__pricing-field">
                <span>缓存写入 / 1M</span>
                <input
                  v-model="pricingForms[chip.id].cacheWriteInputPrice"
                  inputmode="decimal"
                  autocomplete="off"
                  placeholder="0.00"
                />
              </label>
            </template>
            <label class="model-routing__pricing-field is-currency">
              <span>币种</span>
              <input
                v-model="pricingForms[chip.id].currency"
                autocomplete="off"
                spellcheck="false"
                placeholder="USD"
              />
            </label>
          </div>
          <p v-if="pricingErrors[chip.id]" class="model-routing__pricing-error" role="alert">
            {{ pricingErrors[chip.id] }}
          </p>
          <div class="model-routing__pricing-actions">
            <button
              type="button"
              class="model-routing__text-action"
              :disabled="savingModelId === chip.id"
              @click="cancelPricing(chip.id)"
            >
              取消
            </button>
            <button
              type="submit"
              class="md-btn md-btn-tonal"
              :disabled="savingModelId === chip.id"
            >
              {{ savingModelId === chip.id ? '保存中...' : '保存定价' }}
            </button>
          </div>
        </form>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import type { UserAIModel, UserAIModelPricing } from '@/api/llm'
import type { RoutingSection } from './modelRoutingTypes'
import {
  createModelPricingForm,
  formatModelPrice,
  toModelPricingUpdate,
  validateModelPricing,
  type ModelPricingForm,
} from './modelRoutingHelpers'

const props = defineProps<{
  chips: UserAIModel[]
  activeSection: RoutingSection
  saveModelPricing: (model: UserAIModel, pricing: UserAIModelPricing) => Promise<void>
}>()

const emit = defineEmits<{
  (event: 'delete', modelName: string): void
}>()

const editingModelId = ref<number | null>(null)
const savingModelId = ref<number | null>(null)
const pricingForms = reactive<Record<number, ModelPricingForm>>({})
const pricingErrors = reactive<Record<number, string | null>>({})

const pricingSummary = (model: UserAIModel): string => {
  if (
    !model.input_price_per_million &&
    !model.output_price_per_million &&
    !model.cached_input_price_per_million &&
    !model.cache_write_input_price_per_million
  ) {
    return '定价未配置'
  }
  const currency = model.pricing_currency || '币种未设'
  if (props.activeSection === 'embedding') {
    return `${currency} · 输入 ${formatModelPrice(model.input_price_per_million)}`
  }
  return `${currency} · 输入 ${formatModelPrice(model.input_price_per_million)} · 输出 ${formatModelPrice(model.output_price_per_million)}`
}

const togglePricing = (model: UserAIModel) => {
  if (editingModelId.value === model.id) {
    cancelPricing(model.id)
    return
  }
  pricingForms[model.id] = createModelPricingForm(model)
  pricingErrors[model.id] = null
  editingModelId.value = model.id
}

const cancelPricing = (modelId: number) => {
  if (savingModelId.value === modelId) {
    return
  }
  editingModelId.value = null
  pricingErrors[modelId] = null
}

const savePricing = async (model: UserAIModel) => {
  const form = pricingForms[model.id]
  if (!form || savingModelId.value !== null) {
    return
  }
  const error = validateModelPricing(form)
  if (error) {
    pricingErrors[model.id] = error
    return
  }
  pricingErrors[model.id] = null
  savingModelId.value = model.id
  try {
    await props.saveModelPricing(model, toModelPricingUpdate(form))
    editingModelId.value = null
  } catch (error) {
    pricingErrors[model.id] = error instanceof Error ? error.message : '保存模型定价失败。'
  } finally {
    savingModelId.value = null
  }
}
</script>

<style scoped>
.model-routing__selected-models {
  display: grid;
  gap: var(--md-spacing-3);
}

.model-routing__model-list-title,
.model-routing__empty {
  margin: 0;
  color: var(--md-on-surface-variant);
}

.model-routing__empty {
  font-size: var(--md-body-small);
}

.model-routing__model-list {
  border-top: 1px solid var(--md-outline-variant);
}

.model-routing__model-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--md-spacing-3);
  padding: var(--md-spacing-3) 0;
  border-bottom: 1px solid var(--md-outline-variant);
}

.model-routing__model-summary {
  min-width: 0;
  display: grid;
  gap: 2px;
}

.model-routing__model-identity,
.model-routing__model-actions,
.model-routing__pricing-actions {
  display: flex;
  align-items: center;
  gap: var(--md-spacing-2);
}

.model-routing__model-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--md-on-surface);
  font-size: var(--md-body-medium);
}

.model-routing__pricing-status {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--md-on-surface-variant);
  font-family: var(--md-font-mono);
  font-size: var(--md-body-small);
}

.model-routing__stamp-label {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  height: 20px;
  border: 1px solid var(--md-secondary);
  border-radius: 1px;
  color: var(--md-secondary);
  font-family: var(--md-font-display);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0;
}

.model-routing__text-action {
  min-width: 48px;
  min-height: 32px;
  border: 1px solid transparent;
  border-radius: var(--md-radius-xs);
  padding: 4px 8px;
  background: transparent;
  color: var(--md-primary);
  font: inherit;
  font-size: var(--md-body-small);
  cursor: pointer;
}

.model-routing__text-action:hover:not(:disabled) {
  border-color: var(--md-outline-variant);
  background: var(--md-surface-container-high);
}

.model-routing__text-action.is-danger {
  color: var(--md-error);
}

.model-routing__text-action:focus-visible,
.model-routing__pricing-field input:focus-visible {
  outline: 2px solid var(--md-primary);
  outline-offset: 2px;
}

.model-routing__text-action:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.model-routing__pricing-form {
  grid-column: 1 / -1;
  display: grid;
  gap: var(--md-spacing-3);
  padding-top: var(--md-spacing-3);
  border-top: 1px dashed var(--md-outline-variant);
}

.model-routing__pricing-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(104px, 1fr));
  gap: var(--md-spacing-3);
}

.model-routing__pricing-field {
  min-width: 0;
  display: grid;
  gap: var(--md-spacing-1);
  color: var(--md-on-surface-variant);
  font-size: var(--md-label-medium);
}

.model-routing__pricing-field input {
  width: 100%;
  min-width: 0;
  height: 38px;
  border: 1px solid var(--md-outline);
  border-radius: var(--md-radius-xs);
  padding: 0 var(--md-spacing-3);
  background: transparent;
  color: var(--md-on-surface);
  font-family: var(--md-font-mono);
  font-size: var(--md-body-small);
}

.model-routing__pricing-field.is-currency input {
  text-transform: uppercase;
}

.model-routing__pricing-error {
  margin: 0;
  color: var(--md-error);
  font-size: var(--md-body-small);
}

.model-routing__pricing-actions {
  justify-content: flex-end;
}

@media (max-width: 900px) {
  .model-routing__pricing-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 560px) {
  .model-routing__model-row {
    grid-template-columns: minmax(0, 1fr);
  }

  .model-routing__model-actions {
    justify-content: flex-start;
  }

  .model-routing__pricing-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
