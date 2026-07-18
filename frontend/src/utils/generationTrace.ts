/**
 * 章节生成 trace 解析与格式化工具。
 *
 * 从 ChapterGenerating.vue 拆出（#22 ChapterGenerating Slice 1）：纯函数 + 常量 + 类型，
 * 零响应式依赖。组件保留 activeStepTraces / activeTrace / activeStepDetails 等 computed，
 * 调用此处函数组装展示数据。
 */
import type { ChapterGenerationTrace } from '@/api/novel'
import { cleanVersionContent } from '@/utils/chapter'

export type StepDetail = {
  summary: string
  inputs: string
  outputs: string
  next: string
}

export type ParsedStepPayload = {
  raw: string
  baseKey: string
  meta: Record<string, string>
}

export type TraceMetadata = Record<string, any>

export type ActiveStepDetails = {
  label: string
  summary: string
  callType: string
  llmUsage: string
  status: string
  systemDuration: string
  inputs: string
  actions: string
  outputs: string
}

export const PIPELINE_LABELS: Record<string, string> = {
  context_prep: '整理前文',
  director_mission: '规划剧情',
  rag_retrieval: '调用设定',
  draft_generation: '生成正文',
  quality_review: 'AI评审',
  review_refinement: '修复润色',
  auto_optimizing: '修复润色',
  persist_versions: '保存草稿',
  save_draft: '保存草稿',
  waiting_for_confirm: '等待确认',
  selecting_version: '等待确认',
  confirm_finalize: '确认定稿',
  real_summary: '生成章节梳理',
  finalize_memory: '更新记忆快照',
  chapter_ingest: '写入章节索引',
  foreshadowing_sync: '同步伏笔',
  finalized: '定稿完成',
  finalization_error: '定稿失败',
}

export const TRACE_CALL_TYPE_LABELS: Record<string, string> = {
  database_context: '数据库读取',
  database_write: '数据库写入',
  rag_retrieval: 'RAG 检索',
  chat_llm: '聊天模型',
  embedding: '向量模型',
  preview_generation: '预览生成',
  version_review: '版本评审',
  chapter_optimization: '修复润色',
  confirm_finalize: '确认定稿',
  real_summary: '章节梳理',
  finalize_memory: '记忆快照',
  chapter_ingest: '章节索引',
  foreshadowing_sync: '伏笔同步',
  finalized: '定稿完成',
  finalization_error: '定稿失败',
}

export const TRACE_STATUS_LABELS: Record<string, string> = {
  success: '成功',
  failed: '失败',
}

