// AIMETA P=章节工作流Query缓存测试|R=current_null_202_409_stale原子协调|NR=不测试statechart或页面UI|E=test:query:chapter-workflow|X=internal|A=useChapterWorkflowMutations|D=vitest,vue-query|S=test|RD=../README.ai
import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'
import { createApp, defineComponent, ref } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  ChapterWorkflowAPI,
  ChapterWorkflowContractError,
  type ChapterWorkflowCommandEnvelope,
  type ChapterWorkflowCommandResponse,
  type ChapterWorkflowConnection,
  type ChapterWorkflowSnapshot,
  type ChapterWorkflowStartResponse,
} from '@/api/chapterWorkflow'
import { HttpRequestError } from '@/api/http'
import { TaskAPI } from '@/api/tasks'
import { novelQueryKeys } from '@/queries/novel'
import {
  ChapterWorkflowCommandConflictError,
  chapterWorkflowQueryKeys,
  useChapterWorkflowActorPorts,
  useChapterWorkflowCommandMutation,
  useCurrentChapterWorkflowQuery,
  useStartChapterWorkflowMutation,
} from '@/queries/chapterWorkflow'

const RUN_ID = '11111111-1111-4111-8111-111111111111'
const ROOT_JOB_ID = '22222222-2222-4222-8222-222222222222'
const COMMAND_ID = '33333333-3333-4333-8333-333333333333'
const PROJECT_ID = 'project-scope'
const CHAPTER_NUMBER = 3
const CURRENT_KEY = chapterWorkflowQueryKeys.current(PROJECT_ID, CHAPTER_NUMBER)

const snapshot = (
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
  status: 'waiting_for_selection',
  root_job_status: 'waiting',
  node_key: 'waiting_for_selection',
  checkpoint_id: 'checkpoint-3',
  progress: 60,
  row_revision: 4,
  is_active: true,
  successor_run_id: null,
  error_category: null,
  public_error: null,
  allowed_commands: ['select', 'cancel'],
  retry_activity_key: null,
  resume_cursor: 12,
  ...overrides,
})

const connection = (
  overrides: Partial<ChapterWorkflowSnapshot> = {},
): ChapterWorkflowConnection => ({
  events_url: `/api/tasks/events?stream_type=workflow&stream_id=${RUN_ID}`,
  snapshot: snapshot(overrides),
})

const command = (): ChapterWorkflowCommandEnvelope => ({
  command_id: COMMAND_ID,
  type: 'select',
  payload_version: 1,
  payload: { selected_version_id: 8 },
  expected_run_revision: 4,
  expected_chapter_revision: 2,
  expected_checkpoint_id: 'checkpoint-3',
})

const mountHook = <Value>(hook: () => Value) => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  const host = document.createElement('div')
  let value!: Value
  const app = createApp(defineComponent({
    setup() {
      value = hook()
      return () => null
    },
  }))
  app.use(VueQueryPlugin, { queryClient })
  app.mount(host)
  return {
    queryClient,
    value,
    unmount: () => app.unmount(),
  }
}

