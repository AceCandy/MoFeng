/**
 * 墨风（MoFeng）小说章节与文本处理工具模块
 * 
 * 本模块专注于处理章节版本转换、智能JSON解析、文本正则清洗与字数统计，
 * 以确保复杂的前端文本匹配与版本优化行为高效稳定运行。
 */

/**
 * 章节版本内容安全提取
 */
export function extractVersionContent(raw: unknown): string {
  if (typeof raw !== 'string') {
    return ''
  }
  const trimmed = raw.trim()
  if (!trimmed) {
    return ''
  }

  const likelyJson =
    (trimmed.startsWith('{') && trimmed.endsWith('}')) ||
    (trimmed.startsWith('[') && trimmed.endsWith(']'))
  if (!likelyJson) {
    return raw
  }

  try {
    const parsed = JSON.parse(trimmed)
    if (parsed && typeof parsed === 'object') {
      const record = parsed as Record<string, unknown>
      for (const key of ['content', 'chapter_content', 'chapter_text', 'text', 'body', 'story']) {
        const candidate = record[key]
        if (typeof candidate === 'string' && candidate.trim()) {
          return candidate
        }
      }
    }
  } catch {
    // 忽略解析错误，回退到原始文本
  }
  return raw
}

/**
 * 清理并规范化章节内容，剥离结构化载荷中的 JSON 嵌套
 */
export function cleanVersionContent(content: string): string {
  if (!content) return ''

  // 尝试解析JSON，看是否是完整的章节对象
  try {
    const parsed = tryParseOptimizerPayload(content) ?? JSON.parse(content)
    const extractContent = (value: unknown, depth = 0): string | null => {
      if (!value || depth > 3) return null
      if (typeof value === 'string') {
        const nestedPayload = tryParseOptimizerPayload(value)
        return nestedPayload ? (extractContent(nestedPayload, depth + 1) ?? value) : value
      }
      if (Array.isArray(value)) {
        for (const item of value) {
          const nested = extractContent(item, depth + 1)
          if (nested) return nested
        }
        return null
      }
      if (typeof value === 'object') {
        const record = value as Record<string, unknown>
        for (const key of [
          'content',
          'optimized_content',
          'revised_content',
          'chapter_content',
          'chapter_text',
          'text',
          'body',
          'story',
        ]) {
          if (record[key]) {
            const nested = extractContent(record[key], depth + 1)
            if (nested) return nested
          }
        }
      }
      return null
    }
    const extracted = extractContent(parsed)
    if (extracted) {
      // 如果是章节对象/数组，提取正文
      content = extracted
    }
  } catch {
    // 普通正文保持原样
  }

  return content
}

/**
 * 智能解析优化器返回的 Markdown 围栏或纯 JSON 负载
 */
export function tryParseOptimizerPayload(rawText: string): Record<string, unknown> | null {
  return parseOptimizerPayload(rawText, 0)
}

function parseOptimizerPayload(rawText: string, depth: number): Record<string, unknown> | null {
  if (depth > 3) return null
  if (!rawText) return null
  const text = rawText.trim()
  if (!text) return null

  const candidates: string[] = [text]
  const fenceMatch = text.match(/```(?:json|JSON)?\s*([\s\S]*?)\s*```/)
  if (fenceMatch?.[1]) {
    const fenced = fenceMatch[1].trim()
    if (fenced && fenced !== text) candidates.unshift(fenced)
  }
  const escapedFenceMatch = text.match(
    /^```(?:json|JSON)?(?:\\r)?\\n([\s\S]*?)(?:\\r)?\\n```$/,
  )
  if (escapedFenceMatch) {
    try {
      const decoded = JSON.parse(`"${text}"`)
      if (typeof decoded === 'string') {
        const nested = parseOptimizerPayload(decoded, depth + 1)
        if (nested) return nested
      }
    } catch {
      // 忽略无效的转义围栏
    }
  }

  for (const candidate of candidates) {
    try {
      const parsed = JSON.parse(candidate)
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
        return parsed as Record<string, unknown>
      }
      if (typeof parsed === 'string' && parsed !== candidate) {
        const nested = parseOptimizerPayload(parsed, depth + 1)
        if (nested) return nested
      }
    } catch {
      // 忽略
    }
  }
  return null
}

