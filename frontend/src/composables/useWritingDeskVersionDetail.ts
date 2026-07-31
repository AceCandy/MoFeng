// AIMETA P=写作台章节版本详情|R=Chapter_Query版本归一化_详情选择|NR=不读取生成响应_不提交工作流命令|E=composable:writing-desk-version-detail|X=internal|A=useWritingDeskVersionDetail|D=vue|S=state,cache|RD=./README.ai
import { computed, ref, type ComputedRef, type Ref } from 'vue'
import type { Chapter, ChapterVersion } from '@/api/novel'
import { cleanVersionContent } from '@/utils/chapter'

interface UseWritingDeskVersionDetailOptions {
  selectedChapter: ComputedRef<Chapter | null>
  selectedVersionIndex: Ref<number>
  /** 版本详情弹窗组件懒加载 loader（父侧 defineAsyncComponent 同源） */
  loadWDVersionDetailModal: () => Promise<unknown>
}

/**
 * 写作台版本提取与版本详情操作。
 *
 * 从 WritingDesk.vue 抽出（行为逐行等价）。内聚版本内容/元数据提取、可用版本
 * 计算（availableVersions）与版本详情弹窗操作。候选选版由 Chapter Query 的
 * version_selections + 当前 workflow run_id 单独负责，不再混入历史版本索引。
 */
export const useWritingDeskVersionDetail = ({
  selectedChapter,
  selectedVersionIndex,
  loadWDVersionDetailModal,
}: UseWritingDeskVersionDetailOptions) => {
  const showVersionDetailModal = ref(false)
  const detailVersionIndex = ref<number>(0)
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

  const extractVersionMetadata = (raw: unknown): Record<string, unknown> | null => {
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
      return null
    }
    const metadata = (raw as Record<string, unknown>).metadata
    return metadata && typeof metadata === 'object' && !Array.isArray(metadata)
      ? (metadata as Record<string, unknown>)
      : null
  }

  // 历史版本只来自 Chapter Query；工作流候选通过 version_selections 单独展示。
  const availableVersions = computed<ChapterVersion[]>(() => {
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

  // 从详情弹窗中选择版本
  const selectVersionFromDetail = async () => {
    selectedVersionIndex.value = detailVersionIndex.value
    closeVersionDetail()
  }

  return {
    availableVersions,
    isCurrentVersion,
    showVersionDetail,
    closeVersionDetail,
    selectVersionFromDetail,
    showVersionDetailModal,
    detailVersionIndex,
  }
}
