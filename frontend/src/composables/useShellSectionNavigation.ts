import { computed, defineAsyncComponent, onMounted, ref, type Component } from 'vue'
import { useRoute } from 'vue-router'
import { useNovelSectionQuery } from '@/queries/novel'
import type { AllSectionType, NovelSectionType } from '@/api/novel'

type SectionKey = AllSectionType

/**
 * NovelDetailShell 的分区导航状态机：
 * - 分区静态清单（sections）+ 懒加载组件映射（sectionLoaders/sectionComponents）
 * - 当前分区（activeSection），初始分区依据 route.query.section 解析
 * - 分区数据 query（overview/section）+ 切换/预取/加载/重载
 *
 * 侧栏 UI 副作用（非桌面态切换后收起侧栏）通过 onAfterSwitch 回调交还父组件，
 * 本 composable 不持有侧栏状态，保持内聚。
 */
export function useShellSectionNavigation(options: {
  projectId: string
  isAdmin: () => boolean
  onAfterSwitch?: () => void
}) {
  const route = useRoute()
  const { projectId, isAdmin, onAfterSwitch } = options

  const sections: Array<{ key: SectionKey; label: string }> = [
    { key: 'overview', label: '项目概览' },
    { key: 'world_setting', label: '世界设定' },
    { key: 'characters', label: '主要角色' },
    { key: 'relationships', label: '人物关系' },
    { key: 'chapter_outline', label: '章节大纲' },
    { key: 'emotion_curve', label: '情感曲线' },
    { key: 'foreshadowing', label: '伏笔管理' },
  ]

  const sectionKeys = sections.map((section) => section.key)

  const resolveInitialSection = (): SectionKey => {
    const rawSection = Array.isArray(route.query.section)
      ? route.query.section[0]
      : route.query.section
    return sectionKeys.includes(rawSection as SectionKey) ? (rawSection as SectionKey) : 'overview'
  }

  type AsyncSectionModule = { default: Component }

  const sectionLoaders: Record<SectionKey, () => Promise<AsyncSectionModule>> = {
    overview: () => import('@/components/novel-detail/OverviewSection.vue'),
    world_setting: () => import('@/components/novel-detail/WorldSettingSection.vue'),
    characters: () => import('@/components/novel-detail/CharactersSection.vue'),
    relationships: () => import('@/components/novel-detail/RelationshipsSection.vue'),
    chapter_outline: () => import('@/components/novel-detail/ChapterOutlineSection.vue'),
    chapters: () => import('@/components/novel-detail/ChaptersSection.vue'),
    emotion_curve: () => import('@/components/novel-detail/EmotionCurveSection.vue'),
    foreshadowing: () => import('@/components/novel-detail/ForeshadowingSection.vue'),
  }

  const sectionComponents = Object.fromEntries(
    Object.entries(sectionLoaders).map(([key, loader]) => [key, defineAsyncComponent(loader)]),
  ) as Record<SectionKey, ReturnType<typeof defineAsyncComponent>>

  const prefetchedSections = new Set<SectionKey>()
  const prefetchInFlight = new Map<SectionKey, Promise<void>>()

  const prefetchSectionComponent = (key: SectionKey) => {
    if (prefetchedSections.has(key)) {
      return
    }

    const existingRequest = prefetchInFlight.get(key)
    if (existingRequest) {
      return
    }

    const request = sectionLoaders[key]()
      .then(() => {
        prefetchedSections.add(key)
      })
      .catch(() => {
        // 预取失败不阻塞切换，点击分区后会自动重试。
      })
      .finally(() => {
        prefetchInFlight.delete(key)
      })

    prefetchInFlight.set(key, request)
  }

  const isNovelSectionKey = (section: SectionKey): section is NovelSectionType =>
    !['emotion_curve', 'foreshadowing'].includes(section)

  const activeSection = ref<SectionKey>(resolveInitialSection())
  const activeNovelSection = computed<NovelSectionType | null>(() =>
    isNovelSectionKey(activeSection.value) ? activeSection.value : null,
  )

  const overviewQuery = useNovelSectionQuery(() => projectId, 'overview', isAdmin)
  const sectionQuery = useNovelSectionQuery(
    () => projectId,
    () => activeNovelSection.value,
    isAdmin,
  )

  const loadSection = async (section: SectionKey, _force = false) => {
    if (!projectId) return

    if (!isNovelSectionKey(section)) {
      return
    }

    if (section === 'overview') {
      await overviewQuery.refetch()
      return
    }
    if (section === activeSection.value) {
      await sectionQuery.refetch()
    }
  }

  const reloadSection = (section: SectionKey, force = false) => {
    loadSection(section, force)
  }

  const switchSection = (section: SectionKey) => {
    activeSection.value = section
    prefetchSectionComponent(section)
    onAfterSwitch?.()
  }

  onMounted(() => {
    prefetchSectionComponent(activeSection.value)
  })

  return {
    sections,
    activeSection,
    sectionComponents,
    isNovelSectionKey,
    overviewQuery,
    sectionQuery,
    switchSection,
    prefetchSectionComponent,
    loadSection,
    reloadSection,
  }
}
