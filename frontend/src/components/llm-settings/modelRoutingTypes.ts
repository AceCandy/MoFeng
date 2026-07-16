import type { ProviderType } from '@/api/llm'

/**
 * 模型路由配置的公共类型。从 PersonalModelRouting.vue 抽出（Slice 1），
 * 供主组件与后续 composable/子组件共用。
 */

/** 模型能力：文本生成 / 记忆检索 / 语音朗读 */
export type Capability = 'chat' | 'embedding' | 'tts'

/** 路由分区：对应乾坤万象中枢的四个 tab */
export type RoutingSection = 'llm' | 'embedding' | 'tts' | 'routes'

/** 供应商表单模式：新建 / 编辑 / 关闭 */
export type ProviderFormMode = 'create' | 'edit' | null

/** 配置就绪摘要的语义色调 */
export type ReadinessTone = 'success' | 'warning' | 'neutral'

/** 单个创作阶段定义 */
export interface StageDefinition {
  key: string
  label: string
  capability: Capability
  description: string
}

/** 创作阶段分组（用于阶段路由分区展示） */
export interface StageGroup {
  title: string
  stages: StageDefinition[]
}

/** 供应商新建/编辑表单数据 */
export interface ProviderForm {
  name: string
  provider_type: ProviderType
  base_url: string
  api_key: string
  is_enabled: boolean
}

/** 单个供应商的模型拉取状态（按能力缓存） */
export interface ProviderFetchState {
  isLoading: boolean
  modelsByCapability: Record<Capability, string[]>
  error: string
}

/** 分区配置就绪摘要（readiness 展示） */
export interface ReadinessSummary {
  label: string
  value: string
  description: string
  tone: ReadinessTone
}
