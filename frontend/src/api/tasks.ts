// AIMETA P=后台任务API客户端_任务列表和日志|R=查询任务_查询任务详情|NR=不含业务任务提交|E=api:tasks|X=internal|A=TaskAPI|D=fetch|S=net|RD=./README.ai
import { useAuthStore } from '@/stores/auth'
import { API_BASE_URL, API_PREFIX } from './base'
import { HttpRequestError, requestJson, type HttpRequestOptions } from './http'

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

const TASKS_BASE = `${API_BASE_URL}${API_PREFIX}/tasks`

const request = async <T = unknown>(url: string, options: HttpRequestOptions = {}) => {
  const authStore = useAuthStore()
  const headers = new Headers({
    'Content-Type': 'application/json',
    ...options.headers,
  })

  if (authStore.isAuthenticated && authStore.token) {
    headers.set('Authorization', `Bearer ${authStore.token}`)
  }

  try {
    return await requestJson<T>(url, {
      ...options,
      headers,
      timeoutMs: options.timeoutMs ?? 15_000,
      fallbackErrorMessage: '后台任务接口请求失败',
    })
  } catch (error) {
    if (error instanceof HttpRequestError && error.status === 401) {
      authStore.logout()
      throw new Error('会话已过期，请重新登录')
    }
    throw error
  }
}

export class TaskAPI {
  static async getTasks(limit = 20): Promise<BackgroundTask[]> {
    return request(`${TASKS_BASE}?limit=${limit}`)
  }

  static async getTask(taskId: string): Promise<BackgroundTask> {
    return request(`${TASKS_BASE}/${taskId}`)
  }
}