export const STEP_DETAILS: Record<string, StepDetail> = {
  context_prep: {
    summary: '整理前文重点剧情、角色状态和本章任务。',
    inputs: '上章摘要 + 本章标题与摘要',
    outputs: '本章上下文草案',
    next: '规划剧情',
  },
  director_mission: {
    summary: '明确本章冲突、节奏和人物推进目标。',
    inputs: '章节任务 + 蓝图角色关系',
    outputs: '章节创作方案',
    next: '调用设定',
  },
  rag_retrieval: {
    summary: '检索与本章相关的设定、伏笔和历史片段。',
    inputs: '章节任务关键词',
    outputs: '可引用上下文',
    next: '生成正文',
  },
  draft_generation: {
    summary: '根据任务、前文、人物状态与伏笔生成第一版正文。',
    inputs: '章节方案 + 相关设定',
    outputs: '章节草稿版本',
    next: 'AI评审',
  },
  quality_review: {
    summary: '单版本生成修改意见，多版本对比选优并生成修改建议。',
    inputs: '候选正文版本',
    outputs: '评审结果与修改建议',
    next: '修复润色',
  },
  review_refinement: {
    summary: '根据 AI 评审建议自动修复润色推荐版本。',
    inputs: '推荐版本 + AI 修改建议',
    outputs: '修复润色后的最终正文',
    next: '人工编辑或确认定稿',
  },
  persist_versions: {
    summary: '将修复润色后的草稿写入版本库，进入人工确认节点。',
    inputs: '候选版本 + 推荐索引',
    outputs: '待人工确认状态',
    next: '人工确认定稿',
  },
  save_draft: {
    summary: 'AI 产出已结束，当前可人工编辑草稿或确认定稿。',
    inputs: '修复润色后的正文 + 推荐索引',
    outputs: '待人工确认状态',
    next: '人工编辑或确认定稿',
  },
  waiting_for_confirm: {
    summary: '草稿保存完成，等待你确认定稿。',
    inputs: '新草稿版本',
    outputs: '待确认状态',
    next: '确认后进入同步定稿',
  },
  confirm_finalize: {
    summary: '确认最终草稿并锁定本次定稿正文。',
    inputs: '候选版本 + 手动修改正文',
    outputs: '最终正文与选中版本',
    next: '生成章节梳理',
  },
  real_summary: {
    summary: '基于最终正文生成真实章节梳理。',
    inputs: '最终正文',
    outputs: 'Chapter.real_summary',
    next: '更新记忆',
  },
  finalize_memory: {
    summary: '更新全局摘要、角色状态、剧情线和章节快照。',
    inputs: '最终正文 + 当前项目记忆',
    outputs: '项目记忆与章节快照',
    next: '写入索引',
  },
  chapter_ingest: {
    summary: '写入章节向量索引，供后续检索使用。',
    inputs: '最终正文 + 章节梳理',
    outputs: '章节检索索引',
    next: '同步伏笔',
  },
  foreshadowing_sync: {
    summary: '抽取新伏笔并判断历史伏笔推进或回收。',
    inputs: '最终正文 + 历史活跃伏笔',
    outputs: '伏笔表与状态历史',
    next: '定稿完成',
  },
  finalized: {
    summary: '所有后处理完成，章节进入已完成状态。',
    inputs: '后处理统计',
    outputs: 'successful',
    next: '进入正文查看',
  },
  finalization_error: {
    summary: '定稿后处理失败，章节保留草稿待确认。',
    inputs: '失败节点上下文',
    outputs: '错误详情',
    next: '修改后重试',
  },
}

export const parseStepPayload = (rawStep?: string | null): ParsedStepPayload => {
  const raw = (rawStep ?? '').trim()
  if (!raw) {
    return { raw: '', baseKey: '', meta: {} }
  }
  const tokens = raw.split('|').map((item) => item.trim()).filter(Boolean)
  const baseKey = tokens[0] ?? raw
  const meta: Record<string, string> = {}
  for (const token of tokens.slice(1)) {
    const delimiter = token.indexOf('=')
    if (delimiter <= 0) continue
    const key = token.slice(0, delimiter).trim()
    const value = token.slice(delimiter + 1).trim()
    if (key && value) {
      meta[key] = value
    }
  }
  return { raw, baseKey, meta }
}

export const parseBackendTimestampToMs = (raw?: string | null): number | null => {
  if (!raw) return null
  const normalized = raw.trim()
  if (!normalized) return null
  const hasExplicitTimezone = /([zZ]|[+\-]\d{2}:\d{2})$/.test(normalized)
  const isoCandidate = normalized.includes('T') ? normalized : normalized.replace(' ', 'T')
  const parseTarget = hasExplicitTimezone ? isoCandidate : `${isoCandidate}+08:00`
  const ts = Date.parse(parseTarget)
  return Number.isFinite(ts) ? ts : null
}

export const normalizePipelineStepKey = (key?: string | null) => {
  const normalized = (key || '').trim()
  if (normalized === 'persist_versions') return 'save_draft'
  if (normalized === 'evaluation_failed' || normalized === 'evaluating') return 'quality_review'
  if (normalized === 'auto_optimizing') return 'review_refinement'
  if (normalized === 'optimization_done') return 'review_refinement'
  if (normalized === 'failed') return ''
  return normalized
}

