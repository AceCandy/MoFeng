// AIMETA P=LLM设置Query组合函数_模型配置服务端状态|R=bundle_providers_models_routes|NR=不含UI|E=query:llm|X=internal|A=useLLMConfigBundleQuery|D=@tanstack/vue-query|S=net,cache|RD=./README.ai
import { computed, toValue, type MaybeRefOrGetter } from 'vue'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import {
  createProvider,
  createUserModel,
  deleteProvider,
  deleteUserModel,
  getLLMConfigBundle,
  getProviderModels,
  saveStageRoutes,
  updateProvider,
  updateUserModel,
  type LLMConfigBundle,
  type ProviderCreate,
  type ProviderUpdate,
  type StageRoutesPayload,
  type UserAIModelCreate,
  type UserAIModelUpdate,
} from '@/api/llm'

type NumberSource = MaybeRefOrGetter<number | null | undefined>
type EnabledSource = MaybeRefOrGetter<boolean | undefined>
type CapabilitySource = MaybeRefOrGetter<string | undefined>

export const llmQueryKeys = {
  all: ['llm-config'] as const,
  bundle: () => [...llmQueryKeys.all, 'bundle'] as const,
  providerModels: (providerId: number, capability = 'all') =>
    [...llmQueryKeys.all, 'provider-models', providerId, capability] as const,
}

const invalidateBundle = (queryClient: ReturnType<typeof useQueryClient>) =>
  queryClient.invalidateQueries({ queryKey: llmQueryKeys.bundle() })

export function useLLMConfigBundleQuery() {
  return useQuery<LLMConfigBundle>({
    queryKey: llmQueryKeys.bundle(),
    queryFn: getLLMConfigBundle,
  })
}

export function useProviderModelsQuery(
  providerId: NumberSource,
  capability: CapabilitySource = 'all',
  enabled: EnabledSource = true,
) {
  return useQuery<string[]>({
    queryKey: computed(() =>
      llmQueryKeys.providerModels(
        toValue(providerId) ?? -1,
        toValue(capability) || 'all',
      ),
    ),
    queryFn: () => {
      const resolvedProviderId = toValue(providerId)
      if (!resolvedProviderId) {
        throw new Error('缺少供应商 ID')
      }
      return getProviderModels(resolvedProviderId)
    },
    enabled: computed(() => Boolean(toValue(providerId)) && Boolean(toValue(enabled))),
  })
}

export function useSaveProviderMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: { id?: number | null; data: ProviderCreate | ProviderUpdate }) =>
      payload.id ? updateProvider(payload.id, payload.data as ProviderUpdate) : createProvider(payload.data as ProviderCreate),
    onSuccess: () => invalidateBundle(queryClient),
  })
}

export function useToggleProviderMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: { id: number; is_enabled: boolean }) =>
      updateProvider(payload.id, { is_enabled: payload.is_enabled }),
    onSuccess: () => invalidateBundle(queryClient),
  })
}

export function useDeleteProviderMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (providerId: number) => deleteProvider(providerId),
    onSuccess: () => invalidateBundle(queryClient),
  })
}

export function useSaveUserModelMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: UserAIModelCreate) => createUserModel(payload),
    onSuccess: () => invalidateBundle(queryClient),
  })
}

export function useUpdateUserModelMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: { id: number; data: UserAIModelUpdate }) =>
      updateUserModel(payload.id, payload.data),
    onSuccess: () => invalidateBundle(queryClient),
  })
}

export function useDeleteUserModelMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (modelId: number) => deleteUserModel(modelId),
    onSuccess: () => invalidateBundle(queryClient),
  })
}

export function useSaveStageRoutesMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: StageRoutesPayload) => saveStageRoutes(payload),
    onSuccess: () => invalidateBundle(queryClient),
  })
}
