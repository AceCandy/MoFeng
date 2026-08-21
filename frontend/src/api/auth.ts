// AIMETA P=认证API客户端_登录注册和用户会话接口|R=auth_options_login_me_register|NR=不含状态管理|E=api:auth|X=internal|A=authApiFunctions|D=http|S=net|RD=./README.ai
import { API_BASE_URL } from './base'
import { requestJson, requestRaw } from './http'

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

interface AuthRequestResult<T> {
  data: T
  refreshedToken: string | null
}

const fallbackAuthOptions: AuthOptions = {
  allow_registration: true,
  enable_linuxdo_login: false,
}

export async function getAuthOptions(): Promise<AuthOptions> {
  try {
    return await requestJson<AuthOptions>(`${API_URL}/options`, {
      timeoutMs: 10_000,
      fallbackErrorMessage: '请求失败',
    })
  } catch {
    return fallbackAuthOptions
  }
}

export async function loginWithPassword(credentials: LoginCredentials): Promise<LoginResult> {
  const params = new URLSearchParams()
  params.append('grant_type', 'password')
  params.append('username', credentials.username)
  params.append('password', credentials.password)

  const data = await requestJson<{ access_token?: string; must_change_password?: boolean }>(
    `${API_URL}/token`, {
      method: 'POST',
      body: params,
      timeoutMs: 15_000,
      fallbackErrorMessage: '请求失败',
    })

  if (!data?.access_token) {
    throw new Error('Missing access token in login response')
  }

  return {
    accessToken: String(data.access_token),
    mustChangePassword: Boolean(data.must_change_password),
  }
}

export async function getCurrentUser(token: string): Promise<AuthRequestResult<AuthUser>> {
  const response = await requestRaw(`${API_URL}/users/me`, {
    headers: { Authorization: `Bearer ${token}` },
    timeoutMs: 10_000,
    fallbackErrorMessage: '请求失败',
  })
  const data = (await response.json()) as {
    id: number
    username: string
    is_admin?: boolean
    must_change_password?: boolean
  }

  return {
    refreshedToken: response.headers.get('X-Token-Refresh'),
    data: {
      id: data.id,
      username: data.username,
      is_admin: data.is_admin || false,
      must_change_password: data.must_change_password || false,
    },
  }
}

export async function sendVerificationCode(email: string): Promise<void> {
  await requestJson<void>(`${API_URL}/send-code?email=${encodeURIComponent(email)}`, {
    method: 'POST',
    timeoutMs: 15_000,
    fallbackErrorMessage: '请求失败',
  })
}

export async function registerUser(payload: RegisterPayload): Promise<void> {
  await requestJson<void>(`${API_URL}/users`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    timeoutMs: 15_000,
    fallbackErrorMessage: '请求失败',
  })
}
