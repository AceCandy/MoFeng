import { describe, expect, it } from 'vitest'

import {
  cleanVersionContent,
  findNearestIncompleteChapterNumber,
  formatChapterGenerationError,
  isChapterCompletedStatus,
  resolveChapterNumberForEntry,
  resolveChapterNumberForProjectEntry,
} from '@/utils/chapter'

describe('chapter version content cleaning', () => {
  it('unwraps plain optimizer payloads', () => {
    const raw = '{"optimized_content":"候选正文"}'

    expect(cleanVersionContent(raw)).toBe('候选正文')
  })

  it('unwraps fenced optimizer payloads into plain chapter content', () => {
    const raw = '```json\n{"optimized_content":"第一段\\n第二段"}\n```'

    expect(cleanVersionContent(raw)).toBe('第一段\n第二段')
  })

  it('unwraps nested optimizer payloads', () => {
    const nested = JSON.stringify({ optimized_content: '真正正文' })
    const raw = JSON.stringify({ optimized_content: `\`\`\`json\n${nested}\n\`\`\`` })

    expect(cleanVersionContent(raw)).toBe('真正正文')
  })

  it('unwraps escaped fenced optimizer payloads', () => {
    const raw = '```json\\n{\\"optimized_content\\":\\"第一段\\\\n第二段\\"}\\n```'

    expect(cleanVersionContent(raw)).toBe('第一段\n第二段')
  })

  it('unwraps optimizer payloads encoded as a JSON string', () => {
    const raw = JSON.stringify('```json\n{"optimized_content":"外层正文"}\n```')

    expect(cleanVersionContent(raw)).toBe('外层正文')
  })

  it('preserves literal escapes in plain text and parsed chapter content', () => {
    const prose = String.raw`路径 C:\new\chapter，字面量 \n 与 \t`

    expect(cleanVersionContent(prose)).toBe(prose)
    expect(cleanVersionContent(JSON.stringify({ optimized_content: prose }))).toBe(prose)
  })

  it('keeps unrelated JSON text unchanged', () => {
    const raw = '{"kind":"正文中的示例"}'

    expect(cleanVersionContent(raw)).toBe(raw)
  })
})

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
