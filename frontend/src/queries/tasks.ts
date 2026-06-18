// AIMETA P=后台任务Query_任务日志初始查询|R=任务列表初始查询_任务详情查询|NR=不含任务提交|E=query:tasks|X=internal|A=useTasksQuery|D=@tanstack/vue-query|S=net|RD=./README.ai
import { computed, toValue, type MaybeRefOrGetter } from 'vue'
import { useQuery } from '@tanstack/vue-query'

import { TaskAPI, type BackgroundTask } from '@/api/tasks'

type TaskIdSource = MaybeRefOrGetter<string | null | undefined>

export const tasksQueryKeys = {
  all: ['tasks'] as const,
  list: () => [...tasksQueryKeys.all, 'list'] as const,
  detail: (taskId: string) => [...tasksQueryKeys.all, 'detail', taskId] as const,
}

export function useTasksQuery() {
  return useQuery<BackgroundTask[]>({
    queryKey: tasksQueryKeys.list(),
    queryFn: () => TaskAPI.getTasks(),
    // SSE 是主同步通道；轮询用于连接异常时兜底刷新任务日志。
    refetchInterval: 15_000,
  })
}

export function useTaskQuery(taskId: TaskIdSource) {
  return useQuery<BackgroundTask>({
    queryKey: computed(() => tasksQueryKeys.detail(toValue(taskId) || '__missing__')),
    queryFn: () => TaskAPI.getTask(toValue(taskId) || ''),
    enabled: computed(() => Boolean(toValue(taskId))),
  })
}
