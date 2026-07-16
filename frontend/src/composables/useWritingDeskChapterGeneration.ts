import type { ComputedRef, Ref } from 'vue'
import type { Chapter, ChapterGenerationResponse, NovelProject } from '@/api/novel'
import { useGenerateChapterMutation } from '@/queries/novel'
import { globalAlert } from '@/composables/useAlert'
import { formatChapterGenerationError } from '@/utils/chapter'

interface UseWritingDeskChapterGenerationOptions {
  projectId: () => string
  project: ComputedRef<NovelProject | null>
  generatingChapter: Ref<number | null>
  selectedChapterNumber: Ref<number | null>
  chapterGenerationResult: Ref<ChapterGenerationResponse | null>
  selectedVersionIndex: Ref<number>
  /** 乐观更新回写章节缓存（来自 useNovelMutationRefresh，跨状态流复用） */
  upsertChapterInProjectCache: (projectId: string | undefined, chapter: Chapter) => void
  /** 拉起章节生成进度 SSE 状态流 */
  fetchChapterStatus: () => void
  /** 生成兜底：强制拉取当前章最新状态并刷新项目缓存 */
  refetchChapterIntoProject: (chapterNumber: number) => Promise<void>
}

/**
 * 写作台章节生成操作：按序生成 / 节点级重试 / 重新生成。
 *
 * 从 WritingDesk.vue 抽出（行为逐行等价）。内聚了「能否生成」的顺序校验
 * （canGenerateChapter/isChapterFailed/hasChapterInProgress）与生成 mutation，
 * 这三者仅服务生成流程；乐观更新所需的缓存回写、SSE 状态流拉取、生成后
 * 强制刷新均由父侧透传，保持与未抽前完全一致。
 */
