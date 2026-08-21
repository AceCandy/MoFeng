// AIMETA P=小说Mutation缓存测试|R=章节重置缓存_概念对话后台刷新|NR=不测试HTTP实现或页面状态|E=test:query:novel|X=internal|A=useResetChapterMutation_useConverseConceptStreamMutation|D=vitest,vue-query|S=test|RD=../README.ai
import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'
import { createApp, defineComponent } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  NovelAPI,
  type Chapter,
  type ConverseResponse,
  type NovelProject,
} from '@/api/novel'
import {
  novelQueryKeys,
  useConverseConceptStreamMutation,
  useNovelChapterQuery,
  useResetChapterMutation,
} from '@/queries/novel'

const PROJECT_ID = 'reset-cache-project'
const CHAPTER_NUMBER = 3

const mountMutation = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  let mutation!: ReturnType<typeof useResetChapterMutation>
  let chapterQuery!: ReturnType<typeof useNovelChapterQuery>
  const app = createApp(defineComponent({
    setup() {
      mutation = useResetChapterMutation(PROJECT_ID)
      chapterQuery = useNovelChapterQuery(PROJECT_ID, CHAPTER_NUMBER)
      return () => null
    },
  }))
  app.use(VueQueryPlugin, { queryClient })
  app.mount(document.createElement('div'))
  return { app, mutation, chapterQuery, queryClient }
}

const mountConverseMutation = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  let mutation!: ReturnType<typeof useConverseConceptStreamMutation>
  const app = createApp(defineComponent({
    setup() {
      mutation = useConverseConceptStreamMutation(PROJECT_ID)
      return () => null
    },
  }))
  app.use(VueQueryPlugin, { queryClient })
  app.mount(document.createElement('div'))
  return { app, mutation, queryClient }
}

describe('novel queries', () => {
  afterEach(() => vi.restoreAllMocks())

  it('重置章节后立即用响应替换旧 Chapter 缓存', async () => {
    const resetChapter = {
      chapter_number: CHAPTER_NUMBER,
      title: '第三章',
      summary: '章节大纲保留',
      goals: '',
      highlights: [],
      character_states: {},
      content: null,
      versions: null,
      generation_status: 'not_generated',
    } as Chapter
    const project = {
      id: PROJECT_ID,
      title: '缓存重置',
      initial_prompt: '',
      conversation_history: [],
      chapters: [resetChapter],
    } as NovelProject
    const staleChapter = {
      ...resetChapter,
      content: '重置前仍在页面显示的旧正文',
      versions: ['重置前仍在页面显示的旧正文'],
      generation_status: 'finalizing',
    } as Chapter
    vi.spyOn(NovelAPI, 'getChapter').mockResolvedValue(staleChapter)
    vi.spyOn(NovelAPI, 'resetChapter').mockResolvedValue(project)
    const mounted = mountMutation()
    const invalidate = vi.spyOn(mounted.queryClient, 'invalidateQueries')
    await vi.waitFor(() => expect(mounted.chapterQuery.data.value).toEqual(staleChapter))

    await mounted.mutation.mutateAsync(CHAPTER_NUMBER)

    expect(mounted.chapterQuery.data.value).toEqual(resetChapter)
    expect(mounted.queryClient.getQueryData(
      novelQueryKeys.chapter(PROJECT_ID, CHAPTER_NUMBER),
    )).toEqual(resetChapter)
    expect(mounted.queryClient.getQueryData(novelQueryKeys.detail(PROJECT_ID))).toEqual(project)
    expect(invalidate).toHaveBeenCalledWith({ queryKey: novelQueryKeys.projects() })
    mounted.app.unmount()
  })

  it('概念对话完成后不等待后台缓存刷新', async () => {
    const response = {
      ai_message: '请选择下一步',
      conversation_state: { step: 2 },
      is_complete: false,
      ready_for_blueprint: false,
      ui_control: { type: 'single_choice' },
    } satisfies ConverseResponse
    vi.spyOn(NovelAPI, 'converseConceptStream').mockResolvedValue(response)
    const mounted = mountConverseMutation()
    let releaseRefresh!: () => void
    const refreshPending = new Promise<void>((resolve) => {
      releaseRefresh = resolve
    })
    const invalidate = vi
      .spyOn(mounted.queryClient, 'invalidateQueries')
      .mockReturnValue(refreshPending)
    const resolved = vi.fn()

    try {
      const mutationPromise = mounted.mutation.mutateAsync({
        userInput: { id: 'tone', value: '沉稳' },
        conversationState: { step: 1 },
      })
      void mutationPromise.then(resolved)

      await vi.waitFor(() => expect(invalidate).toHaveBeenCalledTimes(2))
      await vi.waitFor(() => expect(resolved).toHaveBeenCalledWith(response))
      await expect(mutationPromise).resolves.toEqual(response)
    } finally {
      releaseRefresh()
      mounted.app.unmount()
    }
  })
})
