// AIMETA P=后台任务API客户端_任务列表和日志|R=查询任务_查询任务详情|NR=不含业务任务提交|E=api:tasks|X=internal|A=TaskAPI|D=fetch|S=net|RD=./README.ai
import { API_BASE_URL, API_PREFIX } from './base'
import { authJson } from './client'
import type { components } from './generated/schema'
import { type HttpRequestOptions } from './http'
import { readSSESubscription, streamRequest } from './novel'

export type BackgroundTaskLogEntry = components['schemas']['BackgroundTaskLogEntry']
export type BackgroundTask = components['schemas']['BackgroundTaskResponse']
export type BackgroundTaskStatus = BackgroundTask['status']
export type BackgroundTaskSnapshot = components['schemas']['BackgroundTaskSnapshotResponse']
export type BackgroundTaskEvent = components['schemas']['BackgroundTaskEventResponse']
export type BackgroundTaskCursorReset = components['schemas']['BackgroundTaskCursorResetResponse']

export interface BackgroundTaskStreamScope {
  stream_type: 'job' | 'workflow'
  stream_id: string
}

type TaskDecodeFailure =
  | { kind: 'unsupported_version'; version: number }
  | {
      kind: 'malformed'
      reason: 'payload' | 'schema_version' | 'snapshot' | 'scope' | 'task' | 'reset'
    }

export type TaskDecodeResult<T> = { kind: 'ok'; value: T } | TaskDecodeFailure

export type TaskStreamDecodeResult =
  | { kind: 'ok'; event: 'snapshot'; value: BackgroundTaskSnapshot }
  | { kind: 'ok'; event: 'task'; value: BackgroundTaskEvent }
  | { kind: 'ok'; event: 'reset'; value: BackgroundTaskCursorReset }
  | TaskDecodeFailure
  | { kind: 'ignored_unknown_event' }

export class TaskContractError extends Error {
  readonly code: TaskDecodeFailure['kind']

  constructor(failure: TaskDecodeFailure) {
    super(
      failure.kind === 'unsupported_version'
        ? '后台任务数据版本不受支持'
        : '后台任务数据格式无效',
    )
    this.name = 'TaskContractError'
    this.code = failure.kind
  }
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value)

const isString = (value: unknown): value is string => typeof value === 'string'
const isInteger = (value: unknown): value is number =>
  typeof value === 'number' && Number.isInteger(value)
const isNullableString = (value: unknown) => value === undefined || value === null || isString(value)
const isNullableRecord = (value: unknown) => value === undefined || value === null || isRecord(value)
const isNullablePositiveInteger = (value: unknown) =>
  value === undefined || value === null || (isInteger(value) && value > 0)

const matchesStreamScope = (
  value: Record<string, unknown>,
  expectedScope?: BackgroundTaskStreamScope,
) => {
  if (!expectedScope) {
    return true
  }
  return value.stream_type === expectedScope.stream_type
    && value.stream_id === expectedScope.stream_id
}

const isLogEntry = (value: unknown): value is BackgroundTaskLogEntry =>
  isRecord(value)
  && isString(value.timestamp)
  && isString(value.level)
  && isString(value.message)

const isBackgroundTask = (value: unknown): value is BackgroundTask => {
  if (!isRecord(value)) return false
  const status = value.status
  return isString(value.id)
    && isInteger(value.user_id)
    && isString(value.task_type)
    && isString(value.title)
    && (status === 'queued' || status === 'running' || status === 'succeeded' || status === 'failed')
    && isInteger(value.progress)
    && isString(value.created_at)
    && !Number.isNaN(Date.parse(value.created_at))
    && isString(value.updated_at)
    && isNullableString(value.project_id)
    && isNullableString(value.stream_type)
    && isNullableString(value.stream_id)
    && isNullablePositiveInteger(value.chapter_number)
    && isNullableRecord(value.payload)
    && isNullableRecord(value.result)
    && isNullableString(value.error)
    && (value.log_entries === undefined
      || (Array.isArray(value.log_entries) && value.log_entries.every(isLogEntry)))
    && isNullableString(value.started_at)
    && isNullableString(value.completed_at)
}

