// AIMETA P=小说API客户端_小说和章节接口|R=小说CRUD_章节管理_生成|NR=不含UI逻辑|E=api:novel|X=internal|A=novelApi对象|D=axios|S=net|RD=./README.ai
import { useAuthStore } from '@/stores/auth'
import router from '@/router'
import { API_BASE_URL, API_PREFIX } from './base'
import { HttpRequestError, requestJson, requestRaw, type HttpRequestOptions } from './http'
import type { BackgroundTask } from './tasks'

const DEFAULT_NOVEL_REQUEST_TIMEOUT_MS = 60_000
const BLUEPRINT_GENERATION_TIMEOUT_MS = 480_000
const CHAPTER_GENERATION_TIMEOUT_MS = 660_000

// 统一的请求处理函数
const request = async <T = any>(url: string, options: HttpRequestOptions = {}) => {
  const authStore = useAuthStore()
  const headers = new Headers({
    'Content-Type': 'application/json',
    ...options.headers
  })

  // 如果 body 是 FormData，删除 Content-Type header，让浏览器自动设置（包含 boundary）
  if (options.body instanceof FormData) {
    headers.delete('Content-Type')
  }

  if (authStore.isAuthenticated && authStore.token) {
    headers.set('Authorization', `Bearer ${authStore.token}`)
  }

  try {
    return await requestJson<T>(url, {
      ...options,
      headers,
      timeoutMs: options.timeoutMs ?? DEFAULT_NOVEL_REQUEST_TIMEOUT_MS,
      fallbackErrorMessage: '小说接口请求失败',
    })
  } catch (error) {
    if (error instanceof HttpRequestError && error.status === 401) {
      // Token 失效或未授权
      authStore.logout()
      router.push('/login')
      throw new Error('会话已过期，请重新登录')
    }
    throw error
  }
}

const streamRequest = async (url: string, options: HttpRequestOptions = {}) => {
  const authStore = useAuthStore()
  const headers = new Headers({
    'Content-Type': 'application/json',
    ...options.headers
  })

  if (authStore.isAuthenticated && authStore.token) {
    headers.set('Authorization', `Bearer ${authStore.token}`)
  }

  try {
    const response = await requestRaw(url, {
      ...options,
      headers,
      timeoutMs: options.timeoutMs ?? DEFAULT_NOVEL_REQUEST_TIMEOUT_MS,
      fallbackErrorMessage: '流式请求失败',
    })

    if (!response.body) {
      throw new Error('浏览器不支持流式响应')
    }

    return response
  } catch (error) {
    if (error instanceof HttpRequestError && error.status === 401) {
      authStore.logout()
      router.push('/login')
      throw new Error('会话已过期，请重新登录')
    }
    throw error
  }
}

const parseSSEData = (rawData: string): unknown => {
  try {
    return JSON.parse(rawData)
  } catch {
    return rawData
  }
}

const parseSSEMessage = (message: string) => {
  let event = 'message'
  const dataLines: string[] = []

  for (const line of message.split(/\r?\n/)) {
    if (line.startsWith('event:')) {
      event = line.slice('event:'.length).trim()
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice('data:'.length).trimStart())
    }
  }

  if (!dataLines.length) {
    return null
  }

  return {
    event,
    data: parseSSEData(dataLines.join('\n')),
  }
}

const findSSEBoundary = (buffer: string): number => {
  const lfBoundary = buffer.indexOf('\n\n')
  const crlfBoundary = buffer.indexOf('\r\n\r\n')

  if (lfBoundary === -1) {
    return crlfBoundary
  }
  if (crlfBoundary === -1) {
    return lfBoundary
  }
  return Math.min(lfBoundary, crlfBoundary)
}

const getBoundaryLength = (buffer: string, startIndex: number) =>
  buffer.startsWith('\r\n\r\n', startIndex) ? 4 : 2

