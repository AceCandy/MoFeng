import type {
  ProviderType,
  UserAIModel,
  UserAIModelCreate,
  UserAIModelPricing,
  UserModelProvider,
} from '@/api/llm'
import type { Capability, RoutingSection } from './modelRoutingTypes'

/**
 * 模型路由配置的纯函数与常量。从 PersonalModelRouting.vue 抽出（Slice 2）。
 * 不含任何响应式状态，便于单元测试覆盖 payload 形状与能力映射契约。
 */

/** 供应商类型 → 中文展示标签 */
export const providerTypeLabels: Record<ProviderType, string> = {
  openai_compatible: 'OpenAI 兼容',
  anthropic: 'Anthropic',
  ollama: 'Ollama',
  custom: '自定义',
}

export const providerTypeLabel = (providerType: ProviderType): string =>
  providerTypeLabels[providerType]

/** 模型展示名：优先 display_name，回退 model_name，缺省占位 */
export const modelDisplayName = (model?: UserAIModel): string => {
  if (!model) {
    return '未设置'
  }
  return model.display_name || model.model_name
}

/** 路由分区 → 该分区操作的能力（纯映射，主组件用薄 wrapper 透传 activeSection） */
export const capabilityForSection = (section: RoutingSection): Capability =>
  section === 'embedding'
    ? 'embedding'
    : section === 'tts'
      ? 'tts'
      : 'chat'

/** 新建供应商时按当前能力生成 capabilities flag（仅当前能力为 true） */
export const createProviderCapabilities = (capability: Capability): Record<Capability, boolean> => ({
  chat: capability === 'chat',
  embedding: capability === 'embedding',
  tts: capability === 'tts',
})

/** 读取供应商已声明的能力 flag（容错可选字段） */
export const providerCapabilities = (provider: UserModelProvider): Record<Capability, boolean> => ({
  chat: Boolean(provider.capabilities?.chat),
  embedding: Boolean(provider.capabilities?.embedding),
  tts: Boolean(provider.capabilities?.tts),
})

/** 按能力把模型分组到各自供应商 id，供分区列表渲染 */
export const groupModelsByProvider = (
  models: UserAIModel[],
  capability: Capability,
): Record<number, UserAIModel[]> => {
  return models.reduce<Record<number, UserAIModel[]>>((result, model) => {
    if (!model.capabilities[capability]) {
      return result
    }
    result[model.provider_id] = result[model.provider_id] || []
    result[model.provider_id].push(model)
    return result
  }, {})
}

export interface ModelPricingForm {
  inputPrice: string
  outputPrice: string
  cachedInputPrice: string
  cacheWriteInputPrice: string
  currency: string
}

const EMPTY_MODEL_PRICING: UserAIModelPricing = {
  input_price_per_million: null,
  output_price_per_million: null,
  cached_input_price_per_million: null,
  cache_write_input_price_per_million: null,
  pricing_currency: null,
}

export const createModelPricingForm = (model: UserAIModel): ModelPricingForm => ({
  inputPrice: model.input_price_per_million || '',
  outputPrice: model.output_price_per_million || '',
  cachedInputPrice: model.cached_input_price_per_million || '',
  cacheWriteInputPrice: model.cache_write_input_price_per_million || '',
  currency: model.pricing_currency || 'USD',
})

export const formatModelPrice = (value: string | null): string => {
  if (!value) {
    return '未设'
  }
  const [integerPart, fractionPart] = value.split('.')
  const trimmedFraction = fractionPart?.replace(/0+$/, '')
  return trimmedFraction ? `${integerPart}.${trimmedFraction}` : integerPart
}

export const validateModelPricing = (form: ModelPricingForm): string | null => {
  const prices = [
    form.inputPrice,
    form.outputPrice,
    form.cachedInputPrice,
    form.cacheWriteInputPrice,
  ].map((value) => value.trim())
  for (const price of prices) {
    if (!price) {
      continue
    }
    if (!/^\d+(?:\.\d{1,12})?$/.test(price)) {
      return '价格必须是非负小数，最多保留 12 位小数。'
    }
    const [integerPart] = price.split('.')
    if (integerPart.replace(/^0+/, '').length > 12) {
      return '价格整数部分最多 12 位。'
    }
  }
  const currency = form.currency.trim()
  if (prices.some(Boolean) && !/^[A-Za-z]{3}$/.test(currency)) {
    return '配置价格时，币种必须是三位字母代码。'
  }
  if (currency && !/^[A-Za-z]{3}$/.test(currency)) {
    return '币种必须是三位字母代码。'
  }
  return null
}

export const toModelPricingUpdate = (form: ModelPricingForm): UserAIModelPricing => {
  const optionalPrice = (value: string): string | null => value.trim() || null
  return {
    input_price_per_million: optionalPrice(form.inputPrice),
    output_price_per_million: optionalPrice(form.outputPrice),
    cached_input_price_per_million: optionalPrice(form.cachedInputPrice),
    cache_write_input_price_per_million: optionalPrice(form.cacheWriteInputPrice),
    pricing_currency: form.currency.trim().toUpperCase() || null,
  }
}

/**
 * 生成新增模型的 payload。hasPrimaryChatModel 决定 chat 模型是否设为默认主模型
 * （无主模型时首个 chat 模型自动默认）。tts 固定 mimo_chat_audio 协议，
 * 音色/倍速在朗读控件配置，模型不预置（llm-settings 红线：TTS 只选默认模型）。
 */
export const createModelPayload = (
  provider: UserModelProvider,
  modelName: string,
  capability: Capability,
  hasPrimaryChatModel: boolean,
): UserAIModelCreate => {
  const isChat = capability === 'chat'
  if (isChat) {
    return {
      provider_id: provider.id,
      display_name: modelName,
      model_name: modelName,
      capabilities: { chat: true, embedding: false },
      context_window: null,
      is_default_chat: !hasPrimaryChatModel,
      is_default_embedding: false,
      is_default_tts: false,
      tts_protocol: null,
      tts_voice: null,
      tts_speed: 1.0,
      ...EMPTY_MODEL_PRICING,
      is_enabled: true,
      sort_order: 0,
    }
  }

  if (capability === 'tts') {
    return {
      provider_id: provider.id,
      display_name: modelName,
      model_name: modelName,
      capabilities: { chat: false, embedding: false, tts: true },
      context_window: null,
      is_default_chat: false,
      is_default_embedding: false,
      is_default_tts: true,
      // 协议跟模型（默认 MiMo）；音色/倍速改在朗读控件配置，模型不预置
      tts_protocol: 'mimo_chat_audio',
      tts_voice: null,
      tts_speed: 1.0,
      ...EMPTY_MODEL_PRICING,
      is_enabled: true,
      sort_order: 0,
    }
  }

  return {
    provider_id: provider.id,
    display_name: modelName,
    model_name: modelName,
    capabilities: { chat: false, embedding: true, tts: false },
    context_window: null,
    is_default_chat: false,
    is_default_embedding: true,
    is_default_tts: false,
    tts_protocol: null,
    tts_voice: null,
    tts_speed: 1.0,
    ...EMPTY_MODEL_PRICING,
    is_enabled: true,
    sort_order: 0,
  }
}
