// AIMETA P=章节工作流纯状态机测试|R=状态穷尽_命令guard_epoch与revision单调性|NR=不测试API_Query或Vue绑定|E=test:composable:chapter-workflow-machine|X=internal|A=chapterWorkflowMachine|D=vitest,xstate|S=test|RD=../README.ai
import { createActor, type ActorRefFrom } from 'xstate'
import { afterEach, describe, expect, it } from 'vitest'

import {
  CHAPTER_WORKFLOW_COMMAND_VALUES,
  CHAPTER_WORKFLOW_STATUS_VALUES,
  type ChapterWorkflowCommand,
  type ChapterWorkflowSnapshot,
} from '@/api/chapterWorkflow'
import {
  chapterWorkflowMachine,
  createChapterWorkflowCommandEnvelope,
  getChapterWorkflowPhase,
  type ChapterWorkflowPhase,
} from '@/composables/chapterWorkflowMachine'

const RUN_ID = '11111111-1111-4111-8111-111111111111'
const RUN_ID_2 = '44444444-4444-4444-8444-444444444444'
const ROOT_JOB_ID = '22222222-2222-4222-8222-222222222222'
const COMMAND_ID = '33333333-3333-4333-8333-333333333333'
const COMMAND_ID_2 = '55555555-5555-4555-8555-555555555555'
const PROJECT_ID = 'project-scope'
const CHAPTER_NUMBER = 3

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
  status: 'running',
  root_job_status: 'running',
  node_key: 'generate_candidates',
  checkpoint_id: 'checkpoint-3',
  progress: 40,
  row_revision: 4,
  is_active: true,
  successor_run_id: null,
  error_category: null,
  public_error: null,
  allowed_commands: ['cancel'],
  retry_activity_key: null,
  resume_cursor: 12,
  ...overrides,
})

type WorkflowActor = ActorRefFrom<typeof chapterWorkflowMachine>
const actors: WorkflowActor[] = []

const startActor = (projectId = PROJECT_ID, chapterNumber = CHAPTER_NUMBER) => {
  const actor = createActor(chapterWorkflowMachine, {
    input: { projectId, chapterNumber },
  }).start()
  actors.push(actor)
  return actor
}

const lookupSnapshot = (actor: WorkflowActor, value: ChapterWorkflowSnapshot) => {
  actor.send({
    type: 'SNAPSHOT_RECEIVED',
    source: 'lookup',
    scopeEpoch: actor.getSnapshot().context.scopeEpoch,
    snapshot: value,
  })
}

const readyValue = (workflow: ChapterWorkflowPhase, transport: string) => ({
  ready: { workflow, transport },
})

afterEach(() => {
  for (const actor of actors.splice(0)) actor.stop()
})

