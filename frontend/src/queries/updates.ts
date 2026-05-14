// AIMETA P=更新日志Query组合函数_入口公告服务端状态|R=latest_updates|NR=不含UI|E=query:updates|X=internal|A=useLatestUpdatesQuery|D=@tanstack/vue-query|S=net,cache|RD=./README.ai
import { computed, toValue, type MaybeRefOrGetter } from 'vue'
import { useQuery } from '@tanstack/vue-query'
import { getLatestUpdates, type UpdateLog } from '@/api/updates'

type EnabledSource = MaybeRefOrGetter<boolean | undefined>

export const updateQueryKeys = {
  all: ['updates'] as const,
  latest: () => [...updateQueryKeys.all, 'latest'] as const,
}

export function useLatestUpdatesQuery(enabled: EnabledSource = true) {
  return useQuery<UpdateLog[]>({
    queryKey: updateQueryKeys.latest(),
    queryFn: getLatestUpdates,
    enabled: computed(() => Boolean(toValue(enabled))),
    staleTime: 5 * 60_000,
  })
}
