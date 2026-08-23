// AIMETA P=创作上下文前端合同测试|R=GET_PATCH_查询缓存替换_稳定排序|NR=不测试页面恢复策略|E=test:query:creation-contexts|X=internal|A=CreationContextAPI_usePatchCreationContextMutation|D=vitest,vue-query|S=test|RD=../README.ai
import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'
import { createApp, defineComponent } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  CreationContextAPI,
  type CreationContext,
} from '@/api/creationContexts'
import {
  creationContextQueryKeys,
  useCreationContextsQuery,
  usePatchCreationContextMutation,
} from '@/queries/creationContexts'
import { useAuthStore } from '@/stores/auth'

const context = (
  projectId: string,
  updatedAt: string,
  draft: string | null = null,
): CreationContext => ({
  user_id: 1,
  project_id: projectId,
  surface: 'inspiration',
  chapter_number: null,
  desk_section: null,
  inspiration_draft: draft,
  inspiration_turn: 0,
  updated_at: updatedAt,
})

const mountContexts = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  let query!: ReturnType<typeof useCreationContextsQuery>
  let mutation!: ReturnType<typeof usePatchCreationContextMutation>
  const app = createApp(defineComponent({
    setup() {
      query = useCreationContextsQuery()
      mutation = usePatchCreationContextMutation()
      return () => null
    },
  }))
  app.use(VueQueryPlugin, { queryClient })
  app.mount(document.createElement('div'))
  return { app, mutation, query, queryClient }
}

describe('creation contexts', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    useAuthStore().setToken('test-token')
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
    localStorage.clear()
  })

  it('调用鉴权 GET 与字段级 PATCH，并保留 null', async () => {
    const current = context('project-a', '2026-08-24T08:00:00Z')
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify([current]), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(current), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(CreationContextAPI.getContexts()).resolves.toEqual([current])
    await expect(CreationContextAPI.patchContext('project-a', {
      inspiration_draft: null,
      inspiration_turn: 1,
    })).resolves.toEqual(current)

    expect(fetchMock.mock.calls[0]?.[0]).toBe('/api/creation-contexts')
    expect(fetchMock.mock.calls[1]?.[0]).toBe('/api/creation-contexts/project-a')
    const options = fetchMock.mock.calls[1]?.[1] as RequestInit
    expect(options.method).toBe('PATCH')
    expect(JSON.parse(String(options.body))).toEqual({
      inspiration_draft: null,
      inspiration_turn: 1,
    })
  })

  it('mutation 用服务端最后响应替换项目缓存，并按稳定次序排序', async () => {
    const initial = [
      context('project-b', '2026-08-24T08:00:00Z', '旧稿'),
      context('project-a', '2026-08-24T08:00:00Z'),
    ]
    const latest = context('project-b', '2026-08-24T09:00:00Z', '最后写入')
    vi.spyOn(CreationContextAPI, 'getContexts').mockResolvedValue(initial)
    vi.spyOn(CreationContextAPI, 'patchContext').mockResolvedValue(latest)
    const mounted = mountContexts()

    try {
      await vi.waitFor(() => expect(mounted.query.data.value).toEqual(initial))
      await mounted.mutation.mutateAsync({
        projectId: 'project-b',
        patch: { inspiration_draft: '最后写入', inspiration_turn: 0 },
      })

      expect(mounted.queryClient.getQueryData(creationContextQueryKeys.list())).toEqual([
        latest,
        initial[1],
      ])
      expect(CreationContextAPI.patchContext).toHaveBeenCalledWith('project-b', {
        inspiration_draft: '最后写入',
        inspiration_turn: 0,
      })
    } finally {
      mounted.app.unmount()
    }
  })
})