/**
 * JSON 特殊字符反转义
 */
export function decodeJsonStringFragment(fragment: string): string {
  try {
    return JSON.parse(`"${fragment}"`) as string
  } catch {
    return fragment.replace(/\\"/g, '"').replace(/\\n/g, '\n').replace(/\\t/g, '\t')
  }
}

/**
 * 正则提取 JSON 指定字段值
 */
export function extractJsonField(
  rawText: string,
  field: 'optimized_content' | 'optimization_notes',
): string | null {
  const pattern = new RegExp(`"${field}"\\s*:\\s*"((?:\\\\.|[^"\\\\])*)"`, 's')
  const match = rawText.match(pattern)
  if (!match?.[1]) return null
  return decodeJsonStringFragment(match[1])
}

/**
 * 归一化评审优化结果
 */
export function normalizeOptimizeResult(
  contentRaw: string,
  notesRaw: string,
): { content: string; notes: string } {
  let content = (contentRaw || '').trim()
  let notes = (notesRaw || '').trim()
  const seen = new Set<string>()

  for (let i = 0; i < 2; i++) {
    if (!content || seen.has(content)) break
    seen.add(content)
    const payload = tryParseOptimizerPayload(content)
    if (!payload) break
    const nestedContent = payload.optimized_content
    if (typeof nestedContent !== 'string' || !nestedContent.trim()) break
    content = nestedContent.trim()
    if (!notes && typeof payload.optimization_notes === 'string') {
      notes = payload.optimization_notes.trim()
    }
  }

  if (content.includes('"optimized_content"')) {
    const extractedContent = extractJsonField(content, 'optimized_content')
    if (extractedContent?.trim()) {
      content = extractedContent.trim()
    }
    if (!notes) {
      const extractedNotes = extractJsonField(contentRaw, 'optimization_notes')
      if (extractedNotes?.trim()) {
        notes = extractedNotes.trim()
      }
    }
  }

  const fenced = content.match(/```(?:json|JSON)?\s*([\s\S]*?)\s*```/)
  if (fenced?.[1]) {
    content = fenced[1].trim()
  }

  return {
    content,
    notes: notes || '优化完成',
  }
}

const CHAPTER_GENERATION_ERROR_FALLBACK = '未收到具体错误信息，请查看后端日志或稍后重试。'

/**
 * 生成失败弹窗只展示真实原因，避免把“生成章节失败”前缀重复拼接。
 */
export function formatChapterGenerationError(error: unknown): string {
  const rawMessage =
    error instanceof Error
      ? error.message
      : typeof error === 'string'
        ? error
        : ''
  let message = rawMessage.trim()

  if (!message) {
    return CHAPTER_GENERATION_ERROR_FALLBACK
  }

  message = message.replace(/^生成章节失败[：:]\s*生成章节失败[，,]?\s*/u, '生成章节失败，')

  const specificReason = message.match(/^(?:生成章节(?:第\s*\d+\s*个版本)?失败)[：:]\s*(.+)$/u)?.[1]?.trim()
  if (specificReason) {
    return specificReason
  }

  return message
}

/**
 * 解析评估报告负载
 */
export function parseEvaluationPayload(evaluation: string | null): Record<string, unknown> | null {
  if (!evaluation) return null
  try {
    let data: unknown = JSON.parse(evaluation)
    if (typeof data === 'string') {
      data = JSON.parse(data)
    }
    if (data && typeof data === 'object' && !Array.isArray(data)) {
      return data as Record<string, unknown>
    }
  } catch (error) {
    console.error('解析评审结果失败:', error)
  }
  return null
}

type ChapterOutlineLike = {
  chapter_number: number
}

type ChapterStatusLike = {
  chapter_number: number
  generation_status?: string | null
}

const sortByChapterNumber = <T extends ChapterOutlineLike>(items: T[]): T[] => {
  return [...items]
    .filter((item) => Number.isFinite(item.chapter_number))
    .sort((left, right) => left.chapter_number - right.chapter_number)
}

const buildChapterSequence = (
  outlines: ChapterOutlineLike[] = [],
  chapters: ChapterStatusLike[] = [],
): ChapterOutlineLike[] => {
  if (outlines.length > 0) {
    return sortByChapterNumber(outlines)
  }
  return sortByChapterNumber(chapters)
}

export const isChapterCompletedStatus = (chapter?: ChapterStatusLike | null): boolean => {
  return chapter?.generation_status === 'successful'
}

/**
 * 最近未完成章节定义为按章节号排序后的第一个非 successful 章节。
 */
export function findNearestIncompleteChapterNumber(
  outlines: ChapterOutlineLike[] = [],
  chapters: ChapterStatusLike[] = [],
): number | null {
  const sequence = buildChapterSequence(outlines, chapters)
  if (sequence.length === 0) return null

  const chapterByNumber = new Map<number, ChapterStatusLike>()
  for (const chapter of chapters) {
    chapterByNumber.set(chapter.chapter_number, chapter)
  }

  const target = sequence.find((outline) => {
    const chapter = chapterByNumber.get(outline.chapter_number)
    return !isChapterCompletedStatus(chapter)
  })

  return target?.chapter_number ?? null
}

export function resolveChapterNumberForEntry(options: {
  outlines?: ChapterOutlineLike[]
  chapters?: ChapterStatusLike[]
  preferredChapterNumber?: number | null
}): number | null {
  const sequence = buildChapterSequence(options.outlines ?? [], options.chapters ?? [])
  if (sequence.length === 0) return null

  if (
    options.preferredChapterNumber !== null &&
    options.preferredChapterNumber !== undefined &&
    Number.isFinite(options.preferredChapterNumber) &&
    sequence.some((chapter) => chapter.chapter_number === options.preferredChapterNumber)
  ) {
    return options.preferredChapterNumber
  }

  const nearestIncomplete = findNearestIncompleteChapterNumber(
    options.outlines ?? [],
    options.chapters ?? [],
  )
  if (nearestIncomplete !== null) {
    return nearestIncomplete
  }

  return sequence[sequence.length - 1].chapter_number
}

export function resolveChapterNumberForProjectEntry(options: {
  projectId?: string | null
  previousProjectId?: string | null
  currentChapterNumber?: number | null
  outlines?: ChapterOutlineLike[]
  chapters?: ChapterStatusLike[]
  preferredChapterNumber?: number | null
}): number | null {
  const outlines = options.outlines ?? []
  const chapters = options.chapters ?? []
  const sequence = buildChapterSequence(outlines, chapters)
  if (sequence.length === 0) return null

  const hasChapterNumber = (chapterNumber: number | null | undefined) =>
    chapterNumber !== null &&
    chapterNumber !== undefined &&
    Number.isFinite(chapterNumber) &&
    sequence.some((chapter) => chapter.chapter_number === chapterNumber)

  if (hasChapterNumber(options.preferredChapterNumber)) {
    return options.preferredChapterNumber ?? null
  }

  const isSameProject =
    Boolean(options.projectId) &&
    Boolean(options.previousProjectId) &&
    options.projectId === options.previousProjectId

  if (isSameProject && hasChapterNumber(options.currentChapterNumber)) {
    return options.currentChapterNumber ?? null
  }

  return resolveChapterNumberForEntry({
    outlines,
    chapters,
    preferredChapterNumber: options.preferredChapterNumber,
  })
}