describe('chapterWorkflowMachine', () => {
  it('以 booting 开始，并将 current null 恢复为 idle + disconnected', () => {
    const actor = startActor()
    expect(actor.getSnapshot().value).toBe('booting')

    actor.send({ type: 'LOOKUP_EMPTY', scopeEpoch: 0 })

    expect(actor.getSnapshot().value).toEqual(readyValue('idle', 'disconnected'))
    expect(actor.getSnapshot().context.runId).toBeNull()
  })

  it.each(CHAPTER_WORKFLOW_STATUS_VALUES)(
    '穷尽映射服务端 status: %s',
    (status) => {
      const actor = startActor()
      const phase = getChapterWorkflowPhase(status)

      lookupSnapshot(actor, snapshot({ status }))

      expect(actor.getSnapshot().value).toEqual(readyValue(phase, 'disconnected'))
      expect(actor.getSnapshot().context).toMatchObject({
        runId: RUN_ID,
        rowRevision: 4,
        chapterRevision: 2,
        checkpointId: 'checkpoint-3',
        resumeCursor: 12,
      })
    },
  )

  it('保留服务端提供的外部重试关联键且不从 node 推导', () => {
    const actor = startActor()
    lookupSnapshot(actor, snapshot({
      status: 'needs_attention',
      root_job_status: 'needs_attention',
      allowed_commands: ['retry_external', 'cancel'],
      retry_activity_key: 'wf:generate_candidates:stable-key',
    }))

    expect(actor.getSnapshot().context.retryActivityKey)
      .toBe('wf:generate_candidates:stable-key')
  })

  it.each(CHAPTER_WORKFLOW_COMMAND_VALUES)(
    'command %s 只由 allowed_commands 和冻结前置条件放行',
    (commandType) => {
      const actor = startActor()
      lookupSnapshot(actor, snapshot({
        status: 'failed',
        root_job_status: 'failed',
        node_key: 'failed',
        allowed_commands: [commandType],
      }))
      const envelope = createChapterWorkflowCommandEnvelope(
        actor.getSnapshot().context,
        commandType,
        {},
        COMMAND_ID,
      )

      actor.send({ type: 'COMMAND_REQUESTED', envelope })

      expect(actor.getSnapshot().context.pendingCommandId).toBe(COMMAND_ID)
    },
  )

  it('拒绝未获服务端允许、前置条件陈旧和重复的 command', () => {
    const actor = startActor()
    lookupSnapshot(actor, snapshot({ allowed_commands: ['cancel'] }))
    const retry = createChapterWorkflowCommandEnvelope(
      actor.getSnapshot().context,
      'retry',
      {},
      COMMAND_ID,
    )
    actor.send({ type: 'COMMAND_REQUESTED', envelope: retry })
    expect(actor.getSnapshot().context.pendingCommandId).toBeNull()

    const stale = {
      ...createChapterWorkflowCommandEnvelope(
        actor.getSnapshot().context,
        'cancel',
        {},
        COMMAND_ID,
      ),
      expected_run_revision: 3,
    }
    actor.send({ type: 'COMMAND_REQUESTED', envelope: stale })
    expect(actor.getSnapshot().context.pendingCommandId).toBeNull()

    const first = createChapterWorkflowCommandEnvelope(
      actor.getSnapshot().context,
      'cancel',
      {},
      COMMAND_ID,
    )
    const duplicate = { ...first, command_id: COMMAND_ID_2 }
    actor.send({ type: 'COMMAND_REQUESTED', envelope: first })
    actor.send({ type: 'COMMAND_REQUESTED', envelope: duplicate })
    expect(actor.getSnapshot().context.pendingCommandId).toBe(COMMAND_ID)
  })

  it('start 只允许 idle/cancelled，pending 时重复 start 被忽略', () => {
    const idleActor = startActor()
    idleActor.send({ type: 'LOOKUP_EMPTY', scopeEpoch: 0 })
    idleActor.send({ type: 'START_REQUESTED', requestId: COMMAND_ID })
    idleActor.send({ type: 'START_REQUESTED', requestId: COMMAND_ID_2 })
    expect(idleActor.getSnapshot().value).toEqual(readyValue('submitting', 'disconnected'))
    expect(idleActor.getSnapshot().context.pendingCommandId).toBe(COMMAND_ID)

    const cancelledActor = startActor()
    lookupSnapshot(cancelledActor, snapshot({
      status: 'cancelled',
      root_job_status: 'cancelled',
      node_key: 'cancelled',
      is_active: false,
      allowed_commands: [],
    }))
    cancelledActor.send({ type: 'START_REQUESTED', requestId: COMMAND_ID })
    expect(cancelledActor.getSnapshot().value).toEqual(
      readyValue('submitting', 'disconnected'),
    )

    const runningActor = startActor()
    lookupSnapshot(runningActor, snapshot())
    runningActor.send({ type: 'START_REQUESTED', requestId: COMMAND_ID })
    expect(runningActor.getSnapshot().value).toEqual(readyValue('running', 'disconnected'))
    expect(runningActor.getSnapshot().context.pendingCommandId).toBeNull()
  })

  it('start 传输失败回到 booting 重新查询服务端事实', () => {
    const actor = startActor()
    actor.send({ type: 'LOOKUP_EMPTY', scopeEpoch: 0 })
    actor.send({ type: 'START_REQUESTED', requestId: COMMAND_ID })

    actor.send({
      type: 'START_FAILED',
      scopeEpoch: 0,
      requestId: COMMAND_ID,
      message: '网络连接中断',
    })

    expect(actor.getSnapshot().value).toBe('booting')
    expect(actor.getSnapshot().context).toMatchObject({
      pendingCommandId: null,
      lastCommandError: '网络连接中断',
    })
  })

  it('同一 run 的 stale snapshot 被忽略，同 revision 只推进 cursor', () => {
    const actor = startActor()
    lookupSnapshot(actor, snapshot({ row_revision: 10, resume_cursor: 20 }))
    const connectionEpoch = actor.getSnapshot().context.connectionEpoch

    actor.send({
      type: 'SNAPSHOT_RECEIVED',
      source: 'refetch',
      scopeEpoch: 0,
      connectionEpoch,
      snapshot: snapshot({ status: 'failed', row_revision: 9, resume_cursor: 99 }),
    })
    actor.send({
      type: 'SNAPSHOT_RECEIVED',
      source: 'refetch',
      scopeEpoch: 0,
      connectionEpoch,
      snapshot: snapshot({ status: 'failed', row_revision: 10, resume_cursor: 100 }),
    })

    expect(actor.getSnapshot().value).toEqual(readyValue('running', 'disconnected'))
    expect(actor.getSnapshot().context).toMatchObject({
      rowRevision: 10,
      resumeCursor: 100,
    })

    actor.send({
      type: 'SNAPSHOT_RECEIVED',
      source: 'refetch',
      scopeEpoch: 0,
      connectionEpoch,
      snapshot: snapshot({ status: 'failed', row_revision: 11, resume_cursor: 21 }),
    })
    expect(actor.getSnapshot().value).toEqual(readyValue('failed', 'disconnected'))
  })

  it('scope 切换清空关联数据，并拒绝旧 scope lookup', () => {
    const actor = startActor()
    lookupSnapshot(actor, snapshot())

    actor.send({ type: 'SCOPE_CHANGED', projectId: 'project-next', chapterNumber: 4 })

    expect(actor.getSnapshot().value).toBe('booting')
    expect(actor.getSnapshot().context).toMatchObject({
      projectId: 'project-next',
      chapterNumber: 4,
      scopeEpoch: 1,
      runId: null,
      pendingCommandId: null,
    })
    actor.send({
      type: 'SNAPSHOT_RECEIVED',
      source: 'lookup',
      scopeEpoch: 0,
      snapshot: snapshot(),
    })
    expect(actor.getSnapshot().value).toBe('booting')

    actor.send({
      type: 'SNAPSHOT_RECEIVED',
      source: 'lookup',
      scopeEpoch: 1,
      snapshot: snapshot({ project_id: 'project-next', chapter_number: 4 }),
    })
    expect(actor.getSnapshot().value).toEqual(readyValue('running', 'disconnected'))
  })

  it('workflow 与 transport 并行演进，断线和 polling 不覆盖业务 phase', () => {
    const actor = startActor()
    lookupSnapshot(actor, snapshot())

    actor.send({ type: 'CONNECT_REQUESTED', scopeEpoch: 0, runId: RUN_ID })
    expect(actor.getSnapshot().value).toEqual(readyValue('running', 'connecting'))
    const firstEpoch = actor.getSnapshot().context.connectionEpoch
    actor.send({
      type: 'STREAM_CONNECTED',
      scopeEpoch: 0,
      connectionEpoch: firstEpoch,
      runId: RUN_ID,
    })
    expect(actor.getSnapshot().value).toEqual(readyValue('running', 'connected'))
    actor.send({
      type: 'STREAM_DISCONNECTED',
      scopeEpoch: 0,
      connectionEpoch: firstEpoch,
      runId: RUN_ID,
    })
    expect(actor.getSnapshot().value).toEqual(readyValue('running', 'reconnecting'))
    actor.send({
      type: 'RECONNECT_REQUESTED',
      scopeEpoch: 0,
      connectionEpoch: firstEpoch,
      runId: RUN_ID,
    })
    const secondEpoch = actor.getSnapshot().context.connectionEpoch
    expect(actor.getSnapshot().value).toEqual(readyValue('running', 'connecting'))
    actor.send({
      type: 'STREAM_DISCONNECTED',
      scopeEpoch: 0,
      connectionEpoch: secondEpoch,
      runId: RUN_ID,
    })
    actor.send({
      type: 'RECONNECT_EXHAUSTED',
      scopeEpoch: 0,
      connectionEpoch: secondEpoch,
      runId: RUN_ID,
    })
    expect(actor.getSnapshot().value).toEqual(readyValue('running', 'polling'))
  })

  it('run 切换使旧 connection epoch 失效并重置 transport', () => {
    const actor = startActor()
    lookupSnapshot(actor, snapshot({ row_revision: 10 }))
    actor.send({ type: 'CONNECT_REQUESTED', scopeEpoch: 0, runId: RUN_ID })
    const oldConnectionEpoch = actor.getSnapshot().context.connectionEpoch
    actor.send({
      type: 'STREAM_CONNECTED',
      scopeEpoch: 0,
      connectionEpoch: oldConnectionEpoch,
      runId: RUN_ID,
    })

    actor.send({
      type: 'SNAPSHOT_RECEIVED',
      source: 'refetch',
      scopeEpoch: 0,
      connectionEpoch: oldConnectionEpoch,
      snapshot: snapshot({
        run_id: RUN_ID_2,
        status: 'waiting_for_selection',
        root_job_status: 'waiting',
        node_key: 'waiting_for_selection',
        row_revision: 1,
      }),
    })

    expect(actor.getSnapshot().value).toEqual(
      readyValue('waitingForSelection', 'disconnected'),
    )
    expect(actor.getSnapshot().context).toMatchObject({
      runId: RUN_ID_2,
      connectionEpoch: oldConnectionEpoch + 1,
    })
    actor.send({
      type: 'STREAM_EVENT_RECEIVED',
      scopeEpoch: 0,
      connectionEpoch: oldConnectionEpoch,
      runId: RUN_ID,
      cursor: 999,
    })
    expect(actor.getSnapshot().context.resumeCursor).not.toBe(999)
  })

  it('cursor 只前进；reset 原子失效旧连接并清空 cursor', () => {
    const actor = startActor()
    lookupSnapshot(actor, snapshot({ resume_cursor: 20 }))
    actor.send({ type: 'CONNECT_REQUESTED', scopeEpoch: 0, runId: RUN_ID })
    const epoch = actor.getSnapshot().context.connectionEpoch
    actor.send({
      type: 'STREAM_EVENT_RECEIVED',
      scopeEpoch: 0,
      connectionEpoch: epoch,
      runId: RUN_ID,
      cursor: 21,
    })
    actor.send({
      type: 'STREAM_EVENT_RECEIVED',
      scopeEpoch: 0,
      connectionEpoch: epoch,
      runId: RUN_ID,
      cursor: 21,
    })
    expect(actor.getSnapshot().context.resumeCursor).toBe(21)

    actor.send({
      type: 'STREAM_RESET',
      scopeEpoch: 0,
      connectionEpoch: epoch,
      runId: RUN_ID,
    })
    expect(actor.getSnapshot().value).toEqual(readyValue('running', 'connecting'))
    expect(actor.getSnapshot().context.resumeCursor).toBeNull()
    expect(actor.getSnapshot().context.connectionEpoch).toBe(epoch + 1)
    actor.send({
      type: 'STREAM_CONNECTED',
      scopeEpoch: 0,
      connectionEpoch: epoch,
      runId: RUN_ID,
    })
    expect(actor.getSnapshot().value).toEqual(readyValue('running', 'connecting'))
  })

  it('command snapshot 协调后清 pending；迟到响应只清 pending 不回退事实', () => {
    const actor = startActor()
    lookupSnapshot(actor, snapshot({
      status: 'waiting_for_selection',
      root_job_status: 'waiting',
      node_key: 'waiting_for_selection',
      allowed_commands: ['select'],
    }))
    const envelope = createChapterWorkflowCommandEnvelope(
      actor.getSnapshot().context,
      'select',
      { selected_version_id: 8 },
      COMMAND_ID,
    )
    actor.send({ type: 'COMMAND_REQUESTED', envelope })
    actor.send({
      type: 'SNAPSHOT_RECEIVED',
      source: 'refetch',
      scopeEpoch: 0,
      connectionEpoch: 0,
      snapshot: snapshot({
        status: 'failed',
        root_job_status: 'failed',
        node_key: 'failed',
        row_revision: 6,
      }),
    })
    actor.send({
      type: 'SNAPSHOT_RECEIVED',
      source: 'command',
      scopeEpoch: 0,
      correlationId: COMMAND_ID,
      commandError: 'stale_run_revision',
      snapshot: snapshot({ status: 'finalizing', row_revision: 5 }),
    })

    expect(actor.getSnapshot().value).toEqual(readyValue('failed', 'disconnected'))
    expect(actor.getSnapshot().context).toMatchObject({
      rowRevision: 6,
      pendingCommandId: null,
      lastCommandError: 'stale_run_revision',
    })
  })

  it('run 已切换时旧 run command response 只清 pending', () => {
    const actor = startActor()
    lookupSnapshot(actor, snapshot({ allowed_commands: ['cancel'] }))
    const envelope = createChapterWorkflowCommandEnvelope(
      actor.getSnapshot().context,
      'cancel',
      {},
      COMMAND_ID,
    )
    actor.send({ type: 'COMMAND_REQUESTED', envelope })
    actor.send({
      type: 'SNAPSHOT_RECEIVED',
      source: 'refetch',
      scopeEpoch: 0,
      connectionEpoch: 0,
      snapshot: snapshot({ run_id: RUN_ID_2, row_revision: 1 }),
    })

    actor.send({
      type: 'SNAPSHOT_RECEIVED',
      source: 'command',
      scopeEpoch: 0,
      correlationId: COMMAND_ID,
      snapshot: snapshot({
        status: 'cancelled',
        root_job_status: 'cancelled',
        node_key: 'cancelled',
        row_revision: 5,
      }),
    })

    expect(actor.getSnapshot().context).toMatchObject({
      runId: RUN_ID_2,
      rowRevision: 1,
      pendingCommandId: null,
    })
    expect(actor.getSnapshot().value).toEqual(readyValue('running', 'disconnected'))
  })

  it('合法 command response 在 SSE reset 后仍按 command identity 协调', () => {
    const actor = startActor()
    lookupSnapshot(actor, snapshot({ allowed_commands: ['cancel'] }))
    actor.send({ type: 'CONNECT_REQUESTED', scopeEpoch: 0, runId: RUN_ID })
    const streamEpoch = actor.getSnapshot().context.connectionEpoch
    const envelope = createChapterWorkflowCommandEnvelope(
      actor.getSnapshot().context,
      'cancel',
      {},
      COMMAND_ID,
    )
    actor.send({ type: 'COMMAND_REQUESTED', envelope })
    actor.send({
      type: 'STREAM_RESET',
      scopeEpoch: 0,
      connectionEpoch: streamEpoch,
      runId: RUN_ID,
    })

    actor.send({
      type: 'SNAPSHOT_RECEIVED',
      source: 'command',
      scopeEpoch: 0,
      correlationId: COMMAND_ID,
      snapshot: snapshot({
        status: 'cancelled',
        root_job_status: 'cancelled',
        node_key: 'cancelled',
        row_revision: 5,
        is_active: false,
        allowed_commands: [],
      }),
    })

    expect(actor.getSnapshot().value).toEqual(readyValue('cancelled', 'connecting'))
    expect(actor.getSnapshot().context.pendingCommandId).toBeNull()
  })

  it('command envelope 只创建一次并冻结 revision/checkpoint/payload', () => {
    const actor = startActor()
    lookupSnapshot(actor, snapshot({ allowed_commands: ['cancel'] }))
    const payload: Record<string, unknown> = { activity_key: 'candidate_generation' }
    const envelope = createChapterWorkflowCommandEnvelope(
      actor.getSnapshot().context,
      'cancel',
      payload,
      COMMAND_ID,
    )
    payload.activity_key = 'changed'

    expect(envelope).toEqual({
      command_id: COMMAND_ID,
      type: 'cancel',
      payload_version: 1,
      payload: { activity_key: 'candidate_generation' },
      expected_run_revision: 4,
      expected_chapter_revision: 2,
      expected_checkpoint_id: 'checkpoint-3',
    })
  })

  it('fatal 禁止业务状态，resync 同时失效 scope 与 connection epoch', () => {
    const actor = startActor()
    lookupSnapshot(actor, snapshot())
    actor.send({ type: 'FATAL', scopeEpoch: 0, message: '契约字段不可信' })
    expect(actor.getSnapshot().value).toBe('fatal')
    expect(actor.getSnapshot().context.lastContractError).toBe('契约字段不可信')
    const previousScopeEpoch = actor.getSnapshot().context.scopeEpoch
    const previousConnectionEpoch = actor.getSnapshot().context.connectionEpoch

    actor.send({ type: 'RESYNC_REQUESTED' })

    expect(actor.getSnapshot().value).toBe('booting')
    expect(actor.getSnapshot().context).toMatchObject({
      scopeEpoch: previousScopeEpoch + 1,
      connectionEpoch: previousConnectionEpoch + 1,
      runId: null,
      lastContractError: null,
    })
  })

  it('状态映射表与 generated status union 保持一一对应', () => {
    const expected: Record<ChapterWorkflowSnapshot['status'], ChapterWorkflowPhase> = {
      queued: 'running',
      running: 'running',
      retry_wait: 'running',
      waiting_for_selection: 'waitingForSelection',
      finalizing: 'finalizing',
      projection_pending: 'projectionPending',
      needs_attention: 'failed',
      successful: 'succeeded',
      failed: 'failed',
      cancelled: 'cancelled',
      superseded: 'superseded',
    }
    for (const status of CHAPTER_WORKFLOW_STATUS_VALUES) {
      expect(getChapterWorkflowPhase(status)).toBe(expected[status])
    }
  })

  it('create command helper 接受 generated command union 的全部值', () => {
    const actor = startActor()
    lookupSnapshot(actor, snapshot())
    const values = CHAPTER_WORKFLOW_COMMAND_VALUES.map((type, index) =>
      createChapterWorkflowCommandEnvelope(
        actor.getSnapshot().context,
        type as ChapterWorkflowCommand,
        {},
        `${index + 1}`.repeat(36).slice(0, 36),
      ).type)
    expect(values).toEqual(CHAPTER_WORKFLOW_COMMAND_VALUES)
  })
})