export const useWritingDeskChapterGeneration = ({
  projectId,
  project,
  generatingChapter,
  selectedChapterNumber,
  chapterGenerationResult,
  selectedVersionIndex,
  upsertChapterInProjectCache,
  fetchChapterStatus,
  refetchChapterIntoProject,
}: UseWritingDeskChapterGenerationOptions) => {
  const generateChapterMutation = useGenerateChapterMutation(projectId)

  const canGenerateChapter = (chapterNumber: number) => {
    if (!project.value?.blueprint?.chapter_outline) return false

    // 检查前面所有章节是否都已成功生成
    const outlines = project.value.blueprint.chapter_outline.sort(
      (a, b) => a.chapter_number - b.chapter_number,
    )

    for (const outline of outlines) {
      if (outline.chapter_number >= chapterNumber) break

      const chapter = project.value?.chapters.find(
        (ch) => ch.chapter_number === outline.chapter_number,
      )
      if (!chapter || chapter.generation_status !== 'successful') {
        return false // 前面有章节未完成
      }
    }

    // 检查当前章节是否已经完成
    const currentChapter = project.value?.chapters.find((ch) => ch.chapter_number === chapterNumber)
    if (currentChapter && currentChapter.generation_status === 'successful') {
      return true // 已完成的章节可以重新生成
    }

    return true // 前面章节都完成了，可以生成当前章节
  }

  const isChapterFailed = (chapterNumber: number) => {
    if (!project.value?.chapters) return false
    const chapter = project.value.chapters.find((ch) => ch.chapter_number === chapterNumber)
    return chapter && chapter.generation_status === 'failed'
  }

  const hasChapterInProgress = (chapterNumber: number) => {
    if (!project.value?.chapters) return false
    const chapter = project.value.chapters.find((ch) => ch.chapter_number === chapterNumber)
    // waiting_for_confirm状态表示等待选择版本 = 进行中状态
    return chapter && chapter.generation_status === 'waiting_for_confirm'
  }

  const generateChapter = async (chapterNumber: number) => {
    // 检查是否可以生成该章节
    if (
      !canGenerateChapter(chapterNumber) &&
      !isChapterFailed(chapterNumber) &&
      !hasChapterInProgress(chapterNumber)
    ) {
      globalAlert.showError('请按顺序生成章节，先完成前面的章节', '生成受限')
      return
    }

    try {
      generatingChapter.value = chapterNumber
      selectedChapterNumber.value = chapterNumber
      const nowIso = new Date().toISOString()

      const existingChapter = project.value?.chapters.find((ch) => ch.chapter_number === chapterNumber)
      const outline = project.value?.blueprint?.chapter_outline?.find(
        (o) => o.chapter_number === chapterNumber,
      )
      upsertChapterInProjectCache(projectId(), {
        ...(existingChapter ?? {}),
        chapter_number: chapterNumber,
        title: existingChapter?.title || outline?.title || '加载中...',
        summary: existingChapter?.summary || outline?.summary || '',
        content: existingChapter?.content || '',
        versions: existingChapter?.versions || [],
        evaluation: existingChapter?.evaluation ?? null,
        generation_status: 'generating',
        generation_progress: 0,
        generation_step: 'context_prep',
        generation_step_index: 1,
        generation_step_total: null,
        generation_started_at: nowIso,
        status_updated_at: nowIso,
        generation_traces: existingChapter?.generation_traces || [],
      } as Chapter)
      fetchChapterStatus()

      await generateChapterMutation.mutateAsync(chapterNumber)
      // 关键兜底：生成接口在极少数情况下可能返回旧快照，这里强制拉取当前章最新状态。
      await refetchChapterIntoProject(chapterNumber)

      // 生成完成只进入草稿确认，必须由用户确认定稿后才执行后处理。
      generatingChapter.value = null
      chapterGenerationResult.value = null
      selectedVersionIndex.value = 0
    } catch (error) {
      console.error('生成章节失败:', error)
      const failureMessage = formatChapterGenerationError(error)

      const failedChapter = project.value?.chapters.find((ch) => ch.chapter_number === chapterNumber)
      if (failedChapter) {
        upsertChapterInProjectCache(projectId(), {
          ...failedChapter,
          generation_status: 'failed',
          generation_step: failureMessage,
          status_updated_at: new Date().toISOString(),
        })
      }

      globalAlert.showError(failureMessage, '生成失败')
    } finally {
      generatingChapter.value = null
    }
  }

  const retryFromNode = async (payload: { chapterNumber: number; nodeKey: string }) => {
    if (!payload || payload.chapterNumber == null || !payload.nodeKey) return
    const { chapterNumber, nodeKey } = payload
    const confirmed = await globalAlert.showConfirm(
      '从此节点重试会丢弃该节点及之后的所有产物并重新生成，确认继续？',
      '节点级重试',
    )
    if (!confirmed) return

    try {
      generatingChapter.value = chapterNumber
      selectedChapterNumber.value = chapterNumber
      const nowIso = new Date().toISOString()
      const existingChapter = project.value?.chapters.find((ch) => ch.chapter_number === chapterNumber)
      upsertChapterInProjectCache(projectId(), {
        ...(existingChapter ?? {}),
        chapter_number: chapterNumber,
        generation_status: 'generating',
        generation_progress: 0,
        generation_step: nodeKey,
        generation_step_index: 1,
        generation_started_at: nowIso,
        status_updated_at: nowIso,
        generation_traces: existingChapter?.generation_traces || [],
      } as Chapter)
      fetchChapterStatus()

      await generateChapterMutation.mutateAsync({ chapterNumber, fromNode: nodeKey })
      await refetchChapterIntoProject(chapterNumber)

      generatingChapter.value = null
      chapterGenerationResult.value = null
      selectedVersionIndex.value = 0
    } catch (error) {
      console.error('节点级重试失败:', error)
      const failureMessage = formatChapterGenerationError(error)
      const failedChapter = project.value?.chapters.find((ch) => ch.chapter_number === chapterNumber)
      if (failedChapter) {
        upsertChapterInProjectCache(projectId(), {
          ...failedChapter,
          generation_status: 'failed',
          generation_step: failureMessage,
          status_updated_at: new Date().toISOString(),
        })
      }
      globalAlert.showError(failureMessage, '重试失败')
    } finally {
      generatingChapter.value = null
    }
  }

  const regenerateChapter = async () => {
    if (selectedChapterNumber.value !== null) {
      await generateChapter(selectedChapterNumber.value)
    }
  }

  return {
    generateChapter,
    retryFromNode,
    regenerateChapter,
  }
}
