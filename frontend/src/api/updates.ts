// AIMETA P=更新API客户端_更新日志接口|R=更新日志查询|NR=不含UI逻辑|E=api:updates|X=internal|A=updatesApi对象|D=axios|S=net|RD=./README.ai
import { API_BASE_URL } from './base'
import { requestJson } from './http'

// A simplified request function for public endpoints that don't require authentication.
const publicRequest = <T>(url: string, options: RequestInit = {}) =>
  requestJson<T>(url, {
    ...options,
    timeoutMs: 15_000,
    fallbackErrorMessage: '更新日志请求失败',
  })

export interface UpdateLog {
  id: number
  content: string
  created_at: string
}

export const getLatestUpdates = (): Promise<UpdateLog[]> => {
  return publicRequest<UpdateLog[]>(`${API_BASE_URL}/api/updates/latest`)
}