const getSSEErrorDetail = (payload: unknown): string => {
  if (typeof payload === 'string' && payload.trim()) {
    return payload.trim()
  }
  if (payload && typeof payload === 'object') {
    const detail = (payload as Record<string, unknown>).detail
    if (typeof detail === 'string' && detail.trim()) {
      return detail.trim()
    }
  }
  return '流式请求失败'
}

const readDelta = (payload: unknown): string => {
  if (payload && typeof payload === 'object') {
    const delta = (payload as Record<string, unknown>).delta
    if (typeof delta === 'string') {
      return delta
    }
  }
  return typeof payload === 'string' ? payload : ''
}

const readSSEStream = async <T>(
  response: Response,
  handlers: {
    onDelta?: (delta: string) => void
    onFinal: (payload: T) => void
  }
): Promise<T> => {
  const reader = response.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  const finishWithFinal = (payload: T): T => {
    handlers.onFinal(payload)
    // final 事件已经包含下一轮输入控件，立刻结束读取，避免等连接关闭才恢复交互。
    try {
      void reader.cancel().catch(() => undefined)
    } catch {
      // 读取器可能已自然关闭，忽略即可。
    }
    return payload
  }

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) {
        buffer += decoder.decode()
        break
      }

      buffer += decoder.decode(value, { stream: true })
      let boundaryIndex = findSSEBoundary(buffer)
      while (boundaryIndex >= 0) {
        const rawMessage = buffer.slice(0, boundaryIndex).trim()
        const boundaryLength = getBoundaryLength(buffer, boundaryIndex)
        buffer = buffer.slice(boundaryIndex + boundaryLength)

        if (rawMessage) {
          const message = parseSSEMessage(rawMessage)
          if (message?.event === 'delta') {
            handlers.onDelta?.(readDelta(message.data))
          } else if (message?.event === 'final') {
            return finishWithFinal(message.data as T)
          } else if (message?.event === 'error') {
            throw new Error(getSSEErrorDetail(message.data))
          }
        }

        boundaryIndex = findSSEBoundary(buffer)
      }
    }

    const trailingMessage = buffer.trim()
    if (trailingMessage) {
      const message = parseSSEMessage(trailingMessage)
      if (message?.event === 'final') {
        return finishWithFinal(message.data as T)
      } else if (message?.event === 'error') {
        throw new Error(getSSEErrorDetail(message.data))
      }
    }

    throw new Error('流式请求未返回最终结果')
  } finally {
    reader.releaseLock()
  }
}

// 类型定义
export interface NovelProject {
  id: string
  title: string
  initial_prompt: string
  blueprint?: Blueprint
  chapters: Chapter[]
  conversation_history: ConversationMessage[]
}

export interface NovelProjectSummary {
  id: string
  title: string
  genre: string
  last_edited: string
  completed_chapters: number
  total_chapters: number
}

export interface Blueprint {
  title?: string
  target_audience?: string
  genre?: string
  style?: string
  tone?: string
  one_sentence_summary?: string
  full_synopsis?: string
  world_setting?: any
  characters?: Character[]
  relationships?: any[]
  chapter_outline?: ChapterOutline[]
}

export interface Character {
  name: string
  description: string
  identity?: string
  personality?: string
  goals?: string
  abilities?: string
  relationship_to_protagonist?: string
}

export interface ChapterOutline {
  chapter_number: number
  title: string
  summary: string
}

export interface ChapterVersion {
  content: string
  style?: string
}

export interface Chapter {
  chapter_number: number
  title: string
  summary: string
  real_summary?: string | null
  content: string | null
  versions: string[] | null  // versions是字符串数组，不是对象数组
  evaluation: string | null
  generation_status: 'not_generated' | 'generating' | 'evaluating' | 'selecting' | 'failed' | 'evaluation_failed' | 'waiting_for_confirm' | 'successful'
  generation_progress?: number | null
  generation_step?: string | null
  generation_step_index?: number | null
  generation_step_total?: number | null
  generation_started_at?: string | null
  status_updated_at?: string | null
  word_count?: number  // 字数统计
}

