// AIMETA P=认证状态_用户登录状态管理|R=token_user_login_logout|NR=不含API调用|E=store:auth|X=internal|A=useAuthStore|D=pinia|S=storage|RD=./README.ai
import { defineStore } from 'pinia'
import type { AuthUser } from '@/api/auth'
import { clearInspirationDraftBackupsForUser } from '@/utils/creationDraft'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('token') || (null as string | null),
    user: null as AuthUser | null,
  }),
  getters: {
    isAuthenticated: (state) => !!state.token,
    mustChangePassword: (state) => state.user?.must_change_password ?? false,
  },
  actions: {
    setToken(token: string | null) {
      this.token = token
      if (token) {
        localStorage.setItem('token', token)
      } else {
        localStorage.removeItem('token')
      }
    },
    setUser(user: AuthUser | null) {
      const previousUserId = this.user?.id
      if (previousUserId != null && previousUserId !== user?.id) {
        clearInspirationDraftBackupsForUser(previousUserId)
      }
      this.user = user
    },
    setSession(token: string, user: AuthUser) {
      this.setToken(token)
      this.setUser(user)
    },
    logout() {
      this.setToken(null)
      this.setUser(null)
    },
  },
})
