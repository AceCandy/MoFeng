import { ref, type ComputedRef } from 'vue'
import { globalAlert } from '@/composables/useAlert'
import type { ChapterOutline } from '@/api/novel'

interface UseChapterClipboardOptions {
  selectedChapterOutline: ComputedRef<ChapterOutline | null>
  selectedChapterResolvedContent: ComputedRef<string>
}

// 章节复制胶水：标题/正文复制（含 clipboard API 不可用时的 execCommand 兜底）+ 标题复制提示态。
// 从 WDWorkspace 抽出，行为逐行等价。
export function useChapterClipboard(options: UseChapterClipboardOptions) {
  const { selectedChapterOutline, selectedChapterResolvedContent } = options

  const copyTextLegacy = (text: string): boolean => {
    const textarea = document.createElement('textarea')
    textarea.value = text
    textarea.setAttribute('readonly', 'readonly')
    textarea.style.position = 'fixed'
    textarea.style.top = '-9999px'
    textarea.style.left = '-9999px'
    document.body.appendChild(textarea)
    textarea.focus()
    textarea.select()

    let copied = false
    try {
      copied = document.execCommand('copy')
    } catch (error) {
      copied = false
    }

    document.body.removeChild(textarea)
    return copied
  }

  const copyText = async (text: string) => {
    try {
      if (window.isSecureContext && navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text)
        return true
      }

      return copyTextLegacy(text)
    } catch (error) {
      console.error('复制失败:', error)
      return copyTextLegacy(text)
    }
  }

  const chapterTitleTooltipText = ref('点击复制')

  const resetChapterTitleTooltip = () => {
    chapterTitleTooltipText.value = '点击复制'
  }

  const copySelectedChapterTitle = async () => {
    const title = (selectedChapterOutline.value?.title || '未知标题').trim()
    if (!title) return

    const copied = await copyText(title)
    chapterTitleTooltipText.value = copied ? '复制成功' : '复制失败'
  }

  const copySelectedChapterContent = async () => {
    const content = selectedChapterResolvedContent.value.trim()
    if (!content) return

    const copied = await copyText(content)
    if (!copied) {
      globalAlert.showError('复制失败，请手动选择文本复制。')
    }
  }

  return {
    chapterTitleTooltipText,
    resetChapterTitleTooltip,
    copySelectedChapterTitle,
    copySelectedChapterContent,
  }
}
