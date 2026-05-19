// AIMETA P=管理后台Query组合函数_管理端服务端状态|R=stats_users_prompts_settings_logs|NR=不含UI|E=query:admin|X=internal|A=useAdminUsersQuery_useSystemConfigsQuery|D=@tanstack/vue-query|S=net,cache|RD=./README.ai
import { computed, toValue, type MaybeRefOrGetter } from 'vue'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import {
  API_BASE_URL,
  AdminAPI,
  type AdminNovelSummary,
  type AdminUser,
  type PromptCreatePayload,
  type PromptItem,
  type PromptUpdatePayload,
  type Statistics,
  type SystemConfig,
  type SystemConfigUpdatePayload,
  type SystemConfigUpsertPayload,
  type UpdateLog,
  type UpdateLogPayload,
  type UserCreatePayload,
  type UserUpdatePayload,
} from '@/api/admin'
import { requestJson } from '@/api/http'

type EnabledSource = MaybeRefOrGetter<boolean | undefined>

export interface RemoteVersionResponse {
  version?: string | null
  source?: string | null
  errors?: string[]
  build_time_beijing?: string | null
}

export const adminQueryKeys = {
  all: ['admin'] as const,
  statistics: () => [...adminQueryKeys.all, 'statistics'] as const,
  users: () => [...adminQueryKeys.all, 'users'] as const,
  novels: () => [...adminQueryKeys.all, 'novels'] as const,
  prompts: () => [...adminQueryKeys.all, 'prompts'] as const,
  updateLogs: () => [...adminQueryKeys.all, 'update-logs'] as const,
  systemConfigs: () => [...adminQueryKeys.all, 'system-configs'] as const,
  remoteVersion: () => [...adminQueryKeys.all, 'remote-version'] as const,
}

const getRemoteVersionInfo = async (): Promise<RemoteVersionResponse> => {
  return requestJson<RemoteVersionResponse>(`${API_BASE_URL}/api/updates/remote-version`, {
    method: 'GET',
    timeoutMs: 15_000,
    fallbackErrorMessage: '获取远程版本信息失败',
  })
}

export function useAdminStatisticsQuery() {
  return useQuery<Statistics>({
    queryKey: adminQueryKeys.statistics(),
    queryFn: () => AdminAPI.getStatistics(),
  })
}

export function useAdminUsersQuery() {
  return useQuery<AdminUser[]>({
    queryKey: adminQueryKeys.users(),
    queryFn: () => AdminAPI.listUsers(),
  })
}

export function useCreateAdminUserMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: UserCreatePayload) => AdminAPI.createUser(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminQueryKeys.users() }),
  })
}

export function useUpdateAdminUserMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: { id: number; data: UserUpdatePayload }) =>
      AdminAPI.updateUser(payload.id, payload.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminQueryKeys.users() }),
  })
}

export function useDeleteAdminUserMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => AdminAPI.deleteUser(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminQueryKeys.users() }),
  })
}

export function useAdminNovelsQuery() {
  return useQuery<AdminNovelSummary[]>({
    queryKey: adminQueryKeys.novels(),
    queryFn: () => AdminAPI.listNovels(),
  })
}

export function useAdminPromptsQuery() {
  return useQuery<PromptItem[]>({
    queryKey: adminQueryKeys.prompts(),
    queryFn: () => AdminAPI.listPrompts(),
  })
}

export function useCreateAdminPromptMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: PromptCreatePayload) => AdminAPI.createPrompt(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminQueryKeys.prompts() }),
  })
}

export function useUpdateAdminPromptMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: { id: number; data: PromptUpdatePayload }) =>
      AdminAPI.updatePrompt(payload.id, payload.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminQueryKeys.prompts() }),
  })
}

export function useDeleteAdminPromptMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => AdminAPI.deletePrompt(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminQueryKeys.prompts() }),
  })
}

export function useAdminUpdateLogsQuery() {
  return useQuery<UpdateLog[]>({
    queryKey: adminQueryKeys.updateLogs(),
    queryFn: () => AdminAPI.listUpdateLogs(),
  })
}

export function useCreateAdminUpdateLogMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: UpdateLogPayload & { content: string }) =>
      AdminAPI.createUpdateLog(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminQueryKeys.updateLogs() }),
  })
}

export function useUpdateAdminUpdateLogMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: { id: number; data: UpdateLogPayload }) =>
      AdminAPI.updateUpdateLog(payload.id, payload.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminQueryKeys.updateLogs() }),
  })
}

export function useDeleteAdminUpdateLogMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => AdminAPI.deleteUpdateLog(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminQueryKeys.updateLogs() }),
  })
}

export function useSystemConfigsQuery() {
  return useQuery<SystemConfig[]>({
    queryKey: adminQueryKeys.systemConfigs(),
    queryFn: () => AdminAPI.listSystemConfigs(),
  })
}

export function useUpsertSystemConfigMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: { key: string; data: SystemConfigUpsertPayload }) =>
      AdminAPI.upsertSystemConfig(payload.key, payload.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminQueryKeys.systemConfigs() }),
  })
}

export function usePatchSystemConfigMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: { key: string; data: SystemConfigUpdatePayload }) =>
      AdminAPI.patchSystemConfig(payload.key, payload.data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminQueryKeys.systemConfigs() }),
  })
}

export function useDeleteSystemConfigMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (key: string) => AdminAPI.deleteSystemConfig(key),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminQueryKeys.systemConfigs() }),
  })
}

export function useRemoteVersionQuery(enabled: EnabledSource = true) {
  return useQuery<RemoteVersionResponse>({
    queryKey: computed(() => adminQueryKeys.remoteVersion()),
    queryFn: getRemoteVersionInfo,
    enabled: computed(() => Boolean(toValue(enabled))),
  })
}

export function useChangePasswordMutation() {
  return useMutation({
    mutationFn: (payload: { oldPassword: string; newPassword: string }) =>
      AdminAPI.changePassword(payload.oldPassword, payload.newPassword),
  })
}
