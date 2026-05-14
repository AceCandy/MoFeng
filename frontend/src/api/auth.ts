// AIMETA P=认证API客户端_登录注册和用户会话接口|R=auth_options_login_me_register|NR=不含状态管理|E=api:auth|X=internal|A=authApiFunctions|D=fetch|S=net|RD=./README.ai
import { API_BASE_URL } from './base'

const API_URL = `${API_BASE_URL}/api/auth`

export interface AuthOptions {
  // 是否允许用户自助注册
  allow_registration: boolean
  // 是否启用 Linux.do 登录
  enable_linuxdo_login: boolean
}

export interface AuthUser {
  id: number
  username: string
  is_admin: boolean
  must_change_password: boolean
}

export interface LoginCredentials {
  username: string
  password: string
}

export interface LoginResult {
  accessToken: string
  mustChangePassword: boolean
}

export interface RegisterPayload {
  username: string
  email: string
  password: string
  verification_code: string
}

interface AuthRequestOptions extends RequestInit {
  token?: string | null
  timeoutMs?: number
  debugTag?: string
}

interface AuthRequestResult<T> {
  data: T
  refreshedToken: string | null
}

const fallbackAuthOptions: AuthOptions = {
  allow_registration: true,
  enable_linuxdo_login: false,
}

const readErrorMessage = async (response: Response, fallback: string) => {
  const errorData = await response.json().catch(() => ({}))
  return typeof errorData.detail === 'string' ? errorData.detail : fallback
}

async function authRequest<T>(
  path: string,
  options: AuthRequestOptions = {},
): Promise<AuthRequestResult<T>> {
  const { token, timeoutMs = 15000, debugTag = path, ...requestOptions } = options
  const method = String(requestOptions.method || 'GET').toUpperCase()
  const headers = new Headers(requestOptions.headers || {})
  const controller = new AbortController()
  const timeoutId = window.setTimeout(() => {
    controller.abort()
  }, timeoutMs)

  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  try {
    const response = await fetch(`${API_URL}${path}`, {
      ...requestOptions,
      headers,
      signal: controller.signal,
    })

    if (!response.ok) {
      throw new Error(await readErrorMessage(response, `请求失败，状态码: ${response.status}`))
    }

    const refreshedToken = response.headers.get('X-Token-Refresh')

    if (response.status === 204) {
      return { data: undefined as T, refreshedToken }
    }

    return {
      data: (await response.json()) as T,
      refreshedToken,
    }
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new Error(`Request timed out after ${timeoutMs}ms: ${method} ${API_URL}${path} (${debugTag})`)
    }
    throw error
  } finally {
    window.clearTimeout(timeoutId)
  }
}

export async function getAuthOptions(): Promise<AuthOptions> {
  try {
    const { data } = await authRequest<AuthOptions>('/options', { timeoutMs: 10000 })
    return data
  } catch {
    return fallbackAuthOptions
  }
}

export async function loginWithPassword(credentials: LoginCredentials): Promise<LoginResult> {
  const params = new URLSearchParams()
  params.append('grant_type', 'password')
  params.append('username', credentials.username)
  params.append('password', credentials.password)

  const { data } = await authRequest<{ access_token?: string; must_change_password?: boolean }>(
    '/token',
    {
      method: 'POST',
      body: params,
      timeoutMs: 15000,
      debugTag: 'login/token',
    },
  )

  if (!data?.access_token) {
    throw new Error('Missing access token in login response')
  }

  return {
    accessToken: String(data.access_token),
    mustChangePassword: Boolean(data.must_change_password),
  }
}

export async function getCurrentUser(token: string): Promise<AuthRequestResult<AuthUser>> {
  const { data, refreshedToken } = await authRequest<{
    id: number
    username: string
    is_admin?: boolean
    must_change_password?: boolean
  }>('/users/me', {
    token,
    timeoutMs: 10000,
    debugTag: 'fetchUser/me',
  })

  return {
    refreshedToken,
    data: {
      id: data.id,
      username: data.username,
      is_admin: data.is_admin || false,
      must_change_password: data.must_change_password || false,
    },
  }
}

export async function sendVerificationCode(email: string): Promise<void> {
  await authRequest<void>(`/send-code?email=${encodeURIComponent(email)}`, {
    method: 'POST',
  })
}

export async function registerUser(payload: RegisterPayload): Promise<void> {
  await authRequest<void>('/users', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}