export const isPlainTraceObject = (value: unknown): value is TraceMetadata => {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

export const traceMetadata = (trace: ChapterGenerationTrace): TraceMetadata => {
  return isPlainTraceObject(trace.metadata) ? trace.metadata : {}
}

export const resolveTraceDurationMs = (trace: ChapterGenerationTrace): number | null => {
  if (typeof trace.duration_ms === 'number' && Number.isFinite(trace.duration_ms)) {
    return Math.max(0, Math.round(trace.duration_ms))
  }
  const metadata = traceMetadata(trace)
  if (typeof metadata.duration_ms === 'number' && Number.isFinite(metadata.duration_ms)) {
    return Math.max(0, Math.round(metadata.duration_ms))
  }
  const startedAt = parseBackendTimestampToMs(trace.started_at)
  const endedAt = parseBackendTimestampToMs(trace.ended_at)
  if (startedAt === null || endedAt === null) {
    return null
  }
  return Math.max(0, endedAt - startedAt)
}

export const formatSystemDuration = (durationMs: number | null): string => {
  if (durationMs === null) {
    return '未记录'
  }
  if (durationMs < 1000) {
    return `${durationMs} ms`
  }
  if (durationMs < 60_000) {
    const seconds = durationMs / 1000
    const display = Number.isInteger(seconds) ? String(seconds) : seconds.toFixed(1)
    return `${display} 秒`
  }
  const totalSeconds = Math.round(durationMs / 1000)
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${minutes} 分 ${String(seconds).padStart(2, '0')} 秒`
}

export const traceUsesLlm = (trace: ChapterGenerationTrace): boolean => {
  if (trace.uses_llm === true || trace.uses_llm === false) {
    return trace.uses_llm
  }
  const metadata = traceMetadata(trace)
  if (metadata.uses_llm === true || metadata.uses_llm === false) {
    return metadata.uses_llm
  }
  if (Array.isArray(metadata.model_calls)) {
    return metadata.model_calls.length > 0
  }
  return Boolean(trace.system_prompt?.trim() || trace.user_prompt?.trim() || trace.raw_response?.trim())
}

export const formatTraceValue = (value: unknown): string => {
  if (value === null || value === undefined || value === '') return '无'
  if (typeof value === 'string') return value
  return JSON.stringify(value, null, 2)
}

export const formatTracePayload = (payload: unknown, emptyText: string): string => {
  if (!isPlainTraceObject(payload)) {
    return payload ? formatTraceValue(payload) : emptyText
  }
  const lines = Object.entries(payload)
    .map(([key, value]) => `${key}：${formatTraceValue(value)}`)
    .filter(Boolean)
  return lines.length ? lines.join('\n\n') : emptyText
}

export const firstTextValue = (...values: unknown[]): string => {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) {
      return value.trim()
    }
  }
  return ''
}

export const toDisplayVersionNumber = (value: unknown): number | null => {
  const index = Number(value)
  if (!Number.isInteger(index) || index < 0) {
    return null
  }
  return index + 1
}

export const getTraceOutputPayload = (trace: ChapterGenerationTrace): TraceMetadata | null => {
  const payload = traceMetadata(trace).output_payload
  return isPlainTraceObject(payload) ? payload : null
}

export const getTraceOutputText = (trace: ChapterGenerationTrace, ...payloadKeys: string[]): string => {
  const payload = getTraceOutputPayload(trace)
  const payloadValues = payloadKeys.map((key) => payload?.[key])
  const rawText = firstTextValue(trace.cleaned_output, ...payloadValues, trace.raw_response)
  return cleanVersionContent(rawText).trim()
}

export const formatDraftGenerationOutputs = (trace: ChapterGenerationTrace) => {
  const text = getTraceOutputText(trace, 'full_chapter', 'content', 'chapter_content')
  return text ? `AI生成正文：\n${text}` : '该节点未记录 AI 生成正文。'
}

export const formatAiReviewOutputs = (trace: ChapterGenerationTrace) => {
  const payload = getTraceOutputPayload(trace)
  const summaries = payload?.review_summaries
  const aiReview = isPlainTraceObject(summaries) && isPlainTraceObject(summaries.ai_review)
    ? summaries.ai_review
    : null
  const lines: string[] = []
  const bestVersionNumber = toDisplayVersionNumber(
    payload?.best_version_index ?? aiReview?.best_version_index,
  )

  if (bestVersionNumber !== null) {
    lines.push(`推荐版本：版本 ${bestVersionNumber}`)
  }

  if (aiReview) {
    const versionReviews = Array.isArray(aiReview.version_reviews) ? aiReview.version_reviews : []
    const bestVersionReview = bestVersionNumber === null
      ? null
      : versionReviews.find((item) =>
          isPlainTraceObject(item) && Number(item.version_number) === bestVersionNumber,
        )
    const evaluation = firstTextValue(
      isPlainTraceObject(bestVersionReview) ? bestVersionReview.overall_review : null,
      aiReview.evaluation,
      aiReview.overall_evaluation,
      aiReview.reason_for_choice,
    )
    const suggestions = firstTextValue(
      aiReview.suggestions,
      aiReview.refinement_suggestions,
    )
    const recommendation = aiReview.mode === 'compare' && bestVersionNumber !== null
      ? `采用版本 ${bestVersionNumber}`
      : firstTextValue(aiReview.final_recommendation)
    if (evaluation) lines.push(`评审结论：${evaluation}`)
    if (suggestions) lines.push(`修改建议：${suggestions}`)
    if (recommendation) lines.push(`最终建议：${recommendation}`)

    const flaws = Array.isArray(aiReview.flaws) ? aiReview.flaws : []
    if (flaws.length) {
      lines.push(`需修复问题：\n${flaws.map((item) => `- ${formatTraceValue(item)}`).join('\n')}`)
    }

    if (versionReviews.length) {
      const reviews = versionReviews
        .map((item) => {
          if (!isPlainTraceObject(item)) return ''
          const versionNumber = Number(item.version_number)
          const title = Number.isInteger(versionNumber) && versionNumber > 0
            ? `版本 ${versionNumber}`
            : '候选版本'
          const review = firstTextValue(item.overall_review)
          return review ? `${title}：${review}` : ''
        })
        .filter(Boolean)
      if (reviews.length) {
        lines.push(`分版本评审：\n${reviews.join('\n')}`)
      }
    }
  }

  if (lines.length) {
    return lines.join('\n\n')
  }

  if (payload) {
    return `评审结论：\n${formatTracePayload(payload, '该节点未记录评审结论。')}`
  }
  return '该节点未记录评审结论。'
}

export const formatReviewRefinementOutputs = (trace: ChapterGenerationTrace) => {
  const text = getTraceOutputText(trace, 'optimized_content', 'refined_content', 'final_content')
  const payload = getTraceOutputPayload(trace)
  const lines = text ? [`AI修复后正文：\n${text}`] : ['该节点未记录 AI 修复后正文。']
  const notes = firstTextValue(payload?.optimization_notes, payload?.notes)
  if (notes) {
    lines.push(`修复说明：${notes}`)
  }
  return lines.join('\n\n')
}

export const formatManualConfirmationOutputs = (trace: ChapterGenerationTrace) => {
  const payload = getTraceOutputPayload(trace)
  const status = firstTextValue(payload?.status) || 'waiting_for_confirm'
  const lines = [
    `人工确认状态：${status}`,
    '此节点不再产生 AI 正文；你可以人工编辑草稿，或确认定稿。',
  ]
  const versions = Array.isArray(payload?.versions) ? payload.versions : []
  if (versions.length) {
    lines.push(`已保存候选版本：${versions.length} 个`)
  }
  return lines.join('\n\n')
}

export const formatModelCall = (call: unknown, index: number): string => {
  if (!isPlainTraceObject(call)) {
    return `模型调用 ${index + 1}：${formatTraceValue(call)}`
  }
  const callType = TRACE_CALL_TYPE_LABELS[String(call.call_type || '')] || call.call_type || '模型调用'
  const pieces = [
    `${call.purpose || call.reason || `模型调用 ${index + 1}`}`,
    `类型：${callType}`,
  ]
  if (call.stage) pieces.push(`stage：${call.stage}`)
  if (call.status) pieces.push(`状态：${call.status}`)
  if (call.temperature !== undefined) pieces.push(`temperature：${call.temperature}`)
  if (call.timeout_seconds !== undefined) pieces.push(`超时：${call.timeout_seconds}s`)
  if (call.max_tokens !== undefined) pieces.push(`max_tokens：${call.max_tokens}`)
  return pieces.join('；')
}

export const formatTraceInputs = (trace: ChapterGenerationTrace) => {
  const metadata = traceMetadata(trace)
  const sections: string[] = []
  if (metadata.input_payload !== undefined) {
    sections.push(formatTracePayload(metadata.input_payload, '该节点未记录输入材料。'))
  }
  if (trace.system_prompt?.trim()) {
    sections.push(`模型系统指令：\n${trace.system_prompt.trim()}`)
  }
  if (trace.user_prompt?.trim()) {
    sections.push(`模型用户输入：\n${trace.user_prompt.trim()}`)
  }
  return sections.length ? sections.join('\n\n') : '该节点未记录输入材料。'
}

export const formatTraceActions = (trace: ChapterGenerationTrace) => {
  const metadata = traceMetadata(trace)
  const lines: string[] = []
  const actions = Array.isArray(metadata.actions) ? metadata.actions : []
  actions.forEach((action: unknown) => {
    lines.push(`- ${formatTraceValue(action)}`)
  })
  const modelCalls = Array.isArray(metadata.model_calls) ? metadata.model_calls : []
  if (modelCalls.length) {
    lines.push('', '模型/向量调用：')
    modelCalls.forEach((call: unknown, index: number) => {
      lines.push(`- ${formatModelCall(call, index)}`)
    })
  } else if (traceUsesLlm(trace)) {
    lines.push('', '模型/向量调用：已调用，但本条记录未保存模型明细。')
  } else {
    lines.push('', '模型/向量调用：无')
  }
  const dataReads = Array.isArray(metadata.data_reads) ? metadata.data_reads : []
  if (dataReads.length) {
    lines.push('', '读取数据：')
    dataReads.forEach((item: unknown) => lines.push(`- ${formatTraceValue(item)}`))
  }
  const dataWrites = Array.isArray(metadata.data_writes) ? metadata.data_writes : []
  if (dataWrites.length) {
    lines.push('', '写入数据：')
    dataWrites.forEach((item: unknown) => lines.push(`- ${formatTraceValue(item)}`))
  }
  if (metadata.skip_reason) {
    lines.push('', `跳过说明：${formatTraceValue(metadata.skip_reason)}`)
  }
  if (metadata.metrics) {
    lines.push('', `运行指标：\n${formatTraceValue(metadata.metrics)}`)
  }
  return lines.length ? lines.join('\n') : '该节点未记录具体动作。'
}

export const formatTraceOutputs = (trace: ChapterGenerationTrace) => {
  const metadata = traceMetadata(trace)
  const sections: string[] = []
  if (trace.error?.trim()) {
    sections.push(`错误：\n${trace.error.trim()}`)
  }
  const normalizedNodeKey = normalizePipelineStepKey(trace.node_key)
  if (!sections.length) {
    if (normalizedNodeKey === 'draft_generation') {
      return formatDraftGenerationOutputs(trace)
    }
    if (normalizedNodeKey === 'quality_review') {
      return formatAiReviewOutputs(trace)
    }
    if (normalizedNodeKey === 'review_refinement') {
      return formatReviewRefinementOutputs(trace)
    }
    if (normalizedNodeKey === 'save_draft') {
      return formatManualConfirmationOutputs(trace)
    }
  }
  if (metadata.output_payload !== undefined) {
    sections.push(formatTracePayload(metadata.output_payload, '该节点未记录产出结果。'))
  }
  if (trace.raw_response?.trim()) {
    sections.push(`模型原始返回：\n${trace.raw_response.trim()}`)
  }
  if (trace.cleaned_output?.trim()) {
    sections.push(`清洗后输出：\n${trace.cleaned_output.trim()}`)
  }
  return sections.length ? sections.join('\n\n') : '该节点未记录产出结果。'
}

export const resolveTraceCallType = (trace: ChapterGenerationTrace) => {
  const metadata = traceMetadata(trace)
  const callType = String(metadata.call_type || '')
  if (callType) return TRACE_CALL_TYPE_LABELS[callType] || callType
  if (traceUsesLlm(trace)) return '聊天模型'
  return '运行节点'
}
