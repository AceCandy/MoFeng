import { type ComputedRef, type Ref } from 'vue'
import type { UserAIModel, UserModelProvider } from '@/api/llm'
import type {
  useDeleteUserModelMutation,
  useSaveUserModelMutation,
  useUpdateUserModelMutation,
} from '@/queries/llm'
import { globalAlert } from '@/composables/useAlert'
import type { Capability, ProviderFetchState, RoutingSection } from './modelRoutingTypes'
import { capabilityForSection, createModelPayload } from './modelRoutingHelpers'

interface UseModelSelectionOptions {
  models: ComputedRef<UserAIModel[]>
  activeSection: ComputedRef<RoutingSection>
  chatModelsByProvider: ComputedRef<Record<number, UserAIModel[]>>
  embeddingModelsByProvider: ComputedRef<Record<number, UserAIModel[]>>
  ttsModelsByProvider: ComputedRef<Record<number, UserAIModel[]>>
  primaryChatModel: ComputedRef<UserAIModel | undefined>
  providerFetchState: (providerId: number) => ProviderFetchState
  modelPickerQuery: Ref<string>
  activeModelPickerProviderId: Ref<number | null>
  pendingChatModelNames: Ref<Set<string>>
  pendingTTSModelName: Ref<string>
  isSavingPicker: Ref<boolean>
  closeModelPicker: () => void
  saveUserModelMutation: ReturnType<typeof useSaveUserModelMutation>
  updateUserModelMutation: ReturnType<typeof useUpdateUserModelMutation>
  deleteUserModelMutation: ReturnType<typeof useDeleteUserModelMutation>
  loadBundle: () => Promise<void>
  setFeedback: (type: 'success' | 'error', message: string) => void
  /** 模型选择/保存/删除成功后的回调（主组件用于 emit('saved')，延迟绑定规避 const TDZ） */
  onSaved: () => void
}

/**
 * 模型选择与保存状态机。从 PersonalModelRouting.vue 抽出（Slice 8）。
 * 内化派生函数群（modelNamesForProvider/filteredModelNamesForProvider/
 * selectedModelChipsForProvider/savedModelForActiveSection/isModelSelectedForActiveSection/
 * activeModelStateLabel + 内部 chatModelForName/embeddingModelForName/ttsModelForName）+
 * 选择/保存方法（upsertModelForCapability/togglePendingChatModel/saveChatSelections/
 * savePickerSelections/setPrimaryChatModel/setPrimaryChatModelById/selectEmbeddingModel/
 * selectPendingTTSModel/saveTTSSelection/deleteModelForActiveSection）。
 * capability 经 capabilityForSection(activeSection) 计算（等价原 activeModelCapability() wrapper）。
 * 入参接收 useModelPicker 的 pending/isSavingPicker/closeModelPicker（单向 picker→selection，无循环依赖）。
 * emit('saved') 经 onSaved 回调交父。
 */
