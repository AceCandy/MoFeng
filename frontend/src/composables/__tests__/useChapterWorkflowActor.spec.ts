// AIMETA P=章节工作流Vue_actor集成测试|R=scope_stream_reset_reconnect_polling与命令协调|NR=不测试页面渲染或真实HTTP|E=test:composable:chapter-workflow-actor|X=internal|A=useChapterWorkflowActor|D=vitest,vue,xstate|S=test|RD=../README.ai
import { createApp, defineComponent, nextTick, ref, type App, type Ref } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  ChapterWorkflowContractError,
  type ChapterWorkflowCommandConflictDetail,
  type ChapterWorkflowConnection,
  type ChapterWorkflowSnapshot,
  type ChapterWorkflowStartResponse,
} from '@/api/chapterWorkflow'
import type { BackgroundTaskEvent } from '@/api/tasks'
import {
  useChapterWorkflowActor,
  type ChapterWorkflowActorPorts,
  type ChapterWorkflowCommandPortResult,
  type ChapterWorkflowTaskSubscription,
} from '@/composables/useChapterWorkflowActor'

const RUN_ID = '11111111-1111-4111-8111-111111111111'
const RUN_ID_2 = '44444444-4444-4444-8444-444444444444'
const ROOT_JOB_ID = '22222222-2222-4222-8222-222222222222'
const PROJECT_ID = 'project-scope'
const CHAPTER_NUMBER = 3

const workflowSnapshot = (
  overrides: Partial<ChapterWorkflowSnapshot> = {},
): ChapterWorkflowSnapshot => ({
  run_id: RUN_ID,
  root_job_id: ROOT_JOB_ID,
  project_id: PROJECT_ID,
  chapter_id: 9,
  chapter_number: CHAPTER_NUMBER,
  base_revision: 2,
  current_chapter_revision: 2,
  workflow_version: 1,
  state_schema_version: 1,
  context_schema_version: 1,
  status: 'running',
  root_job_status: 'running',
  node_key: 'generate_candidate_1',
  checkpoint_id: 'checkpoint-3',
  progress: 40,
  row_revision: 1,
  is_active: true,
  successor_run_id: null,
  error_category: null,
  public_error: null,
  allowed_commands: ['cancel'],
  retry_activity_key: null,
  resume_cursor: 5,
  ...overrides,
})

const connection = (
  overrides: Partial<ChapterWorkflowSnapshot> = {},
  eventsUrl?: string,
): ChapterWorkflowConnection => {
  const snapshot = workflowSnapshot(overrides)
  return {
    events_url: eventsUrl ?? `/events/${snapshot.run_id}`,
    snapshot,
  }
}

const taskEvent = (cursor: number): BackgroundTaskEvent => ({
  schema_version: 1,
  cursor,
  event_type: 'job.progressed',
  task: {
    id: ROOT_JOB_ID,
    user_id: 1,
    task_type: 'chapter_workflow',
    title: '章节工作流',
    status: 'running',
    progress: 50,
    created_at: '2026-07-31T00:00:00Z',
    updated_at: '2026-07-31T00:00:01Z',
  },
})

const deferred = <Value>() => {
  let resolve!: (value: Value) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<Value>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, reject, resolve }
}

const flushPromises = async () => {
  await Promise.resolve()
  await Promise.resolve()
}

const createClock = () => {
  type Scheduled = { callback: () => void; cancelled: boolean }
  const pending: Scheduled[] = []
  const schedule = vi.fn((callback: () => void) => {
    const handle: Scheduled = { callback, cancelled: false }
    pending.push(handle)
    return handle
  })
  const cancel = vi.fn((handle: unknown) => {
    ;(handle as Scheduled).cancelled = true
  })
  const runNext = async () => {
    let next = pending.shift()
    while (next?.cancelled) next = pending.shift()
    if (!next) throw new Error('没有待执行的时钟任务')
    next.callback()
    await flushPromises()
  }
  return { cancel, pending, runNext, schedule }
}

const createStreamPort = () => {
  const subscriptions: ChapterWorkflowTaskSubscription[] = []
  const subscribeTasks: ChapterWorkflowActorPorts['subscribeTasks'] = vi.fn((handlers) => {
    subscriptions.push(handlers)
    return new Promise<'reset'>((_, reject) => {
      handlers.signal.addEventListener(
        'abort',
        () => reject(new DOMException('Aborted', 'AbortError')),
        { once: true },
      )
    })
  })
  return { subscribeTasks, subscriptions }
}