export interface ConversationMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface ConverseResponse {
  ai_message: string
  ui_control: UIControl
  conversation_state: any
  is_complete: boolean
  ready_for_blueprint?: boolean  // 新增：表示准备生成蓝图
}

export interface BlueprintGenerationResponse {
  blueprint: Blueprint
  ai_message: string
}

export interface UIControl {
  type: 'single_choice' | 'text_input'
  options?: Array<{ id: string; label: string }>
  placeholder?: string
}

export interface ChapterGenerationResponse {
  versions: ChapterVersion[] // Renamed from chapter_versions for consistency
  evaluation: string | null
  ai_message: string
  chapter_number: number
}

export interface DeleteNovelsResponse {
  status: string
  message: string
}

export interface EmotionPoint {
  chapter_number: number
  title: string
  emotion_type: string
  intensity: number
  narrative_phase?: string
  description: string
}

export interface EmotionCurveResponse {
  project_id: string
  project_title: string
  total_chapters: number
  emotion_points: EmotionPoint[]
  average_intensity: number
  emotion_distribution: Record<string, number>
}

export interface Foreshadowing {
  id: string
  description: string
  planted_chapter: number
  planted_chapter_title: string
  expected_payoff_chapter?: number
  actual_payoff_chapter?: number
  status: 'planted' | 'paid_off' | 'overdue'
  importance: 'short' | 'medium' | 'long'
}

export interface ForeshadowingResponse {
  project_id: string
  project_title: string
  total_foreshadowings: number
  planted_count: number
  paid_off_count: number
  overdue_count: number
  foreshadowings: Foreshadowing[]
}

export interface ForeshadowingDbItem {
  id: number | string
  chapter_number: number
  content?: string
  type?: string
  status?: string
  resolved_chapter_number?: number | null
  author_note?: string | null
}

export interface ForeshadowingDbListResponse {
  total: number
  data: ForeshadowingDbItem[]
}

// 内容型Section（对应后端NovelSectionType枚举）
export type NovelSectionType = 'overview' | 'world_setting' | 'characters' | 'relationships' | 'chapter_outline' | 'chapters'

// 分析型Section（不属于NovelSectionType，使用独立的analytics API）
export type AnalysisSectionType = 'emotion_curve' | 'foreshadowing'

// 所有Section的联合类型
export type AllSectionType = NovelSectionType | AnalysisSectionType

export interface NovelSectionResponse {
  section: NovelSectionType
  data: Record<string, any>
}

// API 函数
const NOVELS_BASE = `${API_BASE_URL}${API_PREFIX}/novels`
const WRITER_PREFIX = '/api/writer'
const WRITER_BASE = `${API_BASE_URL}${WRITER_PREFIX}/novels`
const ANALYTICS_BASE = `${API_BASE_URL}${API_PREFIX}/analytics`

export class NovelAPI {
  static async createNovel(title: string, initialPrompt: string): Promise<NovelProject> {
    return request(NOVELS_BASE, {
      method: 'POST',
      body: JSON.stringify({ title, initial_prompt: initialPrompt })
    })
  }

  static async importNovel(file: File): Promise<{ id: string }> {
    const formData = new FormData()
    formData.append('file', file)
    return request(`${NOVELS_BASE}/import`, {
      method: 'POST',
      body: formData,
      headers: {
        // 让 browser 自动设置 Content-Type 为 multipart/form-data，不手动设置
      }
    })
  }

  static async getNovel(projectId: string): Promise<NovelProject> {
    return request(`${NOVELS_BASE}/${projectId}`)
  }

  static async getChapter(projectId: string, chapterNumber: number): Promise<Chapter> {
    return request(`${NOVELS_BASE}/${projectId}/chapters/${chapterNumber}`)
  }

