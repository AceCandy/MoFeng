// AIMETA P=后台任务API客户端_任务列表和日志|R=查询任务_查询任务详情|NR=不含业务任务提交|E=api:tasks|X=internal|A=TaskAPI|D=fetch|S=net|RD=./README.ai
import { API_BASE_URL, API_PREFIX } from './base'
import { authJson } from './client'
import { type HttpRequestOptions } from './http'
import { readSSESubscription, streamRequest } from './novel'

export type BackgroundTaskStatus = 'queued' | 'running' | 'succeeded' | 'failed'

export interface BackgroundTaskLogEntry {
  timestamp: string
  level: 'info' | 'warning' | 'error' | string
  message: string
}

export interface BackgroundTask {
  id: string
  user_id: number
  project_id?: string | null
  stream_type?: string | null
  stream_id?: string | null
  task_type: string
  title: string
  status: BackgroundTaskStatus
  progress: number
  payload?: Record<string, unknown> | null
  result?: Record<string, unknown> | null
  error?: string | null
  log_entries: BackgroundTaskLogEntry[]
  created_at: string
  updated_at: string
  started_at?: string | null
  completed_at?: string | null
}

export interface BackgroundTaskSnapshot {
  tasks: BackgroundTask[]
  snapshot_revision: string
  resume_cursor: number
  stream_type?: string | null
  stream_id?: string | null
}

export interface BackgroundTaskEvent {
  cursor: number
  event_type: string
  task: BackgroundTask
}

export interface BackgroundTaskCursorReset {
  reason: 'cursor_expired'
  retained_through_cursor: number
}

export interface BackgroundTaskStreamScope {
  stream_type: 'job' | 'workflow'
  stream_id: string
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
    return request(`${TASKS_BASE}/snapshot?${params.toString()}`)
  }

  static async subscribeTasks(
    handlers: {
      onSnapshot: (snapshot: BackgroundTaskSnapshot) => void
      onTask: (event: BackgroundTaskEvent) => void
      onReset: (reset: BackgroundTaskCursorReset) => void
      onError?: (error: Error) => void
      signal?: AbortSignal
      limit?: number
      cursor?: number | null
      scope?: BackgroundTaskStreamScope
    }
  ): Promise<'reset'> {
    const params = new URLSearchParams({ limit: String(handlers.limit ?? 20) })
    if (handlers.cursor != null) {
      params.set('cursor', String(handlers.cursor))
    }
    appendStreamScope(params, handlers.scope)
    const response = await streamRequest(`${TASKS_BASE}/events?${params.toString()}`, {
      method: 'GET',
      signal: handlers.signal,
      timeoutMs: 600_000,
      headers:
        handlers.cursor == null
          ? undefined
          : { 'Last-Event-ID': String(handlers.cursor) },
    })
    let resetReceived = false
    await readSSESubscription(response, {
      onMessage: (message) => {
        if (message.event === 'snapshot') {
          handlers.onSnapshot(message.data as BackgroundTaskSnapshot)
        } else if (message.event === 'task') {
          handlers.onTask(message.data as BackgroundTaskEvent)
        } else if (message.event === 'reset') {
          resetReceived = true
          handlers.onReset(message.data as BackgroundTaskCursorReset)
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
