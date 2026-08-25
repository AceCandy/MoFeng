// AIMETA P=后台任务Query_任务日志初始查询|R=任务列表初始查询_任务详情查询|NR=不含任务提交|E=query:tasks|X=internal|A=useTasksQuery|D=@tanstack/vue-query|S=net|RD=./README.ai
import {
  computed,
  onMounted,
  onUnmounted,
  ref,
  toValue,
  watch,
  type MaybeRefOrGetter,
} from 'vue'
import { useQuery } from '@tanstack/vue-query'

import {
  TaskContractError,
  TaskAPI,
  type BackgroundTask,
  type BackgroundTaskEvent,
  type BackgroundTaskSnapshot,
  type BackgroundTaskStreamScope,
} from '@/api/tasks'

type TaskIdSource = MaybeRefOrGetter<string | null | undefined>
type TaskStreamScopeSource = MaybeRefOrGetter<BackgroundTaskStreamScope | null | undefined>
type TaskStreamConnectedSource = MaybeRefOrGetter<boolean | null | undefined>

export const tasksQueryKeys = {
  all: ['tasks'] as const,
  list: () => [...tasksQueryKeys.all, 'list'] as const,
  detail: (taskId: string) => [...tasksQueryKeys.all, 'detail', taskId] as const,
}

export function useTasksQuery(streamConnected?: TaskStreamConnectedSource) {
  return useQuery<BackgroundTask[]>({
    queryKey: tasksQueryKeys.list(),
    queryFn: () => TaskAPI.getTasks(),
    // SSE 是主同步通道；轮询用于连接异常时兜底刷新任务日志。
    refetchInterval: computed(() => toValue(streamConnected) ? false : 15_000),
  })
}

export function useTaskQuery(taskId: TaskIdSource) {
  return useQuery<BackgroundTask>({
    queryKey: computed(() => tasksQueryKeys.detail(toValue(taskId) || '__missing__')),
    queryFn: () => TaskAPI.getTask(toValue(taskId) || ''),
    enabled: computed(() => Boolean(toValue(taskId))),
  })
}

export function reduceTaskEvent(
  tasks: BackgroundTask[],
  currentCursor: number | null,
  event: BackgroundTaskEvent,
  limit = 20,
): { tasks: BackgroundTask[]; cursor: number } {
  if (currentCursor !== null && event.cursor <= currentCursor) {
    return { tasks, cursor: currentCursor }
  }
  const nextTasks = tasks.filter((task) => task.id !== event.task.id)
  nextTasks.push(event.task)
  nextTasks.sort((left, right) => Date.parse(right.created_at) - Date.parse(left.created_at))
  return {
    tasks: nextTasks.slice(0, limit),
    cursor: event.cursor,
  }
}

/**
 * 后台任务 SSE 流：封装订阅、断线重连与卸载清理，供 AppShell 等外壳组件复用。
 * 返回 sseBackgroundTasks（SSE 推送快照）、isTaskStreamActive（连接态）与 start/stop 控制。
 */