  static async getSection(projectId: string, section: NovelSectionType): Promise<NovelSectionResponse> {
    return request(`${NOVELS_BASE}/${projectId}/sections/${section}`)
  }

  static async converseConcept(
    projectId: string,
    userInput: any,
    conversationState: any = {}
  ): Promise<ConverseResponse> {
    const formattedUserInput = userInput || { id: null, value: null }
    return request(`${NOVELS_BASE}/${projectId}/concept/converse`, {
      method: 'POST',
      body: JSON.stringify({
        user_input: formattedUserInput,
        conversation_state: conversationState
      })
    })
  }

  static async converseConceptStream(
    projectId: string,
    userInput: any,
    conversationState: any = {},
    onDelta?: (delta: string) => void
  ): Promise<ConverseResponse> {
    const formattedUserInput = userInput || { id: null, value: null }
    const response = await streamRequest(`${NOVELS_BASE}/${projectId}/concept/converse/stream`, {
      method: 'POST',
      body: JSON.stringify({
        user_input: formattedUserInput,
        conversation_state: conversationState
      })
    })

    return readSSEStream<ConverseResponse>(response, {
      onDelta,
      onFinal: () => {},
    })
  }

  static async generateBlueprint(projectId: string): Promise<BlueprintGenerationResponse> {
    return request(`${NOVELS_BASE}/${projectId}/blueprint/generate`, {
      method: 'POST',
      timeoutMs: BLUEPRINT_GENERATION_TIMEOUT_MS,
    })
  }

  static async saveBlueprint(projectId: string, blueprint: Blueprint): Promise<NovelProject> {
    return request(`${NOVELS_BASE}/${projectId}/blueprint/save`, {
      method: 'POST',
      body: JSON.stringify(blueprint)
    })
  }

  static async generateChapter(projectId: string, chapterNumber: number): Promise<NovelProject> {
    return request(`${WRITER_BASE}/${projectId}/chapters/generate`, {
      method: 'POST',
      body: JSON.stringify({ chapter_number: chapterNumber }),
      timeoutMs: CHAPTER_GENERATION_TIMEOUT_MS,
    })
  }

  static async evaluateChapter(projectId: string, chapterNumber: number): Promise<NovelProject> {
    return request(`${WRITER_BASE}/${projectId}/chapters/evaluate`, {
      method: 'POST',
      body: JSON.stringify({ chapter_number: chapterNumber })
    })
  }

  static async selectChapterVersion(
    projectId: string,
    chapterNumber: number,
    versionIndex: number
  ): Promise<NovelProject> {
    return request(`${WRITER_BASE}/${projectId}/chapters/select`, {
      method: 'POST',
      body: JSON.stringify({
        chapter_number: chapterNumber,
        version_index: versionIndex
      })
    })
  }

  static async getAllNovels(): Promise<NovelProjectSummary[]> {
    return request(NOVELS_BASE)
  }

  static async deleteNovels(projectIds: string[]): Promise<DeleteNovelsResponse> {
    return request(NOVELS_BASE, {
      method: 'DELETE',
      body: JSON.stringify(projectIds)
    })
  }

  static async updateChapterOutline(
    projectId: string,
    chapterOutline: ChapterOutline
  ): Promise<NovelProject> {
    return request(`${WRITER_BASE}/${projectId}/chapters/update-outline`, {
      method: 'POST',
      body: JSON.stringify(chapterOutline)
    })
  }

  static async deleteChapter(
    projectId: string,
    chapterNumbers: number[]
  ): Promise<NovelProject> {
    return request(`${WRITER_BASE}/${projectId}/chapters/delete`, {
      method: 'POST',
      body: JSON.stringify({ chapter_numbers: chapterNumbers })
    })
  }

