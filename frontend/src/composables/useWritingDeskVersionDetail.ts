import { computed, ref, watch, type ComputedRef, type Ref } from 'vue'
import type { Chapter, ChapterGenerationResponse, ChapterVersion } from '@/api/novel'
import { cleanVersionContent, parseEvaluationPayload } from '@/utils/chapter'
import { traceMetadata } from '@/utils/generationTrace'

interface UseWritingDeskVersionDetailOptions {
  selectedChapter: ComputedRef<Chapter | null>
  chapterGenerationResult: Ref<ChapterGenerationResponse | null>
  selectedVersionIndex: Ref<number>
  /** 版本详情弹窗组件懒加载 loader（父侧 defineAsyncComponent 同源） */
  loadWDVersionDetailModal: () => Promise<unknown>
}

/**
 * 写作台版本提取与版本详情操作。
 *
 * 从 WritingDesk.vue 抽出（行为逐行等价）。内聚版本内容/元数据提取、可用版本
 * 计算（availableVersions）、推荐版本解析（resolveRecommendedVersionIndex）、
 * 等待确认态的自动选版（syncRecommendedVersionSelection + watch）、版本详情
 * 弹窗操作与隐藏版本选择器。extractVersionContent 本地多 object 分支与
 * @/utils/chapter 仅 string 版本不等价，故保留本地实现。章节定稿
 * （confirmVersionSelection）消费本 composable 返回的 availableVersions 与
 * resolveRecommendedVersionIndex，待其自身收敛后另行抽出。
 */
