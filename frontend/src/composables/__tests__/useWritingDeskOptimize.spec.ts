// AIMETA P=写作台评审优化测试|R=useWritingDeskOptimize_载荷收窄|NR=不测试后端优化实现|E=unit:writing-desk-optimize|X=internal|A=vitest|D=vue|S=none|RD=../../README.ai
import { computed, ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { Chapter, ChapterVersion, NovelProject } from '@/api/novel'
import { useWritingDeskOptimize } from '@/composables/useWritingDeskOptimize'

const optimizeRecommendedVersion = vi.fn()
const applyOptimization = vi.fn()

vi.mock('@/queries/novel', () => ({
  useOptimizeRecommendedVersionMutation: () => ({
    mutateAsync: optimizeRecommendedVersion,
    isPending: { value: false },
  }),
  useApplyOptimizationMutation: () => ({
    mutateAsync: applyOptimization,
    isPending: { value: false },
  }),
}))

const project = computed(() => ({ id: 'novel-1' }) as NovelProject)
const availableVersions = computed<ChapterVersion[]>(() => [
  { content: '第一版正文' },
  { content: '第二版正文' },
])

const createOptimize = (evaluation: string) => useWritingDeskOptimize({
  projectId: () => project.value.id,
  project,
  selectedChapter: computed(() => ({ chapter_number: 3, evaluation }) as Chapter),
  availableVersions,
  refetchChapterIntoProject: vi.fn(),
  showEvaluationDetailModal: ref(false),
})

describe('useWritingDeskOptimize evaluation payload', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    optimizeRecommendedVersion.mockReset().mockResolvedValue({
      optimized_content: '优化正文',
      optimization_notes: '优化说明',
    })
    applyOptimization.mockReset()
  })

  it('submits the selected version and narrowed review fields', async () => {
    const evaluation = JSON.stringify({
      best_choice: 2,
      reason_for_choice: ' 第二版结构更完整 ',
      evaluation: {
        version2: { pros: ['结构完整'], overall_review: '推荐' },
      },
    })

    await createOptimize(evaluation).optimizeRecommendedVersionFromEvaluation()

    expect(optimizeRecommendedVersion).toHaveBeenCalledWith({
      project_id: 'novel-1',
      chapter_number: 3,
      source_content: '第二版正文',
      review_summary: '第二版结构更完整',
      version_number: 2,
      version_review: { pros: ['结构完整'], overall_review: '推荐' },
    })
  })

  it('does not submit malformed evaluation fields', async () => {
    const evaluation = JSON.stringify({
      best_choice: { version: 2 },
      evaluation: [],
    })

    await createOptimize(evaluation).optimizeRecommendedVersionFromEvaluation()

    expect(optimizeRecommendedVersion).not.toHaveBeenCalled()
  })
})
