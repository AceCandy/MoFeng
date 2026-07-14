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
    // 状态标签逻辑随 chapterStatusLabel/chapterStatusTone 抽至 useChapterStatus
    const statusLogic = readSource('src/composables/useChapterStatus.ts')
    const workspace = readSource('src/components/writing-desk/WDWorkspace.vue')

    expect(statusLogic).toContain("case 'finalizing':")
    expect(statusLogic).toContain("return '定稿中'")
    expect(statusLogic).toContain("status === 'finalizing'")
    expect(workspace).toContain('ChapterGenerating')
  })

  it('keeps finalized version labels aligned with candidate indexes', () => {
    // 版本卡片标签随 versions 面板抽至 ChapterVersionsPanel（Slice D 第 3 块），正序契约随之迁移
    const versionsPanel = readSource('src/components/writing-desk/workspace/ChapterVersionsPanel.vue')

    expect(versionsPanel).toContain('版本 {{ index + 1 }}')
    expect(versionsPanel).not.toContain('版本 {{ availableVersions.length - index }}')
  })

  it('only keeps copy and export actions after finalization', () => {
    // toolbar 操作随 template 抽至 ChapterToolbar（Slice D 第 4b 块），契约随之迁移
    const toolbar = readSource('src/components/writing-desk/workspace/ChapterToolbar.vue')

    expect(toolbar).toContain('v-if="isFinalizedSuccessful"')
    expect(toolbar).toContain("@click=\"$emit('copyContent')\"")
    expect(toolbar).toContain('@click="exportContentAsTxt"')
    expect(toolbar).toContain('v-if="isDraftWaitingConfirm" class="writing-workspace__toolbar-row writing-workspace__toolbar-row--primary"')
    expect(toolbar).not.toContain('v-if="isFinalizedSuccessful || isDraftWaitingConfirm"')
  })

  it('renders multi-version evaluations in numeric version order', () => {
    // 评审展示随 template 抽至 ChapterEvaluationPanel（Slice D 第 2 块），排序契约随之迁移
    const evaluationPanel = readSource('src/components/writing-desk/workspace/ChapterEvaluationPanel.vue')
    const detailModal = readSource('src/components/writing-desk/WDEvaluationDetailModal.vue')
    const chaptersSection = readSource('src/components/novel-detail/ChaptersSection.vue')

    for (const source of [evaluationPanel, detailModal, chaptersSection]) {
      expect(source).toContain('sortedEvaluationEntries')
      expect(source).toContain('versionNumber')
      expect(source).toContain('.sort((a, b) => a.versionNumber - b.versionNumber)')
    }

    expect(evaluationPanel).not.toContain('v-for="(evalResult, versionName) in parsedEvaluation.evaluation"')
    expect(detailModal).not.toContain(
      'v-for="(evalResult, versionName) in parsedEvaluation.evaluation"',
    )
    expect(chaptersSection).not.toContain(
      'v-for="(versionEval, versionKey) in evaluationData.evaluation"',
    )
  })

  it('labels finalization trace nodes in the console', () => {
    // finalization 节点 key/标签随 Slice 1 抽至 utils/generationTrace.ts（PIPELINE_LABELS/STEP_DETAILS）
    const generating = readSource('src/utils/generationTrace.ts')

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