const mountedApps: Array<{ app: App; host: HTMLDivElement }> = []

const mountActor = (
  ports: ChapterWorkflowActorPorts,
  projectId: Ref<string> = ref(PROJECT_ID),
  chapterNumber: Ref<number | null> = ref(CHAPTER_NUMBER),
) => {
  let actor!: ReturnType<typeof useChapterWorkflowActor>
  const host = document.createElement('div')
  const app = createApp(defineComponent({
    setup() {
      actor = useChapterWorkflowActor(projectId, chapterNumber, ports)
      return () => null
    },
  }))
  app.mount(host)
  const mounted = { app, host }
  mountedApps.push(mounted)
  const unmount = () => {
    const index = mountedApps.indexOf(mounted)
    if (index >= 0) mountedApps.splice(index, 1)
    app.unmount()
    host.remove()
  }
  return { actor, app, chapterNumber, host, projectId, unmount }
}

const createPorts = (
  overrides: Partial<ChapterWorkflowActorPorts> = {},
) => {
  const clock = createClock()
  const stream = createStreamPort()
  const ports: ChapterWorkflowActorPorts = {
    lookup: vi.fn(async () => null),
    start: vi.fn(async () => {
      throw new Error('unexpected start')
    }),
    command: vi.fn(async () => {
      throw new Error('unexpected command')
    }),
    subscribeTasks: stream.subscribeTasks,
    invalidateChapterAndProject: vi.fn(async () => undefined),
    schedule: clock.schedule,
    cancelScheduled: clock.cancel,
    ...overrides,
  }
  return { clock, ports, stream }
}

