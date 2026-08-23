// AIMETA P=创作上下文API客户端_跨设备语义恢复|R=上下文列表_字段级PATCH|NR=不含页面恢复策略|E=api:creation-contexts|X=internal|A=CreationContextAPI|D=fetch|S=net|RD=./README.ai
import { API_BASE_URL, API_PREFIX } from './base'
import { authJson } from './client'
import type { components } from './generated/schema'

export type CreationContext = components['schemas']['CreationContextRead']
export type CreationContextPatch = components['schemas']['CreationContextPatch']
export type CreationSurface = NonNullable<CreationContext['surface']>
export type WritingDeskSection = NonNullable<CreationContext['desk_section']>

const CREATION_CONTEXTS_BASE = `${API_BASE_URL}${API_PREFIX}/creation-contexts`

export class CreationContextAPI {
  static async getContexts(): Promise<CreationContext[]> {
    return authJson<CreationContext[]>(CREATION_CONTEXTS_BASE, {
      fallbackErrorMessage: '读取创作位置失败',
    })
  }

  static async patchContext(
    projectId: string,
    patch: CreationContextPatch,
  ): Promise<CreationContext> {
    return authJson<CreationContext>(`${CREATION_CONTEXTS_BASE}/${projectId}`, {
      method: 'PATCH',
      body: JSON.stringify(patch),
      fallbackErrorMessage: '同步创作位置失败',
    })
  }
}