describe('chapter workflow queries', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('current lookup 的 null 作为 canonical cache 事实保留', async () => {
    vi.spyOn(ChapterWorkflowAPI, 'getCurrent').mockResolvedValue(null)
    const mounted = mountHook(() =>
      useCurrentChapterWorkflowQuery(PROJECT_ID, CHAPTER_NUMBER))

    await vi.waitFor(() => expect(mounted.value.isSuccess.value).toBe(true))

    expect(ChapterWorkflowAPI.getCurrent).toHaveBeenCalledWith(
      { projectId: PROJECT_ID, chapterNumber: CHAPTER_NUMBER },
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
    expect(mounted.queryClient.getQueryData(CURRENT_KEY)).toBeNull()
    mounted.unmount()
  })

  it('scope 切换后每次请求都绑定创建该请求的 query key', async () => {
    const projectId = ref('project-first')
    const chapterNumber = ref(1)
    vi.spyOn(ChapterWorkflowAPI, 'getCurrent').mockResolvedValue(null)
    const mounted = mountHook(() =>
      useCurrentChapterWorkflowQuery(projectId, chapterNumber))
    await vi.waitFor(() => expect(ChapterWorkflowAPI.getCurrent).toHaveBeenCalledTimes(1))

    projectId.value = 'project-second'
    chapterNumber.value = 2
    await vi.waitFor(() => expect(ChapterWorkflowAPI.getCurrent).toHaveBeenCalledTimes(2))

    expect(ChapterWorkflowAPI.getCurrent).toHaveBeenNthCalledWith(
      1,
      { projectId: 'project-first', chapterNumber: 1 },
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
    expect(ChapterWorkflowAPI.getCurrent).toHaveBeenNthCalledWith(
      2,
      { projectId: 'project-second', chapterNumber: 2 },
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
    mounted.unmount()
  })

  it('start 202 在 mutateAsync 返回前写入完整 connection', async () => {
    const response: ChapterWorkflowStartResponse = {
      ...connection({ status: 'queued', row_revision: 1 }),
      created: true,
    }
    vi.spyOn(ChapterWorkflowAPI, 'start').mockResolvedValue(response)
    const mounted = mountHook(useStartChapterWorkflowMutation)

    await expect(mounted.value.mutateAsync({
      project_id: PROJECT_ID,
      chapter_number: CHAPTER_NUMBER,
    })).resolves.toEqual(response)

    expect(mounted.queryClient.getQueryData(CURRENT_KEY)).toEqual({
      events_url: response.events_url,
      snapshot: response.snapshot,
    })
    mounted.unmount()
  })

  it('command 202 保留 opaque events_url 并只协调更新 snapshot', async () => {
    const initial = connection()
    const response: ChapterWorkflowCommandResponse = {
      command_id: COMMAND_ID,
      type: 'select',
      status: 'pending',
      snapshot: snapshot({ status: 'finalizing', row_revision: 5 }),
    }
    vi.spyOn(ChapterWorkflowAPI, 'submitCommand').mockResolvedValue(response)
    const mounted = mountHook(useChapterWorkflowCommandMutation)
    mounted.queryClient.setQueryData(CURRENT_KEY, initial)

    await expect(mounted.value.mutateAsync({
      projectId: PROJECT_ID,
      chapterNumber: CHAPTER_NUMBER,
      runId: RUN_ID,
      command: command(),
    })).resolves.toEqual(response)

    expect(mounted.queryClient.getQueryData(CURRENT_KEY)).toEqual({
      events_url: initial.events_url,
      snapshot: response.snapshot,
    })
    mounted.unmount()
  })

  it('typed 409 先写当前 snapshot，再抛出可恢复冲突', async () => {
    const latest = snapshot({ row_revision: 6, allowed_commands: ['select'] })
    const httpError = new HttpRequestError('章节工作流命令冲突', {
      status: 409,
      code: 'http',
      url: `/api/writer/chapter-workflows/${RUN_ID}/commands`,
      payload: {
        detail: {
          reason_code: 'stale_run_revision',
          current_snapshot: latest,
        },
      },
    })
    vi.spyOn(ChapterWorkflowAPI, 'submitCommand').mockRejectedValue(httpError)
    const mounted = mountHook(useChapterWorkflowCommandMutation)
    mounted.queryClient.setQueryData(CURRENT_KEY, connection())

    const mutation = mounted.value.mutateAsync({
      projectId: PROJECT_ID,
      chapterNumber: CHAPTER_NUMBER,
      runId: RUN_ID,
      command: command(),
    })
    await expect(mutation).rejects.toMatchObject({
      name: 'ChapterWorkflowCommandConflictError',
      detail: {
        reason_code: 'stale_run_revision',
        current_snapshot: latest,
      },
    })
    expect(mounted.value.error.value).toBeInstanceOf(ChapterWorkflowCommandConflictError)
    expect(
      (mounted.queryClient.getQueryData(CURRENT_KEY) as ChapterWorkflowConnection)
        .snapshot,
    ).toEqual(latest)
    mounted.unmount()
  })

  it('畸形 409 失败关闭且不写缓存', async () => {
    const initial = connection()
    vi.spyOn(ChapterWorkflowAPI, 'submitCommand').mockRejectedValue(
      new HttpRequestError('章节工作流命令冲突', {
        status: 409,
        code: 'http',
        url: `/api/writer/chapter-workflows/${RUN_ID}/commands`,
        payload: { detail: { reason_code: 'stale_run_revision' } },
      }),
    )
    const mounted = mountHook(useChapterWorkflowCommandMutation)
    mounted.queryClient.setQueryData(CURRENT_KEY, initial)

    await expect(mounted.value.mutateAsync({
      projectId: PROJECT_ID,
      chapterNumber: CHAPTER_NUMBER,
      runId: RUN_ID,
      command: command(),
    })).rejects.toBeInstanceOf(ChapterWorkflowContractError)
    expect(mounted.queryClient.getQueryData(CURRENT_KEY)).toEqual(initial)
    mounted.unmount()
  })

  it('较旧 row_revision 的 command 响应不得覆盖新缓存', async () => {
    const latest = connection({ row_revision: 8, status: 'finalizing' })
    vi.spyOn(ChapterWorkflowAPI, 'submitCommand').mockResolvedValue({
      command_id: COMMAND_ID,
      type: 'select',
      status: 'pending',
      snapshot: snapshot({ row_revision: 7 }),
    })
    const mounted = mountHook(useChapterWorkflowCommandMutation)
    mounted.queryClient.setQueryData(CURRENT_KEY, latest)

    await mounted.value.mutateAsync({
      projectId: PROJECT_ID,
      chapterNumber: CHAPTER_NUMBER,
      runId: RUN_ID,
      command: command(),
    })

    expect(mounted.queryClient.getQueryData(CURRENT_KEY)).toEqual(latest)
    mounted.unmount()
  })

  it('相同 row_revision 只推进 cursor，不覆盖业务字段', async () => {
    const current = connection({
      row_revision: 8,
      resume_cursor: 20,
      status: 'finalizing',
      allowed_commands: ['cancel'],
    })
    vi.spyOn(ChapterWorkflowAPI, 'submitCommand').mockResolvedValue({
      command_id: COMMAND_ID,
      type: 'select',
      status: 'pending',
      snapshot: snapshot({
        row_revision: 8,
        resume_cursor: 21,
        status: 'failed',
        allowed_commands: ['retry'],
      }),
    })
    const mounted = mountHook(useChapterWorkflowCommandMutation)
    mounted.queryClient.setQueryData(CURRENT_KEY, current)

    await mounted.value.mutateAsync({
      projectId: PROJECT_ID,
      chapterNumber: CHAPTER_NUMBER,
      runId: RUN_ID,
      command: command(),
    })

    expect(mounted.queryClient.getQueryData(CURRENT_KEY)).toEqual({
      ...current,
      snapshot: { ...current.snapshot, resume_cursor: 21 },
    })
    mounted.unmount()
  })

  it('生产 actor ports 的 lookup 复用 canonical cache 并透传取消信号', async () => {
    const expected = connection()
    const controller = new AbortController()
    vi.spyOn(ChapterWorkflowAPI, 'getCurrent').mockResolvedValue(expected)
    const mounted = mountHook(useChapterWorkflowActorPorts)

    await expect(mounted.value.lookup({
      projectId: PROJECT_ID,
      chapterNumber: CHAPTER_NUMBER,
    }, controller.signal)).resolves.toEqual(expected)

    expect(ChapterWorkflowAPI.getCurrent).toHaveBeenCalledWith(
      { projectId: PROJECT_ID, chapterNumber: CHAPTER_NUMBER },
      { signal: controller.signal },
    )
    expect(mounted.queryClient.getQueryData(CURRENT_KEY)).toEqual(expected)
    mounted.unmount()
  })

  it('生产 actor ports 将 typed 409 转成可协调的 conflict 结果', async () => {
    const latest = snapshot({ row_revision: 6, allowed_commands: ['retry'] })
    vi.spyOn(ChapterWorkflowAPI, 'submitCommand').mockRejectedValue(
      new HttpRequestError('章节工作流命令冲突', {
        status: 409,
        code: 'http',
        url: `/api/writer/chapter-workflows/${RUN_ID}/commands`,
        payload: {
          detail: {
            reason_code: 'stale_run_revision',
            current_snapshot: latest,
          },
        },
      }),
    )
    const mounted = mountHook(useChapterWorkflowActorPorts)
    mounted.queryClient.setQueryData(CURRENT_KEY, connection())

    await expect(mounted.value.command({
      projectId: PROJECT_ID,
      chapterNumber: CHAPTER_NUMBER,
      runId: RUN_ID,
      command: command(),
    })).resolves.toEqual({
      kind: 'conflict',
      detail: {
        reason_code: 'stale_run_revision',
        current_snapshot: latest,
      },
      message: '章节工作流状态已变化，请按最新状态重试',
    })
    expect(
      (mounted.queryClient.getQueryData(CURRENT_KEY) as ChapterWorkflowConnection).snapshot,
    ).toEqual(latest)
    mounted.unmount()
  })

  it('生产 actor ports 复用 task stream 并同时失效 Project 与 Chapter', async () => {
    vi.spyOn(TaskAPI, 'subscribeTasks').mockResolvedValue('reset')
    const mounted = mountHook(useChapterWorkflowActorPorts)
    const invalidateSpy = vi.spyOn(mounted.queryClient, 'invalidateQueries')
    const subscription = {
      onOpen: vi.fn(),
      onSnapshot: vi.fn(),
      onTask: vi.fn(),
      onReset: vi.fn(),
      signal: new AbortController().signal,
      cursor: 12,
      scope: { stream_type: 'workflow' as const, stream_id: RUN_ID },
      eventsUrl: '/opaque/workflow/events',
    }

    await expect(mounted.value.subscribeTasks(subscription)).resolves.toBe('reset')
    await mounted.value.invalidateChapterAndProject({
      projectId: PROJECT_ID,
      chapterNumber: CHAPTER_NUMBER,
    })

    expect(TaskAPI.subscribeTasks).toHaveBeenCalledWith(subscription)
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: novelQueryKeys.detail(PROJECT_ID),
    })
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: novelQueryKeys.chapter(PROJECT_ID, CHAPTER_NUMBER),
    })
    mounted.unmount()
  })
})