const decodeVersionedRecord = (
  payload: unknown,
): { kind: 'ok'; value: Record<string, unknown> } | TaskDecodeFailure => {
  if (!isRecord(payload)) return { kind: 'malformed', reason: 'payload' }
  if (
    !Object.prototype.hasOwnProperty.call(payload, 'schema_version')
    || !isInteger(payload.schema_version)
  ) {
    return { kind: 'malformed', reason: 'schema_version' }
  }
  if (payload.schema_version !== 1) {
    return { kind: 'unsupported_version', version: payload.schema_version }
  }
  return { kind: 'ok', value: payload }
}

export const decodeBackgroundTaskSnapshot = (
  payload: unknown,
  expectedScope?: BackgroundTaskStreamScope,
): TaskDecodeResult<BackgroundTaskSnapshot> => {
  const decoded = decodeVersionedRecord(payload)
  if (decoded.kind !== 'ok') return decoded
  const value = decoded.value
  if (
    !Array.isArray(value.tasks)
    || !value.tasks.every(isBackgroundTask)
    || !isString(value.snapshot_revision)
    || !isInteger(value.resume_cursor)
    || value.resume_cursor < 0
    || !isNullableString(value.stream_type)
    || !isNullableString(value.stream_id)
  ) {
    return { kind: 'malformed', reason: 'snapshot' }
  }
  if (
    !matchesStreamScope(value, expectedScope)
    || (!expectedScope
      && (value.stream_type !== undefined && value.stream_type !== null
        || value.stream_id !== undefined && value.stream_id !== null))
  ) {
    return { kind: 'malformed', reason: 'scope' }
  }
  return { kind: 'ok', value: value as BackgroundTaskSnapshot }
}

const decodeBackgroundTaskEvent = (
  payload: unknown,
  expectedScope?: BackgroundTaskStreamScope,
): TaskDecodeResult<BackgroundTaskEvent> => {
  const decoded = decodeVersionedRecord(payload)
  if (decoded.kind !== 'ok') return decoded
  const value = decoded.value
  if (
    !isInteger(value.cursor)
    || value.cursor < 0
    || !isString(value.event_type)
    || !isBackgroundTask(value.task)
  ) {
    return { kind: 'malformed', reason: 'task' }
  }
  if (!matchesStreamScope(value.task as Record<string, unknown>, expectedScope)) {
    return { kind: 'malformed', reason: 'scope' }
  }
  return { kind: 'ok', value: value as BackgroundTaskEvent }
}

const decodeBackgroundTaskReset = (
  payload: unknown,
): TaskDecodeResult<BackgroundTaskCursorReset> => {
  const decoded = decodeVersionedRecord(payload)
  if (decoded.kind !== 'ok') return decoded
  const value = decoded.value
  if (
    value.reason !== 'cursor_expired'
    || !isInteger(value.retained_through_cursor)
    || value.retained_through_cursor < 0
  ) {
    return { kind: 'malformed', reason: 'reset' }
  }
  return { kind: 'ok', value: value as BackgroundTaskCursorReset }
}

export const decodeBackgroundTaskStreamMessage = (
  event: string,
  payload: unknown,
  expectedScope?: BackgroundTaskStreamScope,
): TaskStreamDecodeResult => {
  if (event === 'snapshot') {
    const decoded = decodeBackgroundTaskSnapshot(payload, expectedScope)
    return decoded.kind === 'ok' ? { ...decoded, event } : decoded
  }
  if (event === 'task') {
    const decoded = decodeBackgroundTaskEvent(payload, expectedScope)
    return decoded.kind === 'ok' ? { ...decoded, event } : decoded
  }
  if (event === 'reset') {
    const decoded = decodeBackgroundTaskReset(payload)
    return decoded.kind === 'ok' ? { ...decoded, event } : decoded
  }
  return { kind: 'ignored_unknown_event' }
}

const requireTaskPayload = <T>(decoded: TaskDecodeResult<T>): T => {
  if (decoded.kind === 'ok') return decoded.value
  throw new TaskContractError(decoded)
}

const TASKS_BASE = `${API_BASE_URL}${API_PREFIX}/tasks`

