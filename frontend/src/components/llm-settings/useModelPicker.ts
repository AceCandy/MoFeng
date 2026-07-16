import {
  computed,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
  type ComputedRef,
  type ComponentPublicInstance,
} from 'vue'
import type { UserAIModel, UserModelProvider } from '@/api/llm'
import { globalAlert } from '@/composables/useAlert'
import { useDialogA11y } from '@/composables/useDialogA11y'
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
 * 模型拉取弹窗状态机。从 PersonalModelRouting.vue 抽出（Slice 7）。
 * 内化 picker 状态（activeModelPickerProviderId/refs/query/position/pending sets/isSavingPicker）+
 * open/close/updatePosition/loadProviderModels/enabledChatModelNamesFor + isModelPickerOpen/
 * modelPickerStyle/isChatPickerDirty + useDialogA11y + onMounted/onBeforeUnmount 监听注册 +
 * watch(activeSection/activeProviders→close)。保留 id 选择器 hack + 函数 ref（v-for 子树内
 * 字符串 ref 会被收集成数组，故用函数 ref 取单个 DOM + id 选择器判定外部点击）。
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
  const isModelPickerActive = computed(() => activeModelPickerProviderId.value !== null)
  const modelPickerDialogRef = ref<HTMLElement | null>(null)
  const modelPickerSearchInputRef = ref<HTMLElement | null>(null)
  const modelPickerQuery = ref('')
  // 弹窗 Teleport 到 body 后的 fixed 定位坐标
  const modelPickerPosition = ref({ top: 0, left: 0 })
  // 弹窗位于 v-for 子树内，字符串 ref 会被收集成数组；
  // 改用函数 ref，只保留当前打开弹窗的单个 DOM
  const setModelPickerDialogRef = (el: Element | ComponentPublicInstance | null) => {
    modelPickerDialogRef.value = el instanceof HTMLElement ? el : null
  }
  const setModelPickerSearchInputRef = (el: Element | ComponentPublicInstance | null) => {
    modelPickerSearchInputRef.value = el instanceof HTMLElement ? el : null
  }
  // 拉取模型弹窗的本地勾选集合（仅文本生成 section），保存前不写后端
  const pendingChatModelNames = ref<Set<string>>(new Set())
  const pendingTTSModelName = ref('')
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
    activeModelPickerProviderId.value = null
    modelPickerQuery.value = ''
    pendingChatModelNames.value = new Set()
    pendingTTSModelName.value = ''
    isSavingPicker.value = false
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

  useDialogA11y({
    active: isModelPickerActive,
    dialogRef: modelPickerDialogRef,
    initialFocusRef: modelPickerSearchInputRef,
    onClose: () => {
      if (!isSavingPicker.value) {
        closeModelPicker()
      }
    },
    trapFocus: false,
    lockBodyScroll: false,
  })

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

  const modelPickerStyle = computed(() => ({
    top: `${modelPickerPosition.value.top}px`,
    left: `${modelPickerPosition.value.left}px`,
  }))

  // 按触发按钮位置计算 fixed 坐标，超出视口时翻转/收边
  const updateModelPickerPosition = (trigger: HTMLElement) => {
    const rect = trigger.getBoundingClientRect()
    const gap = 4
    const vw = window.innerWidth
    const vh = window.innerHeight
    const pickerW = Math.min(420, vw - 16)
    const pickerMaxH = 420
    let top = rect.bottom + gap
    let left = rect.left
    if (left + pickerW > vw - 8) left = vw - pickerW - 8
    if (left < 8) left = 8
    if (top + pickerMaxH > vh - 8) {
      const above = rect.top - gap - pickerMaxH
      top = above > 8 ? above : Math.max(8, vh - pickerMaxH - 8)
    }
    modelPickerPosition.value = { top, left }
  }

  const openProviderModelPicker = async (provider: UserModelProvider, event?: MouseEvent) => {
    if (!provider.is_enabled) {
      return
    }
    // currentTarget 在 await 后会被清空，需先读取
    const trigger = event?.currentTarget
    if (trigger instanceof HTMLElement) {
      updateModelPickerPosition(trigger)
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
    }
    await loadProviderModels(provider)
  }

  // 点击弹窗外部：无改动直接关，有改动弹确认，避免误丢勾选
  const onPickerClickOutside = async (event: MouseEvent) => {
    if (!isModelPickerActive.value || activeSection.value !== 'llm') {
      return
    }
    const target = event.target
    if (target instanceof Element) {
      // 弹窗位于 v-for 子树内，模板 ref 会被收集为数组，
      // 这里用 id 选择器判定点击是否落在弹窗内
      if (target.closest(`#model-picker-${activeModelPickerProviderId.value}`)) {
        return
      }
      if (target.closest('[aria-haspopup="dialog"]')) {
        return
      }
    }
    if (!isChatPickerDirty.value) {
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

  // 视口滚动/缩放会使 fixed 定位漂移，直接关闭弹窗（picker 内部滚动除外）
  const onPickerViewportChange = (event: Event) => {
    if (!isModelPickerActive.value) return
    const target = event.target
    if (target instanceof Element && target.closest(`#model-picker-${activeModelPickerProviderId.value}`)) {
      return
    }
    closeModelPicker()
  }

  onMounted(() => {
    document.addEventListener('click', onPickerClickOutside)
    window.addEventListener('scroll', onPickerViewportChange, true)
    window.addEventListener('resize', onPickerViewportChange)
  })

  onBeforeUnmount(() => {
    document.removeEventListener('click', onPickerClickOutside)
    window.removeEventListener('scroll', onPickerViewportChange, true)
    window.removeEventListener('resize', onPickerViewportChange)
  })

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
    modelPickerStyle,
    isChatPickerDirty,
    setModelPickerDialogRef,
    setModelPickerSearchInputRef,
    openProviderModelPicker,
    closeModelPicker,
  }
}
