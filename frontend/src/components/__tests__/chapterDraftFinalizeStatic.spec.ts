import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const readSource = (relativePath: string) =>
  readFileSync(resolve(process.cwd(), relativePath), 'utf8')

describe('chapter draft finalization contracts', () => {
  it('adds finalizing status and confirm finalize API', () => {
    const api = readSource('src/api/novel.ts')

    expect(api).toContain("'finalizing'")
    expect(api).toContain('export interface ConfirmFinalizeChapterRequest')
    expect(api).toContain('selected_version_index: number')
    expect(api).toContain('edited_content?: string | null')
    expect(api).toContain('export interface ConfirmFinalizeChapterResponse')
    expect(api).toContain('static async confirmFinalizeChapter')
    expect(api).toContain('/confirm-finalize')
  })

  it('uses confirm finalize mutation instead of select mutation in writing desk', () => {
    const queries = readSource('src/queries/novel.ts')
    const desk = readSource('src/views/WritingDesk.vue')

    expect(queries).toContain('export function useConfirmFinalizeChapterMutation')
    expect(queries).toContain('NovelAPI.confirmFinalizeChapter')
    expect(desk).toContain('useConfirmFinalizeChapterMutation')
    expect(desk).toContain('confirmFinalizeChapterMutation')
  })

  it('shows draft confirmation copy and manual edit support', () => {
    const versionSelector = readSource('src/components/writing-desk/workspace/VersionSelector.vue')

    expect(versionSelector).toContain('草稿确认')
    expect(versionSelector).toContain('确认定稿')
    expect(versionSelector).toContain('编辑草稿')
    expect(versionSelector).toContain('draftEditedContent')
    expect(versionSelector).toContain('canConfirmDraft')
    expect(versionSelector).toContain('draftEditOpen.value && draftEditedContent.value.trim()')
    expect(versionSelector).toContain("emit('confirmVersionSelection'")
  })

  it('renders finalizing status in the node console', () => {
    const workspace = readSource('src/components/writing-desk/WDWorkspace.vue')

    expect(workspace).toContain("case 'finalizing':")
    expect(workspace).toContain("return '定稿中'")
    expect(workspace).toContain("status === 'finalizing'")
    expect(workspace).toContain('ChapterGenerating')
  })

  it('labels finalization trace nodes in the console', () => {
    const generating = readSource('src/components/writing-desk/workspace/ChapterGenerating.vue')

    for (const key of [
      'confirm_finalize',
      'real_summary',
      'finalize_memory',
      'chapter_ingest',
      'foreshadowing_sync',
      'finalized',
      'finalization_error',
    ]) {
      expect(generating).toContain(key)
    }

    expect(generating).toContain('确认定稿')
    expect(generating).toContain('生成章节梳理')
    expect(generating).toContain('同步伏笔')
  })
})
