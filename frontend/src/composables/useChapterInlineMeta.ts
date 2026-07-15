import { computed, type ComputedRef } from 'vue'
import { countNonWhitespaceChars } from '@/utils/text'
import type { Chapter } from '@/api/novel'

interface UseChapterInlineMetaOptions {
  selectedChapter: ComputedRef<Chapter | null>
  selectedChapterResolvedContent: ComputedRef<string>
  hasSelectedChapterContent: ComputedRef<boolean>
}

// 章节元信息胶水：装配 ChapterMeta 的 inline-meta 文案（字数 + 最后编辑时间）。
// 从 WDWorkspace 抽出，行为逐行等价。
export function useChapterInlineMeta(options: UseChapterInlineMetaOptions) {
  const { selectedChapter, selectedChapterResolvedContent, hasSelectedChapterContent } = options

  const formatDateTime = (value?: string | null) => {
    if (!value) return '--'
    const parsed = new Date(value)
    if (Number.isNaN(parsed.getTime())) return '--'
    const year = parsed.getFullYear()
    const month = String(parsed.getMonth() + 1).padStart(2, '0')
    const day = String(parsed.getDate()).padStart(2, '0')
    const hour = String(parsed.getHours()).padStart(2, '0')
    const minute = String(parsed.getMinutes()).padStart(2, '0')
    return `${year}/${month}/${day} ${hour}:${minute}`
  }

  const selectedChapterWordCount = computed(() =>
    countNonWhitespaceChars(selectedChapterResolvedContent.value),
  )

  const chapterLastEditedText = computed(() =>
    formatDateTime(selectedChapter.value?.status_updated_at ?? selectedChapter.value?.generation_started_at),
  )

  const chapterInlineMeta = computed(() => {
    const segments: string[] = []
    if (hasSelectedChapterContent.value) {
      segments.push(`${selectedChapterWordCount.value}字`)
    }
    segments.push(`最后编辑 ${chapterLastEditedText.value}`)
    return segments.join(' · ')
  })

  return {
    chapterInlineMeta,
  }
}
