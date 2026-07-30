import { computed, type Ref } from 'vue'
import type { NovelProject } from '@/api/novel'
import type { useForeshadowingQuery } from '@/queries/novel'
import type { useShellSectionNavigation } from '@/composables/useShellSectionNavigation'
import { resolveChapterNumberForEntry } from '@/utils/chapter'
import { readStringProperty } from '@/utils/novelContract'

type ForeshadowingQuery = ReturnType<typeof useForeshadowingQuery>
type OverviewQuery = ReturnType<typeof useShellSectionNavigation>['overviewQuery']

/**
 * NovelDetailShell 的概览指标计算群：
 * - projectStatus：依据章节大纲数与已完成章节数推断项目阶段（已完稿/创作中/筹备中）
 * - characterCount/chapterTotal/chapterCompleted：蓝图角色数/大纲数/已完成章节数
 * - currentChapterLabel：依据大纲与章节进度推断当前章节文案
 * - foreshadowingOverview：伏笔统计（overdue/pending/paidOff）
 * - overviewData/overviewMeta/formattedTitle：概览区原始数据/元信息/带书名号标题
 *
 * 数据源（novel/foreshadowingQuery/overviewQuery）由父组件透传，
 * 本 composable 不持有 query 或项目数据，保持内聚。
 */
export function useShellOverview(options: {
  novel: Ref<NovelProject | null>
  foreshadowingQuery: ForeshadowingQuery
  overviewQuery: OverviewQuery
}) {
  const { novel, foreshadowingQuery, overviewQuery } = options

  const projectStatus = computed(() => {
    const total = novel.value?.blueprint?.chapter_outline?.length ?? 0
    const completed =
      novel.value?.chapters?.filter((chapter) => chapter.generation_status === 'successful').length ?? 0
    if (total > 0 && completed >= total) {
      return { label: '已完稿', tone: 'done' as const }
    }
    if (completed > 0) {
      return { label: '创作中', tone: 'active' as const }
    }
    return { label: '筹备中', tone: 'draft' as const }
  })
  const characterCount = computed(() => novel.value?.blueprint?.characters?.length ?? 0)
  const chapterTotal = computed(() => novel.value?.blueprint?.chapter_outline?.length ?? 0)
  const chapterCompleted = computed(
    () => novel.value?.chapters?.filter((chapter) => chapter.generation_status === 'successful').length ?? 0,
  )
  const currentChapterLabel = computed(() => {
    if (!chapterTotal.value) return '未开始'
    const nextChapterNumber = resolveChapterNumberForEntry({
      outlines: novel.value?.blueprint?.chapter_outline ?? [],
      chapters: novel.value?.chapters ?? [],
    })
    if (nextChapterNumber === null) return `已完成 ${chapterTotal.value} 章`
    const completed =
      novel.value?.chapters?.filter((chapter) => chapter.generation_status === 'successful').length ?? 0
    if (completed >= chapterTotal.value) return `已完成 ${chapterTotal.value} 章`
    return `第 ${nextChapterNumber} 章`
  })
  const foreshadowingOverview = computed(() => {
    const payload = foreshadowingQuery.data.value
    if (!payload) {
      return { overdue: 0, pending: 0, paidOff: 0 }
    }
    return {
      overdue: payload.overdue_count,
      pending: payload.planted_count,
      paidOff: payload.paid_off_count,
    }
  })

  const overviewData = computed(() => overviewQuery.data.value?.data ?? null)
  const overviewSummary = computed(() =>
    readStringProperty(overviewData.value, 'one_sentence_summary'),
  )
  const overviewMeta = computed(() => ({
    title: readStringProperty(overviewData.value, 'title') || novel.value?.title || '加载中...',
    updated_at: readStringProperty(overviewData.value, 'updated_at') || null,
  }))

  const formattedTitle = computed(() => {
    const title = overviewMeta.value.title || '加载中...'
    return title.startsWith('《') && title.endsWith('》') ? title : `《${title}》`
  })

  return {
    projectStatus,
    characterCount,
    chapterTotal,
    chapterCompleted,
    currentChapterLabel,
    foreshadowingOverview,
    overviewData,
    overviewSummary,
    overviewMeta,
    formattedTitle,
  }
}
