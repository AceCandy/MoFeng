// AIMETA P=小说Query组合函数_小说服务端状态管理|R=projects_project_chapter_mutations|NR=不含UI|E=query:novel|X=internal|A=useNovelProjectsQuery_useNovelProjectQuery|D=@tanstack/vue-query|S=net,cache|RD=./README.ai
import { computed, toValue, type MaybeRefOrGetter } from 'vue'
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query'
import {
  NovelAPI,
  OptimizerAPI,
  type ApplyOptimizationResponse,
  type AllSectionType,
  type Blueprint,
  type BlueprintGenerationResponse,
  type Chapter,
  type ChapterOutline,
  type ConverseResponse,
  type DeleteNovelsResponse,
  type EmotionCurveResponse,
  type Foreshadowing,
  type ForeshadowingDbItem,
  type ForeshadowingResponse,
  type NovelProject,
  type NovelProjectSummary,
  type NovelSectionResponse,
  type NovelSectionType,
  type OptimizeRecommendedVersionRequest,
  type OptimizeRequest,
  type OptimizeResponse,
} from '@/api/novel'
import { AdminAPI, type Chapter as AdminChapter } from '@/api/admin'
import { tasksQueryKeys } from '@/queries/tasks'

type ProjectIdSource = MaybeRefOrGetter<string | null | undefined>
type ChapterNumberSource = MaybeRefOrGetter<number | null | undefined>
type SectionSource = MaybeRefOrGetter<AllSectionType | null | undefined>
type AdminModeSource = MaybeRefOrGetter<boolean | null | undefined>

export const novelQueryKeys = {
  all: ['novels'] as const,
  projects: () => [...novelQueryKeys.all, 'projects'] as const,
  detail: (projectId: string) => [...novelQueryKeys.all, 'detail', projectId] as const,
  chapter: (projectId: string, chapterNumber: number) =>
    [...novelQueryKeys.detail(projectId), 'chapter', chapterNumber] as const,
  section: (projectId: string, section: NovelSectionType, isAdmin = false) =>
    [...novelQueryKeys.all, isAdmin ? 'admin' : 'user', 'section', projectId, section] as const,
  chapterDetail: (projectId: string, chapterNumber: number, isAdmin = false) =>
    [
      ...novelQueryKeys.all,
      isAdmin ? 'admin' : 'user',
      'chapter-detail',
      projectId,
      chapterNumber,
    ] as const,
  emotionCurve: (projectId: string) =>
    [...novelQueryKeys.detail(projectId), 'emotion-curve'] as const,
  foreshadowing: (projectId: string) =>
    [...novelQueryKeys.detail(projectId), 'foreshadowing'] as const,
}

const requireProjectId = (projectId: ProjectIdSource) => {
  const resolvedProjectId = toValue(projectId)
  if (!resolvedProjectId) {
    throw new Error('缺少项目 ID')
  }
  return resolvedProjectId
}

const requireChapterNumber = (chapterNumber: ChapterNumberSource) => {
  const resolvedChapterNumber = toValue(chapterNumber)
  if (resolvedChapterNumber === null || resolvedChapterNumber === undefined) {
    throw new Error('缺少章节编号')
  }
  return resolvedChapterNumber
}

const novelSections: NovelSectionType[] = [
  'overview',
  'world_setting',
  'characters',
  'relationships',
  'chapter_outline',
  'chapters',
]

const isNovelSection = (section: unknown): section is NovelSectionType =>
  typeof section === 'string' && novelSections.includes(section as NovelSectionType)

const requireNovelSection = (section: SectionSource) => {
  const resolvedSection = toValue(section)
  if (!isNovelSection(resolvedSection)) {
    throw new Error('缺少有效的详情分区')
  }
  return resolvedSection
}

const upsertChapter = (project: NovelProject, chapter: Chapter) => {
  if (!Array.isArray(project.chapters)) {
    project.chapters = []
  }

  const index = project.chapters.findIndex((item) => item.chapter_number === chapter.chapter_number)
  if (index >= 0) {
    project.chapters.splice(index, 1, chapter)
  } else {
    project.chapters.push(chapter)
  }
  project.chapters.sort((left, right) => left.chapter_number - right.chapter_number)
}

export function useNovelProjectsQuery() {
  return useQuery<NovelProjectSummary[]>({
    queryKey: novelQueryKeys.projects(),
    queryFn: () => NovelAPI.getAllNovels(),
  })
}

