// AIMETA P=WritingDesk章节工作流状态机|R=交互状态_命令关联_transport健康与单调协调|NR=不调用API_不持有Project或Chapter实体|E=composable:chapter-workflow-machine|X=internal|A=chapterWorkflowMachine|D=xstate|S=state|RD=./README.ai
import { assign, setup } from 'xstate'

import type {
  ChapterWorkflowCommand,
  ChapterWorkflowCommandEnvelope,
  ChapterWorkflowSnapshot,
} from '@/api/chapterWorkflow'

export type ChapterWorkflowPhase =
  | 'cancelled'
  | 'failed'
  | 'finalizing'
  | 'idle'
  | 'projectionPending'
  | 'running'
  | 'submitting'
  | 'succeeded'
  | 'superseded'
  | 'waitingForSelection'

export type ChapterWorkflowTransportPhase =
  | 'connected'
  | 'connecting'
  | 'disconnected'
  | 'polling'
  | 'reconnecting'

export interface ChapterWorkflowMachineInput {
  projectId: string
  chapterNumber: number | null
}

export interface ChapterWorkflowMachineContext extends ChapterWorkflowMachineInput {
  scopeEpoch: number
  connectionEpoch: number
  runId: string | null
  rowRevision: number | null
  chapterRevision: number | null
  checkpointId: string | null
  resumeCursor: number | null
  allowedCommands: readonly ChapterWorkflowCommand[]
  retryActivityKey: string | null
  pendingCommandId: string | null
  lastContractError: string | null
  lastCommandError: string | null
}

type SnapshotReceivedEvent =
  | {
      type: 'SNAPSHOT_RECEIVED'
      source: 'lookup'
      scopeEpoch: number
      snapshot: ChapterWorkflowSnapshot
    }
  | {
      type: 'SNAPSHOT_RECEIVED'
      source: 'start'
      scopeEpoch: number
      correlationId: string
      snapshot: ChapterWorkflowSnapshot
    }
  | {
      type: 'SNAPSHOT_RECEIVED'
      source: 'command'
      scopeEpoch: number
      correlationId: string
      commandError?: string | null
      snapshot: ChapterWorkflowSnapshot
    }
  | {
      type: 'SNAPSHOT_RECEIVED'
      source: 'refetch'
      scopeEpoch: number
      connectionEpoch: number
      snapshot: ChapterWorkflowSnapshot
    }

type CurrentTransportEvent = {
  scopeEpoch: number
  connectionEpoch: number
  runId: string
}

export type ChapterWorkflowMachineEvent =
  | SnapshotReceivedEvent
  | { type: 'LOOKUP_EMPTY'; scopeEpoch: number }
  | { type: 'FATAL'; scopeEpoch: number; message: string }
  | { type: 'RESYNC_REQUESTED' }
  | { type: 'SCOPE_CHANGED'; projectId: string; chapterNumber: number | null }
  | { type: 'START_REQUESTED'; requestId: string }
  | { type: 'START_FAILED'; scopeEpoch: number; requestId: string; message: string }
  | { type: 'COMMAND_REQUESTED'; envelope: ChapterWorkflowCommandEnvelope }
  | { type: 'COMMAND_FAILED'; scopeEpoch: number; commandId: string; message: string }
  | ({ type: 'CONNECT_REQUESTED' } & Pick<CurrentTransportEvent, 'scopeEpoch' | 'runId'>)
  | ({ type: 'STREAM_CONNECTED' } & CurrentTransportEvent)
  | ({ type: 'STREAM_DISCONNECTED' } & CurrentTransportEvent)
  | ({ type: 'RECONNECT_REQUESTED' } & CurrentTransportEvent)
  | ({ type: 'RECONNECT_EXHAUSTED' } & CurrentTransportEvent)
  | ({ type: 'TRANSPORT_STOPPED' } & CurrentTransportEvent)
  | ({ type: 'STREAM_RESET' } & CurrentTransportEvent)
  | ({ type: 'STREAM_EVENT_RECEIVED'; cursor: number } & CurrentTransportEvent)

