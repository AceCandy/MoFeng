// AIMETA P=章节工作流API契约测试|R=decoder_HTTP路径_scope与版本失败关闭|NR=不测试Query缓存或UI|E=test:api:chapter-workflow|X=internal|A=ChapterWorkflowAPI|D=vitest,fetch|S=test|RD=../README.ai
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  CHAPTER_WORKFLOW_COMMAND_STATUS_VALUES,
  CHAPTER_WORKFLOW_COMMAND_VALUES,
  CHAPTER_WORKFLOW_NODE_KEY_VALUES,
  CHAPTER_WORKFLOW_ROOT_JOB_STATUS_VALUES,
  CHAPTER_WORKFLOW_STATUS_VALUES,
  ChapterWorkflowAPI,
  ChapterWorkflowContractError,
  decodeChapterWorkflowCommandConflict,
  decodeChapterWorkflowCommandResponse,
  decodeChapterWorkflowConnection,
  decodeCurrentChapterWorkflow,
  type ChapterWorkflowCommandEnvelope,
  type ChapterWorkflowConnection,
  type ChapterWorkflowSnapshot,
} from '@/api/chapterWorkflow'

const RUN_ID = '11111111-1111-4111-8111-111111111111'
const ROOT_JOB_ID = '22222222-2222-4222-8222-222222222222'
const COMMAND_ID = '33333333-3333-4333-8333-333333333333'
const INVALID_UUID = 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx'
const PROJECT_ID = 'project-scope'
const SCOPE = { projectId: PROJECT_ID, chapterNumber: 3 }

