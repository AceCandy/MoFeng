import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const readSource = (relativePath: string) =>
  readFileSync(resolve(process.cwd(), relativePath), 'utf8')

describe('chapter draft finalization contracts', () => {
  it('adds finalizing status and confirm finalize API', () => {
    const api = readSource('src/api/novel.ts')
    const generatedContract = readSource('src/api/generated/schema.d.ts')

    expect(generatedContract).toContain('ChapterGenerationStatus:')
    expect(generatedContract).toContain('| "finalizing" |')
    expect(api).toContain('export interface ConfirmFinalizeChapterRequest')
    expect(api).toContain('selected_version_index: number')
    expect(api).toContain('edited_content?: string | null')
    expect(api).toContain('export interface ConfirmFinalizeChapterResponse')
    expect(api).toContain('static async confirmFinalizeChapter')
    expect(api).toContain('/confirm-finalize')
  })

  it('uses the durable select command in writing desk while retaining the rollback facade', () => {
    const legacyQueries = readSource('src/queries/novel.ts')
    const workflowQueries = readSource('src/queries/chapterWorkflow.ts')
    const desk = readSource('src/views/WritingDesk.vue')

    expect(legacyQueries).toContain('export function useConfirmFinalizeChapterMutation')
    expect(legacyQueries).toContain('NovelAPI.confirmFinalizeChapter')
    expect(workflowQueries).toContain('useChapterWorkflowCommandMutation')
    expect(desk).toContain("submitCommand('select', { selected_version_id: versionId })")
    expect(desk).not.toContain('useConfirmFinalizeChapterMutation')
    expect(desk).not.toContain('confirmFinalizeChapterMutation')
  })

  it('selects a query-owned workflow candidate by durable version id', () => {
    const workflowPanel = readSource('src/components/writing-desk/ChapterWorkflowPanel.vue')

    expect(workflowPanel).toContain('candidate.id')
    expect(workflowPanel).toContain("emit('selectVersion', selectedCandidateId.value)")
    expect(workflowPanel).toContain("props.allowedCommands.includes('select')")
    expect(workflowPanel).toContain('候选版本同步中')
    expect(workflowPanel).not.toContain('selected_version_index')
  })

  it('renders finalizing status in the node console', () => {
    const workspace = readSource('src/components/writing-desk/WDWorkspace.vue')
    const workflowPanel = readSource('src/components/writing-desk/ChapterWorkflowPanel.vue')

    expect(workspace).toContain("case 'finalizing':")
    expect(workspace).toContain("return { label: '定稿中', tone: 'progress' }")
    expect(workflowPanel).toContain("case 'finalizing':")
    expect(workflowPanel).toContain("title: '正在提交正文'")
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
    expect(toolbar).toContain('AI优化')
    expect(toolbar).toContain("$emit('openEditModal')")
    expect(toolbar).not.toContain('confirmVersionSelection')
    expect(toolbar).not.toContain('确认定稿')
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
