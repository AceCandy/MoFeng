// AIMETA P=蓝图展示数据解析|R=动态蓝图字段窄化_兼容历史字段|NR=不含UI渲染|E=util:blueprint|X=internal|A=pure_functions|D=none|S=none|RD=../api/novel.ts
export interface BlueprintWorldItem {
  name: string
  description: string
}

export interface BlueprintWorldSettingView {
  coreRules: string
  keyLocations: BlueprintWorldItem[]
  factions: BlueprintWorldItem[]
}

export interface BlueprintCharacterView {
  name: string
  role?: string
  fields: Array<{ label: string; value: string }>
  description?: string
}

export interface BlueprintRelationshipView {
  from: string
  to: string
  description: string
}

const characterFieldMappings = {
  identity: {
    keys: ['identity_background', 'identity', 'background', '身份背景', '身份'],
    label: '身份背景',
    priority: 1,
  },
  personality: {
    keys: ['personality_traits', 'personality', 'traits', 'character', '性格特质', '性格'],
    label: '性格特质',
    priority: 2,
  },
  goal: {
    keys: ['core_goal', 'goal', 'objectives', 'aims', '核心目标', '目标'],
    label: '核心目标',
    priority: 3,
  },
  abilities: {
    keys: ['abilities_skills', 'abilities', 'skills', 'powers', '能力技能', '能力', '技能'],
    label: '能力技能',
    priority: 4,
  },
  relationship: {
    keys: ['relationship_with_protagonist', 'relationship_to_protagonist', 'relationship', 'relation', '与主角关系', '关系'],
    label: '与主角关系',
    priority: 5,
  },
  role: {
    keys: ['role', 'character_role', 'story_role', '角色定位', '角色'],
    label: '角色定位',
    priority: 0,
  },
} as const

const asRecord = (value: unknown): Record<string, unknown> | null =>
  value !== null && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null

const asText = (value: unknown): string | undefined =>
  typeof value === 'string' && value ? value : undefined

const parseWorldItems = (value: unknown): BlueprintWorldItem[] =>
  Array.isArray(value)
    ? value.flatMap((item) => {
        const record = asRecord(item)
        if (!record) return []
        return [{
          name: asText(record.name) ?? '',
          description: asText(record.description) ?? '',
        }]
      })
    : []

export const parseBlueprintWorldSetting = (
  value: unknown,
): BlueprintWorldSettingView | null => {
  const worldSetting = asRecord(value)
  if (!worldSetting) return null
  return {
    coreRules: asText(worldSetting.core_rules) ?? '',
    keyLocations: parseWorldItems(worldSetting.key_locations),
    factions: parseWorldItems(worldSetting.factions),
  }
}

const parseCharacter = (value: unknown): BlueprintCharacterView => {
  const character = asRecord(value)
  if (!character) {
    return { name: '未知角色', description: '无描述', fields: [] }
  }

  const name = asText(character.name)
  if (!name) {
    const description = character.description
    const descriptionRecord = asRecord(description)
    const fields: Array<{ label: string; value: string }> = []
    const identity = asText(descriptionRecord?.identity)
    const personality = asText(descriptionRecord?.personality)
    const relationship = asText(descriptionRecord?.relationship_to_protagonist)
    if (identity) fields.push({ label: '身份', value: identity })
    if (personality) fields.push({ label: '性格', value: personality })
    if (relationship) fields.push({ label: '关系', value: relationship })
    return {
      name: '未知角色',
      fields,
      description: asText(description) ?? (description ? undefined : '无描述'),
    }
  }

  const extractedFields: Record<string, { value: string; label: string; priority: number }> = {}
  const usedKeys = new Set(['name'])

  Object.entries(characterFieldMappings).forEach(([fieldType, mapping]) => {
    for (const key of mapping.keys) {
      const fieldValue = asText(character[key])
      if (fieldValue && !usedKeys.has(key)) {
        extractedFields[fieldType] = {
          value: fieldValue,
          label: mapping.label,
          priority: mapping.priority,
        }
        usedKeys.add(key)
        break
      }
    }
  })

  Object.entries(character).forEach(([key, fieldValue]) => {
    if (!usedKeys.has(key) && typeof fieldValue === 'string' && fieldValue.trim()) {
      extractedFields[`unknown_${key}`] = {
        value: fieldValue,
        label: key
          .replace(/_/g, ' ')
          .replace(/([A-Z])/g, ' $1')
          .replace(/^./, (firstCharacter) => firstCharacter.toUpperCase()),
        priority: 99,
      }
    }
  })

  return {
    name,
    role: extractedFields.role?.value,
    fields: Object.entries(extractedFields)
      .filter(([fieldType]) => fieldType !== 'role')
      .sort(([, left], [, right]) => left.priority - right.priority)
      .map(([, field]) => ({ label: field.label, value: field.value })),
  }
}

export const parseBlueprintCharacters = (value: unknown): BlueprintCharacterView[] =>
  Array.isArray(value) ? value.map(parseCharacter) : []

export const parseBlueprintRelationships = (value: unknown): BlueprintRelationshipView[] =>
  Array.isArray(value)
    ? value.map((item) => {
        const relationship = asRecord(item)
        return {
          from: asText(relationship?.character_from) ?? asText(relationship?.source) ?? '角色A',
          to: asText(relationship?.character_to) ?? asText(relationship?.target) ?? '角色B',
          description: asText(relationship?.description) ?? '暂无描述',
        }
      })
    : []
