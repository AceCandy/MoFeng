// AIMETA P=后台任务Query_任务日志初始查询|R=任务列表初始查询_任务详情查询|NR=不含任务提交|E=query:tasks|X=internal|A=useTasksQuery|D=@tanstack/vue-query|S=net|RD=./README.ai
import { computed, onUnmounted, ref, toValue, type MaybeRefOrGetter } from 'vue'
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

/**
 * 后台任务 SSE 流：封装订阅、断线重连与卸载清理，供 AppShell 等外壳组件复用。
 * 返回 sseBackgroundTasks（SSE 推送快照）、isTaskStreamActive（连接态）与 start/stop 控制。
 */
export function useTaskStream() {
  const sseBackgroundTasks = ref<BackgroundTask[] | null>(null)
  const isTaskStreamActive = ref(false)
  const controller = ref<AbortController | null>(null)
  const reconnectTimer = ref<number | null>(null)

  const stopTaskStream = () => {
    if (reconnectTimer.value !== null) {
      window.clearTimeout(reconnectTimer.value)
      reconnectTimer.value = null
    }
    controller.value?.abort()
  }

  const startTaskStream = () => {
    if (reconnectTimer.value !== null) {
      window.clearTimeout(reconnectTimer.value)
      reconnectTimer.value = null
    }
    controller.value?.abort()
    const ac = new AbortController()
    controller.value = ac
    isTaskStreamActive.value = true

    void TaskAPI.subscribeTasks({
      signal: ac.signal,
      onTasks: (tasks) => {
        sseBackgroundTasks.value = tasks
        isTaskStreamActive.value = false
      },
      onError: (error) => {
        if (ac.signal.aborted) return
        console.error('任务日志 SSE 同步失败:', error)
        isTaskStreamActive.value = false
      },
    }).catch((error) => {
      if (ac.signal.aborted) return
      console.error('任务日志 SSE 连接失败:', error)
      isTaskStreamActive.value = false
      reconnectTimer.value = window.setTimeout(startTaskStream, 3000)
    })
  }

  onUnmounted(stopTaskStream)

  return {
    sseBackgroundTasks,
    isTaskStreamActive,
    startTaskStream,
    stopTaskStream,
  }
}
