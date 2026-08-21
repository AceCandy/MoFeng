// AIMETA P=小说API流式与任务测试|R=SSE游标_final终止_任务提交|NR=不测试Query或页面状态|E=test:api:novel|X=internal|A=NovelAPI_readSSESubscription|D=vitest,fetch,ReadableStream|S=test|RD=../README.ai
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { NovelAPI, readSSESubscription, type ConverseResponse } from '@/api/novel'

const makeTaskResponse = () => ({
  id: 'chapter-job-1',
  user_id: 1,
  project_id: 'project-1',
  task_type: 'chapter_workflow',
  title: '生成第三章正文',
  status: 'queued',
  progress: 0,
  log_entries: [],
  created_at: '2026-07-28T00:00:00Z',
  updated_at: '2026-07-28T00:00:00Z',
})

describe('NovelAPI', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('解析 SSE event id 供 durable cursor 续传', async () => {
    const messages: Array<{ id: string | null; event: string; data: unknown }> = []
    const response = new Response(
      new ReadableStream({
        start(controller) {
          controller.enqueue(
            new TextEncoder().encode('id: 42\nevent: task\ndata: {"cursor":42}\n\n'),
          )
          controller.close()
        },
      }),
    )

    await readSSESubscription(response, {
      onMessage: (message) => messages.push(message),
      stopEvents: [],
    })

    expect(messages).toEqual([
      { id: '42', event: 'task', data: { cursor: 42 } },
    ])
  })

  it('章节生成只提交 durable job，不再占用长 HTTP 请求', async () => {
    const fetchMock = vi.fn(async () =>
      new Response(JSON.stringify(makeTaskResponse()), {
        status: 202,
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
    expect(timeoutMs).toBe(60_000)
  })

  it('概念对话收到 final 后不等待连接关闭', async () => {
    const finalPayload = {
      ai_message: '下一轮可以输入',
      conversation_state: { step: 2 },
      is_complete: false,
      ready_for_blueprint: false,
      ui_control: { type: 'text_input' },
    } satisfies ConverseResponse
    const cancel = vi.fn()
    const response = new Response(new ReadableStream({
      start(controller) {
        controller.enqueue(
          new TextEncoder().encode(`event: final\ndata: ${JSON.stringify(finalPayload)}\n\n`),
        )
      },
      cancel,
    }))
    vi.stubGlobal('fetch', vi.fn(async () => response))

    await expect(
      NovelAPI.converseConceptStream('project-1', null, { step: 1 }),
    ).resolves.toEqual(finalPayload)
    await vi.waitFor(() => expect(cancel).toHaveBeenCalledOnce())
  })
})
