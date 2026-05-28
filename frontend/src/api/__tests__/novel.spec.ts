import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { NovelAPI } from '@/api/novel'

const makeProjectResponse = () => ({
  id: 'project-1',
  title: '测试项目',
  initial_prompt: '测试',
  chapters: [],
  conversation_history: [],
})

describe('NovelAPI', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('为章节生成请求设置覆盖后端长耗时写作阶段的超时', async () => {
    const fetchMock = vi.fn(async () =>
      new Response(JSON.stringify(makeProjectResponse()), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)
    const setTimeoutSpy = vi.spyOn(window, 'setTimeout')

    await NovelAPI.generateChapter('project-1', 3)

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/writer/novels/project-1/chapters/generate',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ chapter_number: 3 }),
      }),
    )
    expect(setTimeoutSpy).toHaveBeenCalledWith(expect.any(Function), expect.any(Number))
    const timeoutMs = Number(setTimeoutSpy.mock.calls[0]?.[1])
    expect(timeoutMs).toBeGreaterThanOrEqual(600_000)
  })
})
