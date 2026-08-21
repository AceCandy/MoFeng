// AIMETA P=蓝图展示解析回归测试|R=生成字段_历史别名_畸形输入|NR=不测试Vue渲染|E=test:blueprint-util|X=internal|A=unit_test|D=vitest|S=none|RD=../blueprint.ts
import { describe, expect, it } from 'vitest'

import {
  parseBlueprintCharacters,
  parseBlueprintRelationships,
  parseBlueprintWorldSetting,
} from '@/utils/blueprint'

describe('blueprint display parsing', () => {
  it('窄化生成字段并兼容历史别名和畸形输入', () => {
    expect(parseBlueprintWorldSetting({
      core_rules: '灵力守恒',
      key_locations: [{ name: '云城', description: '浮于云海' }, null],
      factions: [{ name: '观星阁', description: '记录天象' }],
    })).toEqual({
      coreRules: '灵力守恒',
      keyLocations: [{ name: '云城', description: '浮于云海' }],
      factions: [{ name: '观星阁', description: '记录天象' }],
    })
    expect(parseBlueprintWorldSetting(null)).toBeNull()

    expect(parseBlueprintCharacters([
      {
        name: '沈砚',
        identity_background: '守卷人',
        性格: '沉静',
        custom_note: '畏火',
        role: '主角',
      },
      { description: { identity: '旅人', personality: '谨慎' } },
      null,
    ])).toEqual([
      {
        name: '沈砚',
        role: '主角',
        fields: [
          { label: '身份背景', value: '守卷人' },
          { label: '性格特质', value: '沉静' },
          { label: 'Custom note', value: '畏火' },
        ],
      },
      {
        name: '未知角色',
        fields: [
          { label: '身份', value: '旅人' },
          { label: '性格', value: '谨慎' },
        ],
        description: undefined,
      },
      { name: '未知角色', description: '无描述', fields: [] },
    ])

    expect(parseBlueprintRelationships([
      { character_from: '沈砚', character_to: '陆离', description: '盟友' },
      { source: '旧主', target: '新王' },
      null,
    ])).toEqual([
      { from: '沈砚', to: '陆离', description: '盟友' },
      { from: '旧主', to: '新王', description: '暂无描述' },
      { from: '角色A', to: '角色B', description: '暂无描述' },
    ])
  })
})
