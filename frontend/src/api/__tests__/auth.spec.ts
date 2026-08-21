// AIMETA P=认证API契约测试|R=请求映射_刷新令牌_共享错误边界|NR=不测试Query或页面交互|E=test:api:auth|X=internal|A=authApiFunctions|D=vitest,fetch|S=test|RD=../README.ai
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  getAuthOptions,
  getCurrentUser,
  loginWithPassword,
  registerUser,
  sendVerificationCode,
} from '@/api/auth'
import { HttpRequestError } from '@/api/http'

describe('api/auth 共享 HTTP 边界', () => {
  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('保持五个认证接口的请求、响应和刷新令牌契约', async () => {
    const timeoutSpy = vi.spyOn(window, 'setTimeout')
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url.endsWith('/options')) {
        return Response.json({ allow_registration: false, enable_linuxdo_login: true })
      }
      if (url.endsWith('/token')) {
        return Response.json({ access_token: 'access-token', must_change_password: true })
      }
      if (url.endsWith('/users/me')) {
        return Response.json(
          { id: 7, username: 'reader' },
          { headers: { 'X-Token-Refresh': 'refreshed-token' } },
        )
      }
      return new Response(null, { status: 204 })
    })
    vi.stubGlobal('fetch', fetchMock)

    await expect(getAuthOptions()).resolves.toEqual({
      allow_registration: false,
      enable_linuxdo_login: true,
    })
    await expect(loginWithPassword({ username: 'reader', password: 'secret' })).resolves.toEqual({
      accessToken: 'access-token',
      mustChangePassword: true,
    })
    await expect(getCurrentUser('explicit-token')).resolves.toEqual({
      refreshedToken: 'refreshed-token',
      data: {
        id: 7,
        username: 'reader',
        is_admin: false,
        must_change_password: false,
      },
    })
    await expect(sendVerificationCode('reader+tag@example.com')).resolves.toBeUndefined()
    await expect(registerUser({
      username: 'reader',
      email: 'reader@example.com',
      password: 'secret12',
      verification_code: '123456',
    })).resolves.toBeUndefined()

    expect(fetchMock.mock.calls.map(([url]) => String(url))).toEqual([
      '/api/auth/options',
      '/api/auth/token',
      '/api/auth/users/me',
      '/api/auth/send-code?email=reader%2Btag%40example.com',
      '/api/auth/users',
    ])

    const loginOptions = fetchMock.mock.calls[1]?.[1] as RequestInit
    expect(loginOptions.method).toBe('POST')
    expect(loginOptions.body).toBeInstanceOf(URLSearchParams)
    expect(String(loginOptions.body)).toBe('grant_type=password&username=reader&password=secret')
    expect(new Headers(loginOptions.headers).has('Content-Type')).toBe(false)

    const userOptions = fetchMock.mock.calls[2]?.[1] as RequestInit
    expect(new Headers(userOptions.headers).get('Authorization')).toBe('Bearer explicit-token')

    const registerOptions = fetchMock.mock.calls[4]?.[1] as RequestInit
    expect(new Headers(registerOptions.headers).get('Content-Type')).toBe('application/json')
    expect(JSON.parse(String(registerOptions.body))).toMatchObject({
      username: 'reader',
      verification_code: '123456',
    })
    expect(timeoutSpy.mock.calls.map(([, delay]) => delay)).toEqual([
      10_000,
      15_000,
      10_000,
      15_000,
      15_000,
    ])
  })

  it('透传服务端错误上下文并保留无详情状态码文案', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(Response.json({ detail: '账号或密码错误' }, { status: 401 }))
      .mockResolvedValueOnce(Response.json({}, { status: 400 }))
      .mockResolvedValueOnce(new Response('上游不可用', { status: 502 }))
    vi.stubGlobal('fetch', fetchMock)

    const detailError = await loginWithPassword({ username: 'reader', password: 'bad' }).catch(
      (error: unknown) => error,
    )
    expect(detailError).toMatchObject({
      message: '账号或密码错误',
      status: 401,
      code: 'http',
      payload: { detail: '账号或密码错误' },
    })

    await expect(sendVerificationCode('reader@example.com')).rejects.toThrow(
      '请求失败，状态码: 400',
    )
    await expect(registerUser({
      username: 'reader',
      email: 'reader@example.com',
      password: 'secret12',
      verification_code: '123456',
    })).rejects.toMatchObject({
      message: '上游不可用',
      status: 502,
      payload: '上游不可用',
    })
  })

  it('将网络错误归一化为 HttpRequestError', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new TypeError('Failed to fetch') }))

    await expect(loginWithPassword({ username: 'reader', password: 'secret' })).rejects.toMatchObject({
      message: '网络连接异常，请检查网络后重试',
      code: 'network',
    })
  })

  it('请求超时时中止 fetch 并返回 timeout 错误码', async () => {
    vi.useFakeTimers()
    vi.stubGlobal('fetch', vi.fn((_input: RequestInfo | URL, init?: RequestInit) => new Promise(
      (_resolve, reject) => {
        init?.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
      },
    )))

    const request = loginWithPassword({ username: 'reader', password: 'secret' })
    const rejection = expect(request).rejects.toMatchObject({
      message: '请求超时，请稍后重试',
      code: 'timeout',
    })
    await vi.advanceTimersByTimeAsync(15_000)

    await rejection
  })

  it('保留 options fallback 和登录缺少 access token 的失败契约', async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockResolvedValueOnce(Response.json({ must_change_password: false }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(getAuthOptions()).resolves.toEqual({
      allow_registration: true,
      enable_linuxdo_login: false,
    })
    await expect(loginWithPassword({ username: 'reader', password: 'secret' })).rejects.toThrow(
      'Missing access token in login response',
    )
  })
})
