// AIMETA P=灵感草稿本机保护测试|R=用户项目隔离_TTL_畸形清理_账号清理|NR=不测试服务端同步|E=test:util:creation-draft|X=internal|A=creationDraft_contract|D=vitest,localStorage|S=test|RD=../README.ai
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  clearInspirationDraftBackupsForUser,
  loadInspirationDraftBackup,
  removeInspirationDraftBackup,
  saveInspirationDraftBackup,
} from '@/utils/creationDraft'

const NOW = new Date('2026-08-24T08:00:00Z')

describe('creationDraft', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.useFakeTimers()
    vi.setSystemTime(NOW)
  })

  afterEach(() => vi.useRealTimers())

  it('按用户和项目隔离保存，并允许删除单个项目', () => {
    saveInspirationDraftBackup({
      userId: 1,
      projectId: 'project-a',
      inspirationTurn: 2,
      value: '设备 A 的草稿',
      savedAt: Date.now(),
    })
    saveInspirationDraftBackup({
      userId: 2,
      projectId: 'project-a',
      inspirationTurn: 2,
      value: '设备 B 的草稿',
      savedAt: Date.now(),
    })

    expect(loadInspirationDraftBackup(1, 'project-a')?.value).toBe('设备 A 的草稿')
    expect(loadInspirationDraftBackup(2, 'project-a')?.value).toBe('设备 B 的草稿')

    removeInspirationDraftBackup(1, 'project-a')
    expect(loadInspirationDraftBackup(1, 'project-a')).toBeNull()
    expect(loadInspirationDraftBackup(2, 'project-a')?.value).toBe('设备 B 的草稿')
  })

  it('清理超过 24 小时或结构畸形的备份', () => {
    saveInspirationDraftBackup({
      userId: 1,
      projectId: 'expired',
      inspirationTurn: 0,
      value: '过期草稿',
      savedAt: Date.now() - 24 * 60 * 60 * 1000 - 1,
    })
    localStorage.setItem('mofeng.creation-draft:1:broken', '{not-json')

    expect(loadInspirationDraftBackup(1, 'expired')).toBeNull()
    expect(loadInspirationDraftBackup(1, 'broken')).toBeNull()
  })

  it('账号清理不影响其他用户', () => {
    for (const [userId, projectId] of [[1, 'a'], [1, 'b'], [2, 'a']] as const) {
      saveInspirationDraftBackup({
        userId,
        projectId,
        inspirationTurn: 0,
        value: `${userId}-${projectId}`,
        savedAt: Date.now(),
      })
    }

    clearInspirationDraftBackupsForUser(1)

    expect(loadInspirationDraftBackup(1, 'a')).toBeNull()
    expect(loadInspirationDraftBackup(1, 'b')).toBeNull()
    expect(loadInspirationDraftBackup(2, 'a')?.value).toBe('2-a')
  })
})
