// AIMETA P=小说动态契约收窄|R=校验对话历史_读取动态字符串字段|NR=不定义HTTP_DTO|E=util:novel-contract|X=internal|A=runtime_narrowing|D=api:novel|S=none|RD=../README.ai
import type { ConversationMessage, NovelProject } from '@/api/novel'

export const readStringProperty = (value: unknown, key: string): string | undefined => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return undefined
  const candidate = (value as Record<string, unknown>)[key]
  return typeof candidate === 'string' ? candidate : undefined
}

export const decodeConversationHistory = (
  history: NovelProject['conversation_history'],
): ConversationMessage[] => history.flatMap((item) => {
  const role = readStringProperty(item, 'role')
  const content = readStringProperty(item, 'content')
  return (role === 'user' || role === 'assistant') && content !== undefined
    ? [{ role, content }]
    : []
})
