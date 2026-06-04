import { describe, expect, it } from 'vitest'

import {
  findNearestIncompleteChapterNumber,
  formatChapterGenerationError,
  isChapterCompletedStatus,
  resolveChapterNumberForEntry,
  resolveChapterNumberForProjectEntry,
} from '@/utils/chapter'

describe('chapter entry resolving', () => {
  const outlines = [
    { chapter_number: 1 },
    { chapter_number: 2 },
    { chapter_number: 3 },
    { chapter_number: 4 },
  ]

  it('locates the first non-successful chapter by chapter number', () => {
    const chapters = [
      { chapter_number: 1, generation_status: 'successful' },
      { chapter_number: 2, generation_status: 'successful' },
      { chapter_number: 3, generation_status: 'waiting_for_confirm' },
    ]

    expect(findNearestIncompleteChapterNumber(outlines, chapters)).toBe(3)
  })

  it('treats missing chapter records as unfinished outline chapters', () => {
    const chapters = [{ chapter_number: 1, generation_status: 'successful' }]

    expect(findNearestIncompleteChapterNumber(outlines, chapters)).toBe(2)
  })

  it('honors an explicit valid chapter number before auto locating unfinished chapters', () => {
    const chapters = [{ chapter_number: 1, generation_status: 'successful' }]

    expect(
      resolveChapterNumberForEntry({
        outlines,
        chapters,
        preferredChapterNumber: 4,
      }),
    ).toBe(4)
  })

  it('falls back to the last chapter when all chapters are completed', () => {
    const chapters = outlines.map((outline) => ({
      chapter_number: outline.chapter_number,
      generation_status: 'successful',
    }))

    expect(resolveChapterNumberForEntry({ outlines, chapters })).toBe(4)
  })

  it('normalizes successful as the only completed status', () => {
    expect(isChapterCompletedStatus({ chapter_number: 1, generation_status: 'successful' })).toBe(
      true,
    )
    expect(isChapterCompletedStatus({ chapter_number: 1, generation_status: 'waiting_for_confirm' })).toBe(
      false,
    )
    expect(isChapterCompletedStatus(null)).toBe(false)
  })

  it('clears a stale selected chapter when the entered project has no chapters', () => {
    expect(
      resolveChapterNumberForProjectEntry({
        projectId: 'empty-project',
        previousProjectId: 'previous-project',
        currentChapterNumber: 76,
        outlines: [],
        chapters: [],
      }),
    ).toBeNull()
  })

  it('does not carry the selected chapter number from another project', () => {
    expect(
      resolveChapterNumberForProjectEntry({
        projectId: 'new-project',
        previousProjectId: 'previous-project',
        currentChapterNumber: 76,
        outlines,
        chapters: [],
      }),
    ).toBe(1)
  })

  it('keeps the current selected chapter when project data refreshes for the same project', () => {
    expect(
      resolveChapterNumberForProjectEntry({
        projectId: 'same-project',
        previousProjectId: 'same-project',
        currentChapterNumber: 3,
        outlines,
        chapters: [],
      }),
    ).toBe(3)
  })
})

describe('chapter generation error formatting', () => {
  it('removes duplicated chapter generation failure prefixes', () => {
    const error = new Error('生成章节失败，请重试。')

    expect(formatChapterGenerationError(error)).toBe('生成章节失败，请重试。')
  })

  it('keeps the specific backend failure reason visible', () => {
    const error = new Error('生成章节失败：阶段 chapter_writing 使用的供应商缺少 API Key')

    expect(formatChapterGenerationError(error)).toBe(
      '阶段 chapter_writing 使用的供应商缺少 API Key',
    )
  })

  it('handles versioned generation failure messages', () => {
    const error = '生成章节第 1 个版本失败：字数仅 1780，低于最低要求 2200（容错阈值 1870）。请重试。'

    expect(formatChapterGenerationError(error)).toBe(
      '字数仅 1780，低于最低要求 2200（容错阈值 1870）。请重试。',
    )
  })

  it('uses an actionable fallback when the error has no readable message', () => {
    expect(formatChapterGenerationError(null)).toBe('未收到具体错误信息，请查看后端日志或稍后重试。')
  })
})