  static async generateChapterOutline(
    projectId: string,
    startChapter: number,
    numChapters: number
  ): Promise<BackgroundTask> {
    return request(`${WRITER_BASE}/${projectId}/chapters/outline`, {
      method: 'POST',
      body: JSON.stringify({
        start_chapter: startChapter,
        num_chapters: numChapters
      })
    })
  }

  static async updateBlueprint(projectId: string, data: Record<string, any>): Promise<NovelProject> {
    return request(`${NOVELS_BASE}/${projectId}/blueprint`, {
      method: 'PATCH',
      body: JSON.stringify(data)
    })
  }

  static async editChapterContent(
    projectId: string,
    chapterNumber: number,
    content: string
  ): Promise<Chapter> {
    return request(`${WRITER_BASE}/${projectId}/chapters/edit-fast`, {
      method: 'POST',
      body: JSON.stringify({
        chapter_number: chapterNumber,
        content: content
      })
    })
  }

  static async getEmotionCurve(projectId: string): Promise<EmotionCurveResponse> {
    return request(`${ANALYTICS_BASE}/${projectId}/emotion-curve`)
  }

  static async analyzeEmotionAI(projectId: string): Promise<EmotionCurveResponse> {
    return request(`${ANALYTICS_BASE}/${projectId}/analyze-emotion-ai`, {
      method: 'POST'
    })
  }

  static async getForeshadowings(projectId: string): Promise<ForeshadowingDbListResponse> {
    return request(`${NOVELS_BASE}/${projectId}/foreshadowings?limit=500`)
  }

  static async getForeshadowingAnalytics(projectId: string): Promise<ForeshadowingResponse> {
    return request(`${ANALYTICS_BASE}/${projectId}/foreshadowing`)
  }
}


// 优化相关类型定义
export interface EmotionBeat {
  primary_emotion: string
  intensity: number
  curve: {
    start: number
    peak: number
    end: number
  }
  turning_point: string
}

export interface OptimizeRequest {
  project_id: string
  chapter_number: number
  dimension: 'dialogue' | 'environment' | 'psychology' | 'rhythm'
  additional_notes?: string
}

export interface OptimizeRecommendedVersionRequest {
  project_id: string
  chapter_number: number
  source_content: string
  review_summary: string
  version_number?: number
  version_review?: Record<string, unknown>
}

export interface OptimizeResponse {
  optimized_content: string
  optimization_notes: string
  dimension: string
}

export interface ForeshadowingSyncStats {
  created: number
  revealed: number
  developing: number
}

export interface ApplyOptimizationResponse {
  status: string
  message: string
  foreshadowing_sync?: ForeshadowingSyncStats
}

// 优化API
const OPTIMIZER_BASE = `${API_BASE_URL}${API_PREFIX}/optimizer`

export class OptimizerAPI {
  /**
   * 对章节内容进行分层优化
   */
  static async optimizeChapter(optimizeReq: OptimizeRequest): Promise<OptimizeResponse> {
    return request(`${OPTIMIZER_BASE}/optimize`, {
      method: 'POST',
      body: JSON.stringify(optimizeReq)
    })
  }

  /**
   * 根据 AI 评审建议优化推荐版本
   */
  static async optimizeRecommendedVersion(optimizeReq: OptimizeRecommendedVersionRequest): Promise<OptimizeResponse> {
    return request(`${OPTIMIZER_BASE}/optimize-recommended-version`, {
      method: 'POST',
      body: JSON.stringify(optimizeReq)
    })
  }

  /**
   * 应用优化后的内容到章节
   */
  static async applyOptimization(
    projectId: string,
    chapterNumber: number,
    optimizedContent: string
  ): Promise<ApplyOptimizationResponse> {
    return request(`${OPTIMIZER_BASE}/apply-optimization`, {
      method: 'POST',
      body: JSON.stringify({
        project_id: projectId,
        chapter_number: chapterNumber,
        optimized_content: optimizedContent
      })
    })
  }
}
