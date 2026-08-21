// AIMETA P=管理员API客户端_管理接口调用|R=用户管理_系统配置_统计|NR=不含UI逻辑|E=api:admin|X=internal|A=adminApi对象|D=fetch|S=net|RD=./README.ai
import type {
  Chapter as NovelChapter,
  NovelProject as NovelProjectContract,
  NovelProjectSummary as NovelProjectSummaryContract,
  NovelSectionResponse,
  NovelSectionType,
} from '@/api/novel'
import { authJson } from './client'
import { API_BASE_URL } from './base'
import type { components } from './generated/schema'
export { API_BASE_URL } from './base'

// API 配置
export const ADMIN_API_PREFIX = '/api/admin'

// 类型定义
export type Statistics = components['schemas']['Statistics']
export type AdminUser = components['schemas']['User']
export type UserCreatePayload = components['schemas']['UserCreateAdmin']
export type UserUpdatePayload = components['schemas']['UserUpdateAdmin']
export type NovelProjectSummary = NovelProjectSummaryContract
export type AdminNovelSummary = components['schemas']['AdminNovelSummary']
export type Chapter = NovelChapter
export type NovelProject = NovelProjectContract
export type PromptItem = components['schemas']['PromptRead']
export type PromptCreatePayload = components['schemas']['PromptCreate']
export type PromptUpdatePayload = components['schemas']['PromptUpdate']
export type UpdateLog = components['schemas']['UpdateLogRead']
export type UpdateLogPayload = components['schemas']['UpdateLogUpdate']
export type SystemConfig = components['schemas']['SystemConfigRead']
export type SystemConfigUpsertPayload = Omit<components['schemas']['SystemConfigCreate'], 'key'>
export type SystemConfigUpdatePayload = components['schemas']['SystemConfigUpdate']

export class AdminAPI {
  private static request<T = unknown>(path: string, options: RequestInit = {}) {
    return authJson<T>(`${API_BASE_URL}${ADMIN_API_PREFIX}${path}`, {
      ...options,
      timeoutMs: 20_000,
      fallbackErrorMessage: '管理接口请求失败',
    })
  }

  // Overview
  static getStatistics(): Promise<Statistics> {
    return this.request('/stats')
  }

  // Users
  static listUsers(): Promise<AdminUser[]> {
    return this.request('/users')
  }

  static createUser(payload: UserCreatePayload): Promise<AdminUser> {
    return this.request('/users', {
      method: 'POST',
      body: JSON.stringify(payload)
    })
  }

  static getUser(id: number): Promise<AdminUser> {
    return this.request(`/users/${id}`)
  }

  static updateUser(id: number, payload: UserUpdatePayload): Promise<AdminUser> {
    return this.request(`/users/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload)
    })
  }

  static deleteUser(id: number): Promise<void> {
    return this.request(`/users/${id}`, {
      method: 'DELETE'
    })
  }

  // Novels
  static listNovels(): Promise<AdminNovelSummary[]> {
    return this.request('/novel-projects')
  }

  static getNovelDetails(projectId: string): Promise<NovelProject> {
    return this.request(`/novel-projects/${projectId}`)
  }

  static getNovelSection(projectId: string, section: NovelSectionType): Promise<NovelSectionResponse> {
    return this.request(`/novel-projects/${projectId}/sections/${section}`)
  }

  static getNovelChapter(projectId: string, chapterNumber: number): Promise<Chapter> {
    return this.request(`/novel-projects/${projectId}/chapters/${chapterNumber}`)
  }

  // Prompts
  static listPrompts(): Promise<PromptItem[]> {
    return this.request('/prompts')
  }

  static createPrompt(payload: PromptCreatePayload): Promise<PromptItem> {
    return this.request('/prompts', {
      method: 'POST',
      body: JSON.stringify(payload)
    })
  }

  static getPrompt(id: number): Promise<PromptItem> {
    return this.request(`/prompts/${id}`)
  }

  static updatePrompt(id: number, payload: PromptUpdatePayload): Promise<PromptItem> {
    return this.request(`/prompts/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload)
    })
  }

  static deletePrompt(id: number): Promise<void> {
    return this.request(`/prompts/${id}`, {
      method: 'DELETE'
    })
  }

  // Update logs
  static listUpdateLogs(): Promise<UpdateLog[]> {
    return this.request('/update-logs')
  }

  static createUpdateLog(payload: UpdateLogPayload & { content: string }): Promise<UpdateLog> {
    return this.request('/update-logs', {
      method: 'POST',
      body: JSON.stringify(payload)
    })
  }

  static updateUpdateLog(id: number, payload: UpdateLogPayload): Promise<UpdateLog> {
    return this.request(`/update-logs/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload)
    })
  }

  static deleteUpdateLog(id: number): Promise<void> {
    return this.request(`/update-logs/${id}`, {
      method: 'DELETE'
    })
  }

  // Settings
  static listSystemConfigs(): Promise<SystemConfig[]> {
    return this.request('/system-configs')
  }

  static upsertSystemConfig(key: string, payload: SystemConfigUpsertPayload): Promise<SystemConfig> {
    return this.request(`/system-configs/${key}`, {
      method: 'PUT',
      body: JSON.stringify({ key, ...payload })
    })
  }

  static patchSystemConfig(key: string, payload: SystemConfigUpdatePayload): Promise<SystemConfig> {
    return this.request(`/system-configs/${key}`, {
      method: 'PATCH',
      body: JSON.stringify(payload)
    })
  }

  static deleteSystemConfig(key: string): Promise<void> {
    return this.request(`/system-configs/${key}`, {
      method: 'DELETE'
    })
  }

  static changePassword(oldPassword: string, newPassword: string): Promise<void> {
    return this.request('/password', {
      method: 'POST',
      body: JSON.stringify({
        old_password: oldPassword,
        new_password: newPassword
      })
    })
  }
}
