// AIMETA P=HTTP错误归一化测试|R=非成功响应上下文与payload保留|NR=不测试业务API或鉴权跳转|E=test:api:http|X=internal|A=requestRaw_HttpRequestError|D=vitest,fetch|S=test|RD=../README.ai
import { afterEach, describe, expect, it, vi } from 'vitest'

import { HttpRequestError, requestRaw } from '@/api/http'

describe('requestRaw', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('保留 409 JSON 响应的状态和 payload', async () => {
    const url = '/api/writer/novels/project-1/concept/converse'
    const payload = {
      detail: {
        code: 'unfinished_inspiration',
        project_id: 'project-existing',
      },
    }
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(payload), {
      status: 409,
      headers: { 'content-type': 'application/json' },
    })))

    const error = await requestRaw(url).then(
      () => null,
      (reason: unknown) => reason,
    )

    expect(error).toBeInstanceOf(HttpRequestError)
    expect(error).toMatchObject({
      status: 409,
      code: 'http',
      url,
      payload,
    })
  })

  it('区分外部取消和请求超时', async () => {
    const controller = new AbortController()
    controller.abort()
    vi.stubGlobal('fetch', vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.signal?.aborted) {
        return Promise.reject(new DOMException('Aborted', 'AbortError'))
      }
      return Promise.resolve(Response.json({ ok: true }))
    }))

    await expect(requestRaw('/api/cancelled', { signal: controller.signal })).rejects.toMatchObject({
      message: '请求已取消',
      code: 'abort',
      url: '/api/cancelled',
    })
  })
})
