import {
  computed,
  ref,
  watch,
  type ComputedRef,
  type ComponentPublicInstance,
} from 'vue'
import type { UserAIModel, UserModelProvider } from '@/api/llm'
import { globalAlert } from '@/composables/useAlert'
import { useProviderModelsQuery } from '@/queries/llm'
import type { Capability, ProviderFetchState, RoutingSection } from './modelRoutingTypes'
import { capabilityForSection } from './modelRoutingHelpers'

interface UseModelPickerOptions {
  models: ComputedRef<UserAIModel[]>
  activeSection: ComputedRef<RoutingSection>
  providerFetchState: (providerId: number) => ProviderFetchState
  defaultTTSModel: ComputedRef<UserAIModel | undefined>
  ttsModelsByProvider: ComputedRef<Record<number, UserAIModel[]>>
  activeProviders: ComputedRef<UserModelProvider[]>
}

/**
 * 模型选择面板状态：拉取供应商模型、维护待保存选择，
 * 并在关闭后将焦点还给触发按钮。
 * capability 经 capabilityForSection(activeSection) 计算（等价原 activeModelCapability() wrapper）。
 */
export const useModelPicker = (options: UseModelPickerOptions) => {
  const {
    models,
    activeSection,
    providerFetchState,
    defaultTTSModel,
    ttsModelsByProvider,
    activeProviders,
  } = options

  const activeModelPickerProviderId = ref<number | null>(null)
  const modelPickerSearchInputRef = ref<HTMLElement | null>(null)
  const modelPickerTriggerRef = ref<HTMLElement | null>(null)
  const modelPickerQuery = ref('')
  const setModelPickerSearchInputRef = (el: Element | ComponentPublicInstance | null) => {
    modelPickerSearchInputRef.value = el instanceof HTMLElement ? el : null
  }
  // 拉取模型弹窗的本地勾选集合（仅文本生成 section），保存前不写后端
  const pendingChatModelNames = ref<Set<string>>(new Set())
  const pendingTTSModelName = ref('')
  const initialTTSModelName = ref('')
  const isSavingPicker = ref(false)

  const activeModelCapability = (): Capability => capabilityForSection(activeSection.value)

  const providerModelsQuery = useProviderModelsQuery(
    () => activeModelPickerProviderId.value,
    () => activeModelCapability(),
    false,
  )

  const isModelPickerOpen = (providerId: number): boolean =>
    activeModelPickerProviderId.value === providerId

  const closeModelPicker = () => {
    const trigger = modelPickerTriggerRef.value
    activeModelPickerProviderId.value = null
    modelPickerQuery.value = ''
    pendingChatModelNames.value = new Set()
    pendingTTSModelName.value = ''
    initialTTSModelName.value = ''
    isSavingPicker.value = false
    modelPickerTriggerRef.value = null
    requestAnimationFrame(() => trigger?.focus())
  }

  const enabledChatModelNamesFor = (providerId: number): Set<string> =>
    new Set(
      models.value
        .filter(
          (model) =>
            model.provider_id === providerId &&
            Boolean(model.capabilities.chat) &&
            model.is_enabled,
        )
        .map((model) => model.model_name),
    )

  const isChatPickerDirty = computed(() => {
    if (activeSection.value !== 'llm' || activeModelPickerProviderId.value === null) {
      return false
    }
    const current = enabledChatModelNamesFor(activeModelPickerProviderId.value)
    const pending = pendingChatModelNames.value
    if (current.size !== pending.size) {
      return true
    }
    for (const name of pending) {
      if (!current.has(name)) {
        return true
      }
    }
    return false
  })

  const isTTSPickerDirty = computed(
    () => activeSection.value === 'tts' && pendingTTSModelName.value !== initialTTSModelName.value,
  )

  const loadProviderModels = async (provider: UserModelProvider) => {
    const state = providerFetchState(provider.id)
    const capability = activeModelCapability()
    state.isLoading = true
    state.error = ''
    try {
      activeModelPickerProviderId.value = provider.id
      const result = await providerModelsQuery.refetch()
      if (result.error) {
        throw result.error
      }
      state.modelsByCapability[capability] = result.data ?? []
      if (state.modelsByCapability[capability].length === 0) {
        state.error = '未拉取到模型，请检查 API URL 与 API Key。'
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : '未知错误'
      state.error = `拉取模型失败：${message}`
    } finally {
      state.isLoading = false
    }
  }

  const openProviderModelPicker = async (provider: UserModelProvider, event?: MouseEvent) => {
    if (!provider.is_enabled) {
      return
    }
    // currentTarget 在 await 后会被清空，需先读取
    const trigger = event?.currentTarget
    if (trigger instanceof HTMLElement) {
      modelPickerTriggerRef.value = trigger
    }
    activeModelPickerProviderId.value = provider.id
    modelPickerQuery.value = ''
    if (activeSection.value === 'llm') {
      pendingChatModelNames.value = enabledChatModelNamesFor(provider.id)
    }
    if (activeSection.value === 'tts') {
      const current = defaultTTSModel.value?.provider_id === provider.id
        ? defaultTTSModel.value
        : ttsModelsByProvider.value[provider.id]?.[0]
      pendingTTSModelName.value = current?.model_name || ''
      initialTTSModelName.value = pendingTTSModelName.value
    }
    await loadProviderModels(provider)
    requestAnimationFrame(() => modelPickerSearchInputRef.value?.focus())
  }

  const requestCloseModelPicker = async () => {
    if (isSavingPicker.value) return
    if (!isChatPickerDirty.value && !isTTSPickerDirty.value) {
      closeModelPicker()
      return
    }
    const confirmed = await globalAlert.showConfirm(
      '有未保存的模型改动，确认放弃吗？',
      '未保存的改动',
    )
    if (confirmed) {
      closeModelPicker()
    }
  }

  watch(
    () => activeSection.value,
    () => {
      closeModelPicker()
    },
  )

  watch(
    () => activeProviders.value,
    (providersSnapshot) => {
      if (activeModelPickerProviderId.value === null) return
      const isCurrentProviderVisible = providersSnapshot.some(
        (provider) => provider.id === activeModelPickerProviderId.value,
      )
      if (!isCurrentProviderVisible) {
        closeModelPicker()
      }
    },
  )

  return {
    activeModelPickerProviderId,
    modelPickerQuery,
    pendingChatModelNames,
    pendingTTSModelName,
    isSavingPicker,
    isModelPickerOpen,
    isChatPickerDirty,
    isTTSPickerDirty,
    setModelPickerSearchInputRef,
    openProviderModelPicker,
    closeModelPicker,
    requestCloseModelPicker,
  }
}