afterEach(() => {
  for (const mounted of mountedApps.splice(0)) {
    mounted.app.unmount()
    mounted.host.remove()
  }
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('useChapterWorkflowActor', () => {
  it('未选择章节时不查询，选中后再建立 scope', async () => {
    const { ports } = createPorts()
    const chapterNumber = ref<number | null>(null)
    const { actor } = mountActor(ports, ref(PROJECT_ID), chapterNumber)

    await nextTick()
    expect(ports.lookup).not.toHaveBeenCalled()
    expect(actor.snapshot.value.value).toBe('booting')

    chapterNumber.value = CHAPTER_NUMBER
    await vi.waitFor(() => expect(ports.lookup).toHaveBeenCalledOnce())
    await vi.waitFor(() => expect(actor.snapshot.value.value).toEqual({
      ready: { workflow: 'idle', transport: 'disconnected' },
    }))

    chapterNumber.value = null
    await nextTick()
    expect(actor.snapshot.value.value).toBe('booting')
    expect(actor.snapshot.value.context.runId).toBeNull()
  })

  it('refresh 时从 current null 恢复 idle，且不创建 stream', async () => {
    const { ports, stream } = createPorts()
    const { actor } = mountActor(ports)

    await vi.waitFor(() => expect(actor.snapshot.value.value).toEqual({
      ready: { workflow: 'idle', transport: 'disconnected' },
    }))

    expect(ports.lookup).toHaveBeenCalledOnce()
    expect(stream.subscriptions).toHaveLength(0)
  })

  it('fatal 再次检查串行执行，并在查询为空后恢复 idle', async () => {
    const retriedLookup = deferred<ChapterWorkflowConnection | null>()
    const lookup = vi
      .fn()
      .mockRejectedValueOnce(
        new ChapterWorkflowContractError('unsupported_version', 'workflow_version'),
      )
      .mockImplementationOnce(() => retriedLookup.promise)
    const { ports } = createPorts({ lookup })
    const { actor } = mountActor(ports)
    await vi.waitFor(() => expect(actor.phase.value).toBe('fatal'))

    const first = actor.resync()
    const duplicate = actor.resync()
    expect(actor.resyncing.value).toBe(true)
    await expect(duplicate).resolves.toBe(false)
    expect(lookup).toHaveBeenCalledTimes(2)

    retriedLookup.resolve(null)
    await expect(first).resolves.toBe(true)
    expect(actor.resyncing.value).toBe(false)
    expect(actor.phase.value).toBe('idle')
  })

  it('rehydrate 后只在 SSE HTTP 建立时进入 connected', async () => {
    const { ports, stream } = createPorts({
      lookup: vi.fn(async () => connection()),
    })
    const { actor, unmount } = mountActor(ports)
    await vi.waitFor(() => expect(stream.subscriptions).toHaveLength(1))

    expect(actor.snapshot.value.value).toEqual({
      ready: { workflow: 'running', transport: 'connecting' },
    })
    stream.subscriptions[0].onOpen()
    expect(actor.snapshot.value.value).toEqual({
      ready: { workflow: 'running', transport: 'connected' },
    })
    unmount()
    expect(stream.subscriptions[0].signal.aborted).toBe(true)
  })

  it('scope 切换先中止旧 stream，并忽略旧 callback', async () => {
    const projectId = ref(PROJECT_ID)
    const chapterNumber = ref(CHAPTER_NUMBER)
    const lookup = vi.fn(async (scope: { projectId: string; chapterNumber: number }) =>
      scope.projectId === PROJECT_ID
        ? connection()
        : connection({
            project_id: 'project-next',
            chapter_number: 4,
            run_id: RUN_ID_2,
            row_revision: 1,
          }))
    const { ports, stream } = createPorts({ lookup })
    const { actor } = mountActor(ports, projectId, chapterNumber)
    await vi.waitFor(() => expect(stream.subscriptions).toHaveLength(1))
    const oldSubscription = stream.subscriptions[0]

    projectId.value = 'project-next'
    chapterNumber.value = 4
    await nextTick()
    await vi.waitFor(() => expect(stream.subscriptions).toHaveLength(2))

    expect(oldSubscription.signal.aborted).toBe(true)
    oldSubscription.onTask(taskEvent(99))
    await flushPromises()
    expect(lookup).toHaveBeenCalledTimes(2)
    expect(actor.snapshot.value.context).toMatchObject({
      projectId: 'project-next',
      chapterNumber: 4,
      runId: RUN_ID_2,
      resumeCursor: 5,
    })
  })

  it('有效 task event 只唤醒 current refetch，duplicate cursor 不重复查询', async () => {
    const lookup = vi
      .fn()
      .mockResolvedValueOnce(connection())
      .mockResolvedValueOnce(connection({
        status: 'waiting_for_selection',
        root_job_status: 'waiting',
        node_key: 'wait_for_selection',
        row_revision: 2,
        resume_cursor: 6,
      }))
    const { ports, stream } = createPorts({ lookup })
    const { actor } = mountActor(ports)
    await vi.waitFor(() => expect(stream.subscriptions).toHaveLength(1))

    stream.subscriptions[0].onTask(taskEvent(6))
    await vi.waitFor(() => expect(actor.snapshot.value.value).toEqual({
      ready: { workflow: 'waitingForSelection', transport: 'connecting' },
    }))
    expect(lookup).toHaveBeenCalledTimes(2)

    stream.subscriptions[0].onTask(taskEvent(6))
    await flushPromises()
    expect(lookup).toHaveBeenCalledTimes(2)
  })

  it('合并在途 refetch 期间的多个新 cursor，并在完成后补查最新快照', async () => {
    const firstRefetch = deferred<ChapterWorkflowConnection | null>()
    const secondRefetch = deferred<ChapterWorkflowConnection | null>()
    const lookup = vi
      .fn()
      .mockResolvedValueOnce(connection())
      .mockImplementationOnce(() => firstRefetch.promise)
      .mockImplementation(() => secondRefetch.promise)
    const { ports, stream } = createPorts({ lookup })
    const { actor } = mountActor(ports)
    await vi.waitFor(() => expect(stream.subscriptions).toHaveLength(1))

    stream.subscriptions[0].onTask(taskEvent(6))
    stream.subscriptions[0].onTask(taskEvent(7))
    stream.subscriptions[0].onTask(taskEvent(8))
    await flushPromises()
    expect(lookup).toHaveBeenCalledTimes(2)

    firstRefetch.resolve(connection({ resume_cursor: 6 }))
    await vi.waitFor(() => expect(lookup).toHaveBeenCalledTimes(3))
    secondRefetch.resolve(connection({
      status: 'waiting_for_selection',
      root_job_status: 'waiting',
      node_key: 'wait_for_selection',
      row_revision: 3,
      resume_cursor: 8,
    }))
    await vi.waitFor(() => expect(actor.snapshot.value.context.rowRevision).toBe(3))
    await flushPromises()

    expect(lookup).toHaveBeenCalledTimes(3)
    expect(actor.snapshot.value.context).toMatchObject({
      runId: RUN_ID,
      rowRevision: 3,
      resumeCursor: 8,
    })
    expect(actor.snapshot.value.value).toEqual({
      ready: { workflow: 'waitingForSelection', transport: 'connecting' },
    })
  })

  it('reset 中止旧流，获取同 revision 的新 cursor pair 后再重连', async () => {
    const recovered = connection({ resume_cursor: 10 }, '/events/recovered')
    const lookup = vi
      .fn()
      .mockResolvedValueOnce(connection())
      .mockResolvedValueOnce(recovered)
    const { ports, stream } = createPorts({ lookup })
    const { actor } = mountActor(ports)
    await vi.waitFor(() => expect(stream.subscriptions).toHaveLength(1))
    const oldSubscription = stream.subscriptions[0]

    oldSubscription.onReset({
      schema_version: 1,
      reason: 'cursor_expired',
      retained_through_cursor: 9,
    })

    await vi.waitFor(() => expect(stream.subscriptions).toHaveLength(2))
    expect(oldSubscription.signal.aborted).toBe(true)
    expect(stream.subscriptions[1]).toMatchObject({
      cursor: 10,
      eventsUrl: '/events/recovered',
    })
    expect(actor.snapshot.value.context.resumeCursor).toBe(10)
    expect(actor.snapshot.value.value).toEqual({
      ready: { workflow: 'running', transport: 'connecting' },
    })
  })

  it('重连耗尽后进入 polling，轮询仍只更新 workflow region', async () => {
    const polled = connection({
      status: 'waiting_for_selection',
      root_job_status: 'waiting',
      node_key: 'wait_for_selection',
      row_revision: 2,
    })
    const lookup = vi
      .fn()
      .mockResolvedValueOnce(connection())
      .mockResolvedValueOnce(polled)
    const subscribeTasks: ChapterWorkflowActorPorts['subscribeTasks'] = vi.fn(
      async (handlers) => {
        handlers.onOpen()
        throw new Error('offline')
      },
    )
    const { clock, ports } = createPorts({ lookup, subscribeTasks })
    const { actor } = mountActor(ports)

    await vi.waitFor(() => expect(clock.pending.length).toBe(1))
    await clock.runNext()
    await vi.waitFor(() => expect(subscribeTasks).toHaveBeenCalledTimes(2))
    await clock.runNext()
    await vi.waitFor(() => expect(subscribeTasks).toHaveBeenCalledTimes(3))
    await clock.runNext()
    await vi.waitFor(() => expect(subscribeTasks).toHaveBeenCalledTimes(4))
    await vi.waitFor(() => expect(actor.snapshot.value.value).toEqual({
      ready: { workflow: 'running', transport: 'polling' },
    }))

    await clock.runNext()
    await vi.waitFor(() => expect(actor.snapshot.value.value).toEqual({
      ready: { workflow: 'waitingForSelection', transport: 'polling' },
    }))
    expect(lookup).toHaveBeenCalledTimes(2)
  })

  it('409 与 SSE 竞态不回退新事实，并且双击 command 只调用一次 port', async () => {
    const conflict = deferred<ChapterWorkflowCommandPortResult>()
    const lookup = vi
      .fn()
      .mockResolvedValueOnce(connection({
        status: 'waiting_for_selection',
        root_job_status: 'waiting',
        node_key: 'wait_for_selection',
        row_revision: 4,
        allowed_commands: ['select'],
        resume_cursor: 12,
      }))
      .mockResolvedValueOnce(connection({
        status: 'finalizing',
        node_key: 'finalize_chapter',
        row_revision: 6,
        allowed_commands: ['cancel'],
        resume_cursor: 13,
      }))
    const command = vi.fn(() => conflict.promise)
    const { ports, stream } = createPorts({ lookup, command })
    const { actor } = mountActor(ports)
    await vi.waitFor(() => expect(stream.subscriptions).toHaveLength(1))

    const first = actor.submitCommand('select', { selected_version_id: 8 })
    const duplicate = actor.submitCommand('select', { selected_version_id: 8 })
    await expect(duplicate).resolves.toBe(false)
    expect(command).toHaveBeenCalledOnce()

    stream.subscriptions[0].onTask(taskEvent(13))
    await vi.waitFor(() => expect(actor.snapshot.value.context.rowRevision).toBe(6))
    const detail: ChapterWorkflowCommandConflictDetail = {
      reason_code: 'stale_run_revision',
      current_snapshot: workflowSnapshot({
        status: 'finalizing',
        node_key: 'finalize_chapter',
        row_revision: 5,
      }),
    }
    conflict.resolve({ kind: 'conflict', detail })

    await expect(first).resolves.toBe(true)
    expect(actor.snapshot.value.context).toMatchObject({
      rowRevision: 6,
      pendingCommandId: null,
      lastCommandError: '章节工作流状态已变化，请按最新状态重试',
    })
  })

  it('202 与 SSE 竞态只结算 command，不覆盖更高 revision', async () => {
    const response = deferred<ChapterWorkflowCommandPortResult>()
    const lookup = vi
      .fn()
      .mockResolvedValueOnce(connection({
        status: 'waiting_for_selection',
        root_job_status: 'waiting',
        node_key: 'wait_for_selection',
        row_revision: 4,
        allowed_commands: ['select'],
        resume_cursor: 12,
      }))
      .mockResolvedValueOnce(connection({
        status: 'finalizing',
        node_key: 'finalize_chapter',
        row_revision: 6,
        allowed_commands: ['cancel'],
        resume_cursor: 13,
      }))
    const command = vi.fn(() => response.promise)
    const { ports, stream } = createPorts({ lookup, command })
    const { actor } = mountActor(ports)
    await vi.waitFor(() => expect(stream.subscriptions).toHaveLength(1))

    const submitted = actor.submitCommand('select', { selected_version_id: 8 })
    stream.subscriptions[0].onTask(taskEvent(13))
    await vi.waitFor(() => expect(actor.snapshot.value.context.rowRevision).toBe(6))
    response.resolve({
      kind: 'response',
      response: {
        command_id: '00000000-0000-4000-8000-000000000000',
        type: 'select',
        status: 'pending',
        snapshot: workflowSnapshot({
          status: 'finalizing',
          node_key: 'finalize_chapter',
          row_revision: 5,
        }),
      },
    })

    await expect(submitted).resolves.toBe(true)
    expect(actor.snapshot.value.context).toMatchObject({
      rowRevision: 6,
      pendingCommandId: null,
      lastCommandError: null,
    })
  })

  it('workflow row revision 增长时持续刷新节点详情', async () => {
    const lookup = vi
      .fn()
      .mockResolvedValueOnce(connection())
      .mockResolvedValueOnce(connection({
        status: 'waiting_for_selection',
        root_job_status: 'waiting',
        node_key: 'wait_for_selection',
        row_revision: 2,
        resume_cursor: 6,
      }))
      .mockResolvedValueOnce(connection({
        status: 'waiting_for_selection',
        root_job_status: 'waiting',
        node_key: 'wait_for_selection',
        row_revision: 3,
        resume_cursor: 7,
      }))
      .mockResolvedValueOnce(connection({
        current_chapter_revision: 3,
        row_revision: 4,
        resume_cursor: 8,
      }))
    const invalidateChapterAndProject = vi.fn(async () => undefined)
    const { ports, stream } = createPorts({ lookup, invalidateChapterAndProject })
    mountActor(ports)
    await vi.waitFor(() => expect(stream.subscriptions).toHaveLength(1))

    stream.subscriptions[0].onTask(taskEvent(6))
    await vi.waitFor(() => expect(invalidateChapterAndProject).toHaveBeenCalledTimes(1))
    stream.subscriptions[0].onTask(taskEvent(7))
    await vi.waitFor(() => expect(invalidateChapterAndProject).toHaveBeenCalledTimes(2))
    stream.subscriptions[0].onTask(taskEvent(8))
    await vi.waitFor(() => expect(invalidateChapterAndProject).toHaveBeenCalledTimes(3))
    expect(invalidateChapterAndProject).toHaveBeenLastCalledWith({
      projectId: PROJECT_ID,
      chapterNumber: CHAPTER_NUMBER,
    })
  })

  it('首次业务快照只建立刷新基线', async () => {
    const lookup = vi
      .fn()
      .mockResolvedValueOnce(connection({
        status: 'waiting_for_selection',
        root_job_status: 'waiting',
        node_key: 'wait_for_selection',
      }))
      .mockResolvedValueOnce(connection({
        status: 'waiting_for_selection',
        root_job_status: 'waiting',
        node_key: 'wait_for_selection',
        row_revision: 2,
        resume_cursor: 6,
      }))
    const invalidateChapterAndProject = vi.fn(async () => undefined)
    const { ports, stream } = createPorts({ lookup, invalidateChapterAndProject })
    mountActor(ports)
    await vi.waitFor(() => expect(stream.subscriptions).toHaveLength(1))

    expect(invalidateChapterAndProject).not.toHaveBeenCalled()
    stream.subscriptions[0].onTask(taskEvent(6))
    await vi.waitFor(() => expect(invalidateChapterAndProject).toHaveBeenCalledOnce())
  })

  it('superseded 首次进入后自动 lookup successor', async () => {
    const lookup = vi
      .fn()
      .mockResolvedValueOnce(connection({
        status: 'superseded',
        root_job_status: 'cancelled',
        node_key: 'superseded',
        is_active: false,
        successor_run_id: RUN_ID_2,
        allowed_commands: [],
      }))
      .mockResolvedValueOnce(connection({ run_id: RUN_ID_2, row_revision: 1 }))
    const { ports, stream } = createPorts({ lookup })
    const { actor } = mountActor(ports)

    await vi.waitFor(() => expect(actor.snapshot.value.context.runId).toBe(RUN_ID_2))
    expect(lookup).toHaveBeenCalledTimes(2)
    expect(stream.subscriptions).toHaveLength(1)
    expect(stream.subscriptions[0].scope.stream_id).toBe(RUN_ID_2)
  })

  it('start 先占用 correlation，失败后重新 lookup 而不在本地猜回 idle', async () => {
    const startResult = deferred<ChapterWorkflowStartResponse>()
    const lookup = vi
      .fn()
      .mockResolvedValueOnce(null)
      .mockResolvedValueOnce(connection({ row_revision: 2 }))
    const start = vi.fn(() => startResult.promise)
    const { ports } = createPorts({ lookup, start })
    const { actor } = mountActor(ports)
    await vi.waitFor(() => expect(actor.snapshot.value.value).toEqual({
      ready: { workflow: 'idle', transport: 'disconnected' },
    }))

    const first = actor.start()
    const duplicate = actor.start()
    await expect(duplicate).resolves.toBe(false)
    expect(start).toHaveBeenCalledOnce()
    startResult.reject(new Error('network failed'))

    await expect(first).resolves.toBe(true)
    await vi.waitFor(() => expect(actor.snapshot.value.context.runId).toBe(RUN_ID))
    expect(lookup).toHaveBeenCalledTimes(2)
  })

  it('非安全来源缺少 randomUUID 时仍能启动工作流', async () => {
    const getRandomValues = vi.fn((bytes: Uint8Array) => {
      bytes.set(Array.from({ length: 16 }, (_, index) => index))
      return bytes
    })
    vi.stubGlobal('crypto', { getRandomValues })
    const startResult = deferred<ChapterWorkflowStartResponse>()
    const start = vi.fn(() => startResult.promise)
    const { ports } = createPorts({ start })
    const { actor } = mountActor(ports)
    await vi.waitFor(() => expect(actor.phase.value).toBe('idle'))

    const startPromise = actor.start()

    expect(getRandomValues).toHaveBeenCalledOnce()
    expect(actor.snapshot.value.context.pendingCommandId).toBe(
      '00010203-0405-4607-8809-0a0b0c0d0e0f',
    )
    expect(start).toHaveBeenCalledWith({
      project_id: PROJECT_ID,
      chapter_number: CHAPTER_NUMBER,
    })
    startResult.resolve({ ...connection(), created: true })
    await expect(startPromise).resolves.toBe(true)
  })
})