export function useNovelProjectQuery(projectId: ProjectIdSource) {
  return useQuery<NovelProject>({
    queryKey: computed(() => novelQueryKeys.detail(toValue(projectId) || '__missing__')),
    queryFn: () => NovelAPI.getNovel(requireProjectId(projectId)),
    enabled: computed(() => Boolean(toValue(projectId))),
  })
}

export function useNovelChapterQuery(
  projectId: ProjectIdSource,
  chapterNumber: ChapterNumberSource,
) {
  return useQuery<Chapter>({
    queryKey: computed(() =>
      novelQueryKeys.chapter(toValue(projectId) || '__missing__', toValue(chapterNumber) ?? -1),
    ),
    queryFn: () =>
      NovelAPI.getChapter(requireProjectId(projectId), requireChapterNumber(chapterNumber)),
    enabled: computed(
      () =>
        Boolean(toValue(projectId)) &&
        toValue(chapterNumber) !== null &&
        toValue(chapterNumber) !== undefined,
    ),
  })
}

export function useNovelSectionQuery(
  projectId: ProjectIdSource,
  section: SectionSource,
  isAdmin: AdminModeSource = false,
) {
  return useQuery<NovelSectionResponse>({
    queryKey: computed(() => {
      const resolvedProjectId = toValue(projectId) || '__missing__'
      const resolvedSection = isNovelSection(toValue(section))
        ? (toValue(section) as NovelSectionType)
        : 'overview'
      return novelQueryKeys.section(resolvedProjectId, resolvedSection, Boolean(toValue(isAdmin)))
    }),
    queryFn: () => {
      const resolvedProjectId = requireProjectId(projectId)
      const resolvedSection = requireNovelSection(section)
      return toValue(isAdmin)
        ? AdminAPI.getNovelSection(resolvedProjectId, resolvedSection)
        : NovelAPI.getSection(resolvedProjectId, resolvedSection)
    },
    enabled: computed(() => Boolean(toValue(projectId)) && isNovelSection(toValue(section))),
  })
}

export function useNovelChapterDetailQuery(
  projectId: ProjectIdSource,
  chapterNumber: ChapterNumberSource,
  isAdmin: AdminModeSource = false,
) {
  return useQuery<Chapter | AdminChapter>({
    queryKey: computed(() =>
      novelQueryKeys.chapterDetail(
        toValue(projectId) || '__missing__',
        toValue(chapterNumber) ?? -1,
        Boolean(toValue(isAdmin)),
      ),
    ),
    queryFn: () =>
      toValue(isAdmin)
        ? AdminAPI.getNovelChapter(requireProjectId(projectId), requireChapterNumber(chapterNumber))
        : NovelAPI.getChapter(requireProjectId(projectId), requireChapterNumber(chapterNumber)),
    enabled: computed(
      () =>
        Boolean(toValue(projectId)) &&
        toValue(chapterNumber) !== null &&
        toValue(chapterNumber) !== undefined,
    ),
  })
}

export function useEmotionCurveQuery(projectId: ProjectIdSource) {
  return useQuery<EmotionCurveResponse>({
    queryKey: computed(() => novelQueryKeys.emotionCurve(toValue(projectId) || '__missing__')),
    queryFn: () => NovelAPI.getEmotionCurve(requireProjectId(projectId)),
    enabled: computed(() => Boolean(toValue(projectId))),
  })
}

const mapDbStatusToUiStatus = (
  status?: string,
  resolvedChapter?: number | null,
): Foreshadowing['status'] => {
  if (status === 'resolved' || !!resolvedChapter) return 'paid_off'
  if (status === 'abandoned' || status === 'overdue') return 'overdue'
  return 'planted'
}

const mapDbTypeToImportance = (type?: string): Foreshadowing['importance'] => {
  const normalizedType = (type || '').toLowerCase()
  if (['long', 'long_term', 'core', 'major'].includes(normalizedType)) {
    return 'long'
  }
  if (['short', 'short_term', 'hint', 'minor'].includes(normalizedType)) {
    return 'short'
  }
  return 'medium'
}

const mapForeshadowingDbItem = (item: ForeshadowingDbItem): Foreshadowing => {
  const chapterNumber = Number(item.chapter_number || 0)
  return {
    id: String(item.id),
    description: item.content || item.author_note || '未命名伏笔',
    planted_chapter: chapterNumber,
    planted_chapter_title: `第${chapterNumber}章`,
    expected_payoff_chapter: undefined,
    actual_payoff_chapter: item.resolved_chapter_number ?? undefined,
    status: mapDbStatusToUiStatus(item.status, item.resolved_chapter_number),
    importance: mapDbTypeToImportance(item.type),
  }
}

