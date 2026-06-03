export function countAlphaNumericHan(text: string | null | undefined): number {
  if (!text) return 0
  const matches = text.match(/[A-Za-z0-9㐀-䶿一-鿿豈-﫿]/g)
  return matches ? matches.length : 0
}

export function countNonWhitespaceChars(text: string | null | undefined): number {
  if (!text) return 0
  return text.replace(/\s/g, '').length
}

export function resolveChapterDisplayWordCount(
  content: string | null | undefined,
  persistedWordCount: number | null | undefined,
): number {
  const contentWordCount = countNonWhitespaceChars(content)
  if (contentWordCount > 0) return contentWordCount
  if (typeof persistedWordCount === 'number' && persistedWordCount >= 0) return persistedWordCount
  return 0
}
