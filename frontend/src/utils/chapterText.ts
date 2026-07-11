/**
 * 章节正文段落切分。朗读（useChapterReader）与正文渲染（ChapterContent）共用此切分，
 * 确保「当前朗读段」与正文 <p> 一一对应，用于朗读时的段落高亮与滚动定位。
 */
export const splitChapterParagraphs = (content: string): string[] => {
  if (!content) return []
  const normalized = content
    .replace(/\r\n?/g, '\n')
    .replace(/ /g, ' ')
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
  if (!normalized) return []

  const paragraphs = normalized
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean)

  if (paragraphs.length !== 1) {
    return paragraphs
  }

  // 单段超长文本兜底：按句号等标点粗分段，提升可读性
  const singleParagraph = paragraphs[0]
  const sentences = (singleParagraph.match(/[^。！？!?；;]+[。！？!?；;]?/g) || [singleParagraph])
    .map((sentence) => sentence.trim())
    .filter(Boolean)

  if (sentences.length < 6) {
    return paragraphs
  }

  const grouped: string[] = []
  for (let i = 0; i < sentences.length; i += 2) {
    grouped.push(`${sentences[i]}${sentences[i + 1] || ''}`.trim())
  }
  return grouped.filter(Boolean)
}