const summarizeForeshadowings = (
  projectId: string,
  list: Foreshadowing[],
): ForeshadowingResponse => ({
  project_id: projectId,
  project_title: '',
  total_foreshadowings: list.length,
  planted_count: list.filter((item) => item.status === 'planted').length,
  paid_off_count: list.filter((item) => item.status === 'paid_off').length,
  overdue_count: list.filter((item) => item.status === 'overdue').length,
  foreshadowings: list,
})

const loadForeshadowingWithFallback = async (projectId: string) => {
  let storeError: string | null = null

  try {
    const storeResponse = await NovelAPI.getForeshadowings(projectId)
    const dbItems = Array.isArray(storeResponse.data) ? storeResponse.data : []
    const storeForeshadowings = dbItems.map(mapForeshadowingDbItem)
    if (storeForeshadowings.length > 0) {
      return summarizeForeshadowings(projectId, storeForeshadowings)
    }

    try {
      const analyticsResponse = await NovelAPI.getForeshadowingAnalytics(projectId)
      return summarizeForeshadowings(projectId, analyticsResponse.foreshadowings || [])
    } catch {
      return summarizeForeshadowings(projectId, [])
    }
  } catch (error) {
    storeError = error instanceof Error ? error.message : String(error)
  }

  try {
    const analyticsResponse = await NovelAPI.getForeshadowingAnalytics(projectId)
    return summarizeForeshadowings(projectId, analyticsResponse.foreshadowings || [])
  } catch (analyticsError) {
    const analyticsMessage =
      analyticsError instanceof Error ? analyticsError.message : String(analyticsError)
    throw new Error(`${storeError || '伏笔库请求失败'}；自动识别接口也失败：${analyticsMessage}`)
  }
}

export function useForeshadowingQuery(projectId: ProjectIdSource) {
  return useQuery<ForeshadowingResponse>({
    queryKey: computed(() => novelQueryKeys.foreshadowing(toValue(projectId) || '__missing__')),
    queryFn: () => loadForeshadowingWithFallback(requireProjectId(projectId)),
    enabled: computed(() => Boolean(toValue(projectId))),
  })
}

export function useNovelMutationRefresh(projectId?: ProjectIdSource) {
  const queryClient = useQueryClient()

  const resolveProjectId = (fallbackProjectId?: string) =>
    fallbackProjectId || (projectId ? toValue(projectId) : undefined) || null

  const refreshProjects = () =>
    queryClient.invalidateQueries({ queryKey: novelQueryKeys.projects() })

  const refreshProjectQueries = async (fallbackProjectId?: string) => {
    const resolvedProjectId = resolveProjectId(fallbackProjectId)
    if (!resolvedProjectId) {
      return
    }

    await Promise.all([
      queryClient.invalidateQueries({ queryKey: novelQueryKeys.detail(resolvedProjectId) }),
      refreshProjects(),
    ])
  }

  const refreshChapter = async (fallbackProjectId: string | undefined, chapterNumber: number) => {
    const resolvedProjectId = resolveProjectId(fallbackProjectId)
    if (!resolvedProjectId) {
      return
    }

    await queryClient.invalidateQueries({
      queryKey: novelQueryKeys.chapter(resolvedProjectId, chapterNumber),
    })
  }

  const setProjectCache = (project: NovelProject) => {
    queryClient.setQueryData(novelQueryKeys.detail(project.id), project)
  }

  const upsertChapterInProjectCache = (fallbackProjectId: string | undefined, chapter: Chapter) => {
    const resolvedProjectId = resolveProjectId(fallbackProjectId)
    if (!resolvedProjectId) {
      return
    }

    queryClient.setQueryData<NovelProject>(
      novelQueryKeys.detail(resolvedProjectId),
      (currentProject) => {
        if (!currentProject) {
          return currentProject
        }
        const chaptersCopy = [...(currentProject.chapters || [])]
        const index = chaptersCopy.findIndex((item) => item.chapter_number === chapter.chapter_number)
        if (index >= 0) {
          chaptersCopy[index] = chapter
        } else {
          chaptersCopy.push(chapter)
        }
        chaptersCopy.sort((left, right) => left.chapter_number - right.chapter_number)

        return {
          ...currentProject,
          chapters: chaptersCopy,
        }
      },
    )
    queryClient.setQueryData(
      novelQueryKeys.chapter(resolvedProjectId, chapter.chapter_number),
      chapter,
    )
  }

  return {
    queryClient,
    refreshProjects,
    refreshProjectQueries,
    refreshChapter,
    setProjectCache,
    upsertChapterInProjectCache,
  }
}

