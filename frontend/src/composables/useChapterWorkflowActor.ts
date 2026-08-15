// AIMETA P=WritingDesk章节工作流Vue_actor|R=scope生命周期_SSE恢复_命令关联与实体失效|NR=不调用fetch_不创建QueryClient_不持有Project或Chapter实体|E=composable:chapter-workflow-actor|X=internal|A=useChapterWorkflowActor|D=@xstate/vue,vue|S=state,net|RD=./README.ai
import { useMachine } from '@xstate/vue'
import { computed, onScopeDispose, ref, toValue, watch, type MaybeRefOrGetter } from 'vue'

import {
  ChapterWorkflowContractError,
  type ChapterWorkflowCommand,
  type ChapterWorkflowCommandConflictDetail,
  type ChapterWorkflowCommandEnvelope,
  type ChapterWorkflowCommandResponse,
  type ChapterWorkflowConnection,
  type ChapterWorkflowScope,
  type ChapterWorkflowSnapshot,
  type ChapterWorkflowStartRequest,
  type ChapterWorkflowStartResponse,
} from '@/api/chapterWorkflow'
import { HttpRequestError } from '@/api/http'
import {
  TaskContractError,
  type BackgroundTaskCursorReset,
  type BackgroundTaskEvent,
  type BackgroundTaskSnapshot,
  type BackgroundTaskStreamScope,
} from '@/api/tasks'
import {
  chapterWorkflowMachine,
  createChapterWorkflowCommandEnvelope,
  createChapterWorkflowRequestId,
  getChapterWorkflowPhase,
  type ChapterWorkflowPhase,
  type ChapterWorkflowTransportPhase,
} from '@/composables/chapterWorkflowMachine'

export type ChapterWorkflowActorPhase = ChapterWorkflowPhase | 'booting' | 'fatal'

export interface ChapterWorkflowTaskSubscription {
  onOpen: () => void
  onSnapshot: (snapshot: BackgroundTaskSnapshot) => void
  onTask: (event: BackgroundTaskEvent) => void
  onReset: (reset: BackgroundTaskCursorReset) => void
  signal: AbortSignal
  cursor: number | null
  scope: BackgroundTaskStreamScope
  eventsUrl: string
}

export interface ChapterWorkflowCommandPortInput extends ChapterWorkflowScope {
  runId: string
  command: ChapterWorkflowCommandEnvelope
}

export type ChapterWorkflowCommandPortResult =
  | { kind: 'response'; response: ChapterWorkflowCommandResponse }
  | { kind: 'conflict'; detail: ChapterWorkflowCommandConflictDetail; message?: string }

export interface ChapterWorkflowActorPorts {
  lookup: (
    scope: ChapterWorkflowScope,
    signal: AbortSignal,
  ) => Promise<ChapterWorkflowConnection | null>
  start: (request: ChapterWorkflowStartRequest) => Promise<ChapterWorkflowStartResponse>
  command: (
    input: ChapterWorkflowCommandPortInput,
  ) => Promise<ChapterWorkflowCommandPortResult>
  subscribeTasks: (subscription: ChapterWorkflowTaskSubscription) => Promise<'reset'>
  invalidateChapterAndProject: (scope: ChapterWorkflowScope) => Promise<void> | void
  schedule: (callback: () => void, delayMs: number) => unknown
  cancelScheduled: (handle: unknown) => void
}

type LookupMode = 'bootstrap' | 'poll' | 'refetch' | 'reset' | 'superseded'
type ReconnectMode = 'reset' | 'stream'

interface StreamIdentity extends ChapterWorkflowScope {
  scopeEpoch: number
  connectionEpoch: number
  runId: string
  eventsUrl: string
}

interface ActiveStream extends StreamIdentity {
  controller: AbortController
}

const RECONNECT_DELAYS_MS = [1_000, 2_000, 5_000] as const
const POLLING_INTERVAL_MS = 30_000
const CONFLICT_MESSAGE = '章节工作流状态已变化，请按最新状态重试'

