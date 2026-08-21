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
})
