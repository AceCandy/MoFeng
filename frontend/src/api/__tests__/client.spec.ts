import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

// 提前定义 mock 工厂，避免与被测模块的 import 顺序耦合
const { requestJsonMock, requestRawMock, HttpRequestErrorMock } = vi.hoisted(() => ({
  requestJsonMock: vi.fn(),
  requestRawMock: vi.fn(),
  HttpRequestErrorMock: class HttpRequestError extends Error {
    status: number | null
    constructor(message: string, status?: number) {
      super(message)
      this.name = 'HttpRequestError'
      this.status = status ?? null
    }
  },
}))

vi.mock('@/api/http', () => ({
  HttpRequestError: HttpRequestErrorMock,
  requestJson: requestJsonMock,
  requestRaw: requestRawMock,
}))

const { pushMock } = vi.hoisted(() => ({ pushMock: vi.fn() }))
vi.mock('@/router', () => ({ default: { push: pushMock } }))

import { useAuthStore } from '@/stores/auth'
import { authJson, authRaw } from '@/api/client'

describe('api/client 鉴权收敛', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    requestJsonMock.mockReset()
    requestRawMock.mockReset()
    pushMock.mockReset()
  })

  it('已认证时注入 Authorization: Bearer <token>', async () => {
    useAuthStore().setToken('abc123')
    requestJsonMock.mockResolvedValue({ ok: true })
    await authJson('/api/x')
    const opts = requestJsonMock.mock.calls[0][1]
    expect(opts.headers.get('Authorization')).toBe('Bearer abc123')
  })

  it('未认证时不注入 Authorization', async () => {
    requestJsonMock.mockResolvedValue({ ok: true })
    await authJson('/api/x')
    const opts = requestJsonMock.mock.calls[0][1]
    expect(opts.headers.get('Authorization')).toBeNull()
  })

  it('401 时登出并跳转登录页', async () => {
    useAuthStore().setToken('abc123')
    requestJsonMock.mockRejectedValue(new HttpRequestErrorMock('未授权', 401))
    await expect(authJson('/api/x')).rejects.toThrow('会话已过期')
    expect(pushMock).toHaveBeenCalledWith('/login')
    expect(useAuthStore().token).toBeNull()
  })

  it('非 401 错误原样抛出，不触发登出', async () => {
    useAuthStore().setToken('abc123')
    requestJsonMock.mockRejectedValue(new HttpRequestErrorMock('服务器错误', 500))
    await expect(authJson('/api/x')).rejects.toThrow('服务器错误')
    expect(pushMock).not.toHaveBeenCalled()
    expect(useAuthStore().token).toBe('abc123')
  })

  it('authRaw 透传 Response 并注入凭证', async () => {
    useAuthStore().setToken('t')
    const resp = new Response('{}')
    requestRawMock.mockResolvedValue(resp)
    await expect(authRaw('/api/y')).resolves.toBe(resp)
    const opts = requestRawMock.mock.calls[0][1]
    expect(opts.headers.get('Authorization')).toBe('Bearer t')
  })
})
