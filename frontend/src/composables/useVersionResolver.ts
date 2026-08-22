import { computed, type ComputedRef } from 'vue'
import type { Chapter, ChapterVersion } from '@/api/novel'
import { cleanVersionContent } from '@/utils/chapter'
import { traceMetadata } from '@/utils/generationTrace'

interface UseVersionResolverOptions {
  /** 当前选中的章节（解析其展示正文的主体） */
  selectedChapter: ComputedRef<Chapter | null>
  /** 当前可用版本列表（正文兜底来源） */
  availableVersions: ComputedRef<ChapterVersion[]>
  /** 当前选中的版本索引（参与兜底顺序） */
  selectedVersionIndex: ComputedRef<number>
}

const asRecord = (value: unknown): Record<string, unknown> | null =>
  value !== null && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null

/**
 * 选中章节的版本正文解析。
 *
 * 从 WDWorkspace.vue 抽出（行为逐行等价）。按"直连 content → 推荐/选中版本 →
 * 兜底遍历全部版本"的顺序解析出应展示的正文，并派生展示用章节对象与"是否有正文"标志。
 * 纯 computed，无副作用。4 个 resolve 纯函数仅作内部实现，组件其他位置不直接调用。
 */
export const useVersionResolver = ({
  selectedChapter,
  availableVersions,
  selectedVersionIndex,
}: UseVersionResolverOptions) => {
  const toBoundedVersionIndex = (value: unknown): number | null => {
    const index = Number(value)
    if (!Number.isInteger(index) || index < 0 || index >= availableVersions.value.length) {
      return null
    }
    return index
  }

  const resolveRecommendedVersionIndex = (chapter: Chapter | null): number | null => {
    if (!chapter || availableVersions.value.length === 0) {
      return null
    }

    const metadataIndex = availableVersions.value.findIndex((version) => {
      const aiReview = asRecord(version.metadata?.ai_review)
      return aiReview?.is_best === true
    })
    if (metadataIndex >= 0) {
      return metadataIndex
    }

    for (const version of availableVersions.value) {
      const metadata = version.metadata
      const reviewSummaries = asRecord(metadata?.review_summaries)
      const summaryAiReview = asRecord(reviewSummaries?.ai_review)
      const aiReview = asRecord(metadata?.ai_review)
      const metadataBestIndex = toBoundedVersionIndex(
        summaryAiReview?.best_version_index ?? aiReview?.best_version_index,
      )
      if (metadataBestIndex !== null) {
        return metadataBestIndex
      }
    }

    const traces = [...(chapter.generation_traces ?? [])].reverse()
    for (const trace of traces) {
      if (trace.node_key !== 'save_draft') {
        continue
      }
      const metadata = traceMetadata(trace)
      const inputPayload = asRecord(metadata.input_payload)
      const metrics = asRecord(metadata.metrics)
      for (const candidate of [
        inputPayload?.recommended_version_index,
        metrics?.recommended_version_index,
        metadata.recommended_version_index,
        inputPayload?.best_version_index,
        metrics?.best_version_index,
      ]) {
        const traceIndex = toBoundedVersionIndex(candidate)
        if (traceIndex !== null) {
          return traceIndex
        }
      }
    }

    return null
  }

  const resolveVersionFallbackOrder = (chapter: Chapter | null): number[] => {
    const indices: number[] = []
    const pushIndex = (index: number | null) => {
      if (index !== null && !indices.includes(index)) {
        indices.push(index)
      }
    }

    const selectedIndex = toBoundedVersionIndex(selectedVersionIndex.value)
    const recommendedIndex = resolveRecommendedVersionIndex(chapter)
    // 待确认草稿初始索引常为 0；若 AI 明确推荐其他版本，正文兜底先展示推荐版本。
    if (chapter?.generation_status === 'waiting_for_confirm' && selectedVersionIndex.value === 0) {
      pushIndex(recommendedIndex)
    }
    pushIndex(selectedIndex)
    pushIndex(recommendedIndex)
    availableVersions.value.forEach((_, index) => pushIndex(index))
    return indices
  }

  const resolveChapterContent = (chapter: Chapter | null): string => {
    if (!chapter) {
      return ''
    }

    const directContent = cleanVersionContent(chapter?.content || '')
    if (directContent.trim()) {
      return directContent
    }

    for (const index of resolveVersionFallbackOrder(chapter)) {
      const version = availableVersions.value[index]
      const normalized = cleanVersionContent(version.content || '')
      if (normalized.trim()) {
        return normalized
      }
    }

    return ''
  }

  const selectedChapterResolvedContent = computed(() => resolveChapterContent(selectedChapter.value))

  const selectedChapterForDisplay = computed<Chapter | null>(() => {
    const chapter = selectedChapter.value
    if (!chapter) return null
    if (chapter.content && cleanVersionContent(chapter.content).trim()) {
      return chapter
    }
    return {
      ...chapter,
      content: selectedChapterResolvedContent.value,
    }
  })

  const hasSelectedChapterContent = computed(() => {
    return selectedChapterResolvedContent.value.trim().length > 0
  })

  return {
    selectedChapterResolvedContent,
    selectedChapterForDisplay,
    hasSelectedChapterContent,
  }
}
