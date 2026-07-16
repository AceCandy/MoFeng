import { reactive, ref, type ComputedRef } from 'vue'
import type { ProviderCreate, UserModelProvider } from '@/api/llm'
import type {
  useDeleteProviderMutation,
  useSaveProviderMutation,
  useToggleProviderMutation,
} from '@/queries/llm'
import { globalAlert } from '@/composables/useAlert'
import type { ProviderFetchState, ProviderForm, ProviderFormMode, RoutingSection } from './modelRoutingTypes'
import { capabilityForSection, createProviderCapabilities, providerCapabilities } from './modelRoutingHelpers'

interface UseProviderFormOptions {
  providers: ComputedRef<UserModelProvider[]>
  activeSection: ComputedRef<RoutingSection>
  saveProviderMutation: ReturnType<typeof useSaveProviderMutation>
  toggleProviderMutation: ReturnType<typeof useToggleProviderMutation>
  deleteProviderMutation: ReturnType<typeof useDeleteProviderMutation>
  loadBundle: () => Promise<void>
  setFeedback: (type: 'success' | 'error', message: string) => void
  /** 供应商保存/启停/删除成功后的回调（主组件用于 emit('saved')，延迟绑定规避 const TDZ） */
  onSaved: () => void
}

/**
 * 供应商表单与 CRUD 状态机。从 PersonalModelRouting.vue 抽出（Slice 6）。
 * 内化 providerForm/providerFormMode/editingProviderId + providerFetchStates/providerFetchState +
 * emptyProviderForm/assignProviderForm + beginCreate/beginEdit/cancel/saveProviderForm +
 * toggleProviderEnabled/deleteProviderFromCard。capability 经 capabilityForSection(activeSection)
 * 计算（等价原 activeModelCapability() wrapper）。emit('saved') 经 onSaved 回调交父。
 */
export const useProviderForm = (options: UseProviderFormOptions) => {
  const {
    providers,
    activeSection,
    saveProviderMutation,
    toggleProviderMutation,
    deleteProviderMutation,
    loadBundle,
    setFeedback,
    onSaved,
  } = options

  const providerFetchStates = reactive<Record<number, ProviderFetchState>>({})
  const editingProviderId = ref<number | null>(null)
  const providerFormMode = ref<ProviderFormMode>(null)
  const emptyProviderForm = (): ProviderForm => ({
    name: '',
    provider_type: 'openai_compatible',
    base_url: '',
    api_key: '',
    is_enabled: true,
  })

  const providerForm = reactive<ProviderForm>(emptyProviderForm())

  const providerFetchState = (providerId: number): ProviderFetchState => {
    if (!providerFetchStates[providerId]) {
      providerFetchStates[providerId] = {
        isLoading: false,
        modelsByCapability: { chat: [], embedding: [], tts: [] },
        error: '',
      }
    }
    return providerFetchStates[providerId]
  }

  const assignProviderForm = (next: ProviderForm) => {
    Object.assign(providerForm, next)
  }

  const beginCreateProvider = () => {
    editingProviderId.value = null
    providerFormMode.value = 'create'
    assignProviderForm(emptyProviderForm())
  }

  const beginEditProvider = (provider: UserModelProvider) => {
    editingProviderId.value = provider.id
    providerFormMode.value = 'edit'
    assignProviderForm({
      name: provider.name,
      provider_type: provider.provider_type,
      base_url: provider.base_url,
      api_key: '',
      is_enabled: provider.is_enabled,
    })
  }

  const cancelProviderForm = () => {
    editingProviderId.value = null
    providerFormMode.value = null
    assignProviderForm(emptyProviderForm())
  }

  const saveProviderForm = async () => {
    const capability = capabilityForSection(activeSection.value)
    const payload: ProviderCreate = {
      name: providerForm.name.trim(),
      provider_type: providerForm.provider_type,
      base_url: providerForm.base_url.trim(),
      api_key: providerForm.api_key.trim() || null,
      capabilities: createProviderCapabilities(capability),
      is_enabled: providerForm.is_enabled,
    }
    if (!payload.name || !payload.base_url) {
      setFeedback('error', '请填写供应商名称和 API URL。')
      return
    }

    try {
      const editingProvider = providers.value.find((provider) => provider.id === editingProviderId.value)
      await saveProviderMutation.mutateAsync({
        id: editingProviderId.value,
        data: editingProviderId.value
          ? {
            name: payload.name,
            provider_type: payload.provider_type,
            base_url: payload.base_url,
            ...(providerForm.api_key.trim() ? { api_key: payload.api_key } : {}),
            capabilities: {
              ...(editingProvider ? providerCapabilities(editingProvider) : {}),
              [capability]: true,
            },
            is_enabled: payload.is_enabled,
          }
          : payload,
      })
      await loadBundle()
      cancelProviderForm()
      setFeedback('success', '供应商已保存。')
      onSaved()
    } catch (error) {
      const message = error instanceof Error ? error.message : '未知错误'
      setFeedback('error', `供应商保存失败：${message}`)
    }
  }

  const toggleProviderEnabled = async (provider: UserModelProvider) => {
    try {
      await toggleProviderMutation.mutateAsync({
        id: provider.id,
        is_enabled: !provider.is_enabled,
      })
      await loadBundle()
      setFeedback('success', provider.is_enabled ? '供应商已停用。' : '供应商已启用。')
      onSaved()
    } catch (error) {
      const message = error instanceof Error ? error.message : '未知错误'
      setFeedback('error', `供应商状态更新失败：${message}`)
    }
  }

  const deleteProviderFromCard = async (provider: UserModelProvider) => {
    const confirmed = await globalAlert.showConfirm(
      `确定删除供应商"${provider.name}"吗？关联模型和阶段路由也会一起删除。`,
      '删除供应商',
    )
    if (!confirmed) {
      return
    }

    try {
      await deleteProviderMutation.mutateAsync(provider.id)
      if (editingProviderId.value === provider.id) {
        cancelProviderForm()
      }
      delete providerFetchStates[provider.id]
      await loadBundle()
      setFeedback('success', '供应商已删除。')
      onSaved()
    } catch (error) {
      const message = error instanceof Error ? error.message : '未知错误'
      setFeedback('error', `删除供应商失败：${message}`)
    }
  }

  return {
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
  }
}
