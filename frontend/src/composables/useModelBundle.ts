import { computed, ref, watch } from 'vue'
import type { UserAIModel, UserModelProvider } from '@/api/llm'
import {
  useDeleteProviderMutation,
  useDeleteUserModelMutation,
  useLLMConfigBundleQuery,
  useSaveProviderMutation,
  useSaveStageRoutesMutation,
  useSaveUserModelMutation,
  useToggleProviderMutation,
  useUpdateUserModelMutation,
} from '@/queries/llm'

interface UseModelBundleOptions {
  /** bundle 刷新成功后的回调（主组件用于同步阶段路由选择，延迟绑定规避 const TDZ） */
  onLoaded?: () => void
}

/**
 * 模型路由的数据获取与变更基础设施。从 PersonalModelRouting.vue 抽出（Slice 3）。
 * 内化 bundleQuery + 7 mutation + providers/models/各类 saving 状态 computed + feedback 反馈 +
 * loadBundle 刷新 + bundle.error 错误反馈 watch。onLoaded 回调交父，解耦阶段路由状态（Slice 5）。
 */
export const useModelBundle = (options: UseModelBundleOptions = {}) => {
  const bundleQuery = useLLMConfigBundleQuery()
  const saveProviderMutation = useSaveProviderMutation()
  const toggleProviderMutation = useToggleProviderMutation()
  const deleteProviderMutation = useDeleteProviderMutation()
  const saveUserModelMutation = useSaveUserModelMutation()
  const updateUserModelMutation = useUpdateUserModelMutation()
  const deleteUserModelMutation = useDeleteUserModelMutation()
  const saveStageRoutesMutation = useSaveStageRoutesMutation()

  const providers = computed<UserModelProvider[]>(() => bundleQuery.data.value?.providers ?? [])
  const models = computed<UserAIModel[]>(() => bundleQuery.data.value?.models ?? [])
  const isLoading = computed(() => bundleQuery.isLoading.value || bundleQuery.isFetching.value)
  const isSavingProvider = computed(
    () =>
      saveProviderMutation.isPending.value ||
      toggleProviderMutation.isPending.value ||
      deleteProviderMutation.isPending.value,
  )
  const isSavingRoutes = computed(() => saveStageRoutesMutation.isPending.value)

  const feedback = ref<{ type: 'success' | 'error'; message: string }>({
    type: 'success',
    message: '',
  })
  const setFeedback = (type: 'success' | 'error', message: string) => {
    feedback.value = { type, message }
  }

  const loadBundle = async () => {
    const result = await bundleQuery.refetch()
    if (result.error) {
      const message = result.error instanceof Error ? result.error.message : '未知错误'
      setFeedback('error', `读取模型设置失败：${message}`)
      return
    }
    options.onLoaded?.()
  }

  watch(
    () => bundleQuery.error.value,
    (error) => {
      if (!error) return
      const message = error instanceof Error ? error.message : '未知错误'
      setFeedback('error', `读取模型设置失败：${message}`)
    },
  )

  return {
    bundleQuery,
    saveProviderMutation,
    toggleProviderMutation,
    deleteProviderMutation,
    saveUserModelMutation,
    updateUserModelMutation,
    deleteUserModelMutation,
    saveStageRoutesMutation,
    providers,
    models,
    isLoading,
    isSavingProvider,
    isSavingRoutes,
    feedback,
    setFeedback,
    loadBundle,
  }
}
