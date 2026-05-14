// AIMETA P=TanStack_Query客户端_全局服务端状态策略|R=cache_retry_refresh|NR=不含业务接口|E=queryClient|X=internal|A=queryClient|D=@tanstack/vue-query|S=cache|RD=./README.ai
import { QueryClient } from '@tanstack/vue-query'

const NON_RETRYABLE_MESSAGES = ['会话已过期', '401', '403']

export const shouldRetryQuery = (failureCount: number, error: Error) => {
  if (failureCount >= 2) {
    return false
  }

  const message = error.message || ''
  return !NON_RETRYABLE_MESSAGES.some((item) => message.includes(item))
}

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      gcTime: 5 * 60_000,
      retry: shouldRetryQuery,
      refetchOnWindowFocus: false,
      refetchOnReconnect: true,
    },
    mutations: {
      retry: false,
    },
  },
})
