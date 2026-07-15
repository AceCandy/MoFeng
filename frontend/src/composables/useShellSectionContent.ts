import { computed, type Ref } from 'vue'
import type { NovelProject, AllSectionType } from '@/api/novel'
import type { useShellSectionNavigation } from '@/composables/useShellSectionNavigation'
import type { useShellOverview } from '@/composables/useShellOverview'

type Navigation = ReturnType<typeof useShellSectionNavigation>
type Overview = ReturnType<typeof useShellOverview>
type SectionKey = AllSectionType

/**
 * NovelDetailShell 的分区内容渲染计算群：
 * - activeQuery/currentSectionResponse/currentSectionData：依据当前分区路由到 overview/section query 并取响应数据（内部中间量，不对外返回）
 * - currentComponent：当前分区对应的懒加载组件
 * - isSectionLoading/currentError：分区数据加载态与错误文案
 * - componentProps：按分区类型拼装下发给分区组件的 props
 * - componentContainerClass/contentCardClass：分区容器与内容卡片的 class
 *
 * 数据源（navigation/novel/characterCount/chapterTotal/isAdmin）由父组件透传，
 * 本 composable 不持有 query 或项目数据，保持内聚。
 */
export function useShellSectionContent(options: {
  navigation: Navigation
  novel: Ref<NovelProject | null>
  characterCount: Overview['characterCount']
  chapterTotal: Overview['chapterTotal']
  isAdmin: () => boolean
}) {
  const { navigation, novel, characterCount, chapterTotal, isAdmin } = options
  const { activeSection, sectionComponents, isNovelSectionKey, overviewQuery, sectionQuery } = navigation

  const activeQuery = computed(() => (activeSection.value === 'overview' ? overviewQuery : sectionQuery))
  const currentSectionResponse = computed(() => {
    if (!isNovelSectionKey(activeSection.value)) {
      return null
    }
    return activeSection.value === 'overview'
      ? overviewQuery.data.value
      : sectionQuery.data.value
  })
  const currentSectionData = computed(() => currentSectionResponse.value?.data ?? null)

  const componentContainerClass = computed(() => {
    const fillSections: SectionKey[] = ['chapters']
    return fillSections.includes(activeSection.value)
      ? 'flex-1 min-h-0 h-full flex flex-col overflow-hidden'
      : 'min-w-0'
  })

  const contentCardClass = computed(() => {
    // 所有蓝图分区共享同一装订外框，概览页不再使用特殊透明托盘。
    return 'detail-shell__content-surface--fill detail-shell__content-surface--classical overflow-y-auto overscroll-contain'
  })

  const currentComponent = computed(() => sectionComponents[activeSection.value])
  const isSectionLoading = computed(() => {
    if (!isNovelSectionKey(activeSection.value)) {
      return false
    }
    return activeQuery.value.isLoading.value || activeQuery.value.isFetching.value
  })
  const currentError = computed(() => {
    if (!isNovelSectionKey(activeSection.value)) {
      return null
    }
    const error = activeQuery.value.error.value
    if (!error) {
      return null
    }
    return error instanceof Error ? error.message : String(error)
  })

  const componentProps = computed(() => {
    const data = currentSectionData.value
    const editable = !isAdmin()

    switch (activeSection.value) {
      case 'overview':
        return {
          data: data || null,
          editable,
          characterCount: characterCount.value,
          chapterCount: chapterTotal.value,
        }
      case 'world_setting':
        return { data: data || null, editable }
      case 'characters':
        return { data: data || null, editable }
      case 'relationships':
        return { data: data || null, editable }
      case 'chapter_outline':
        return { outline: data?.chapter_outline || [], editable }
      case 'chapters':
        return {
          chapters: data?.chapters || [],
          chapterOutlines: novel.value?.blueprint?.chapter_outline || [],
          isAdmin: isAdmin(),
        }
      default:
        return {}
    }
  })

  return {
    currentComponent,
    isSectionLoading,
    currentError,
    componentProps,
    contentCardClass,
    componentContainerClass,
  }
}