export function useCreateNovelMutation() {
  const { refreshProjects, setProjectCache } = useNovelMutationRefresh()

  return useMutation({
    mutationFn: (payload: { title: string; initialPrompt: string }) =>
      NovelAPI.createNovel(payload.title, payload.initialPrompt),
    onSuccess: async (project) => {
      setProjectCache(project)
      await refreshProjects()
    },
  })
}

export function useImportNovelMutation() {
  const { refreshProjects } = useNovelMutationRefresh()

  return useMutation({
    mutationFn: (file: File) => NovelAPI.importNovel(file),
    onSuccess: async () => {
      await refreshProjects()
    },
  })
}

export function useConverseConceptStreamMutation(projectId: ProjectIdSource) {
  const { refreshProjectQueries } = useNovelMutationRefresh(projectId)

  return useMutation<
    ConverseResponse,
    Error,
    {
      userInput: any
      conversationState: any
      onDelta?: (delta: string) => void
    }
  >({
    mutationFn: ({ userInput, conversationState, onDelta }) =>
      NovelAPI.converseConceptStream(
        requireProjectId(projectId),
        userInput,
        conversationState,
        onDelta,
      ),
    onSuccess: () => {
      // 选项来自当前流式响应，缓存刷新只做后台同步，避免拖住下一轮输入。
      void refreshProjectQueries().catch((error) => {
        console.error('刷新概念对话缓存失败:', error)
      })
    },
  })
}

export function useGenerateBlueprintMutation(projectId: ProjectIdSource) {
  return useMutation<BlueprintGenerationResponse, Error, void>({
    mutationFn: () => NovelAPI.generateBlueprint(requireProjectId(projectId)),
  })
}

export function useSaveBlueprintMutation(projectId: ProjectIdSource) {
  const { setProjectCache, refreshProjectQueries } = useNovelMutationRefresh(projectId)

  return useMutation<NovelProject, Error, Blueprint>({
    mutationFn: (blueprint) => NovelAPI.saveBlueprint(requireProjectId(projectId), blueprint),
    onSuccess: async (project) => {
      setProjectCache(project)
      await refreshProjectQueries(project.id)
    },
  })
}

export function useUpdateBlueprintMutation(projectId: ProjectIdSource) {
  const { setProjectCache, refreshProjectQueries } = useNovelMutationRefresh(projectId)

  return useMutation<NovelProject, Error, Record<string, any>>({
    mutationFn: (data) => NovelAPI.updateBlueprint(requireProjectId(projectId), data),
    onSuccess: async (project) => {
      setProjectCache(project)
      await refreshProjectQueries(project.id)
    },
  })
}

export function useDeleteNovelsMutation() {
  const { queryClient, refreshProjects } = useNovelMutationRefresh()

  return useMutation<DeleteNovelsResponse, Error, string[]>({
    mutationFn: (projectIds) => NovelAPI.deleteNovels(projectIds),
    onSuccess: async (_response, projectIds) => {
      queryClient.setQueryData<NovelProjectSummary[]>(
        novelQueryKeys.projects(),
        (currentProjects) =>
          currentProjects?.filter((project) => !projectIds.includes(project.id)) ?? currentProjects,
      )
      projectIds.forEach((projectId) => {
        queryClient.removeQueries({ queryKey: novelQueryKeys.detail(projectId) })
      })
      await refreshProjects()
    },
  })
}

export function useGenerateChapterMutation(projectId: ProjectIdSource) {
  const { setProjectCache, refreshProjectQueries } = useNovelMutationRefresh(projectId)

  return useMutation({
    mutationFn: (payload: number | { chapterNumber: number; fromNode?: string }) => {
      const args = typeof payload === 'number' ? { chapterNumber: payload } : payload
      return NovelAPI.generateChapter(
        requireProjectId(projectId),
        args.chapterNumber,
        args.fromNode,
      )
    },
    onSuccess: async (project) => {
      setProjectCache(project)
      await refreshProjectQueries(project.id)
    },
  })
}

export function useEvaluateChapterMutation(projectId: ProjectIdSource) {
  const { setProjectCache, refreshProjectQueries } = useNovelMutationRefresh(projectId)

  return useMutation({
    mutationFn: (chapterNumber: number) =>
      NovelAPI.evaluateChapter(requireProjectId(projectId), chapterNumber),
    onSuccess: async (project) => {
      setProjectCache(project)
      await refreshProjectQueries(project.id)
    },
  })
}

