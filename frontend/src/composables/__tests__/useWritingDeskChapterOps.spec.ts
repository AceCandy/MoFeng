// AIMETA P=写作台章节操作测试_删除确认行为|R=useWritingDeskChapterOps|NR=不测试后端清理实现|E=unit:chapter-delete|X=internal|A=vitest|D=vue|S=none|RD=../../README.ai
import { computed, ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { globalAlert } from '@/composables/useAlert'
import { useWritingDeskChapterOps } from '@/composables/useWritingDeskChapterOps'

const deleteChapter = vi.fn()
const resetChapter = vi.fn()

vi.mock('@/queries/novel', () => ({
  useDeleteChapterMutation: () => ({
    mutateAsync: deleteChapter,
    isPending: { value: false },
  }),
  useResetChapterMutation: () => ({
    mutateAsync: resetChapter,
    isPending: { value: false },
  }),
}))

describe('useWritingDeskChapterOps chapter deletion', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    deleteChapter.mockReset().mockResolvedValue(undefined)
    resetChapter.mockReset().mockResolvedValue(undefined)
  })

  it('deletes completed chapter artifacts by chapter number after two confirmations', async () => {
    const showConfirm = vi.spyOn(globalAlert, 'showConfirm').mockResolvedValue(true)
    vi.spyOn(globalAlert, 'showToast').mockImplementation(() => undefined)

    const { deleteChapter: deleteSelectedChapter } = useWritingDeskChapterOps({
      projectId: () => 'novel-delete',
      selectedChapterNumber: ref<number | null>(2),
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

  it('重置保留大纲并只提交当前章节号', async () => {
    vi.spyOn(globalAlert, 'showConfirm').mockResolvedValue(true)
    vi.spyOn(globalAlert, 'showToast').mockImplementation(() => undefined)

    const { resetChapter: resetSelectedChapter } = useWritingDeskChapterOps({
      projectId: () => 'novel-reset',
      selectedChapterNumber: ref<number | null>(4),
      latestCompletedChapterNumber: computed(() => 3),
    })

    await expect(resetSelectedChapter(4)).resolves.toBe(true)
    expect(resetChapter).toHaveBeenCalledWith(4)
    expect(deleteChapter).not.toHaveBeenCalled()
  })

  it('删除异常章节先重置旧运行，再删除章节与尾部大纲', async () => {
    vi.spyOn(globalAlert, 'showConfirm').mockResolvedValue(true)
    vi.spyOn(globalAlert, 'showToast').mockImplementation(() => undefined)
    const selectedChapterNumber = ref<number | null>(4)
    const { deleteBrokenChapter } = useWritingDeskChapterOps({
      projectId: () => 'novel-reset',
      selectedChapterNumber,
      latestCompletedChapterNumber: computed(() => 3),
    })

    await expect(deleteBrokenChapter(4, [4, 5])).resolves.toBe(true)
    expect(resetChapter).toHaveBeenCalledWith(4)
    expect(deleteChapter).toHaveBeenCalledWith({
      chapterNumbers: [4, 5],
      deleteArtifactsConfirmed: false,
    })
    expect(selectedChapterNumber.value).toBeNull()
  })
})
