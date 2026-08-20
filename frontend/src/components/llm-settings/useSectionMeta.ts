import { computed, type ComputedRef } from 'vue'
import type { UserAIModel, UserModelProvider } from '@/api/llm'
import type { ReadinessSummary, RoutingSection } from './modelRoutingTypes'
import {
  capabilityForSection,
  groupModelsByProvider,
  modelDisplayName,
  providerCapabilities,
} from './modelRoutingHelpers'

interface UseSectionMetaOptions {
  providers: ComputedRef<UserModelProvider[]>
  models: ComputedRef<UserAIModel[]>
  activeSection: ComputedRef<RoutingSection>
  /** 阶段路由选择（reactive 对象，configuredRouteCount 追踪其键值） */
  routeSelections: Record<string, string>
  allStageKeys: ComputedRef<string[]>
}

/**
 * 分区元信息与模型派生状态。从 PersonalModelRouting.vue 抽出（Slice 4）。
 * 内化分区文案（eyebrow/heading/description/readinessSummary）+ 各能力模型派生 computed 群 +
 * activeProviders（单一 capability 过滤，llm-settings 红线 #1）+ configuredRouteCount + xxxModelsByProvider。
 * 入参透传 bundle 的 providers/models + activeSection + routeSelections/allStageKeys。
 */
export const useSectionMeta = (options: UseSectionMetaOptions) => {
  const { providers, models, activeSection, routeSelections, allStageKeys } = options

  const enabledChatModels = computed(() =>
    models.value.filter((model) => model.is_enabled && Boolean(model.capabilities.chat)),
  )
  const primaryChatModel = computed(() =>
    enabledChatModels.value.find((model) => model.is_default_chat),
  )
  const enabledEmbeddingModels = computed(() =>
    models.value.filter((model) => model.is_enabled && Boolean(model.capabilities.embedding)),
  )
  const defaultEmbeddingModel = computed(() =>
    enabledEmbeddingModels.value.find((model) => model.is_default_embedding),
  )
  const enabledTTSModels = computed(() =>
    models.value.filter((model) => model.is_enabled && Boolean(model.capabilities.tts)),
  )
  const defaultTTSModel = computed(() =>
    enabledTTSModels.value.find((model) => model.is_default_tts),
  )
  const configuredRouteCount = computed(
    () => Object.values(routeSelections).filter((modelId) => Boolean(modelId)).length,
  )
  const chatModelsByProvider = computed(() => groupModelsByProvider(models.value, 'chat'))
  const embeddingModelsByProvider = computed(() => groupModelsByProvider(models.value, 'embedding'))
  const ttsModelsByProvider = computed(() => groupModelsByProvider(models.value, 'tts'))
  const activeProviders = computed(() => {
    const capability = capabilityForSection(activeSection.value)
    return providers.value.filter((provider) => providerCapabilities(provider)[capability])
  })
  const sectionEyebrow = computed(() =>
    activeSection.value === 'routes'
      ? '阶段覆盖'
      : activeSection.value === 'embedding'
        ? '记忆检索'
        : activeSection.value === 'tts'
          ? '语音朗读'
          : '文本生成',
  )
  const sectionHeading = computed(() => {
    if (activeSection.value === 'routes') {
      return '按创作阶段选择默认模型'
    }
    if (activeSection.value === 'embedding') {
      return '配置向量供应商和检索模型'
    }
    return activeSection.value === 'tts' ? '配置朗读供应商和语音模型' : '配置供应商和主模型'
  })
  const sectionDescription = computed(() => {
    if (activeSection.value === 'routes') {
      return '按正文节点查看实际路由；未覆盖的文本阶段使用主模型，向量阶段使用当前检索模型。'
    }
    if (activeSection.value === 'embedding') {
      return '记忆检索只使用一个当前向量模型，避免索引和查询维度不一致。'
    }
    if (activeSection.value === 'tts') {
      return '设置默认朗读模型、协议、音色与语速；未配置时自动使用浏览器朗读。'
    }
    return '先保存供应商，再拉取模型并指定主模型，写作流程才能稳定生成正文。'
  })
  const sectionReadinessSummary = computed<ReadinessSummary>(() => {
    if (activeSection.value === 'routes') {
      return {
        label: '阶段覆盖',
        value: `${configuredRouteCount.value}/${allStageKeys.value.length}`,
        description: `文本：${modelDisplayName(primaryChatModel.value)} · 向量：${modelDisplayName(defaultEmbeddingModel.value)}`,
        tone: primaryChatModel.value ? 'success' : 'warning',
      }
    }

    if (activeSection.value === 'embedding') {
      return {
        label: '当前检索模型',
        value: modelDisplayName(defaultEmbeddingModel.value),
        description: `${enabledEmbeddingModels.value.length} 个可用向量模型 · ${activeProviders.value.length} 个供应商`,
        tone: defaultEmbeddingModel.value ? 'success' : 'warning',
      }
    }

    if (activeSection.value === 'tts') {
      return {
        label: '当前朗读模型',
        value: modelDisplayName(defaultTTSModel.value),
        description: `${enabledTTSModels.value.length} 个可用语音模型 · ${activeProviders.value.length} 个供应商`,
        tone: defaultTTSModel.value ? 'success' : 'warning',
      }
    }

    return {
      label: '主模型',
      value: modelDisplayName(primaryChatModel.value),
      description: `${enabledChatModels.value.length} 个可用文本模型 · ${activeProviders.value.length} 个供应商`,
      tone: primaryChatModel.value ? 'success' : 'warning',
    }
  })

  return {
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
  }
}
