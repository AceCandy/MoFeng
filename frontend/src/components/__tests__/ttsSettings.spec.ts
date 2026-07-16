import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'


const source = (path: string) => readFileSync(resolve(process.cwd(), path), 'utf8')


describe('TTS settings integration', () => {
  it('adds a keyboard reachable speech settings tab', () => {
    const settings = source('src/views/SettingsView.vue')

    expect(settings).toContain("type SettingsSectionId = 'llm' | 'embedding' | 'tts' | 'routes'")
    expect(settings).toContain("{ id: 'tts', label: '语音朗读'")
    expect(settings).toContain("activeSettingsSection === 'tts'")
    expect(settings).toContain('active-section="tts"')
    expect(settings).toContain('tts: null')
  })

  it('extends the API contract with typed TTS model configuration', () => {
    const api = source('src/api/llm.ts')

    expect(api).toContain("export type TTSProtocol = 'mimo_chat_audio' | 'openai_speech'")
    expect(api).toContain('is_default_tts: boolean')
    expect(api).toContain('tts_protocol: TTSProtocol | null')
    expect(api).toContain('tts_voice: string | null')
    expect(api).toContain('tts_speed: number')
  })

  it('keeps TTS settings to model selection only — voice/speed moved to the reader control', () => {
    const routing = source('src/components/llm-settings/PersonalModelRouting.vue')
    // Capability/RoutingSection 类型定义已抽离到 modelRoutingTypes.ts
    const types = source('src/components/llm-settings/modelRoutingTypes.ts')

    expect(types).toContain("type Capability = 'chat' | 'embedding' | 'tts'")
    expect(types).toContain("type RoutingSection = 'llm' | 'embedding' | 'tts' | 'routes'")
    expect(routing).toContain('is_default_tts: true')
    // 协议/音色/倍速表单已从设置页移除，改在朗读控件配置
    expect(routing).not.toContain('MiMo Chat Audio')
    expect(routing).not.toContain('ttsForm.speed')
    expect(routing).not.toContain('mimo-tts-voices')
  })

  it('saves existing TTS settings explicitly without racing model changes', () => {
    const routing = source('src/components/llm-settings/PersonalModelRouting.vue')

    expect(routing).toContain('@click="savePickerSelections(provider)"')
    expect(routing).toContain('@change="selectPendingTTSModel(provider, modelName)"')
    expect(routing).toContain(':disabled="!provider.is_enabled || isSavingPicker"')
    expect(routing).toContain('const saveTTSSelection = async (provider: UserModelProvider)')
    expect(routing).toContain("v-if=\"activeSection === 'tts' || !isChatPickerDirty\"")
    expect(routing).toContain('@keydown.esc.stop.prevent="!isSavingPicker && closeModelPicker()"')
    expect(routing).toMatch(
      /v-if="activeSection === 'tts' \|\| !isChatPickerDirty"[\s\S]{0,180}:disabled="isSavingPicker"/,
    )
    expect(routing).toContain('onClose: () => {')
    expect(routing).toContain('if (!isSavingPicker.value) {')
    expect(routing).not.toContain('onClose: closeModelPicker')
  })

  it('isolates TTS providers by capability like chat and embedding', () => {
    // activeProviders 派生已抽离到 useSectionMeta.ts（Slice 4），按能力过滤的逻辑随之迁移
    const sectionMeta = source('src/components/llm-settings/useSectionMeta.ts')

    // 语音朗读不再走“显示所有供应商”特例，与文本生成/记忆检索一致按能力过滤
    expect(sectionMeta).not.toContain("activeSection.value === 'tts' ? providers.value")
    expect(sectionMeta).toContain('providerCapabilities(provider)[capability]')
  })
})