const snapshot = (
  overrides: Partial<ChapterWorkflowSnapshot> = {},
): ChapterWorkflowSnapshot => ({
  run_id: RUN_ID,
  root_job_id: ROOT_JOB_ID,
  project_id: PROJECT_ID,
  chapter_id: 9,
  chapter_number: 3,
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

describe('ChapterWorkflow API contract', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('运行时枚举与 generated union 保持完整矩阵', () => {
    expect(CHAPTER_WORKFLOW_STATUS_VALUES).toEqual([
      'queued',
      'running',
      'retry_wait',
      'waiting_for_selection',
      'finalizing',
      'projection_pending',
      'needs_attention',
      'successful',
      'failed',
      'cancelled',
      'superseded',
    ])
    expect(CHAPTER_WORKFLOW_ROOT_JOB_STATUS_VALUES).toHaveLength(9)
    expect(CHAPTER_WORKFLOW_NODE_KEY_VALUES).toHaveLength(13)
    expect(CHAPTER_WORKFLOW_COMMAND_VALUES).toEqual([
      'select',
      'retry',
      'retry_external',
      'retry_projection',
      'cancel',
    ])
    expect(CHAPTER_WORKFLOW_COMMAND_STATUS_VALUES).toEqual([
      'pending',
      'applied',
      'rejected',
    ])
  })

  it('解码合法 connection、null current、command 与 typed 409', () => {
    const current = connection()
    const commandResponse = {
      command_id: COMMAND_ID,
      type: 'select',
      status: 'pending',
      snapshot: snapshot({ row_revision: 5 }),
    }
    const conflict = {
      detail: {
        reason_code: 'stale_run_revision',
        current_snapshot: snapshot({ row_revision: 6 }),
      },
    }

    expect(decodeChapterWorkflowConnection(current, SCOPE)).toEqual(current)
    expect(decodeCurrentChapterWorkflow(null, SCOPE)).toBeNull()
    expect(decodeChapterWorkflowCommandResponse(commandResponse, {
      scope: SCOPE,
      runId: RUN_ID,
      commandId: COMMAND_ID,
      commandType: 'select',
    })).toEqual(commandResponse)
    expect(decodeChapterWorkflowCommandConflict(conflict, {
      scope: SCOPE,
      runId: RUN_ID,
    })).toEqual(conflict)
  })

  it.each([
    ['unknown workflow version', { workflow_version: 2 }, 'unsupported_version'],
    ['non-canonical run id', { run_id: INVALID_UUID }, 'malformed'],
    ['non-canonical root job id', { root_job_id: INVALID_UUID }, 'malformed'],
    ['non-canonical successor run id', { successor_run_id: INVALID_UUID }, 'malformed'],
    ['unknown status', { status: 'future_status' }, 'malformed'],
    ['unknown root status', { root_job_status: 'future_status' }, 'malformed'],
    ['unknown node', { node_key: 'future_node' }, 'malformed'],
    ['unknown command', { allowed_commands: ['future_command'] }, 'malformed'],
    ['missing retry activity key', { retry_activity_key: undefined }, 'malformed'],
    ['empty retry activity key', { retry_activity_key: '' }, 'malformed'],
    ['negative cursor', { resume_cursor: -1 }, 'malformed'],
  ])('拒绝 %s', (_label, overrides, code) => {
    expect(() => decodeChapterWorkflowConnection(
      connection(overrides as Partial<ChapterWorkflowSnapshot>),
      SCOPE,
    )).toThrowError(expect.objectContaining({
      name: 'ChapterWorkflowContractError',
      code,
    }))
  })

  it('command response 拒绝非规范 UUID identity', () => {
    expect(() => decodeChapterWorkflowCommandResponse({
      command_id: INVALID_UUID,
      type: 'select',
      status: 'pending',
      snapshot: snapshot(),
    }, {
      scope: SCOPE,
      runId: RUN_ID,
      commandId: INVALID_UUID,
      commandType: 'select',
    })).toThrowError(expect.objectContaining({
      name: 'ChapterWorkflowContractError',
      code: 'malformed',
    }))
  })

  it('scope 或 run identity 漂移时失败关闭', () => {
    expect(() => decodeChapterWorkflowConnection(connection(), {
      projectId: 'foreign-project',
      chapterNumber: 3,
    })).toThrowError(expect.objectContaining({ code: 'scope_mismatch' }))

    expect(() => decodeChapterWorkflowCommandResponse({
      command_id: COMMAND_ID,
      type: 'select',
      status: 'pending',
      snapshot: snapshot(),
    }, {
      scope: SCOPE,
      runId: '44444444-4444-4444-8444-444444444444',
    })).toThrowError(expect.objectContaining({ code: 'identity_mismatch' }))
  })

  it('current 使用编码后的 scope query 并透传 AbortSignal', async () => {
    const specialScope = { projectId: 'project+scope/3', chapterNumber: 3 }
    const response = connection({ project_id: specialScope.projectId })
    const fetchMock = vi.fn(async () => new Response(JSON.stringify(response), {
      headers: { 'content-type': 'application/json' },
    }))
    vi.stubGlobal('fetch', fetchMock)
    const controller = new AbortController()

    await expect(ChapterWorkflowAPI.getCurrent(specialScope, {
      signal: controller.signal,
    })).resolves.toEqual(response)

    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      '/api/writer/chapter-workflows/current?project_id=project%2Bscope%2F3&chapter_number=3',
    )
    const options = fetchMock.mock.calls[0]?.[1] as RequestInit
    expect(options.signal).toBeInstanceOf(AbortSignal)
  })

  it('current 保留 HTTP JSON null 作为无活动工作流事实', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('null', {
      headers: { 'content-type': 'application/json' },
    })))

    await expect(ChapterWorkflowAPI.getCurrent(SCOPE)).resolves.toBeNull()
  })

  it('run snapshot API 同时校验 path identity 与当前 scope', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(
      snapshot({ project_id: 'foreign-project' }),
    ), {
      headers: { 'content-type': 'application/json' },
    })))

    await expect(ChapterWorkflowAPI.getSnapshot(SCOPE, RUN_ID)).rejects.toMatchObject({
      name: 'ChapterWorkflowContractError',
      code: 'scope_mismatch',
    })
  })

  it('start 与 command 使用生成契约请求体并校验响应关联身份', async () => {
    const startResponse = { ...connection(), created: true }
    const commandResponse = {
      command_id: COMMAND_ID,
      type: 'select' as const,
      status: 'pending' as const,
      snapshot: snapshot({ row_revision: 5 }),
    }
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(startResponse), {
        status: 202,
        headers: { 'content-type': 'application/json' },
      }))
      .mockResolvedValueOnce(new Response(JSON.stringify(commandResponse), {
        status: 202,
        headers: { 'content-type': 'application/json' },
      }))
    vi.stubGlobal('fetch', fetchMock)

    await ChapterWorkflowAPI.start({
      project_id: PROJECT_ID,
      chapter_number: 3,
      writing_notes: null,
    })
    await ChapterWorkflowAPI.submitCommand(SCOPE, RUN_ID, command())

    expect(fetchMock.mock.calls[0]?.[0]).toBe('/api/writer/chapter-workflows')
    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({
      method: 'POST',
      body: JSON.stringify({
        project_id: PROJECT_ID,
        chapter_number: 3,
        writing_notes: null,
      }),
    })
    expect(fetchMock.mock.calls[1]?.[0]).toBe(
      `/api/writer/chapter-workflows/${RUN_ID}/commands`,
    )
    expect(fetchMock.mock.calls[1]?.[1]).toMatchObject({
      method: 'POST',
      body: JSON.stringify(command()),
    })
  })

  it('畸形 typed 409 不得伪装成可恢复冲突', () => {
    expect(() => decodeChapterWorkflowCommandConflict({
      detail: { reason_code: 'stale_run_revision' },
    }, {
      scope: SCOPE,
      runId: RUN_ID,
    })).toThrow(ChapterWorkflowContractError)
  })
})
