import { createApp, defineComponent, nextTick, ref } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  TaskAPI,
  TaskContractError,
  decodeBackgroundTaskStreamMessage,
  type BackgroundTask,
  type BackgroundTaskEvent,
  type BackgroundTaskSnapshot,
  type BackgroundTaskStreamScope,
} from '@/api/tasks'
import { reduceTaskEvent, useTaskStream } from '@/queries/tasks'


const task = (id: string, createdAt: string, progress = 0): BackgroundTask => ({
  id,
  user_id: 1,
  task_type: 'test',
  title: id,
  status: progress === 100 ? 'succeeded' : 'running',
  progress,
  log_entries: [],
  created_at: createdAt,
  updated_at: createdAt,
})

const scopedTask = (
  id: string,
  scope: BackgroundTaskStreamScope,
  createdAt = '2026-07-28T00:00:00Z',
) => ({ ...task(id, createdAt), ...scope })

const event = (cursor: number, value: BackgroundTask): BackgroundTaskEvent => ({
  schema_version: 1,
  cursor,
  event_type: 'job.progressed',
  task: value,
})

const snapshot = (
  tasks: BackgroundTask[] = [],
  cursor = 0,
  scope?: BackgroundTaskStreamScope,
): BackgroundTaskSnapshot => ({
  schema_version: 1,
  tasks,
  snapshot_revision: `snapshot:${cursor}`,
  resume_cursor: cursor,
  stream_type: scope?.stream_type,
  stream_id: scope?.stream_id,
})

const mountTaskStream = (
  ownerId: Parameters<typeof useTaskStream>[0],
  scope: Parameters<typeof useTaskStream>[1],
) => {
  let stream!: ReturnType<typeof useTaskStream>
  const host = document.createElement('div')
  const app = createApp(
    defineComponent({
      setup() {
        stream = useTaskStream(ownerId, scope)
        return () => null
      },
    }),
  )
  app.mount(host)
  return { app, stream }
}