const STATUS_TO_PHASE: Record<ChapterWorkflowSnapshot['status'], ChapterWorkflowPhase> = {
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

export const getChapterWorkflowPhase = (
  status: ChapterWorkflowSnapshot['status'],
): ChapterWorkflowPhase => STATUS_TO_PHASE[status]

const boundedMessage = (message: string) => message.trim().slice(0, 512) || null

const isUuidLength = (value: string) => value.length === 36

const matchesSnapshotScope = (
  context: ChapterWorkflowMachineContext,
  snapshot: ChapterWorkflowSnapshot,
) => snapshot.project_id === context.projectId
  && snapshot.chapter_number === context.chapterNumber

const isCorrelatedRequest = (
  context: ChapterWorkflowMachineContext,
  event: SnapshotReceivedEvent,
) => {
  if (
    event.scopeEpoch !== context.scopeEpoch
    || !matchesSnapshotScope(context, event.snapshot)
    || (event.source !== 'start' && event.source !== 'command')
    || event.correlationId !== context.pendingCommandId
  ) {
    return false
  }
  return true
}

const isCorrelatedSnapshotResponse = (
  context: ChapterWorkflowMachineContext,
  event: SnapshotReceivedEvent,
) => {
  if (!isCorrelatedRequest(context, event)) return false
  if (event.source === 'command') {
    return event.snapshot.run_id === context.runId
  }
  return true
}

const canApplySnapshot = (
  context: ChapterWorkflowMachineContext,
  event: SnapshotReceivedEvent,
) => {
  if (event.scopeEpoch !== context.scopeEpoch || !matchesSnapshotScope(context, event.snapshot)) {
    return false
  }
  if (event.source === 'start' && !isCorrelatedSnapshotResponse(context, event)) {
    return false
  }
  if (event.source === 'command' && !isCorrelatedSnapshotResponse(context, event)) {
    return false
  }
  if (
    event.source === 'refetch'
    && event.connectionEpoch !== context.connectionEpoch
  ) {
    return false
  }
  if (context.runId === event.snapshot.run_id) {
    return context.rowRevision === null || event.snapshot.row_revision > context.rowRevision
  }
  return event.source !== 'command'
}

const isSnapshotForPhase = (
  context: ChapterWorkflowMachineContext,
  event: ChapterWorkflowMachineEvent,
  phase: ChapterWorkflowPhase,
) => event.type === 'SNAPSHOT_RECEIVED'
  && canApplySnapshot(context, event)
  && getChapterWorkflowPhase(event.snapshot.status) === phase

const isCurrentScopeEpoch = (
  context: ChapterWorkflowMachineContext,
  event: ChapterWorkflowMachineEvent,
) => 'scopeEpoch' in event && event.scopeEpoch === context.scopeEpoch

const isCurrentTransportEvent = (
  context: ChapterWorkflowMachineContext,
  event: ChapterWorkflowMachineEvent,
): event is ChapterWorkflowMachineEvent & CurrentTransportEvent =>
  'scopeEpoch' in event
  && 'connectionEpoch' in event
  && 'runId' in event
  && event.scopeEpoch === context.scopeEpoch
  && event.connectionEpoch === context.connectionEpoch
  && event.runId === context.runId

const isRunChangingSnapshot = (
  context: ChapterWorkflowMachineContext,
  event: ChapterWorkflowMachineEvent,
) => event.type === 'SNAPSHOT_RECEIVED'
  && canApplySnapshot(context, event)
  && context.runId !== null
  && context.runId !== event.snapshot.run_id

const isSameRevisionCursorAdvance = (
  context: ChapterWorkflowMachineContext,
  event: ChapterWorkflowMachineEvent,
) => event.type === 'SNAPSHOT_RECEIVED'
  && event.source === 'refetch'
  && event.scopeEpoch === context.scopeEpoch
  && event.connectionEpoch === context.connectionEpoch
  && matchesSnapshotScope(context, event.snapshot)
  && event.snapshot.run_id === context.runId
  && event.snapshot.row_revision === context.rowRevision
  && (context.resumeCursor === null || event.snapshot.resume_cursor > context.resumeCursor)

const machineSetup = setup({
  types: {
    context: {} as ChapterWorkflowMachineContext,
    events: {} as ChapterWorkflowMachineEvent,
    input: {} as ChapterWorkflowMachineInput,
  },
  guards: {
    isRunningSnapshot: ({ context, event }) => isSnapshotForPhase(context, event, 'running'),
    isWaitingSnapshot: ({ context, event }) =>
      isSnapshotForPhase(context, event, 'waitingForSelection'),
    isFinalizingSnapshot: ({ context, event }) =>
      isSnapshotForPhase(context, event, 'finalizing'),
    isProjectionSnapshot: ({ context, event }) =>
      isSnapshotForPhase(context, event, 'projectionPending'),
    isSucceededSnapshot: ({ context, event }) =>
      isSnapshotForPhase(context, event, 'succeeded'),
    isFailedSnapshot: ({ context, event }) => isSnapshotForPhase(context, event, 'failed'),
    isCancelledSnapshot: ({ context, event }) =>
      isSnapshotForPhase(context, event, 'cancelled'),
    isSupersededSnapshot: ({ context, event }) =>
      isSnapshotForPhase(context, event, 'superseded'),
    isCorrelatedRequest: ({ context, event }) =>
      event.type === 'SNAPSHOT_RECEIVED' && isCorrelatedRequest(context, event),
    isCurrentScopeEpoch: ({ context, event }) => isCurrentScopeEpoch(context, event),
    isDifferentScope: ({ context, event }) => event.type === 'SCOPE_CHANGED'
      && (event.projectId !== context.projectId || event.chapterNumber !== context.chapterNumber),
    canStart: ({ context, event }) => event.type === 'START_REQUESTED'
      && context.pendingCommandId === null
      && isUuidLength(event.requestId),
    isCurrentStartFailure: ({ context, event }) => event.type === 'START_FAILED'
      && event.scopeEpoch === context.scopeEpoch
      && event.requestId === context.pendingCommandId,
    isAllowedCommand: ({ context, event }) => {
      if (
        event.type !== 'COMMAND_REQUESTED'
        || context.pendingCommandId !== null
        || context.runId === null
        || context.rowRevision === null
        || context.chapterRevision === null
        || context.checkpointId === null
      ) {
        return false
      }
      const envelope = event.envelope
      return isUuidLength(envelope.command_id)
        && context.allowedCommands.includes(envelope.type)
        && envelope.payload_version === 1
        && envelope.expected_run_revision === context.rowRevision
        && envelope.expected_chapter_revision === context.chapterRevision
        && envelope.expected_checkpoint_id === context.checkpointId
    },
    isCurrentCommandFailure: ({ context, event }) => event.type === 'COMMAND_FAILED'
      && event.scopeEpoch === context.scopeEpoch
      && event.commandId === context.pendingCommandId,
    isCurrentConnectRequest: ({ context, event }) => event.type === 'CONNECT_REQUESTED'
      && event.scopeEpoch === context.scopeEpoch
      && event.runId === context.runId,
    isCurrentTransportEvent: ({ context, event }) => isCurrentTransportEvent(context, event),
    isNewStreamCursor: ({ context, event }) => event.type === 'STREAM_EVENT_RECEIVED'
      && isCurrentTransportEvent(context, event)
      && (context.resumeCursor === null || event.cursor > context.resumeCursor),
    isRunChangingSnapshot: ({ context, event }) => isRunChangingSnapshot(context, event),
    isSameRevisionCursorAdvance: ({ context, event }) =>
      isSameRevisionCursorAdvance(context, event),
  },
  actions: {
    applySnapshot: assign(({ context, event }) => {
      if (event.type !== 'SNAPSHOT_RECEIVED') return {}
      const runChanged = context.runId !== null && context.runId !== event.snapshot.run_id
      return {
        runId: event.snapshot.run_id,
        rowRevision: event.snapshot.row_revision,
        chapterRevision: event.snapshot.current_chapter_revision,
        checkpointId: event.snapshot.checkpoint_id ?? null,
        resumeCursor: event.snapshot.resume_cursor,
        allowedCommands: [...event.snapshot.allowed_commands],
        retryActivityKey: event.snapshot.retry_activity_key,
        connectionEpoch: runChanged ? context.connectionEpoch + 1 : context.connectionEpoch,
        lastContractError: null,
        lastCommandError: event.source === 'command'
          ? boundedMessage(event.commandError ?? '')
          : event.source === 'start'
            ? null
            : context.lastCommandError,
      }
    }),
    settleCorrelatedRequest: assign(({ context, event }) => ({
      pendingCommandId: event.type === 'SNAPSHOT_RECEIVED'
        && isCorrelatedRequest(context, event)
        ? null
        : context.pendingCommandId,
      resumeCursor: event.type === 'SNAPSHOT_RECEIVED'
        && isCorrelatedRequest(context, event)
        && event.snapshot.run_id === context.runId
        && event.snapshot.row_revision === context.rowRevision
        && (context.resumeCursor === null || event.snapshot.resume_cursor > context.resumeCursor)
        ? event.snapshot.resume_cursor
        : context.resumeCursor,
      lastCommandError: event.type === 'SNAPSHOT_RECEIVED'
        && isCorrelatedRequest(context, event)
        && event.source === 'command'
        ? boundedMessage(event.commandError ?? '')
        : context.lastCommandError,
    })),
    clearRun: assign(({ context }) => ({
      connectionEpoch: context.connectionEpoch + 1,
      runId: null,
      rowRevision: null,
      chapterRevision: null,
      checkpointId: null,
      resumeCursor: null,
      allowedCommands: [],
      retryActivityKey: null,
      pendingCommandId: null,
      lastCommandError: null,
    })),
    changeScope: assign(({ context, event }) => {
      if (event.type !== 'SCOPE_CHANGED') return {}
      return {
        projectId: event.projectId,
        chapterNumber: event.chapterNumber,
        scopeEpoch: context.scopeEpoch + 1,
        connectionEpoch: context.connectionEpoch + 1,
        runId: null,
        rowRevision: null,
        chapterRevision: null,
        checkpointId: null,
        resumeCursor: null,
        allowedCommands: [],
        retryActivityKey: null,
        pendingCommandId: null,
        lastContractError: null,
        lastCommandError: null,
      }
    }),
    prepareResync: assign(({ context }) => ({
      scopeEpoch: context.scopeEpoch + 1,
      connectionEpoch: context.connectionEpoch + 1,
      runId: null,
      rowRevision: null,
      chapterRevision: null,
      checkpointId: null,
      resumeCursor: null,
      allowedCommands: [],
      retryActivityKey: null,
      pendingCommandId: null,
      lastContractError: null,
      lastCommandError: null,
    })),
    recordFatal: assign(({ event }) => ({
      pendingCommandId: null,
      lastContractError: event.type === 'FATAL' ? boundedMessage(event.message) : null,
    })),
    beginStart: assign(({ event }) => ({
      pendingCommandId: event.type === 'START_REQUESTED' ? event.requestId : null,
      lastCommandError: null,
    })),
    failStart: assign(({ event }) => ({
      pendingCommandId: null,
      lastCommandError: event.type === 'START_FAILED' ? boundedMessage(event.message) : null,
    })),
    beginCommand: assign(({ event }) => ({
      pendingCommandId: event.type === 'COMMAND_REQUESTED'
        ? event.envelope.command_id
        : null,
      lastCommandError: null,
    })),
    failCommand: assign(({ event }) => ({
      pendingCommandId: null,
      lastCommandError: event.type === 'COMMAND_FAILED' ? boundedMessage(event.message) : null,
    })),
    beginConnection: assign(({ context }) => ({
      connectionEpoch: context.connectionEpoch + 1,
    })),
    stopConnection: assign(({ context }) => ({
      connectionEpoch: context.connectionEpoch + 1,
    })),
    applyStreamCursor: assign(({ event }) => ({
      resumeCursor: event.type === 'STREAM_EVENT_RECEIVED' ? event.cursor : null,
    })),
    applySnapshotCursor: assign(({ event }) => ({
      resumeCursor: event.type === 'SNAPSHOT_RECEIVED'
        ? event.snapshot.resume_cursor
        : null,
    })),
    resetStream: assign(({ context }) => ({
      connectionEpoch: context.connectionEpoch + 1,
      resumeCursor: null,
    })),
  },
})

const SNAPSHOT_TRANSITIONS = [
  {
    guard: 'isRunningSnapshot',
    target: '#workflowRunning',
    actions: ['applySnapshot', 'settleCorrelatedRequest'],
  },
  {
    guard: 'isWaitingSnapshot',
    target: '#workflowWaitingForSelection',
    actions: ['applySnapshot', 'settleCorrelatedRequest'],
  },
  {
    guard: 'isFinalizingSnapshot',
    target: '#workflowFinalizing',
    actions: ['applySnapshot', 'settleCorrelatedRequest'],
  },
  {
    guard: 'isProjectionSnapshot',
    target: '#workflowProjectionPending',
    actions: ['applySnapshot', 'settleCorrelatedRequest'],
  },
  {
    guard: 'isSucceededSnapshot',
    target: '#workflowSucceeded',
    actions: ['applySnapshot', 'settleCorrelatedRequest'],
  },
  {
    guard: 'isFailedSnapshot',
    target: '#workflowFailed',
    actions: ['applySnapshot', 'settleCorrelatedRequest'],
  },
  {
    guard: 'isCancelledSnapshot',
    target: '#workflowCancelled',
    actions: ['applySnapshot', 'settleCorrelatedRequest'],
  },
  {
    guard: 'isSupersededSnapshot',
    target: '#workflowSuperseded',
    actions: ['applySnapshot', 'settleCorrelatedRequest'],
  },
  {
    guard: 'isSameRevisionCursorAdvance',
    actions: 'applySnapshotCursor',
  },
  {
    guard: 'isCorrelatedRequest',
    actions: 'settleCorrelatedRequest',
  },
] as const

export const chapterWorkflowMachine = machineSetup.createMachine({
  id: 'chapterWorkflow',
  initial: 'booting',
  context: ({ input }) => ({
    projectId: input.projectId,
    chapterNumber: input.chapterNumber,
    scopeEpoch: 0,
    connectionEpoch: 0,
    runId: null,
    rowRevision: null,
    chapterRevision: null,
    checkpointId: null,
    resumeCursor: null,
    allowedCommands: [],
    retryActivityKey: null,
    pendingCommandId: null,
    lastContractError: null,
    lastCommandError: null,
  }),
  on: {
    SCOPE_CHANGED: {
      guard: 'isDifferentScope',
      target: '#workflowBooting',
      actions: 'changeScope',
    },
    FATAL: {
      guard: 'isCurrentScopeEpoch',
      target: '#workflowFatal',
      actions: 'recordFatal',
    },
  },
  states: {
    booting: {
      id: 'workflowBooting',
      on: {
        SNAPSHOT_RECEIVED: SNAPSHOT_TRANSITIONS,
        LOOKUP_EMPTY: {
          guard: 'isCurrentScopeEpoch',
          target: '#workflowIdle',
          actions: 'clearRun',
        },
      },
    },
    fatal: {
      id: 'workflowFatal',
      on: {
        RESYNC_REQUESTED: {
          target: '#workflowBooting',
          actions: 'prepareResync',
        },
      },
    },
    ready: {
      type: 'parallel',
      states: {
        workflow: {
          initial: 'idle',
          on: {
            SNAPSHOT_RECEIVED: SNAPSHOT_TRANSITIONS,
            LOOKUP_EMPTY: {
              guard: 'isCurrentScopeEpoch',
              target: '#workflowIdle',
              actions: 'clearRun',
            },
            COMMAND_REQUESTED: {
              guard: 'isAllowedCommand',
              actions: 'beginCommand',
            },
            COMMAND_FAILED: {
              guard: 'isCurrentCommandFailure',
              actions: 'failCommand',
            },
          },
          states: {
            idle: {
              id: 'workflowIdle',
              on: {
                START_REQUESTED: {
                  guard: 'canStart',
                  target: '#workflowSubmitting',
                  actions: 'beginStart',
                },
              },
            },
            submitting: {
              id: 'workflowSubmitting',
              on: {
                START_FAILED: {
                  guard: 'isCurrentStartFailure',
                  target: '#workflowBooting',
                  actions: 'failStart',
                },
              },
            },
            running: { id: 'workflowRunning' },
            waitingForSelection: { id: 'workflowWaitingForSelection' },
            finalizing: { id: 'workflowFinalizing' },
            projectionPending: { id: 'workflowProjectionPending' },
            succeeded: { id: 'workflowSucceeded' },
            failed: { id: 'workflowFailed' },
            cancelled: {
              id: 'workflowCancelled',
              on: {
                START_REQUESTED: {
                  guard: 'canStart',
                  target: '#workflowSubmitting',
                  actions: 'beginStart',
                },
              },
            },
            superseded: { id: 'workflowSuperseded' },
          },
        },
        transport: {
          initial: 'disconnected',
          on: {
            CONNECT_REQUESTED: {
              guard: 'isCurrentConnectRequest',
              target: '.connecting',
              actions: 'beginConnection',
            },
            RECONNECT_REQUESTED: {
              guard: 'isCurrentTransportEvent',
              target: '.connecting',
              actions: 'beginConnection',
            },
            TRANSPORT_STOPPED: {
              guard: 'isCurrentTransportEvent',
              target: '.disconnected',
              actions: 'stopConnection',
            },
            STREAM_RESET: {
              guard: 'isCurrentTransportEvent',
              target: '.connecting',
              actions: 'resetStream',
            },
            STREAM_EVENT_RECEIVED: {
              guard: 'isNewStreamCursor',
              actions: 'applyStreamCursor',
            },
            SNAPSHOT_RECEIVED: {
              guard: 'isRunChangingSnapshot',
              target: '.disconnected',
            },
            LOOKUP_EMPTY: {
              guard: 'isCurrentScopeEpoch',
              target: '.disconnected',
            },
          },
          states: {
            disconnected: {},
            connecting: {
              on: {
                STREAM_CONNECTED: {
                  guard: 'isCurrentTransportEvent',
                  target: 'connected',
                },
                STREAM_DISCONNECTED: {
                  guard: 'isCurrentTransportEvent',
                  target: 'reconnecting',
                },
              },
            },
            connected: {
              on: {
                STREAM_DISCONNECTED: {
                  guard: 'isCurrentTransportEvent',
                  target: 'reconnecting',
                },
              },
            },
            reconnecting: {
              on: {
                RECONNECT_EXHAUSTED: {
                  guard: 'isCurrentTransportEvent',
                  target: 'polling',
                },
              },
            },
            polling: {},
          },
        },
      },
    },
  },
})

export const createChapterWorkflowCommandEnvelope = (
  context: ChapterWorkflowMachineContext,
  type: ChapterWorkflowCommand,
  payload: Record<string, unknown> = {},
  commandId = globalThis.crypto.randomUUID(),
): ChapterWorkflowCommandEnvelope => {
  if (
    context.runId === null
    || context.rowRevision === null
    || context.chapterRevision === null
    || context.checkpointId === null
    || !isUuidLength(commandId)
  ) {
    throw new Error('章节工作流命令缺少可用的关联快照')
  }
  return {
    command_id: commandId,
    type,
    payload_version: 1,
    payload: { ...payload },
    expected_run_revision: context.rowRevision,
    expected_chapter_revision: context.chapterRevision,
    expected_checkpoint_id: context.checkpointId,
  }
}
