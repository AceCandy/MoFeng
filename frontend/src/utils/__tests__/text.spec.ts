import { describe, expect, it } from 'vitest'

import { countNonWhitespaceChars, resolveChapterDisplayWordCount } from '@/utils/text'

describe('text word counting', () => {
  it('counts chapter words after removing whitespace', () => {
    expect(countNonWhitespaceChars('新\n 内\t容')).toBe(3)
  })

  it('prefers live content count over persisted word_count for chapter display', () => {
    expect(resolveChapterDisplayWordCount('新\n 内 容', 99)).toBe(3)
  })

  it('falls back to persisted word_count when chapter content is not available', () => {
    expect(resolveChapterDisplayWordCount('', 88)).toBe(88)
  })
})
