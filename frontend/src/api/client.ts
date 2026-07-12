// AIMETA P=鉴权请求客户端_统一注入令牌与401拦截|R=Authorization注入_会话过期处理|NR=不含业务接口路径|E=api:client|X=internal|A=authJson_authRaw|D=fetch,pinia|S=net|RD=./README.ai
import { useAuthStore } from '@/stores/auth'
import router from '@/router'
import { HttpRequestError, requestJson, requestRaw, type HttpRequestOptions } from './http'

/** 401 统一登出并跳转登录；其他错误原样抛出（标注 never 便于调用处类型收敛）。 */
const handleAuthError = (error: unknown): never => {
  if (error instanceof HttpRequestError && error.status === 401) {
    const authStore = useAuthStore()
    authStore.logout()
    router.push('/login')
    throw new Error('会话已过期，请重新登录')
  }
  throw error
}

/** 构造带鉴权的请求头；FormData 时移除 Content-Type 让浏览器自定 boundary。 */
const buildAuthHeaders = (options: HttpRequestOptions): Headers => {
  const authStore = useAuthStore()
  const headers = new Headers({
    'Content-Type': 'application/json',
    ...((options.headers as Record<string, string> | undefined) ?? {}),
  })
  if (options.body instanceof FormData) {
    headers.delete('Content-Type')
  }
  if (authStore.isAuthenticated && authStore.token) {
    headers.set('Authorization', `Bearer ${authStore.token}`)
  }
  return headers
}

/** 带鉴权的 JSON 请求；401 统一登出并跳转登录。 */
export const authJson = async <T>(url: string, options: HttpRequestOptions = {}): Promise<T> => {
  try {
    return await requestJson<T>(url, { ...options, headers: buildAuthHeaders(options) })
  } catch (error) {
    return handleAuthError(error)
  }
}

/** 带鉴权的原始（流/二进制）请求；401 统一登出并跳转登录。 */
export const authRaw = async (url: string, options: HttpRequestOptions = {}): Promise<Response> => {
  try {
    return await requestRaw(url, { ...options, headers: buildAuthHeaders(options) })
  } catch (error) {
    return handleAuthError(error)
  }
}