export const useWritingDeskVersionDetail = ({
  selectedChapter,
  chapterGenerationResult,
  selectedVersionIndex,
  loadWDVersionDetailModal,
}: UseWritingDeskVersionDetailOptions) => {
  const showVersionDetailModal = ref(false)
  const detailVersionIndex = ref<number>(0)
  const lastAutoRecommendedSelectionKey = ref<string | null>(null)

  const extractVersionContent = (raw: unknown): string => {
    if (raw && typeof raw === 'object' && !Array.isArray(raw)) {
      const record = raw as Record<string, unknown>
      for (const key of ['content', 'chapter_content', 'chapter_text', 'text', 'body', 'story']) {
        const candidate = record[key]
        if (typeof candidate === 'string' && candidate.trim()) {
          return candidate
        }
      }
    }

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
      // ignore parse errors, fallback to raw text
    }
    return raw
  }

  const extractVersionMetadata = (raw: unknown): Record<string, any> | null => {
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
      return null
    }
    const metadata = (raw as Record<string, unknown>).metadata
    return metadata && typeof metadata === 'object' && !Array.isArray(metadata)
      ? (metadata as Record<string, any>)
      : null
  }

  // 可用版本列表（来源优先级：生成结果 > 章节 versions > 章节 content 兜底）
  const availableVersions = computed<ChapterVersion[]>(() => {
    if (
      Array.isArray(chapterGenerationResult.value?.versions) &&
      chapterGenerationResult.value.versions.length > 0
    ) {
      return chapterGenerationResult.value.versions.filter((item) => Boolean(item?.content?.trim()))
    }

    const chapter = selectedChapter.value
    if (!chapter) {
      return []
    }

    if (Array.isArray(chapter.versions) && chapter.versions.length > 0) {
      const converted = chapter.versions
        .map((versionRaw) => {
          const content = extractVersionContent(versionRaw)
          if (!content.trim()) {
            return null
          }
          return {
            content,
            style: '标准',
            metadata: extractVersionMetadata(versionRaw),
          } as ChapterVersion
        })
        .filter((item): item is ChapterVersion => item !== null)
      if (converted.length > 0) {
        return converted
      }
    }

    if (typeof chapter.content === 'string' && chapter.content.trim()) {
      return [{ content: chapter.content, style: '标准' }]
    }

    return []
  })

  const isCurrentVersion = (versionIndex: number) => {
    if (!selectedChapter.value?.content || !availableVersions.value?.[versionIndex]?.content)
      return false

    // 使用cleanVersionContent函数清理内容进行比较
    const cleanCurrentContent = cleanVersionContent(selectedChapter.value.content)
    const cleanVersionContentStr = cleanVersionContent(availableVersions.value[versionIndex].content)

    return cleanCurrentContent === cleanVersionContentStr
  }

  const toBoundedVersionIndex = (value: unknown, versionCount: number): number | null => {
    const index = Number(value)
    if (!Number.isInteger(index) || index < 0 || index >= versionCount) {
      return null
    }
    return index
  }

  const resolveRecommendedVersionIndex = (
    chapter: Chapter | null,
    versions: ChapterVersion[],
  ): number | null => {
    if (!versions.length) {
      return null
    }

    const metadataIndex = versions.findIndex((version) => {
      const metadata = version.metadata
      return metadata?.ai_review?.is_best === true
    })
    if (metadataIndex >= 0) {
      return metadataIndex
    }

    for (const version of versions) {
      const metadata = version.metadata
      const metadataBestIndex = toBoundedVersionIndex(
        metadata?.review_summaries?.ai_review?.best_version_index ??
          metadata?.ai_review?.best_version_index,
        versions.length,
      )
      if (metadataBestIndex !== null) {
        return metadataBestIndex
      }
    }

    const evaluationPayload = parseEvaluationPayload(chapter?.evaluation || null)
    const bestChoiceIndex = toBoundedVersionIndex(
      Number(evaluationPayload?.best_choice) - 1,
      versions.length,
    )
    if (bestChoiceIndex !== null) {
      return bestChoiceIndex
    }

    const traces = [...(chapter?.generation_traces ?? [])].reverse()
    for (const trace of traces) {
      if (trace.node_key !== 'save_draft') {
        continue
      }
      const metadata = traceMetadata(trace)
      for (const candidate of [
        metadata.input_payload?.recommended_version_index,
        metadata.metrics?.recommended_version_index,
        metadata.recommended_version_index,
        metadata.input_payload?.best_version_index,
        metadata.metrics?.best_version_index,
      ]) {
        const traceIndex = toBoundedVersionIndex(candidate, versions.length)
        if (traceIndex !== null) {
          return traceIndex
        }
      }
    }

    return null
  }

  const syncRecommendedVersionSelection = () => {
    const chapter = selectedChapter.value
    const versions = availableVersions.value
    if (!chapter || chapter.generation_status !== 'waiting_for_confirm' || versions.length === 0) {
      lastAutoRecommendedSelectionKey.value = null
      return
    }

    const recommendedIndex = resolveRecommendedVersionIndex(chapter, versions)
    if (recommendedIndex === null) {
      return
    }

    const selectionKey = [
      chapter.chapter_number,
      chapter.status_updated_at ?? '',
      chapter.generation_traces?.length ?? 0,
      versions.length,
      recommendedIndex,
    ].join(':')

    if (lastAutoRecommendedSelectionKey.value === selectionKey) {
      return
    }

    selectedVersionIndex.value = recommendedIndex
    lastAutoRecommendedSelectionKey.value = selectionKey
  }

  // 显示版本详情
  const showVersionDetail = (versionIndex: number) => {
    if (versionIndex < 0 || versionIndex >= availableVersions.value.length) {
      return
    }
    void loadWDVersionDetailModal()
    detailVersionIndex.value = versionIndex
    showVersionDetailModal.value = true
  }

  // 关闭版本详情弹窗
  const closeVersionDetail = () => {
    showVersionDetailModal.value = false
  }

  // 隐藏版本选择器，返回内容视图
  const hideVersionSelector = () => {
    // Now controlled by computed property, but we can clear the generation result
    chapterGenerationResult.value = null
    selectedVersionIndex.value = 0
  }

  // 从详情弹窗中选择版本
  const selectVersionFromDetail = async () => {
    selectedVersionIndex.value = detailVersionIndex.value
    closeVersionDetail()
  }

  watch(
    [
      () => selectedChapter.value?.chapter_number ?? null,
      () => selectedChapter.value?.generation_status ?? null,
      () => selectedChapter.value?.status_updated_at ?? null,
      () => selectedChapter.value?.generation_traces ?? [],
      () => availableVersions.value,
    ],
    syncRecommendedVersionSelection,
    { deep: true, immediate: true },
  )

  return {
    availableVersions,
    isCurrentVersion,
    resolveRecommendedVersionIndex,
    showVersionDetail,
    closeVersionDetail,
    hideVersionSelector,
    selectVersionFromDetail,
    showVersionDetailModal,
    detailVersionIndex,
  }
}