describe('reduceTaskEvent', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
    vi.useRealTimers()
  })

  it('按任务 ID upsert，并忽略重复或倒退 cursor', () => {
    const initial = [task('one', '2026-07-28T00:00:00Z')]
    const updated = task('one', '2026-07-28T00:00:00Z', 100)

    const applied = reduceTaskEvent(initial, 10, event(11, updated))
    const duplicate = reduceTaskEvent(applied.tasks, applied.cursor, event(11, initial[0]))

    expect(applied.tasks).toEqual([updated])
    expect(applied.cursor).toBe(11)
    expect(duplicate).toEqual(applied)
  })

  it('维持创建时间倒序并限制 snapshot 窗口', () => {
    const older = task('older', '2026-07-27T00:00:00Z')
    const newer = task('newer', '2026-07-29T00:00:00Z')

    const applied = reduceTaskEvent([older], null, event(12, newer), 1)

    expect(applied.tasks).toEqual([newer])
    expect(applied.cursor).toBe(12)
  })

  it('解码合法 snapshot、task、reset 并忽略未知外层事件', () => {
    const value = task('job-1', '2026-07-28T00:00:00Z')
    const currentSnapshot = snapshot([value], 10)
    const currentEvent = event(11, value)
    const reset = {
      schema_version: 1 as const,
      reason: 'cursor_expired' as const,
      retained_through_cursor: 11,
    }

    expect(decodeBackgroundTaskStreamMessage('snapshot', currentSnapshot)).toEqual({
      kind: 'ok',
      event: 'snapshot',
      value: currentSnapshot,
    })
    expect(decodeBackgroundTaskStreamMessage('task', currentEvent)).toEqual({
      kind: 'ok',
      event: 'task',
      value: currentEvent,
    })
    expect(decodeBackgroundTaskStreamMessage('reset', reset)).toEqual({
      kind: 'ok',
      event: 'reset',
      value: reset,
    })
    expect(decodeBackgroundTaskStreamMessage('future-event', currentEvent)).toEqual({
      kind: 'ignored_unknown_event',
    })
  })

  it('拒绝畸形数据与未知 schema version', () => {
    const value = task('job-1', '2026-07-28T00:00:00Z')

    expect(decodeBackgroundTaskStreamMessage('task', {
      ...event(11, value),
      cursor: '11',
    })).toEqual({ kind: 'malformed', reason: 'task' })
    expect(decodeBackgroundTaskStreamMessage('snapshot', {
      ...snapshot([value], 10),
      schema_version: 2,
    })).toEqual({ kind: 'unsupported_version', version: 2 })
    expect(decodeBackgroundTaskStreamMessage('reset', {
      reason: 'cursor_expired',
      retained_through_cursor: 10,
    })).toEqual({ kind: 'malformed', reason: 'schema_version' })
  })

  it('只接受可空正整数章节号', () => {
    const value = task('job-1', '2026-07-28T00:00:00Z')
    const withChapter = { ...value, chapter_number: 3 }

    expect(decodeBackgroundTaskStreamMessage('task', event(11, withChapter))).toEqual({
      kind: 'ok',
      event: 'task',
      value: event(11, withChapter),
    })
    for (const chapterNumber of [0, -1, 1.5, true, '3']) {
      expect(decodeBackgroundTaskStreamMessage('task', event(11, {
        ...value,
        chapter_number: chapterNumber,
      } as BackgroundTask))).toEqual({ kind: 'malformed', reason: 'task' })
    }
  })

  it('task 事件严格复核 expected scope，并保留全局流兼容性', () => {
    const expectedScope = { stream_type: 'workflow' as const, stream_id: 'run-1' }
    const matching = event(11, scopedTask('job-1', expectedScope))
    const wrongType = event(11, scopedTask('job-1', { stream_type: 'job', stream_id: 'run-1' }))
    const wrongId = event(11, scopedTask('job-1', { stream_type: 'workflow', stream_id: 'run-2' }))

    expect(decodeBackgroundTaskStreamMessage('task', matching, expectedScope)).toEqual({
      kind: 'ok', event: 'task', value: matching,
    })
    expect(decodeBackgroundTaskStreamMessage('task', wrongType, expectedScope)).toEqual({
      kind: 'malformed', reason: 'scope',
    })
    expect(decodeBackgroundTaskStreamMessage('task', wrongId, expectedScope)).toEqual({
      kind: 'malformed', reason: 'scope',
    })
    expect(decodeBackgroundTaskStreamMessage('task', matching)).toEqual({
      kind: 'ok', event: 'task', value: matching,
    })
  })

  it('等待指定 durable task 到 succeeded 后才返回', async () => {
    vi.useFakeTimers()
    const running = task('job-1', '2026-07-28T00:00:00Z', 50)
    const succeeded = task('job-1', '2026-07-28T00:00:00Z', 100)
    vi.spyOn(TaskAPI, 'getTask')
      .mockResolvedValueOnce(running)
      .mockResolvedValueOnce(succeeded)

    const completion = TaskAPI.waitForCompletion('job-1', {
      pollIntervalMs: 100,
      timeoutMs: 1_000,
    })
    await vi.runAllTimersAsync()

    await expect(completion).resolves.toEqual(succeeded)
  })

  it('durable task 失败时向 mutation 传播公开错误', async () => {
    const failed = {
      ...task('job-2', '2026-07-28T00:00:00Z'),
      status: 'failed' as const,
      error: '章节生成外部调用结果不确定，需要人工确认',
    }
    vi.spyOn(TaskAPI, 'getTask').mockResolvedValue(failed)

    await expect(TaskAPI.waitForCompletion('job-2')).rejects.toThrow(failed.error)
  })

  it('snapshot 和 SSE 成对传递 workflow scope 与 cursor', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            schema_version: 1,
            tasks: [],
            snapshot_revision: 'stream:workflow:run-1:sequence:0:cursor:0',
            resume_cursor: 0,
            stream_type: 'workflow',
            stream_id: 'run-1',
          }),
          { headers: { 'content-type': 'application/json' } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          new ReadableStream({
            start(controller) {
              controller.enqueue(
                new TextEncoder().encode(
                  'id: 42\nevent: reset\ndata: {"schema_version":1,"reason":"cursor_expired","retained_through_cursor":42}\n\n',
                ),
              )
              controller.close()
            },
          }),
        ),
      )
    vi.stubGlobal('fetch', fetchMock)
    const scope = { stream_type: 'workflow' as const, stream_id: 'run-1' }

    await TaskAPI.getSnapshot(5, scope)
    await TaskAPI.subscribeTasks({
      limit: 5,
      cursor: 42,
      scope,
      onSnapshot: vi.fn(),
      onTask: vi.fn(),
      onReset: vi.fn(),
    })

    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      '/api/tasks/snapshot?limit=5&stream_type=workflow&stream_id=run-1',
    )
    expect(fetchMock.mock.calls[1]?.[0]).toBe(
      '/api/tasks/events?limit=5&cursor=42&stream_type=workflow&stream_id=run-1',
    )
    const eventOptions = fetchMock.mock.calls[1]?.[1] as RequestInit
    expect(new Headers(eventOptions.headers).get('Last-Event-ID')).toBe('42')
  })

  it('workflow opaque events_url 原样复用且仍通过 scope decoder', async () => {
    const opaqueUrl = '/opaque/workflow/events?signature=token%2Fvalue&mode=durable'
    const reset = {
      schema_version: 1 as const,
      reason: 'cursor_expired' as const,
      retained_through_cursor: 42,
    }
    const fetchMock = vi.fn(async () => new Response(new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(
          `event: reset\ndata: ${JSON.stringify(reset)}\n\n`,
        ))
        controller.close()
      },
    })))
    vi.stubGlobal('fetch', fetchMock)
    const scope = { stream_type: 'workflow' as const, stream_id: 'run-1' }
    const onOpen = vi.fn()
    const onReset = vi.fn()

    await expect(TaskAPI.subscribeTasks({
      eventsUrl: opaqueUrl,
      cursor: 42,
      scope,
      onOpen,
      onSnapshot: vi.fn(),
      onTask: vi.fn(),
      onReset,
    })).resolves.toBe('reset')

    expect(fetchMock.mock.calls[0]?.[0]).toBe(opaqueUrl)
    const eventOptions = fetchMock.mock.calls[0]?.[1] as RequestInit
    expect(new Headers(eventOptions.headers).get('Last-Event-ID')).toBe('42')
    expect(onOpen).toHaveBeenCalledOnce()
    expect(onReset).toHaveBeenCalledWith(reset)
  })

  it('SSE 仅将通过校验的事件交给 handler', async () => {
    const value = task('job-1', '2026-07-28T00:00:00Z')
    const currentSnapshot = snapshot([value], 10)
    const currentEvent = event(11, value)
    const reset = {
      schema_version: 1 as const,
      reason: 'cursor_expired' as const,
      retained_through_cursor: 11,
    }
    const payload = [
      `event: snapshot\ndata: ${JSON.stringify(currentSnapshot)}\n\n`,
      'event: future-event\ndata: {"schema_version":1}\n\n',
      `id: 11\nevent: task\ndata: ${JSON.stringify(currentEvent)}\n\n`,
      `event: reset\ndata: ${JSON.stringify(reset)}\n\n`,
    ].join('')
    vi.stubGlobal('fetch', vi.fn(async () => new Response(new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(payload))
        controller.close()
      },
    }))))
    const onSnapshot = vi.fn()
    const onTask = vi.fn()
    const onReset = vi.fn()

    await TaskAPI.subscribeTasks({ onSnapshot, onTask, onReset })

    expect(onSnapshot).toHaveBeenCalledOnce()
    expect(onSnapshot).toHaveBeenCalledWith(currentSnapshot)
    expect(onTask).toHaveBeenCalledOnce()
    expect(onTask).toHaveBeenCalledWith(currentEvent)
    expect(onReset).toHaveBeenCalledOnce()
    expect(onReset).toHaveBeenCalledWith(reset)
  })

  it('无效 SSE payload 不得调用状态 handler', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(
          'event: task\ndata: {"schema_version":1,"cursor":"bad"}\n\n',
        ))
        controller.close()
      },
    }))))
    const onSnapshot = vi.fn()
    const onTask = vi.fn()
    const onReset = vi.fn()

    await expect(TaskAPI.subscribeTasks({ onSnapshot, onTask, onReset }))
      .rejects.toBeInstanceOf(TaskContractError)
    expect(onSnapshot).not.toHaveBeenCalled()
    expect(onTask).not.toHaveBeenCalled()
    expect(onReset).not.toHaveBeenCalled()
  })

  it('scope 漂移的 task SSE 不调用 onTask', async () => {
    const scope = { stream_type: 'workflow' as const, stream_id: 'run-1' }
    const drifted = event(11, scopedTask('job-2', { stream_type: 'workflow', stream_id: 'run-2' }))
    vi.stubGlobal('fetch', vi.fn(async () => new Response(new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(
          `event: task\ndata: ${JSON.stringify(drifted)}\n\n`,
        ))
        controller.close()
      },
    }))))
    const onTask = vi.fn()

    await expect(TaskAPI.subscribeTasks({
      scope,
      onSnapshot: vi.fn(),
      onTask,
      onReset: vi.fn(),
    })).rejects.toMatchObject({ name: 'TaskContractError', code: 'malformed' })
    expect(onTask).not.toHaveBeenCalled()
  })

  it('HTTP snapshot 与 SSE 共用版本校验', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({
      ...snapshot([], 0),
      schema_version: 2,
    }), { headers: { 'content-type': 'application/json' } })))

    await expect(TaskAPI.getSnapshot()).rejects.toMatchObject({
      name: 'TaskContractError',
      code: 'unsupported_version',
    })
  })

  it('HTTP 与 SSE snapshot 都拒绝响应 scope 漂移', async () => {
    const expectedScope = { stream_type: 'workflow' as const, stream_id: 'run-1' }
    const mismatchedSnapshot = snapshot([], 10, {
      stream_type: 'workflow',
      stream_id: 'run-2',
    })
    expect(
      decodeBackgroundTaskStreamMessage('snapshot', mismatchedSnapshot, expectedScope),
    ).toEqual({ kind: 'malformed', reason: 'scope' })

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(mismatchedSnapshot), {
        headers: { 'content-type': 'application/json' },
      }))
      .mockResolvedValueOnce(new Response(new ReadableStream({
        start(controller) {
          controller.enqueue(new TextEncoder().encode(
            `event: snapshot\ndata: ${JSON.stringify(mismatchedSnapshot)}\n\n`,
          ))
          controller.close()
        },
      })))
    vi.stubGlobal('fetch', fetchMock)

    await expect(TaskAPI.getSnapshot(20, expectedScope)).rejects.toBeInstanceOf(TaskContractError)
    const onSnapshot = vi.fn()
    await expect(TaskAPI.subscribeTasks({
      scope: expectedScope,
      onSnapshot,
      onTask: vi.fn(),
      onReset: vi.fn(),
    })).rejects.toBeInstanceOf(TaskContractError)
    expect(onSnapshot).not.toHaveBeenCalled()
  })

  it('切换用户或 stream scope 前清空旧 snapshot 与 cursor', async () => {
    const ownerId = ref(1)
    const scope = ref({ stream_type: 'workflow' as const, stream_id: 'run-1' })
    let subscriptionCount = 0
    const subscribe = vi.spyOn(TaskAPI, 'subscribeTasks').mockImplementation(async (handlers) => {
      subscriptionCount += 1
      if (subscriptionCount === 1) {
        handlers.onSnapshot({
          schema_version: 1,
          tasks: [task('job-1', '2026-07-28T00:00:00Z')],
          snapshot_revision: 'stream:workflow:run-1:sequence:1:cursor:10',
          resume_cursor: 10,
          stream_type: 'workflow',
          stream_id: 'run-1',
        })
      }
      await new Promise<void>((resolve) => {
        handlers.signal?.addEventListener('abort', () => resolve(), { once: true })
      })
      return 'reset'
    })
    const { app, stream } = mountTaskStream(ownerId, scope)
    await vi.waitFor(() => expect(stream.resumeCursor.value).toBe(10))

    scope.value = { stream_type: 'workflow', stream_id: 'run-2' }
    await nextTick()

    expect(stream.sseBackgroundTasks.value).toBeNull()
    expect(stream.resumeCursor.value).toBeNull()
    expect(subscribe).toHaveBeenCalledTimes(2)
    expect(subscribe.mock.calls[1]?.[0].scope).toEqual(scope.value)

    app.unmount()
  })

  it('切换 scope 后忽略旧连接迟到的 snapshot 与 task', async () => {
    const ownerId = ref(1)
    const scope = ref({ stream_type: 'workflow' as const, stream_id: 'run-1' })
    const subscribe = vi.spyOn(TaskAPI, 'subscribeTasks').mockImplementation(async (handlers) => {
      await new Promise<void>((resolve) => {
        if (handlers.signal?.aborted) {
          resolve()
          return
        }
        handlers.signal?.addEventListener('abort', () => resolve(), { once: true })
      })
      return 'reset'
    })
    const { app, stream } = mountTaskStream(ownerId, scope)
    await vi.waitFor(() => expect(subscribe).toHaveBeenCalledOnce())
    const oldHandlers = subscribe.mock.calls[0]![0]

    scope.value = { stream_type: 'workflow', stream_id: 'run-2' }
    await nextTick()
    await vi.waitFor(() => expect(subscribe).toHaveBeenCalledTimes(2))
    const currentHandlers = subscribe.mock.calls[1]![0]
    const currentTask = task('run-2-task', '2026-07-28T00:00:00Z')
    currentHandlers.onSnapshot(snapshot([currentTask], 20, scope.value))

    const staleTask = task('run-1-task', '2026-07-29T00:00:00Z')
    oldHandlers.onSnapshot(snapshot([staleTask], 99, {
      stream_type: 'workflow',
      stream_id: 'run-1',
    }))
    oldHandlers.onTask(event(100, staleTask))

    expect(stream.sseBackgroundTasks.value).toEqual([currentTask])
    expect(stream.resumeCursor.value).toBe(20)

    app.unmount()
  })

  it('契约失败时仅执行一次同 scope snapshot 恢复', async () => {
    const ownerId = ref(1)
    const scope = ref({ stream_type: 'workflow' as const, stream_id: 'run-1' })
    const recoveredTask = task('job-recovered', '2026-07-28T00:00:00Z')
    const recoveredSnapshot = snapshot([recoveredTask], 25, scope.value)
    let subscriptionCount = 0
    const subscribe = vi.spyOn(TaskAPI, 'subscribeTasks').mockImplementation(async (handlers) => {
      subscriptionCount += 1
      if (subscriptionCount === 1) {
        throw new TaskContractError({ kind: 'malformed', reason: 'task' })
      }
      await new Promise<void>((resolve) => {
        handlers.signal?.addEventListener('abort', () => resolve(), { once: true })
      })
      return 'reset'
    })
    const getSnapshot = vi.spyOn(TaskAPI, 'getSnapshot').mockResolvedValue(recoveredSnapshot)

    const { app, stream } = mountTaskStream(ownerId, scope)
    await vi.waitFor(() => expect(subscribe).toHaveBeenCalledTimes(2))

    expect(getSnapshot).toHaveBeenCalledOnce()
    expect(getSnapshot).toHaveBeenCalledWith(20, scope.value)
    expect(stream.sseBackgroundTasks.value).toEqual([recoveredTask])
    expect(stream.resumeCursor.value).toBe(25)
    expect(subscribe.mock.calls[1]?.[0]).toMatchObject({
      cursor: 25,
      scope: scope.value,
    })

    app.unmount()
  })

  it('恢复 snapshot 仍无效时停止 SSE 并让出给轮询结果', async () => {
    const ownerId = ref(1)
    const scope = ref({ stream_type: 'workflow' as const, stream_id: 'run-1' })
    const contractError = new TaskContractError({ kind: 'malformed', reason: 'snapshot' })
    const subscribe = vi.spyOn(TaskAPI, 'subscribeTasks').mockRejectedValue(contractError)
    const getSnapshot = vi.spyOn(TaskAPI, 'getSnapshot').mockRejectedValue(contractError)
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => undefined)

    const { app, stream } = mountTaskStream(ownerId, scope)
    await vi.waitFor(() => expect(getSnapshot).toHaveBeenCalledOnce())

    expect(subscribe).toHaveBeenCalledOnce()
    expect(getSnapshot).toHaveBeenCalledWith(20, scope.value)
    expect(stream.sseBackgroundTasks.value).toBeNull()
    expect(stream.resumeCursor.value).toBeNull()
    expect(stream.isTaskStreamActive.value).toBe(false)
    expect(consoleError).toHaveBeenCalledWith('任务日志数据校验失败，已回退到轮询同步')

    app.unmount()
  })
})
