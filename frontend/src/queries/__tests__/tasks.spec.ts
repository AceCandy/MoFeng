import { createApp, defineComponent, nextTick, ref } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { TaskAPI, type BackgroundTask, type BackgroundTaskEvent } from '@/api/tasks'
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

const event = (cursor: number, value: BackgroundTask): BackgroundTaskEvent => ({
  cursor,
  event_type: 'job.progressed',
  task: value,
})

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
                  'id: 42\nevent: reset\ndata: {"reason":"cursor_expired","retained_through_cursor":42}\n\n',
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

  it('切换用户或 stream scope 前清空旧 snapshot 与 cursor', async () => {
    const ownerId = ref(1)
    const scope = ref({ stream_type: 'workflow' as const, stream_id: 'run-1' })
    let stream: ReturnType<typeof useTaskStream> | undefined
    let subscriptionCount = 0
    const subscribe = vi.spyOn(TaskAPI, 'subscribeTasks').mockImplementation(async (handlers) => {
      subscriptionCount += 1
      if (subscriptionCount === 1) {
        handlers.onSnapshot({
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
    await vi.waitFor(() => expect(stream?.resumeCursor.value).toBe(10))

    scope.value = { stream_type: 'workflow', stream_id: 'run-2' }
    await nextTick()

    expect(stream?.sseBackgroundTasks.value).toBeNull()
    expect(stream?.resumeCursor.value).toBeNull()
    expect(subscribe).toHaveBeenCalledTimes(2)
    expect(subscribe.mock.calls[1]?.[0].scope).toEqual(scope.value)

    app.unmount()
  })
})
