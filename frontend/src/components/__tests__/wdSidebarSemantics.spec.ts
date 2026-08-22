import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

const readSource = (relativePath: string) =>
  readFileSync(resolve(process.cwd(), relativePath), 'utf8')

describe('WDSidebar semantics', () => {
  it('uses native button semantics for chapter rows', () => {
    const source = readSource('src/components/writing-desk/WDSidebar.vue')
    const normalizedSource = source.replace(/\s+/g, ' ')

    expect(source).toContain('writing-sidebar__chapter-row')
    expect(source).toContain('type="button"')
    expect(source).toContain('@click="$emit(\'selectChapter\', chapter.chapter_number)"')
    expect(source).toContain(':aria-label="getChapterA11yLabel(chapter.chapter_number, chapter.title)"')
    expect(source).toContain(':aria-current="selectedChapterNumber === chapter.chapter_number ? \'true\' : undefined"')
    expect(normalizedSource).toContain(
      '<span class="writing-sidebar__chapter-title md-body-medium font-semibold line-clamp-1"',
    )
    expect(source).not.toContain('role="button"')
    expect(source).not.toContain('tabindex="0"')
    expect(source).not.toContain('@keydown.enter.prevent="$emit(\'selectChapter\', chapter.chapter_number)"')
    expect(source).not.toContain('@keydown.space.prevent="$emit(\'selectChapter\', chapter.chapter_number)"')
    expect(source).not.toContain('<h2 class="md-title-medium font-semibold">故事蓝图</h2>')
    expect(source).not.toContain('<h4')
  })

  it('keeps persisted completion ahead of transient selected workflow state', () => {
    const sidebar = readSource('src/components/writing-desk/WDSidebar.vue')
    const tagResolver = sidebar.split('const getChapterTag', 2)[1].split('const chapterStatusDotClass', 1)[0]
    const dotResolver = sidebar
      .split('const chapterStatusDotClass', 2)[1]
      .split('// 状态印三态', 1)[0]
    const workspace = readSource('src/components/writing-desk/WDWorkspace.vue')

    expect(tagResolver.indexOf('isChapterCompleted')).toBeLessThan(
      tagResolver.indexOf('props.selectedChapterNumber'),
    )
    expect(dotResolver.indexOf('isChapterCompleted')).toBeLessThan(
      dotResolver.indexOf('props.selectedChapterNumber'),
    )
    expect(workspace).toContain(
      "!(props.workflowPhase === 'idle' && hasFinalizedChapterContent.value)",
    )
  })
})
