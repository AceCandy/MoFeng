// AIMETA P=HTTP请求工具_超时与错误归一化|R=统一fetch错误处理与JSON解析|NR=不含业务API路径|E=api:http|X=internal|A=requestJson_requestRaw|D=fetch|S=net|RD=./README.ai
import { HttpRequestError, type HttpErrorCode } from '@/utils/errors'

// HttpRequestError 错误类型下沉到 @/utils/errors，@/api/http re-export 保持向后兼容
export { HttpRequestError, type HttpErrorCode }

export interface HttpRequestOptions extends RequestInit {
  timeoutMs?: number
  fallbackErrorMessage?: string
}

const DEFAULT_TIMEOUT_MS = 15_000

const parsePossibleJson = (text: string): unknown => {
  const trimmed = text.trim()
  if (!trimmed) {
    return null
  }

  const maybeJson =
    (trimmed.startsWith('{') && trimmed.endsWith('}'))
    || (trimmed.startsWith('[') && trimmed.endsWith(']'))
  if (!maybeJson) {
    return text
  }

  try {
    return JSON.parse(trimmed)
  } catch {
    return text
  }
}

const readResponsePayload = async (response: Response): Promise<unknown> => {
  if (response.status === 204 || response.status === 205) {
    return null
  }

  const text = await response.text().catch(() => '')
  if (!text.trim()) {
    return null
  }

  const contentType = (response.headers.get('content-type') || '').toLowerCase()
  if (contentType.includes('application/json') || contentType.includes('+json')) {
    try {
      return JSON.parse(text)
    } catch {
      return text
    }
  }

  return parsePossibleJson(text)
}

const readErrorMessage = (payload: unknown): string | null => {
  if (!payload) {
    return null
  }

  if (typeof payload === 'string') {
    const message = payload.trim()
    return message || null
  }

  if (typeof payload !== 'object') {
    return null
  }

  const record = payload as Record<string, unknown>
  const fields = ['detail', 'message', 'error', 'msg', 'title']

  for (const field of fields) {
    const value = record[field]
    if (typeof value === 'string' && value.trim()) {
      return value.trim()
    }
  }

  const errors = record.errors
  if (Array.isArray(errors)) {
    const firstTextError = errors.find((item) => typeof item === 'string' && item.trim())
    if (typeof firstTextError === 'string') {
      return firstTextError.trim()
    }
  }

  return null
}

const bindExternalAbortSignal = (signal: AbortSignal | null | undefined, controller: AbortController) => {
  if (!signal) {
    return () => {}
  }

  const onAbort = () => controller.abort()
  if (signal.aborted) {
    controller.abort()
    return () => {}
  }

  signal.addEventListener('abort', onAbort)
  return () => signal.removeEventListener('abort', onAbort)
}

const normalizeTransportError = (
  error: unknown,
  context: {
    url: string
    didTimeout: boolean
    wasAborted: boolean
  },
) => {
  if (error instanceof DOMException && error.name === 'AbortError') {
    if (context.didTimeout) {
      return new HttpRequestError('请求超时，请稍后重试', {
        code: 'timeout',
        url: context.url,
      })
    }

    return new HttpRequestError('请求已取消', {
      code: 'abort',
      url: context.url,
    })
  }

  if (context.didTimeout) {
    return new HttpRequestError('请求超时，请稍后重试', {
      code: 'timeout',
      url: context.url,
    })
  }

  if (error instanceof TypeError || context.wasAborted) {
    return new HttpRequestError('网络连接异常，请检查网络后重试', {
      code: 'network',
      url: context.url,
    })
  }

  if (error instanceof Error) {
    return error
  }

  return new Error('请求失败，请稍后重试')
}

export const requestRaw = async (url: string, options: HttpRequestOptions = {}): Promise<Response> => {
  const {
    timeoutMs = DEFAULT_TIMEOUT_MS,
    fallbackErrorMessage = '请求失败，请稍后重试',
    signal,
    ...requestOptions
  } = options

  const controller = new AbortController()
  let didTimeout = false
  const timeoutId = window.setTimeout(() => {
    didTimeout = true
    controller.abort()
  }, timeoutMs)
  const unbindExternalSignal = bindExternalAbortSignal(signal, controller)

  try {
    const response = await fetch(url, {
      ...requestOptions,
      signal: controller.signal,
    })

    if (!response.ok) {
      const payload = await readResponsePayload(response)
      const errorMessage =
        readErrorMessage(payload) || `${fallbackErrorMessage}，状态码: ${response.status}`
      throw new HttpRequestError(errorMessage, {
        status: response.status,
        code: 'http',
        url,
        payload,
      })
    }

    return response
  } catch (error) {
    if (error instanceof HttpRequestError) {
      throw error
    }

    const wasAborted = Boolean(signal?.aborted)
    throw normalizeTransportError(error, { url, didTimeout, wasAborted })
  } finally {
    window.clearTimeout(timeoutId)
    unbindExternalSignal()
  }
}

export const requestJson = async <T>(url: string, options: HttpRequestOptions = {}): Promise<T> => {
  const response = await requestRaw(url, options)
  if (response.status === 204 || response.status === 205) {
    return undefined as T
  }
  const payload = await readResponsePayload(response)
  return payload as T
}
