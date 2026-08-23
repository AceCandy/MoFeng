// AIMETA P=认证状态草稿清理测试|R=账号切换_退出清理当前用户备份|NR=不测试登录API|E=test:store:auth|X=internal|A=useAuthStore_draft_cleanup|D=vitest,pinia|S=test|RD=../README.ai
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'

import { useAuthStore } from '@/stores/auth'
import {
  loadInspirationDraftBackup,
  saveInspirationDraftBackup,
} from '@/utils/creationDraft'

const user = (id: number) => ({
  id,
  username: `user-${id}`,
  is_admin: false,
  must_change_password: false,
})

const saveDraft = (userId: number) => saveInspirationDraftBackup({
  userId,
  projectId: 'project-1',
  inspirationTurn: 0,
  value: `draft-${userId}`,
  savedAt: Date.now(),
})

describe('auth store draft cleanup', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
  })

  it('切换账号和退出时清理上一账号草稿', () => {
    const store = useAuthStore()
    store.setUser(user(1))
    saveDraft(1)
    saveDraft(2)

    store.setUser(user(2))
    expect(loadInspirationDraftBackup(1, 'project-1')).toBeNull()
    expect(loadInspirationDraftBackup(2, 'project-1')?.value).toBe('draft-2')

    store.logout()
    expect(loadInspirationDraftBackup(2, 'project-1')).toBeNull()
  })
})
