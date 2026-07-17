// HTTP 请求错误类型：下沉到 @/utils/errors 供 components/views 复用，避免直连 @/api/http
export type HttpErrorCode = 'http' | 'timeout' | 'network' | 'abort'

export class HttpRequestError extends Error {
  status: number | null
  code: HttpErrorCode
  url: string
  payload: unknown

  constructor(
    message: string,
    options: {
      status?: number | null
      code: HttpErrorCode
      url: string
      payload?: unknown
    },
  ) {
    super(message)
    this.name = 'HttpRequestError'
    this.status = options.status ?? null
    this.code = options.code
    this.url = options.url
    this.payload = options.payload
  }
}