const isValidScope = (
  scope: { projectId: string; chapterNumber: number | null },
): scope is ChapterWorkflowScope =>
  Boolean(scope.projectId)
  && scope.chapterNumber !== null
  && Number.isInteger(scope.chapterNumber)
  && scope.chapterNumber > 0

const errorMessage = (error: unknown) =>
  error instanceof Error && error.message.trim()
    ? error.message
    : '章节工作流同步失败'

const isFatalBoundaryError = (error: unknown) =>
  error instanceof ChapterWorkflowContractError
  || error instanceof TaskContractError
  || (error instanceof HttpRequestError && (error.status === 401 || error.status === 403))

const boundaryForSnapshot = (snapshot: ChapterWorkflowSnapshot) => {
  const phase = getChapterWorkflowPhase(snapshot.status)
  return phase === 'waitingForSelection'
    || phase === 'projectionPending'
    || phase === 'succeeded'
    || phase === 'failed'
    || phase === 'cancelled'
    || phase === 'superseded'
    ? phase
    : null
}

export function useChapterWorkflowActor(
  projectId: MaybeRefOrGetter<string>,
  chapterNumber: MaybeRefOrGetter<number | null>,
  ports: ChapterWorkflowActorPorts,
) {
  const initialScope = {
    projectId: toValue(projectId),
    chapterNumber: toValue(chapterNumber),
  }
  const { snapshot, send, actorRef } = useMachine(chapterWorkflowMachine, {
    input: initialScope,
  })
  const resyncing = ref(false)
  const phase = computed<ChapterWorkflowActorPhase>(() => {
    const value = snapshot.value
    if (value.matches('booting')) return 'booting'
    if (value.matches('fatal')) return 'fatal'
    if (value.matches({ ready: { workflow: 'idle' } })) return 'idle'
    if (value.matches({ ready: { workflow: 'submitting' } })) return 'submitting'
    if (value.matches({ ready: { workflow: 'running' } })) return 'running'
    if (value.matches({ ready: { workflow: 'waitingForSelection' } })) {
      return 'waitingForSelection'
    }
    if (value.matches({ ready: { workflow: 'finalizing' } })) return 'finalizing'
    if (value.matches({ ready: { workflow: 'projectionPending' } })) {
      return 'projectionPending'
    }
    if (value.matches({ ready: { workflow: 'succeeded' } })) return 'succeeded'
    if (value.matches({ ready: { workflow: 'failed' } })) return 'failed'
    if (value.matches({ ready: { workflow: 'cancelled' } })) return 'cancelled'
    return 'superseded'
  })
  const transport = computed<ChapterWorkflowTransportPhase>(() => {
    const value = snapshot.value
    if (value.matches({ ready: { transport: 'connecting' } })) return 'connecting'
    if (value.matches({ ready: { transport: 'connected' } })) return 'connected'
    if (value.matches({ ready: { transport: 'reconnecting' } })) return 'reconnecting'
    if (value.matches({ ready: { transport: 'polling' } })) return 'polling'
    return 'disconnected'
  })

  let disposed = false
  let activeStream: ActiveStream | null = null
  let currentEventsUrl: string | null = null
  let lookupRequestEpoch = 0
  let wakeUpLookupGeneration = 0
  let wakeUpLookupInFlight = false
  let wakeUpLookupPending = false
  let reconnectFailures = 0
  let reconnectHandle: unknown | null = null
  let pollingHandle: unknown | null = null
  let highestChapterRevision: number | null = null
  let followedSupersededRunId: string | null = null
  const invalidatedBoundaries = new Set<string>()
  const lookupControllers = new Set<AbortController>()

  const currentScope = (): ChapterWorkflowScope | null => {
    const scope = {
      projectId: snapshot.value.context.projectId,
      chapterNumber: snapshot.value.context.chapterNumber,
    }
    return isValidScope(scope) ? scope : null
  }

  const isCurrentScope = (scope: ChapterWorkflowScope, scopeEpoch: number) => {
    const context = snapshot.value.context
    return !disposed
      && context.scopeEpoch === scopeEpoch
      && context.projectId === scope.projectId
      && context.chapterNumber === scope.chapterNumber
  }

  const isCurrentIdentity = (identity: StreamIdentity) => {
    const context = snapshot.value.context
    return isCurrentScope(identity, identity.scopeEpoch)
      && context.connectionEpoch === identity.connectionEpoch
      && context.runId === identity.runId
  }

  const cancelReconnect = () => {
    if (reconnectHandle === null) return
    ports.cancelScheduled(reconnectHandle)
    reconnectHandle = null
  }

  const cancelPolling = () => {
    if (pollingHandle === null) return
    ports.cancelScheduled(pollingHandle)
    pollingHandle = null
  }

  const abortLookups = () => {
    lookupRequestEpoch += 1
    wakeUpLookupGeneration += 1
    wakeUpLookupInFlight = false
    wakeUpLookupPending = false
    for (const controller of lookupControllers) controller.abort()
    lookupControllers.clear()
  }

  const abortActiveStream = () => {
    const stream = activeStream
    activeStream = null
    stream?.controller.abort()
  }

  const stopScopeResources = () => {
    abortActiveStream()
    abortLookups()
    cancelReconnect()
    cancelPolling()
    currentEventsUrl = null
    reconnectFailures = 0
  }

  const enterFatal = (scopeEpoch: number, error: unknown) => {
    if (snapshot.value.context.scopeEpoch !== scopeEpoch) return
    stopScopeResources()
    send({ type: 'FATAL', scopeEpoch, message: errorMessage(error) })
  }

  const invalidateForSnapshot = (
    value: ChapterWorkflowSnapshot,
    businessSnapshotAccepted: boolean,
    workflowRevisionIncreased: boolean,
  ) => {
    if (!businessSnapshotAccepted) return
    const revisionIncreased = highestChapterRevision !== null
      && value.current_chapter_revision > highestChapterRevision
    highestChapterRevision = highestChapterRevision === null
      ? value.current_chapter_revision
      : Math.max(highestChapterRevision, value.current_chapter_revision)

    const boundary = boundaryForSnapshot(value)
    const boundaryKey = boundary ? `${value.run_id}:${boundary}` : null
    const enteredBoundary = boundaryKey !== null && !invalidatedBoundaries.has(boundaryKey)
    if (boundaryKey) invalidatedBoundaries.add(boundaryKey)
    if (!revisionIncreased && !enteredBoundary && !workflowRevisionIncreased) return

    void Promise.resolve(ports.invalidateChapterAndProject({
      projectId: value.project_id,
      chapterNumber: value.chapter_number,
    })).catch(() => undefined)
  }

  const afterSnapshot = (
    beforeRunId: string | null,
    beforeRowRevision: number | null,
    value: ChapterWorkflowSnapshot,
  ) => {
    const context = snapshot.value.context
    const matchesSnapshot = context.runId === value.run_id
      && context.projectId === value.project_id
      && context.chapterNumber === value.chapter_number
    const businessSnapshotAccepted = matchesSnapshot
      && context.rowRevision === value.row_revision
      && (beforeRunId !== context.runId || beforeRowRevision !== context.rowRevision)
    const workflowRevisionIncreased = businessSnapshotAccepted
      && beforeRunId === value.run_id
      && beforeRowRevision !== null
      && value.row_revision > beforeRowRevision
    if (businessSnapshotAccepted && beforeRunId !== null && beforeRunId !== context.runId) {
      abortActiveStream()
      cancelReconnect()
      cancelPolling()
      reconnectFailures = 0
    }
    invalidateForSnapshot(value, businessSnapshotAccepted, workflowRevisionIncreased)
    return { businessSnapshotAccepted }
  }

  const applyLookupSnapshot = (
    connection: ChapterWorkflowConnection,
    mode: LookupMode,
    scopeEpoch: number,
    connectionEpoch: number,
  ) => {
    const before = snapshot.value.context
    if (mode === 'bootstrap' || mode === 'superseded') {
      send({
        type: 'SNAPSHOT_RECEIVED',
        source: 'lookup',
        scopeEpoch,
        snapshot: connection.snapshot,
      })
    } else {
      send({
        type: 'SNAPSHOT_RECEIVED',
        source: 'refetch',
        scopeEpoch,
        connectionEpoch,
        snapshot: connection.snapshot,
      })
    }
    return afterSnapshot(
      before.runId,
      before.rowRevision,
      connection.snapshot,
    )
  }

  const applyStartSnapshot = (
    response: ChapterWorkflowStartResponse,
    scopeEpoch: number,
    requestId: string,
  ) => {
    const before = snapshot.value.context
    send({
      type: 'SNAPSHOT_RECEIVED',
      source: 'start',
      scopeEpoch,
      correlationId: requestId,
      snapshot: response.snapshot,
    })
    return afterSnapshot(
      before.runId,
      before.rowRevision,
      response.snapshot,
    )
  }

  const applyCommandSnapshot = (
    value: ChapterWorkflowSnapshot,
    scopeEpoch: number,
    commandId: string,
    commandError?: string,
  ) => {
    const before = snapshot.value.context
    send({
      type: 'SNAPSHOT_RECEIVED',
      source: 'command',
      scopeEpoch,
      correlationId: commandId,
      commandError,
      snapshot: value,
    })
    return afterSnapshot(
      before.runId,
      before.rowRevision,
      value,
    )
  }

  const streamIdentity = (eventsUrl: string): StreamIdentity | null => {
    const context = snapshot.value.context
    const scope = currentScope()
    if (context.runId === null || scope === null) return null
    return {
      ...scope,
      scopeEpoch: context.scopeEpoch,
      connectionEpoch: context.connectionEpoch,
      runId: context.runId,
      eventsUrl,
    }
  }

  let lookupAndApply: (
    scope: ChapterWorkflowScope,
    scopeEpoch: number,
    mode: LookupMode,
    connectionEpoch: number,
  ) => Promise<void>

  const schedulePolling = (identity: StreamIdentity) => {
    cancelPolling()
    pollingHandle = ports.schedule(() => {
      pollingHandle = null
      if (!isCurrentIdentity(identity)) return
      void lookupAndApply(
        { projectId: identity.projectId, chapterNumber: identity.chapterNumber },
        identity.scopeEpoch,
        'poll',
        identity.connectionEpoch,
      )
    }, POLLING_INTERVAL_MS)
  }

  const startPolling = (identity: StreamIdentity) => {
    if (!isCurrentIdentity(identity)) return
    send({
      type: 'RECONNECT_EXHAUSTED',
      scopeEpoch: identity.scopeEpoch,
      connectionEpoch: identity.connectionEpoch,
      runId: identity.runId,
    })
    schedulePolling(identity)
  }

  let openStream: (identity: StreamIdentity) => void

  const scheduleReconnect = (identity: StreamIdentity, mode: ReconnectMode) => {
    if (!isCurrentIdentity(identity)) return
    reconnectFailures += 1
    if (reconnectFailures > RECONNECT_DELAYS_MS.length) {
      startPolling(identity)
      return
    }
    cancelReconnect()
    const delay = RECONNECT_DELAYS_MS[reconnectFailures - 1]
    reconnectHandle = ports.schedule(() => {
      reconnectHandle = null
      if (!isCurrentIdentity(identity)) return
      send({
        type: 'RECONNECT_REQUESTED',
        scopeEpoch: identity.scopeEpoch,
        connectionEpoch: identity.connectionEpoch,
        runId: identity.runId,
      })
      const nextIdentity = streamIdentity(identity.eventsUrl)
      if (!nextIdentity) return
      if (mode === 'reset') {
        void lookupAndApply(
          { projectId: nextIdentity.projectId, chapterNumber: nextIdentity.chapterNumber },
          nextIdentity.scopeEpoch,
          'reset',
          nextIdentity.connectionEpoch,
        )
      } else {
        openStream(nextIdentity)
      }
    }, delay)
  }

  const handleTransportFailure = (identity: StreamIdentity, mode: ReconnectMode) => {
    if (!isCurrentIdentity(identity)) return
    abortActiveStream()
    send({
      type: 'STREAM_DISCONNECTED',
      scopeEpoch: identity.scopeEpoch,
      connectionEpoch: identity.connectionEpoch,
      runId: identity.runId,
    })
    scheduleReconnect(identity, mode)
  }

  const scheduleWakeUpLookup = (identity: StreamIdentity) => {
    wakeUpLookupPending = true
    if (wakeUpLookupInFlight) return
    const generation = wakeUpLookupGeneration
    wakeUpLookupInFlight = true
    void (async () => {
      try {
        while (
          generation === wakeUpLookupGeneration
          && wakeUpLookupPending
          && isCurrentIdentity(identity)
          && !snapshot.value.matches({ ready: { transport: 'reconnecting' } })
        ) {
          wakeUpLookupPending = false
          await lookupAndApply(
            { projectId: identity.projectId, chapterNumber: identity.chapterNumber },
            identity.scopeEpoch,
            'refetch',
            identity.connectionEpoch,
          )
        }
      } finally {
        if (generation === wakeUpLookupGeneration) wakeUpLookupInFlight = false
      }
    })()
  }

  const handleWakeUp = (identity: StreamIdentity, cursor: number) => {
    if (!isCurrentIdentity(identity)) return
    const previousCursor = snapshot.value.context.resumeCursor
    send({
      type: 'STREAM_EVENT_RECEIVED',
      scopeEpoch: identity.scopeEpoch,
      connectionEpoch: identity.connectionEpoch,
      runId: identity.runId,
      cursor,
    })
    if (snapshot.value.context.resumeCursor !== cursor || previousCursor === cursor) return
    reconnectFailures = 0
    scheduleWakeUpLookup(identity)
  }

  const handleReset = (identity: StreamIdentity) => {
    if (!isCurrentIdentity(identity)) return
    abortLookups()
    abortActiveStream()
    cancelReconnect()
    cancelPolling()
    reconnectFailures = 0
    send({
      type: 'STREAM_RESET',
      scopeEpoch: identity.scopeEpoch,
      connectionEpoch: identity.connectionEpoch,
      runId: identity.runId,
    })
    const nextIdentity = streamIdentity(identity.eventsUrl)
    if (!nextIdentity) return
    void lookupAndApply(
      { projectId: nextIdentity.projectId, chapterNumber: nextIdentity.chapterNumber },
      nextIdentity.scopeEpoch,
      'reset',
      nextIdentity.connectionEpoch,
    )
  }

  openStream = (identity) => {
    if (!isCurrentIdentity(identity)) return
    abortActiveStream()
    const controller = new AbortController()
    activeStream = { ...identity, controller }
    void ports.subscribeTasks({
      eventsUrl: identity.eventsUrl,
      cursor: snapshot.value.context.resumeCursor,
      scope: { stream_type: 'workflow', stream_id: identity.runId },
      signal: controller.signal,
      onOpen: () => {
        if (!isCurrentIdentity(identity) || controller.signal.aborted) return
        send({
          type: 'STREAM_CONNECTED',
          scopeEpoch: identity.scopeEpoch,
          connectionEpoch: identity.connectionEpoch,
          runId: identity.runId,
        })
      },
      onSnapshot: (taskSnapshot) => {
        if (controller.signal.aborted) return
        handleWakeUp(identity, taskSnapshot.resume_cursor)
      },
      onTask: (event) => {
        if (controller.signal.aborted) return
        handleWakeUp(identity, event.cursor)
      },
      onReset: () => {
        if (controller.signal.aborted) return
        handleReset(identity)
      },
    }).catch((error: unknown) => {
      if (controller.signal.aborted || !isCurrentIdentity(identity)) return
      if (isFatalBoundaryError(error)) {
        enterFatal(identity.scopeEpoch, error)
        return
      }
      handleTransportFailure(identity, 'stream')
    })
  }

  const ensureStream = (
    connection: ChapterWorkflowConnection,
    mode: LookupMode,
    runChanged: boolean,
  ) => {
    const state = snapshot.value
    if (state.context.runId !== connection.snapshot.run_id) return
    if (state.matches({ ready: { workflow: 'superseded' } })) return
    currentEventsUrl = connection.events_url

    if (state.matches({ ready: { transport: 'polling' } }) && !runChanged) {
      if (mode === 'poll') {
        const identity = streamIdentity(connection.events_url)
        if (identity) schedulePolling(identity)
      }
      return
    }
    if (state.matches({ ready: { transport: 'disconnected' } })) {
      reconnectFailures = 0
      send({
        type: 'CONNECT_REQUESTED',
        scopeEpoch: state.context.scopeEpoch,
        runId: connection.snapshot.run_id,
      })
    }
    const identity = streamIdentity(connection.events_url)
    if (!identity || !snapshot.value.matches({ ready: { transport: 'connecting' } })) return
    if (
      activeStream
      && !activeStream.controller.signal.aborted
      && activeStream.scopeEpoch === identity.scopeEpoch
      && activeStream.connectionEpoch === identity.connectionEpoch
      && activeStream.runId === identity.runId
    ) {
      return
    }
    openStream(identity)
  }

  lookupAndApply = async (scope, scopeEpoch, mode, connectionEpoch) => {
    if (!isCurrentScope(scope, scopeEpoch)) return
    const requestEpoch = ++lookupRequestEpoch
    const controller = new AbortController()
    lookupControllers.add(controller)
    try {
      const connection = await ports.lookup(scope, controller.signal)
      if (
        controller.signal.aborted
        || requestEpoch !== lookupRequestEpoch
        || !isCurrentScope(scope, scopeEpoch)
        || (mode !== 'bootstrap'
          && mode !== 'superseded'
          && snapshot.value.context.connectionEpoch !== connectionEpoch)
      ) {
        return
      }
      if (connection === null) {
        abortActiveStream()
        cancelReconnect()
        cancelPolling()
        currentEventsUrl = null
        send({ type: 'LOOKUP_EMPTY', scopeEpoch })
        return
      }

      const beforeRunId = snapshot.value.context.runId
      const applied = applyLookupSnapshot(connection, mode, scopeEpoch, connectionEpoch)
      const after = snapshot.value
      if (after.context.runId !== connection.snapshot.run_id) return

      if (
        applied.businessSnapshotAccepted
        && after.matches({ ready: { workflow: 'superseded' } })
        && followedSupersededRunId !== connection.snapshot.run_id
      ) {
        followedSupersededRunId = connection.snapshot.run_id
        abortActiveStream()
        cancelReconnect()
        cancelPolling()
        void lookupAndApply(scope, scopeEpoch, 'superseded', after.context.connectionEpoch)
        return
      }
      ensureStream(connection, mode, beforeRunId !== after.context.runId)
    } catch (error) {
      if (
        controller.signal.aborted
        || requestEpoch !== lookupRequestEpoch
        || !isCurrentScope(scope, scopeEpoch)
      ) return
      if (isFatalBoundaryError(error) || mode === 'bootstrap' || mode === 'superseded') {
        enterFatal(scopeEpoch, error)
        return
      }
      const identity = currentEventsUrl ? streamIdentity(currentEventsUrl) : null
      if (mode === 'poll') {
        if (identity) schedulePolling(identity)
        return
      }
      if (identity) handleTransportFailure(identity, mode === 'reset' ? 'reset' : 'stream')
    } finally {
      lookupControllers.delete(controller)
    }
  }

  const start = async (
    request: Omit<ChapterWorkflowStartRequest, 'project_id' | 'chapter_number'> = {},
  ) => {
    const scope = currentScope()
    if (scope === null) return false
    const requestId = createChapterWorkflowRequestId()
    send({ type: 'START_REQUESTED', requestId })
    if (snapshot.value.context.pendingCommandId !== requestId) return false

    const scopeEpoch = snapshot.value.context.scopeEpoch
    abortLookups()
    abortActiveStream()
    cancelReconnect()
    cancelPolling()
    try {
      const response = await ports.start({
        ...request,
        project_id: scope.projectId,
        chapter_number: scope.chapterNumber,
      })
      if (!isCurrentScope(scope, scopeEpoch)) return true
      const applied = applyStartSnapshot(response, scopeEpoch, requestId)
      if (snapshot.value.context.runId !== response.snapshot.run_id) return true
      ensureStream(
        { events_url: response.events_url, snapshot: response.snapshot },
        'bootstrap',
        applied.businessSnapshotAccepted,
      )
    } catch (error) {
      if (!isCurrentScope(scope, scopeEpoch)) return true
      if (isFatalBoundaryError(error)) {
        enterFatal(scopeEpoch, error)
        return true
      }
      send({
        type: 'START_FAILED',
        scopeEpoch,
        requestId,
        message: errorMessage(error),
      })
      if (snapshot.value.matches('booting')) {
        void lookupAndApply(scope, scopeEpoch, 'bootstrap', snapshot.value.context.connectionEpoch)
      }
    }
    return true
  }

  const submitCommand = async (
    type: ChapterWorkflowCommand,
    payload: Record<string, unknown> = {},
  ) => {
    let envelope: ChapterWorkflowCommandEnvelope
    try {
      envelope = createChapterWorkflowCommandEnvelope(snapshot.value.context, type, payload)
    } catch {
      return false
    }
    send({ type: 'COMMAND_REQUESTED', envelope })
    if (snapshot.value.context.pendingCommandId !== envelope.command_id) return false

    const scope = currentScope()
    if (scope === null) return false
    const scopeEpoch = snapshot.value.context.scopeEpoch
    const runId = snapshot.value.context.runId
    if (runId === null) return false
    try {
      const result = await ports.command({ ...scope, runId, command: envelope })
      if (!isCurrentScope(scope, scopeEpoch)) return true
      if (result.kind === 'response') {
        applyCommandSnapshot(result.response.snapshot, scopeEpoch, envelope.command_id)
      } else {
        applyCommandSnapshot(
          result.detail.current_snapshot,
          scopeEpoch,
          envelope.command_id,
          result.message ?? CONFLICT_MESSAGE,
        )
      }
    } catch (error) {
      if (!isCurrentScope(scope, scopeEpoch)) return true
      if (isFatalBoundaryError(error)) {
        enterFatal(scopeEpoch, error)
        return true
      }
      send({
        type: 'COMMAND_FAILED',
        scopeEpoch,
        commandId: envelope.command_id,
        message: errorMessage(error),
      })
    }
    return true
  }

  const resync = async () => {
    if (!snapshot.value.matches('fatal') || resyncing.value) return false
    const scope = currentScope()
    if (scope === null) return false
    resyncing.value = true
    stopScopeResources()
    send({ type: 'RESYNC_REQUESTED' })
    const scopeEpoch = snapshot.value.context.scopeEpoch
    try {
      await lookupAndApply(
        scope,
        scopeEpoch,
        'bootstrap',
        snapshot.value.context.connectionEpoch,
      )
    } finally {
      resyncing.value = false
    }
    return true
  }

  let initialized = false
  watch(
    [() => toValue(projectId), () => toValue(chapterNumber)] as const,
    ([nextProjectId, nextChapterNumber]) => {
      const scope = { projectId: nextProjectId, chapterNumber: nextChapterNumber }
      stopScopeResources()
      highestChapterRevision = null
      followedSupersededRunId = null
      invalidatedBoundaries.clear()
      if (initialized) {
        send({
          type: 'SCOPE_CHANGED',
          projectId: scope.projectId,
          chapterNumber: scope.chapterNumber,
        })
      }
      initialized = true
      const scopeEpoch = snapshot.value.context.scopeEpoch
      if (!isValidScope(scope)) {
        return
      }
      void lookupAndApply(scope, scopeEpoch, 'bootstrap', snapshot.value.context.connectionEpoch)
    },
    { immediate: true, flush: 'pre' },
  )

  onScopeDispose(() => {
    disposed = true
    stopScopeResources()
  })

  return {
    snapshot,
    actorRef,
    phase,
    transport,
    start,
    submitCommand,
    resync,
    resyncing,
  }
}
