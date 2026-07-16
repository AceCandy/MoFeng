import { ref, watch } from 'vue'
import type { ComputedRef, Ref } from 'vue'
import { useRoute } from 'vue-router'
import type { ChapterGenerationResponse, NovelProject } from '@/api/novel'
import { resolveChapterNumberForEntry, resolveChapterNumberForProjectEntry } from '@/utils/chapter'

interface UseWritingDeskNavigationOptions {
  projectId: () => string
  project: ComputedRef<NovelProject | null>
  selectedChapterNumber: Ref<number | null>
  chapterGenerationResult: Ref<ChapterGenerationResponse | null>
  selectedVersionIndex: Ref<number>
  selectChapter: (chapterNumber: number) => void
  stopChapterStatusStream: () => void
}

/**
 * 写作台「章节定位导航」状态机。
 *
 * 从 WritingDesk.vue 抽出（行为逐行等价）。响应项目加载、路由 query 与项目切换，
 * 重新定位当前选中章节：项目就绪时按 blueprint + chapters + query 首次定位（immediate），
 * query 变化时跳转章节，项目切换时停止上一项目的章节生成 SSE 流。
 * resolvedProjectEntryId 仅用于检测项目切换、getQueryChapterNumber/route 仅本状态机使用，故内化。
 */
export const useWritingDeskNavigation = ({
  projectId,
  project,
  selectedChapterNumber,
  chapterGenerationResult,
  selectedVersionIndex,
  selectChapter,
  stopChapterStatusStream,
}: UseWritingDeskNavigationOptions) => {
  const route = useRoute()
  const resolvedProjectEntryId = ref<string | null>(null)

  const getQueryChapterNumber = () => {
    const rawChapterNumber = Array.isArray(route.query.chapter_number)
      ? route.query.chapter_number[0]
      : route.query.chapter_number
    const chapterNumber = Number(rawChapterNumber)
    return Number.isFinite(chapterNumber) && chapterNumber > 0 ? chapterNumber : null
  }

  // 写作台会在不同项目间复用组件，进入新项目时必须按当前项目重新定位章节。
  watch(
    () => project.value,
    (newProject) => {
      if (!newProject) {
        selectedChapterNumber.value = null
        resolvedProjectEntryId.value = null
        return
      }

      const resolvedChapterNumber = resolveChapterNumberForProjectEntry({
        projectId: newProject.id,
        previousProjectId: resolvedProjectEntryId.value,
        currentChapterNumber: selectedChapterNumber.value,
        outlines: newProject.blueprint?.chapter_outline ?? [],
        chapters: newProject.chapters ?? [],
        preferredChapterNumber: getQueryChapterNumber(),
      })

      selectedChapterNumber.value = resolvedChapterNumber
      selectedVersionIndex.value = 0
      chapterGenerationResult.value = null
      resolvedProjectEntryId.value = newProject.id
    },
    { immediate: true },
  )

  watch(
    () => route.query.chapter_number,
    () => {
      if (!project.value) {
        return
      }
      const chapterNumber = getQueryChapterNumber()
      if (!chapterNumber) {
        return
      }
      const resolvedChapterNumber = resolveChapterNumberForEntry({
        outlines: project.value.blueprint?.chapter_outline ?? [],
        chapters: project.value.chapters ?? [],
        preferredChapterNumber: chapterNumber,
      })
      if (resolvedChapterNumber !== null) {
        selectChapter(resolvedChapterNumber)
      }
    },
  )

  watch(projectId, () => {
    stopChapterStatusStream()
  })
}
