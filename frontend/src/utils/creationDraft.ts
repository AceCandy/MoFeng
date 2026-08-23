// AIMETA P=灵感草稿本机保护_短期故障恢复|R=按用户项目保存_24小时过期_账号清理|NR=不参与跨设备冲突比较|E=util:creation-draft|X=internal|A=localStorage_helpers|D=web-storage|S=storage|RD=./README.ai
const DRAFT_STORAGE_PREFIX = 'mofeng.creation-draft:'
const DRAFT_MAX_AGE_MS = 24 * 60 * 60 * 1000

export interface InspirationDraftBackup {
  userId: number
  projectId: string
  inspirationTurn: number
  value: string
  savedAt: number
}

const draftKey = (userId: number, projectId: string) =>
  `${DRAFT_STORAGE_PREFIX}${userId}:${projectId}`

export const saveInspirationDraftBackup = (backup: InspirationDraftBackup) => {
  try {
    if (!backup.value.trim()) {
      window.localStorage.removeItem(draftKey(backup.userId, backup.projectId))
      return
    }
    window.localStorage.setItem(draftKey(backup.userId, backup.projectId), JSON.stringify(backup))
  } catch {
    // 本机存储不可用时仍允许继续输入，服务端同步保持主路径。
  }
}

export const loadInspirationDraftBackup = (
  userId: number,
  projectId: string,
): InspirationDraftBackup | null => {
  const key = draftKey(userId, projectId)
  try {
    const raw = window.localStorage.getItem(key)
    if (!raw) return null
    const value = JSON.parse(raw) as unknown
    if (!value || typeof value !== 'object') throw new Error('invalid draft')
    const record = value as Record<string, unknown>
    if (
      record.userId !== userId
      || record.projectId !== projectId
      || typeof record.inspirationTurn !== 'number'
      || !Number.isInteger(record.inspirationTurn)
      || typeof record.value !== 'string'
      || typeof record.savedAt !== 'number'
      || Date.now() - record.savedAt > DRAFT_MAX_AGE_MS
    ) {
      window.localStorage.removeItem(key)
      return null
    }
    return value as InspirationDraftBackup
  } catch {
    window.localStorage.removeItem(key)
    return null
  }
}

export const removeInspirationDraftBackup = (userId: number, projectId: string) => {
  try {
    window.localStorage.removeItem(draftKey(userId, projectId))
  } catch {
    // 清理失败不阻断退出或继续创作。
  }
}

export const clearInspirationDraftBackupsForUser = (userId: number) => {
  const prefix = `${DRAFT_STORAGE_PREFIX}${userId}:`
  try {
    const keys = Array.from({ length: window.localStorage.length }, (_, index) =>
      window.localStorage.key(index),
    ).filter((key): key is string => Boolean(key?.startsWith(prefix)))
    keys.forEach((key) => window.localStorage.removeItem(key))
  } catch {
    // 清理失败不阻断账号退出。
  }
}