export function useAnalyzeEmotionMutation(projectId: ProjectIdSource) {
  const queryClient = useQueryClient()

  return useMutation<EmotionCurveResponse, Error, void>({
    mutationFn: () => NovelAPI.analyzeEmotionAI(requireProjectId(projectId)),
    onSuccess: (emotionCurve) => {
      queryClient.setQueryData(novelQueryKeys.emotionCurve(requireProjectId(projectId)), emotionCurve)
      return queryClient.invalidateQueries({
        queryKey: novelQueryKeys.emotionCurve(requireProjectId(projectId)),
      })
    },
  })
}

export function useOptimizeChapterMutation() {
  return useMutation<OptimizeResponse, Error, OptimizeRequest>({
    mutationFn: (payload) => OptimizerAPI.optimizeChapter(payload),
  })
}

export function useOptimizeRecommendedVersionMutation() {
  return useMutation<OptimizeResponse, Error, OptimizeRecommendedVersionRequest>({
    mutationFn: (payload) => OptimizerAPI.optimizeRecommendedVersion(payload),
  })
}

export function useApplyOptimizationMutation(projectId?: ProjectIdSource) {
  const { refreshChapter, refreshProjectQueries } = useNovelMutationRefresh(projectId)

  return useMutation<
    ApplyOptimizationResponse,
    Error,
    { projectId: string; chapterNumber: number; optimizedContent: string }
  >({
    mutationFn: (payload) =>
      OptimizerAPI.applyOptimization(
        payload.projectId,
        payload.chapterNumber,
        payload.optimizedContent,
      ),
    onSuccess: async (_response, payload) => {
      await refreshChapter(payload.projectId, payload.chapterNumber)
      await refreshProjectQueries(payload.projectId)
    },
  })
}

export function useConfirmFinalizeChapterMutation(projectId: ProjectIdSource) {
  const { refreshChapter, refreshProjectQueries, upsertChapterInProjectCache } =
    useNovelMutationRefresh(projectId)

  return useMutation({
    mutationFn: (payload: {
      chapterNumber: number
      selectedVersionIndex: number
      editedContent?: string | null
      skipVectorUpdate?: boolean
    }) =>
      NovelAPI.confirmFinalizeChapter(requireProjectId(projectId), payload.chapterNumber, {
        selected_version_index: payload.selectedVersionIndex,
        edited_content: payload.editedContent ?? null,
        skip_vector_update: payload.skipVectorUpdate ?? false,
      }),
    onSuccess: async (response, payload) => {
      upsertChapterInProjectCache(undefined, response.chapter)
      await refreshChapter(undefined, payload.chapterNumber)
      await refreshProjectQueries(requireProjectId(projectId))
    },
  })
}

export function useUpdateChapterOutlineMutation(projectId: ProjectIdSource) {
  const { setProjectCache, refreshProjectQueries } = useNovelMutationRefresh(projectId)

  return useMutation({
    mutationFn: (chapterOutline: ChapterOutline) =>
      NovelAPI.updateChapterOutline(requireProjectId(projectId), chapterOutline),
    onSuccess: async (project) => {
      setProjectCache(project)
      await refreshProjectQueries(project.id)
    },
  })
}

export function useDeleteChapterMutation(projectId: ProjectIdSource) {
  const { setProjectCache, refreshProjectQueries } = useNovelMutationRefresh(projectId)

  return useMutation({
    mutationFn: (payload: {
      chapterNumbers: number[]
      deleteArtifactsConfirmed?: boolean
      confirmationText?: string | null
    }) =>
      NovelAPI.deleteChapter(requireProjectId(projectId), {
        chapter_numbers: payload.chapterNumbers,
        delete_artifacts_confirmed: payload.deleteArtifactsConfirmed ?? false,
        confirmation_text: payload.confirmationText ?? null,
      }),
    onSuccess: async (project) => {
      setProjectCache(project)
      await refreshProjectQueries(project.id)
    },
  })
}

export function useGenerateChapterOutlineMutation(projectId: ProjectIdSource) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (payload: { startChapter: number; numChapters: number }) =>
      NovelAPI.generateChapterOutline(
        requireProjectId(projectId),
        payload.startChapter,
        payload.numChapters,
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: tasksQueryKeys.all })
    },
  })
}

export function useEditChapterContentMutation(projectId: ProjectIdSource) {
  const { refreshChapter, upsertChapterInProjectCache } = useNovelMutationRefresh(projectId)

  return useMutation({
    mutationFn: (payload: { chapterNumber: number; content: string }) =>
      NovelAPI.editChapterContent(
        requireProjectId(projectId),
        payload.chapterNumber,
        payload.content,
      ),
    onSuccess: async (chapter) => {
      upsertChapterInProjectCache(undefined, chapter)
      await refreshChapter(undefined, chapter.chapter_number)
    },
  })
}