const request = async <T = unknown>(url: string, options: HttpRequestOptions = {}) =>
  authJson<T>(url, {
    ...options,
    timeoutMs: options.timeoutMs ?? 15_000,
    fallbackErrorMessage: '后台任务接口请求失败',
  })

const appendStreamScope = (
  params: URLSearchParams,
  scope?: BackgroundTaskStreamScope,
) => {
  if (!scope) return
  params.set('stream_type', scope.stream_type)
  params.set('stream_id', scope.stream_id)
}

export class TaskAPI {
  static async getTasks(limit = 20): Promise<BackgroundTask[]> {
    return request(`${TASKS_BASE}?limit=${limit}`)
  }

  static async getSnapshot(
    limit = 20,
    scope?: BackgroundTaskStreamScope,
  ): Promise<BackgroundTaskSnapshot> {
    const params = new URLSearchParams({ limit: String(limit) })
    appendStreamScope(params, scope)
    const payload = await request<unknown>(`${TASKS_BASE}/snapshot?${params.toString()}`)
    return requireTaskPayload(decodeBackgroundTaskSnapshot(payload, scope))
  }

  static async subscribeTasks(
    handlers: {
      onSnapshot: (snapshot: BackgroundTaskSnapshot) => void
      onTask: (event: BackgroundTaskEvent) => void
      onReset: (reset: BackgroundTaskCursorReset) => void
      onOpen?: () => void
      onError?: (error: Error) => void
      signal?: AbortSignal
      limit?: number
      cursor?: number | null
      scope?: BackgroundTaskStreamScope
      eventsUrl?: string
    }
  ): Promise<'reset'> {
    const params = new URLSearchParams({ limit: String(handlers.limit ?? 20) })
    if (handlers.cursor != null) {
      params.set('cursor', String(handlers.cursor))
    }
    appendStreamScope(params, handlers.scope)
    const eventsUrl = handlers.eventsUrl ?? `${TASKS_BASE}/events?${params.toString()}`
    const response = await streamRequest(eventsUrl, {
      method: 'GET',
      signal: handlers.signal,
      timeoutMs: 600_000,
      headers:
        handlers.cursor == null
          ? undefined
          : { 'Last-Event-ID': String(handlers.cursor) },
    })
    handlers.onOpen?.()
    let resetReceived = false
    await readSSESubscription(response, {
      onMessage: (message) => {
        const decoded = decodeBackgroundTaskStreamMessage(
          message.event,
          message.data,
          handlers.scope,
        )
        if (decoded.kind === 'ignored_unknown_event') return
        if (decoded.kind !== 'ok') throw new TaskContractError(decoded)
        if (decoded.event === 'snapshot') {
          handlers.onSnapshot(decoded.value)
        } else if (decoded.event === 'task') {
          handlers.onTask(decoded.value)
        } else {
          resetReceived = true
          handlers.onReset(decoded.value)
        }
      },
      onError: handlers.onError,
      stopEvents: ['reset'],
    })
    if (resetReceived) {
      return 'reset'
    }
    throw new Error('任务日志推送中断')
  }

  static async getTask(taskId: string): Promise<BackgroundTask> {
    return request(`${TASKS_BASE}/${taskId}`)
  }

  static async waitForCompletion(
    taskId: string,
    options: {
      pollIntervalMs?: number
      timeoutMs?: number
      signal?: AbortSignal
    } = {},
  ): Promise<BackgroundTask> {
    const pollIntervalMs = options.pollIntervalMs ?? 1_500
    const timeoutMs = options.timeoutMs ?? 900_000
    const startedAt = Date.now()

    while (true) {
      if (options.signal?.aborted) {
        throw new Error('后台任务等待已取消')
      }
      const task = await TaskAPI.getTask(taskId)
      if (task.status === 'succeeded') {
        return task
      }
      if (task.status === 'failed') {
        throw new Error(task.error || '后台任务执行失败')
      }
      if (Date.now() - startedAt >= timeoutMs) {
        throw new Error('后台任务等待超时，请在任务日志中查看后续结果')
      }
      await new Promise<void>((resolve) => {
        globalThis.setTimeout(resolve, pollIntervalMs)
      })
    }
  }
}
