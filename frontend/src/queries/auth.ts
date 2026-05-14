// AIMETA P=认证Query组合函数_登录注册和会话服务端状态|R=options_current_user_login_register|NR=不含UI|E=query:auth|X=internal|A=useAuthOptionsQuery_useLoginMutation|D=@tanstack/vue-query|S=net,cache|RD=./README.ai
import { computed, toValue, type MaybeRefOrGetter } from 'vue'
import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/vue-query'
import {
  getAuthOptions,
  getCurrentUser,
  loginWithPassword,
  registerUser,
  sendVerificationCode,
  type AuthOptions,
  type AuthUser,
  type LoginCredentials,
  type RegisterPayload,
} from '@/api/auth'
import { useAuthStore } from '@/stores/auth'

type TokenSource = MaybeRefOrGetter<string | null | undefined>

export const authQueryKeys = {
  all: ['auth'] as const,
  options: () => [...authQueryKeys.all, 'options'] as const,
  currentUser: () => [...authQueryKeys.all, 'current-user'] as const,
}

export const authOptionsQueryOptions = () => ({
  queryKey: authQueryKeys.options(),
  queryFn: getAuthOptions,
  staleTime: 5 * 60_000,
})

export const currentUserQueryOptions = (token: TokenSource) => ({
  queryKey: authQueryKeys.currentUser(),
  queryFn: async () => {
    const resolvedToken = toValue(token)
    if (!resolvedToken) {
      throw new Error('缺少登录令牌')
    }

    const result = await getCurrentUser(resolvedToken)
    if (result.refreshedToken) {
      useAuthStore().setToken(result.refreshedToken)
    }
    return result.data
  },
  staleTime: 0,
  retry: false,
})

export const clearAuthQueryCache = (queryClient: QueryClient) =>
  queryClient.removeQueries({ queryKey: authQueryKeys.all })

export function useAuthOptionsQuery() {
  return useQuery<AuthOptions>(authOptionsQueryOptions())
}

export function useCurrentUserQuery() {
  const authStore = useAuthStore()
  return useQuery<AuthUser>({
    ...currentUserQueryOptions(computed(() => authStore.token)),
    enabled: computed(() => Boolean(authStore.token)),
  })
}

export function useLoginMutation() {
  const authStore = useAuthStore()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (credentials: LoginCredentials) => {
      const loginResult = await loginWithPassword(credentials)
      authStore.setToken(loginResult.accessToken)

      const loadedUser = await queryClient.fetchQuery(
        currentUserQueryOptions(loginResult.accessToken),
      )
      const user = {
        ...loadedUser,
        must_change_password:
          loginResult.mustChangePassword || loadedUser.must_change_password,
      }

      queryClient.setQueryData(authQueryKeys.currentUser(), user)
      authStore.setSession(loginResult.accessToken, user)

      return {
        user,
        mustChangePassword: user.must_change_password,
      }
    },
    onError: () => {
      authStore.logout()
      clearAuthQueryCache(queryClient)
    },
  })
}

export function useSendVerificationCodeMutation() {
  return useMutation({
    mutationFn: (email: string) => sendVerificationCode(email),
  })
}

export function useRegisterMutation() {
  return useMutation({
    mutationFn: (payload: RegisterPayload) => registerUser(payload),
  })
}