export function useTaskStream(
  ownerId?: MaybeRefOrGetter<number | null | undefined>,
  streamScope?: TaskStreamScopeSource,
) {
  const sseBackgroundTasks = ref<BackgroundTask[] | null>(null)
  const isTaskStreamActive = ref(false)
  const isTaskStreamConnected = ref(false)
  const resumeCursor = ref<number | null>(null)
  const controller = ref<AbortController | null>(null)
  const reconnectTimer = ref<number | null>(null)
  let mounted = false
  let contractRecoveryAttempted = false

  const applySnapshot = (snapshot: BackgroundTaskSnapshot) => {
    sseBackgroundTasks.value = snapshot.tasks
    resumeCursor.value = snapshot.resume_cursor
    isTaskStreamActive.value = false
  }

  const stopTaskStream = () => {
    if (reconnectTimer.value !== null) {
      window.clearTimeout(reconnectTimer.value)
      reconnectTimer.value = null
    }
    controller.value?.abort()
    controller.value = null
    isTaskStreamActive.value = false
    isTaskStreamConnected.value = false
    contractRecoveryAttempted = false
  }

  const fallBackToPolling = (ac: AbortController) => {
    ac.abort()
    if (controller.value === ac) controller.value = null
    sseBackgroundTasks.value = null
    resumeCursor.value = null
    isTaskStreamActive.value = false
    isTaskStreamConnected.value = false
    console.error('任务日志数据校验失败，已回退到轮询同步')
  }

  const connectTaskStream = () => {
    if (ownerId && toValue(ownerId) == null) return
    if (reconnectTimer.value !== null) {
      window.clearTimeout(reconnectTimer.value)
      reconnectTimer.value = null
    }
    controller.value?.abort()
    const ac = new AbortController()
    controller.value = ac
    isTaskStreamConnected.value = false
    isTaskStreamActive.value = true
    const scope = streamScope ? toValue(streamScope) ?? undefined : undefined
    const isCurrentConnection = () => controller.value === ac && !ac.signal.aborted

    void (async () => {
      try {
        const outcome = await TaskAPI.subscribeTasks({
          signal: ac.signal,
          cursor: resumeCursor.value,
          scope,
          onOpen: () => {
            if (!isCurrentConnection()) return
            isTaskStreamConnected.value = true
          },
          onSnapshot: (snapshot) => {
            if (!isCurrentConnection()) return
            contractRecoveryAttempted = false
            applySnapshot(snapshot)
          },
          onTask: (event) => {
            if (!isCurrentConnection()) return
            contractRecoveryAttempted = false
            const next = reduceTaskEvent(
              sseBackgroundTasks.value ?? [],
              resumeCursor.value,
              event,
            )
            sseBackgroundTasks.value = next.tasks
            resumeCursor.value = next.cursor
            isTaskStreamActive.value = false
          },
          onReset: () => {
            if (!isCurrentConnection()) return
            contractRecoveryAttempted = false
            isTaskStreamConnected.value = false
            isTaskStreamActive.value = true
          },
          onError: (error) => {
            if (!isCurrentConnection()) return
            console.error('任务日志 SSE 同步失败:', error)
            sseBackgroundTasks.value = null
            isTaskStreamConnected.value = false
            isTaskStreamActive.value = false
          },
        })
        if (!isCurrentConnection() || outcome !== 'reset') return
        let snapshot: BackgroundTaskSnapshot
        try {
          snapshot = await TaskAPI.getSnapshot(20, scope)
        } catch (error) {
          if (error instanceof TaskContractError) {
            fallBackToPolling(ac)
            return
          }
          throw error
        }
        if (!isCurrentConnection()) return
        applySnapshot(snapshot)
        connectTaskStream()
      } catch (error) {
        if (!isCurrentConnection()) return
        sseBackgroundTasks.value = null
        isTaskStreamConnected.value = false
        if (error instanceof TaskContractError) {
          if (contractRecoveryAttempted) {
            fallBackToPolling(ac)
            return
          }
          contractRecoveryAttempted = true
          try {
            const snapshot = await TaskAPI.getSnapshot(20, scope)
            if (!isCurrentConnection()) return
            applySnapshot(snapshot)
            connectTaskStream()
          } catch (snapshotError) {
            if (!isCurrentConnection()) return
            if (snapshotError instanceof TaskContractError) {
              fallBackToPolling(ac)
              return
            }
            console.error('任务日志 snapshot 恢复失败:', snapshotError)
            isTaskStreamActive.value = false
            reconnectTimer.value = window.setTimeout(connectTaskStream, 3000)
          }
          return
        }
        console.error('任务日志 SSE 连接失败:', error)
        isTaskStreamActive.value = false
        reconnectTimer.value = window.setTimeout(connectTaskStream, 3000)
      }
    })()
  }

  const startTaskStream = () => {
    contractRecoveryAttempted = false
    connectTaskStream()
  }

  onMounted(() => {
    mounted = true
    startTaskStream()
  })

  if (ownerId || streamScope) {
    watch(
      () => [
        ownerId ? toValue(ownerId) : null,
        streamScope
          ? `${toValue(streamScope)?.stream_type ?? ''}:${toValue(streamScope)?.stream_id ?? ''}`
          : '',
      ] as const,
      (nextIdentity, previousIdentity) => {
        if (
          nextIdentity[0] === previousIdentity[0]
          && nextIdentity[1] === previousIdentity[1]
        ) return
        stopTaskStream()
        sseBackgroundTasks.value = null
        resumeCursor.value = null
        if (mounted && (!ownerId || nextIdentity[0] != null)) {
          startTaskStream()
        }
      },
    )
  }

  onUnmounted(stopTaskStream)

  return {
    sseBackgroundTasks,
    isTaskStreamActive,
    isTaskStreamConnected,
    resumeCursor,
    startTaskStream,
    stopTaskStream,
  }
}
