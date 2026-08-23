// AIMETA P=创作上下文Query_跨设备语义恢复缓存|R=列表查询_字段PATCH_缓存更新|NR=不含组件本地草稿|E=query:creation-contexts|X=internal|A=useCreationContextsQuery|D=@tanstack/vue-query|S=net,cache|RD=./README.ai
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'

import {
  CreationContextAPI,
  type CreationContext,
  type CreationContextPatch,
} from '@/api/creationContexts'

export const creationContextQueryKeys = {
  all: ['creation-contexts'] as const,
  list: () => [...creationContextQueryKeys.all, 'list'] as const,
}

const sortContexts = (contexts: CreationContext[]) =>
  [...contexts].sort((left, right) => {
    const updatedDifference = Date.parse(right.updated_at) - Date.parse(left.updated_at)
    return updatedDifference || left.project_id.localeCompare(right.project_id)
  })

export function useCreationContextsQuery() {
  return useQuery<CreationContext[]>({
    queryKey: creationContextQueryKeys.list(),
    queryFn: () => CreationContextAPI.getContexts(),
    refetchOnWindowFocus: 'always',
  })
}

export function usePatchCreationContextMutation() {
  const queryClient = useQueryClient()
  return useMutation<
    CreationContext,
    Error,
    { projectId: string; patch: CreationContextPatch }
  >({
    mutationFn: ({ projectId, patch }) => CreationContextAPI.patchContext(projectId, patch),
    onSuccess: (context) => {
      queryClient.setQueryData<CreationContext[]>(
        creationContextQueryKeys.list(),
        (current = []) => sortContexts([
          ...current.filter((item) => item.project_id !== context.project_id),
          context,
        ]),
      )
    },
  })
}
