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
  TaskAPI,
  type BackgroundTask,
  type BackgroundTaskEvent,
  type BackgroundTaskStreamScope,
} from '@/api/tasks'

type TaskIdSource = MaybeRefOrGetter<string | null | undefined>
type TaskStreamScopeSource = MaybeRefOrGetter<BackgroundTaskStreamScope | null | undefined>

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
  const resumeCursor = ref<number | null>(null)
  const controller = ref<AbortController | null>(null)
  const reconnectTimer = ref<number | null>(null)
  let mounted = false

  const stopTaskStream = () => {
    if (reconnectTimer.value !== null) {
      window.clearTimeout(reconnectTimer.value)
      reconnectTimer.value = null
    }
    controller.value?.abort()
    controller.value = null
    isTaskStreamActive.value = false
  }

  const startTaskStream = () => {
    if (ownerId && toValue(ownerId) == null) return
    if (reconnectTimer.value !== null) {
      window.clearTimeout(reconnectTimer.value)
      reconnectTimer.value = null
    }
    controller.value?.abort()
    const ac = new AbortController()
    controller.value = ac
    isTaskStreamActive.value = true

    void (async () => {
      try {
        const outcome = await TaskAPI.subscribeTasks({
          signal: ac.signal,
          cursor: resumeCursor.value,
          scope: streamScope ? toValue(streamScope) ?? undefined : undefined,
          onSnapshot: (snapshot) => {
            sseBackgroundTasks.value = snapshot.tasks
            resumeCursor.value = snapshot.resume_cursor
            isTaskStreamActive.value = false
          },
          onTask: (event) => {
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
            isTaskStreamActive.value = true
          },
          onError: (error) => {
            if (ac.signal.aborted) return
            console.error('任务日志 SSE 同步失败:', error)
            isTaskStreamActive.value = false
          },
        })
        if (ac.signal.aborted || outcome !== 'reset') return
        const snapshot = await TaskAPI.getSnapshot(
          20,
          streamScope ? toValue(streamScope) ?? undefined : undefined,
        )
        if (ac.signal.aborted) return
        sseBackgroundTasks.value = snapshot.tasks
        resumeCursor.value = snapshot.resume_cursor
        startTaskStream()
      } catch (error) {
        if (ac.signal.aborted) return
        console.error('任务日志 SSE 连接失败:', error)
        isTaskStreamActive.value = false
        reconnectTimer.value = window.setTimeout(startTaskStream, 3000)
      }
    })()
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
    resumeCursor,
    startTaskStream,
    stopTaskStream,
  }
}
