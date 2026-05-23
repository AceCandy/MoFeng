import { describe, expect, it } from 'vitest'

import {
  findNearestIncompleteChapterNumber,
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
