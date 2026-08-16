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

export type PipelineStepKind = 'execution' | 'system' | 'control' | 'terminal'
export type PipelineRetryCommand = 'retry' | 'retry_external' | 'retry_projection'

export type PipelineStep = {
  key: string
  label: string
  kind?: PipelineStepKind
  group?: string
  groupLabel?: string
  groupMode?: 'serial' | 'parallel'
  optional?: boolean
  retryCommand?: PipelineRetryCommand
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
  freeze_base_context: '冻结基础上下文',
  retrieve_context: '检索章节上下文',
  plan_chapter: '规划章节任务',
  generate_candidate_1: '候选版本 1',
  generate_candidate_2: '候选版本 2',
  review_candidates: '评审候选版本',
  refine_candidate: '润色推荐版本',
  enhance_content: '增强正文',
  repair_consistency: '修复一致性',
  optimize_style: '优化文风',
  enrich_content: '扩写正文',
  compress_candidate: '压缩超长正文',
  persist_drafts: '保存候选草稿',
  wait_for_selection: '等待选择版本',
  finalize_revision: '定稿章节版本',
  generate_summary: '生成章节梳理',
  commit_summary_projection: '保存章节梳理',
  memory_global_summary: '更新全局剧情记忆',
  memory_character_state: '更新角色状态记忆',
  memory_plot_arcs: '更新剧情线记忆',
  memory_chapter_summary: '更新章节记忆摘要',
  commit_memory_projection: '写入章节记忆',
  project_rag: '生成章节索引向量',
  commit_rag_projection: '写入章节索引',
  foreshadowing_candidate_review: '筛选新增伏笔',
  foreshadowing_status_judge: '判断伏笔状态',
  commit_foreshadowing_projection: '写入伏笔同步结果',
  wait_for_projections: '等待投影完成',
  reconcile_projections: '汇合投影结果',
  successful: '章节工作流完成',
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
  running: '进行中',
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
  freeze_base_context: {
    summary: '校验并引用本轮启动时冻结的基础上下文。',
    inputs: '章节身份 + 基础上下文 hash',
    outputs: '基础上下文引用',
    next: '检索章节上下文',
  },
  retrieve_context: {
    summary: '按冻结配置检索设定、历史片段和相关伏笔。',
    inputs: '基础上下文 + 检索配置',
    outputs: '检索快照引用',
    next: '规划章节任务',
  },
  plan_chapter: {
    summary: '形成本章冲突、节奏和人物推进方案。',
    inputs: '检索上下文 + 章节大纲',
    outputs: '章节任务方案',
    next: '并行生成候选版本',
  },
  generate_candidate_1: {
    summary: '生成第一个独立候选正文。',
    inputs: '章节任务方案 + 上下文',
    outputs: '候选正文 1',
    next: '等待候选汇合后进入评审',
  },
  generate_candidate_2: {
    summary: '按配置生成第二个独立候选正文。',
    inputs: '章节任务方案 + 上下文',
    outputs: '候选正文 2',
    next: '等待候选汇合后进入评审',
  },
  review_candidates: {
    summary: '跨候选比较并给出推荐版本和修改意见。',
    inputs: '候选正文集合',
    outputs: '评审报告 + 推荐版本',
    next: '润色推荐版本',
  },
  refine_candidate: {
    summary: '根据评审意见生成推荐版本的润色正文。',
    inputs: '推荐正文 + 评审报告',
    outputs: '润色正文',
    next: '执行已启用的正文处理',
  },
  enhance_content: {
    summary: '按增强配置继续改善正文表现。',
    inputs: '上一阶段正文',
    outputs: '增强后的正文',
    next: '一致性修复',
  },
  repair_consistency: {
    summary: '修复人物、情节和设定的一致性问题。',
    inputs: '上一阶段正文 + 评审报告',
    outputs: '一致性修订正文',
    next: '优化文风',
  },
  optimize_style: {
    summary: '按当前写作配置优化语言和节奏。',
    inputs: '上一阶段正文',
    outputs: '文风优化正文',
    next: '扩写正文',
  },
  enrich_content: {
    summary: '在不改变章节目标的前提下补充正文细节。',
    inputs: '上一阶段正文',
    outputs: '扩写正文',
    next: '保存候选草稿',
  },
  compress_candidate: {
    summary: '推荐正文超过冻结字数上限时删减冗余内容。',
    inputs: '最终修订正文 + 冻结字数合同',
    outputs: '满足字数上限的推荐正文',
    next: '保存候选草稿',
  },
  persist_drafts: {
    summary: '事务写入候选版本、推荐结果和评审元数据。',
    inputs: '候选与修订引用',
    outputs: '候选版本 ID',
    next: '等待选择版本',
  },
  wait_for_selection: {
    summary: '候选草稿已保存，等待人工选择定稿版本。',
    inputs: '候选版本 ID',
    outputs: '人工选择命令',
    next: '定稿章节版本',
  },
  finalize_revision: {
    summary: '原子写入正式 revision、outbox 和投影派发身份。',
    inputs: '选中版本',
    outputs: '正式章节 revision',
    next: '生成定稿投影',
  },
  generate_summary: {
    summary: '基于正式正文生成章节梳理。',
    inputs: '正式正文',
    outputs: '章节真实梳理',
    next: '并行派发下游投影',
  },
  commit_summary_projection: {
    summary: '保存章节梳理并派发后续投影。',
    inputs: '章节梳理结果',
    outputs: '已保存的章节梳理',
    next: '并行派发下游投影',
  },
  memory_global_summary: {
    summary: '调用模型更新全局剧情记忆。',
    inputs: '正式正文 + 原全局记忆',
    outputs: '新的全局剧情记忆',
    next: '继续更新记忆',
  },
  memory_character_state: {
    summary: '调用模型更新角色状态记忆。',
    inputs: '正式正文 + 原角色状态',
    outputs: '新的角色状态记忆',
    next: '继续更新记忆',
  },
  memory_plot_arcs: {
    summary: '调用模型更新剧情线记忆。',
    inputs: '正式正文 + 原剧情线',
    outputs: '新的剧情线记忆',
    next: '继续更新记忆',
  },
  memory_chapter_summary: {
    summary: '调用模型生成供记忆快照使用的章节摘要。',
    inputs: '正式正文 + 章节梳理',
    outputs: '章节记忆摘要',
    next: '写入章节记忆',
  },
  commit_memory_projection: {
    summary: '将已经生成的记忆结果写入本地存储。',
    inputs: '各项记忆调用结果',
    outputs: '记忆投影',
    next: '等待投影汇合',
  },
  project_rag: {
    summary: '调用向量模型生成章节索引向量。',
    inputs: '正式正文 + 章节梳理',
    outputs: '章节分块与摘要向量',
    next: '写入章节索引',
  },
  commit_rag_projection: {
    summary: '将已经生成的向量写入章节索引。',
    inputs: '章节分块与摘要向量',
    outputs: '检索索引或跳过原因',
    next: '等待投影汇合',
  },
  foreshadowing_candidate_review: {
    summary: '有新增伏笔候选时，调用模型筛选有效候选。',
    inputs: '规则候选 + 正文片段',
    outputs: '新增伏笔候选',
    next: '判断伏笔状态',
  },
  foreshadowing_status_judge: {
    summary: '有活跃历史伏笔时，调用模型判断其最新状态。',
    inputs: '正式正文 + 活跃伏笔',
    outputs: '伏笔状态判断',
    next: '写入伏笔同步结果',
  },
  commit_foreshadowing_projection: {
    summary: '将规则计算与模型判断结果写入伏笔记录。',
    inputs: '伏笔计算结果',
    outputs: '伏笔投影',
    next: '等待投影汇合',
  },
  wait_for_projections: {
    summary: '等待本轮要求的定稿投影全部完成。',
    inputs: '目标 revision + 投影任务',
    outputs: '投影完成信号',
    next: '汇合投影结果',
  },
  reconcile_projections: {
    summary: '校验投影来源、revision、generation 和任务身份。',
    inputs: '全部必需投影结果',
    outputs: '投影汇合结论',
    next: '章节工作流完成',
  },
  successful: {
    summary: '生成、选择、定稿和必需投影均已完成。',
    inputs: '工作流终态',
    outputs: 'successful',
    next: '进入正文查看',
  },
}

export const resolvePipelineStepKey = (
  key: string | null | undefined,
  pipelineSteps: readonly PipelineStep[],
) => {
  const raw = (key || '').trim()
  if (!raw) return ''
  if (pipelineSteps.some((item) => item.key === raw)) return raw
  return ''
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
  return (key || '').trim()
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
    if (normalizedNodeKey === 'generate_candidate_1' || normalizedNodeKey === 'generate_candidate_2') {
      return formatDraftGenerationOutputs(trace)
    }
    if (normalizedNodeKey === 'review_candidates') {
      return formatAiReviewOutputs(trace)
    }
    if (
      normalizedNodeKey === 'refine_candidate'
      || normalizedNodeKey === 'enhance_content'
      || normalizedNodeKey === 'repair_consistency'
      || normalizedNodeKey === 'optimize_style'
      || normalizedNodeKey === 'enrich_content'
      || normalizedNodeKey === 'compress_candidate'
    ) {
      return formatReviewRefinementOutputs(trace)
    }
    if (normalizedNodeKey === 'persist_drafts' || normalizedNodeKey === 'wait_for_selection') {
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
