import { nextTick, onUnmounted, ref } from 'vue'
import type { ComputedRef, Ref } from 'vue'
import { useRouter } from 'vue-router'
import { NovelAPI } from '@/api/novel'
import type { ChapterGenerationResponse, NovelProject } from '@/api/novel'
import { useNovelChapterQuery, useNovelMutationRefresh, useNovelProjectQuery } from '@/queries/novel'

interface UseWritingDeskProjectOptions {
  projectId: () => string
  project: ComputedRef<NovelProject | null>
  projectQuery: ReturnType<typeof useNovelProjectQuery>
  chapterQuery: ReturnType<typeof useNovelChapterQuery>
  selectedChapterNumber: Ref<number | null>
  chapterGenerationResult: Ref<ChapterGenerationResponse | null>
  selectedVersionIndex: Ref<number>
  closeAllDrawers: () => void
  upsertChapterInProjectCache: ReturnType<typeof useNovelMutationRefresh>['upsertChapterInProjectCache']
  refreshProjectQueries: ReturnType<typeof useNovelMutationRefresh>['refreshProjectQueries']
}

/**
 * 写作台项目加载与章节状态同步。
 *
 * 从 WritingDesk.vue 抽出（行为逐行等价）。聚合项目加载/刷新、章节状态 SSE 流、
 * 章节选择三类副作用：loadProject/refetchChapterIntoProject 负责数据刷新，
 * fetchChapterStatus/stopChapterStatusStream 维护 SSE 订阅与重连，selectChapter 负责
 * 切换章节时的本地状态重置。章节状态 SSE 句柄（4 个 ref）仅本块使用，故内化；
 * onUnmounted 统一在此注销流。
 */
export const useWritingDeskProject = ({
  projectId,
  project,
  projectQuery,
  chapterQuery,
  selectedChapterNumber,
  chapterGenerationResult,
  selectedVersionIndex,
  closeAllDrawers,
  upsertChapterInProjectCache,
  refreshProjectQueries,
}: UseWritingDeskProjectOptions) => {
  const router = useRouter()

  // 章节状态 SSE 流的运行时句柄
  const isFetchingChapterStatus = ref(false)
  const statusStreamController = ref<AbortController | null>(null)
  const statusStreamKey = ref<string | null>(null)
  const statusStreamReconnectTimer = ref<number | null>(null)

  const goBack = () => {
    router.push('/workspace')
  }

  const viewProjectDetail = () => {
    if (project.value) {
      router.push(`/projects/${project.value.id}`)
    }
  }

  const loadProject = async () => {
    try {
      await projectQuery.refetch()
    } catch (error) {
      console.error('加载项目失败:', error)
    }
  }

  const refetchChapterIntoProject = async (
    chapterNumber: number,
    options: { refreshProject?: boolean } = { refreshProject: true },
  ) => {
    if (selectedChapterNumber.value !== chapterNumber) {
      selectedChapterNumber.value = chapterNumber
      await nextTick()
    }

    const result = await chapterQuery.refetch()
    if (result.data) {
      upsertChapterInProjectCache(projectId(), result.data)
    }
    if (options.refreshProject) {
      await refreshProjectQueries()
    }
  }

  const stopChapterStatusStream = () => {
    if (statusStreamReconnectTimer.value !== null) {
      window.clearTimeout(statusStreamReconnectTimer.value)
      statusStreamReconnectTimer.value = null
    }
    statusStreamController.value?.abort()
    statusStreamController.value = null
    statusStreamKey.value = null
    isFetchingChapterStatus.value = false
  }

  const fetchChapterStatus = () => {
    if (selectedChapterNumber.value === null) {
      return
    }
    const currentProjectId = projectId()
    const chapterNumber = selectedChapterNumber.value
    const streamKey = `${currentProjectId}:${chapterNumber}`
    if (statusStreamKey.value === streamKey) {
      return
    }

    stopChapterStatusStream()
    if (statusStreamReconnectTimer.value !== null) {
      window.clearTimeout(statusStreamReconnectTimer.value)
      statusStreamReconnectTimer.value = null
    }
    const controller = new AbortController()
    statusStreamController.value = controller
    statusStreamKey.value = streamKey
    isFetchingChapterStatus.value = true

    void NovelAPI.subscribeChapterStatus(currentProjectId, chapterNumber, {
      signal: controller.signal,
      onChapter: (chapter) => {
        if (chapter.chapter_number !== chapterNumber) return
        upsertChapterInProjectCache(currentProjectId, chapter)
      },
      onError: (error) => {
        if (controller.signal.aborted) return
        console.error('章节状态 SSE 同步失败:', error)
      },
    }).catch((error) => {
      if (controller.signal.aborted) return
      console.error('章节状态 SSE 连接失败:', error)
      if (projectId() === currentProjectId && selectedChapterNumber.value === chapterNumber) {
        void refetchChapterIntoProject(chapterNumber, { refreshProject: false })
      }
      statusStreamReconnectTimer.value = window.setTimeout(() => {
        if (projectId() === currentProjectId && selectedChapterNumber.value === chapterNumber) {
          statusStreamKey.value = null
          fetchChapterStatus()
        }
      }, 3000)
    }).finally(() => {
      if (statusStreamKey.value === streamKey) {
        statusStreamController.value = null
        statusStreamKey.value = null
        isFetchingChapterStatus.value = false
      }
    })
  }

  const selectChapter = (chapterNumber: number) => {
    selectedChapterNumber.value = chapterNumber
    chapterGenerationResult.value = null
    selectedVersionIndex.value = 0
    closeAllDrawers()
  }

  onUnmounted(() => {
    stopChapterStatusStream()
  })

  return {
    goBack,
    viewProjectDetail,
    loadProject,
    refetchChapterIntoProject,
    stopChapterStatusStream,
    fetchChapterStatus,
    selectChapter,
  }
}
