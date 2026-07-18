// AIMETA P=写作台章节操作测试_删除确认行为|R=useWritingDeskChapterOps|NR=不测试后端清理实现|E=unit:chapter-delete|X=internal|A=vitest|D=vue|S=none|RD=../../README.ai
import { computed, ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { NovelProject } from '@/api/novel'
import { globalAlert } from '@/composables/useAlert'
import { useWritingDeskChapterOps } from '@/composables/useWritingDeskChapterOps'

const deleteChapter = vi.fn()

vi.mock('@/queries/novel', () => ({
  useDeleteChapterMutation: () => ({ mutateAsync: deleteChapter }),
  useEvaluateChapterMutation: () => ({ mutateAsync: vi.fn() }),
}))

describe('useWritingDeskChapterOps chapter deletion', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    deleteChapter.mockReset().mockResolvedValue(undefined)
  })

  it('deletes completed chapter artifacts by chapter number after two confirmations', async () => {
    const showConfirm = vi.spyOn(globalAlert, 'showConfirm').mockResolvedValue(true)
    vi.spyOn(globalAlert, 'showToast').mockImplementation(() => undefined)

    const { deleteChapter: deleteSelectedChapter } = useWritingDeskChapterOps({
      projectId: () => 'novel-delete',
      project: computed<NovelProject | null>(() => null),
      selectedChapterNumber: ref<number | null>(2),
      evaluatingChapter: ref<number | null>(null),
      latestCompletedChapterNumber: computed(() => 2),
    })

    await deleteSelectedChapter([2, 3])

    expect(showConfirm).toHaveBeenCalledTimes(2)
    expect(showConfirm.mock.calls[1]?.[0]).toContain('第 2 章对应的')
    expect(deleteChapter).toHaveBeenCalledWith({
      chapterNumbers: [2, 3],
      deleteArtifactsConfirmed: true,
    })
  })
})