export const useModelSelection = (options: UseModelSelectionOptions) => {
  const {
    models,
    activeSection,
    chatModelsByProvider,
    embeddingModelsByProvider,
    ttsModelsByProvider,
    primaryChatModel,
    providerFetchState,
    modelPickerQuery,
    activeModelPickerProviderId,
    pendingChatModelNames,
    pendingTTSModelName,
    isSavingPicker,
    closeModelPicker,
    saveUserModelMutation,
    updateUserModelMutation,
    deleteUserModelMutation,
    loadBundle,
    setFeedback,
    onSaved,
  } = options

  const activeModelCapability = (): Capability => capabilityForSection(activeSection.value)

  const modelNamesForProvider = (providerId: number): string[] => {
    const capability = activeModelCapability()
    const grouped =
      capability === 'chat'
        ? chatModelsByProvider.value
        : capability === 'embedding'
          ? embeddingModelsByProvider.value
          : ttsModelsByProvider.value
    const existing = (grouped[providerId] || []).map((model) => model.model_name)
    const fetched = providerFetchState(providerId).modelsByCapability[capability]
    return Array.from(new Set([...existing, ...fetched])).sort((a, b) => a.localeCompare(b))
  }

  const filteredModelNamesForProvider = (providerId: number): string[] => {
    const query = modelPickerQuery.value.trim().toLowerCase()
    const names = modelNamesForProvider(providerId)
    if (!query) {
      return names
    }
    return names.filter((modelName) => modelName.toLowerCase().includes(query))
  }

  const selectedModelChipsForProvider = (providerId: number): UserAIModel[] => {
    const capability = activeModelCapability()
    const source =
      capability === 'chat'
        ? chatModelsByProvider.value[providerId] || []
        : capability === 'embedding'
          ? embeddingModelsByProvider.value[providerId] || []
          : ttsModelsByProvider.value[providerId] || []
    return source.filter((model) => model.is_enabled)
  }

  const chatModelForName = (providerId: number, modelName: string): UserAIModel | undefined =>
    models.value.find(
      (model) =>
        model.provider_id === providerId &&
        model.model_name === modelName &&
        Boolean(model.capabilities.chat),
    )

  const embeddingModelForName = (providerId: number, modelName: string): UserAIModel | undefined =>
    models.value.find(
      (model) =>
        providerId === model.provider_id &&
        model.model_name === modelName &&
        Boolean(model.capabilities.embedding),
    )

  const ttsModelForName = (providerId: number, modelName: string): UserAIModel | undefined =>
    models.value.find(
      (model) =>
        providerId === model.provider_id &&
        model.model_name === modelName &&
        Boolean(model.capabilities.tts),
    )

  const savedModelForActiveSection = (
    providerId: number,
    modelName: string,
  ): UserAIModel | undefined =>
    activeSection.value === 'embedding'
      ? embeddingModelForName(providerId, modelName)
      : activeSection.value === 'tts'
        ? ttsModelForName(providerId, modelName)
        : chatModelForName(providerId, modelName)

  const isModelSelectedForActiveSection = (providerId: number, modelName: string): boolean => {
    // 文本生成弹窗打开时，行高亮跟随本地待保存勾选，避免勾选与高亮不一致
    if (activeSection.value === 'llm' && activeModelPickerProviderId.value === providerId) {
      return pendingChatModelNames.value.has(modelName)
    }
    return Boolean(savedModelForActiveSection(providerId, modelName)?.is_enabled)
  }

  const activeModelStateLabel = (providerId: number, modelName: string): string => {
    const model = savedModelForActiveSection(providerId, modelName)
    if (!model?.is_enabled) {
      return ''
    }
    if (activeSection.value === 'embedding') {
      return model.is_default_embedding ? '当前使用' : '已登记'
    }
    if (activeSection.value === 'tts') {
      return model.is_default_tts ? '当前朗读' : '已登记'
    }
    return model.is_default_chat ? '主模型' : '已启用'
  }

  const upsertModelForCapability = async (
    provider: UserModelProvider,
    modelName: string,
    capability: Capability,
  ): Promise<UserAIModel> => {
    const existing =
      capability === 'chat'
        ? chatModelForName(provider.id, modelName)
        : capability === 'embedding'
          ? embeddingModelForName(provider.id, modelName)
          : ttsModelForName(provider.id, modelName)
    if (!existing) {
      return saveUserModelMutation.mutateAsync(
        createModelPayload(provider, modelName, capability, Boolean(primaryChatModel.value)),
      )
    }
    if (!existing.is_enabled) {
      return updateUserModelMutation.mutateAsync({
        id: existing.id,
        data: { is_enabled: true },
      })
    }
    return existing
  }

  // 仅更新本地待保存勾选集合，提交前不写后端
  const togglePendingChatModel = (
    provider: UserModelProvider,
    modelName: string,
    event: Event,
  ) => {
    const checked = (event.target as HTMLInputElement).checked
    if (!checked) {
      const existing = chatModelForName(provider.id, modelName)
      if (existing?.is_default_chat) {
        setFeedback('error', '主模型不能直接停用，请先选择另一个主模型。')
        ;(event.target as HTMLInputElement).checked = true
        return
      }
    }
    const next = new Set(pendingChatModelNames.value)
    if (checked) {
      next.add(modelName)
    } else {
      next.delete(modelName)
    }
    pendingChatModelNames.value = next
  }

  const saveChatSelections = async (provider: UserModelProvider) => {
    if (isSavingPicker.value) {
      return
    }
    const pending = new Set(pendingChatModelNames.value)
    const currentEnabled = models.value.filter(
      (model) =>
        model.provider_id === provider.id &&
        Boolean(model.capabilities.chat) &&
        model.is_enabled,
    )
    const toAdd = [...pending].filter(
      (name) => !currentEnabled.some((model) => model.model_name === name),
    )
    const toDisable = currentEnabled.filter((model) => !pending.has(model.model_name))

    isSavingPicker.value = true
    try {
      for (const name of toAdd) {
        await upsertModelForCapability(provider, name, 'chat')
      }
      for (const model of toDisable) {
        if (model.is_default_chat) {
          continue
        }
        await updateUserModelMutation.mutateAsync({
          id: model.id,
          data: { is_enabled: false },
        })
      }
      await loadBundle()
      setFeedback('success', '文本生成模型选择已保存。')
      onSaved()
      closeModelPicker()
    } catch (error) {
      const message = error instanceof Error ? error.message : '未知错误'
      setFeedback('error', `保存模型失败：${message}`)
    } finally {
      isSavingPicker.value = false
    }
  }

  const saveTTSSelection = async (provider: UserModelProvider) => {
    if (isSavingPicker.value) {
      return
    }
    if (!pendingTTSModelName.value) {
      setFeedback('error', '请选择默认语音朗读模型。')
      return
    }
    isSavingPicker.value = true
    try {
      const selected = await upsertModelForCapability(provider, pendingTTSModelName.value, 'tts')
      await updateUserModelMutation.mutateAsync({
        id: selected.id,
        data: {
          is_enabled: true,
          is_default_tts: true,
          // 协议跟模型（默认 MiMo，保留已配置协议）；音色/倍速在朗读控件配置
          tts_protocol: selected.tts_protocol || 'mimo_chat_audio',
        },
      })
      await loadBundle()
      setFeedback('success', '默认语音朗读模型已保存。')
      onSaved()
      closeModelPicker()
    } catch (error) {
      const message = error instanceof Error ? error.message : '未知错误'
      setFeedback('error', `设置语音朗读模型失败：${message}`)
    } finally {
      isSavingPicker.value = false
    }
  }

  const savePickerSelections = async (provider: UserModelProvider) => {
    if (activeSection.value === 'tts') {
      await saveTTSSelection(provider)
      return
    }
    await saveChatSelections(provider)
  }

  const setPrimaryChatModel = async (model?: UserAIModel) => {
    if (!model) {
      return
    }
    try {
      await updateUserModelMutation.mutateAsync({
        id: model.id,
        data: { is_enabled: true, is_default_chat: true },
      })
      await loadBundle()
      onSaved()
    } catch (error) {
      const message = error instanceof Error ? error.message : '未知错误'
      setFeedback('error', `设置主模型失败：${message}`)
    }
  }

  const setPrimaryChatModelById = async (event: Event) => {
    const modelId = Number((event.target as HTMLSelectElement).value)
    if (!modelId) {
      return
    }
    await setPrimaryChatModel(models.value.find((model) => model.id === modelId))
  }

  const selectEmbeddingModel = async (provider: UserModelProvider, modelName: string) => {
    try {
      const selected = await upsertModelForCapability(provider, modelName, 'embedding')
      const embeddingModels = models.value.filter((model) => model.capabilities.embedding)
      await Promise.all(
        embeddingModels.map((model) =>
          updateUserModelMutation.mutateAsync({
            id: model.id,
            data: {
              is_enabled: model.id === selected.id,
              is_default_embedding: model.id === selected.id,
            },
          }),
        ),
      )
      if (!embeddingModels.some((model) => model.id === selected.id)) {
        await updateUserModelMutation.mutateAsync({
          id: selected.id,
          data: { is_enabled: true, is_default_embedding: true },
        })
      }
      await loadBundle()
      onSaved()
    } catch (error) {
      const message = error instanceof Error ? error.message : '未知错误'
      setFeedback('error', `设置向量模型失败：${message}`)
    }
  }

  const selectPendingTTSModel = (provider: UserModelProvider, modelName: string) => {
    // 音色/倍速已移至朗读控件（全局偏好），这里只记录待保存的默认朗读模型
    void provider
    pendingTTSModelName.value = modelName
  }

  const deleteModelForActiveSection = async (provider: UserModelProvider, modelName: string) => {
    const model = savedModelForActiveSection(provider.id, modelName)
    if (!model) {
      return
    }
    if (model.is_default_chat) {
      setFeedback('error', '主模型不能直接删除，请先选择另一个主模型。')
      return
    }
    if (model.is_default_embedding) {
      setFeedback('error', '当前向量模型不能直接删除，请先选择另一个向量模型。')
      return
    }
    if (model.is_default_tts) {
      setFeedback('error', '当前语音朗读模型不能直接删除，请先选择另一个语音朗读模型。')
      return
    }

    const label = model.display_name || model.model_name
    const confirmed = await globalAlert.showConfirm(
      `确定删除模型"${label}"吗？关联的阶段路由也会一起移除。`,
      '删除模型',
    )
    if (!confirmed) {
      return
    }

    try {
      await deleteUserModelMutation.mutateAsync(model.id)
      await loadBundle()
      setFeedback('success', '模型已删除。')
      onSaved()
    } catch (error) {
      const message = error instanceof Error ? error.message : '未知错误'
      setFeedback('error', `删除模型失败：${message}`)
    }
  }

  return {
    modelNamesForProvider,
    filteredModelNamesForProvider,
    selectedModelChipsForProvider,
    savedModelForActiveSection,
    isModelSelectedForActiveSection,
    activeModelStateLabel,
    upsertModelForCapability,
    togglePendingChatModel,
    saveChatSelections,
    savePickerSelections,
    setPrimaryChatModel,
    setPrimaryChatModelById,
    selectEmbeddingModel,
    selectPendingTTSModel,
    saveTTSSelection,
    deleteModelForActiveSection,
  }
}
