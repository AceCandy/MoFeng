// AIMETA P=写作台项目与章节查询协调|R=项目加载_章节刷新_章节选择|NR=不订阅章节生命周期SSE_不持有工作流状态|E=composable:writing-desk-project|X=internal|A=useWritingDeskProject|D=vue-router,@tanstack/vue-query|S=state,cache|RD=./README.ai
import { nextTick } from 'vue'
import type { ComputedRef, Ref } from 'vue'
import { useRouter } from 'vue-router'
import type { NovelProject } from '@/api/novel'
import { useNovelChapterQuery, useNovelMutationRefresh, useNovelProjectQuery } from '@/queries/novel'

interface UseWritingDeskProjectOptions {
  projectId: () => string
  project: ComputedRef<NovelProject | null>
  projectQuery: ReturnType<typeof useNovelProjectQuery>
  chapterQuery: ReturnType<typeof useNovelChapterQuery>
  selectedChapterNumber: Ref<number | null>
  selectedVersionIndex: Ref<number>
  closeAllDrawers: () => void
  upsertChapterInProjectCache: ReturnType<typeof useNovelMutationRefresh>['upsertChapterInProjectCache']
  refreshProjectQueries: ReturnType<typeof useNovelMutationRefresh>['refreshProjectQueries']
}

/**
 * 写作台项目加载与章节查询协调。
 *
 * 章节工作流的 current lookup、SSE 与轮询由 useChapterWorkflowActor 独占；本块只
 * 负责 Vue Query 项目/章节刷新和切章时的本地版本索引重置。
 */
export const useWritingDeskProject = ({
  projectId,
  project,
  projectQuery,
  chapterQuery,
  selectedChapterNumber,
  selectedVersionIndex,
  closeAllDrawers,
  upsertChapterInProjectCache,
  refreshProjectQueries,
}: UseWritingDeskProjectOptions) => {
  const router = useRouter()

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

  const selectChapter = (chapterNumber: number) => {
    selectedChapterNumber.value = chapterNumber
    selectedVersionIndex.value = 0
    closeAllDrawers()
  }

  return {
    goBack,
    viewProjectDetail,
    loadProject,
    refetchChapterIntoProject,
    selectChapter,
  }
}
