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
    // saveTTSSelection 的 is_default_tts 写入逻辑已抽离到 useModelSelection.ts（Slice 8）
    const selection = source('src/components/llm-settings/useModelSelection.ts')

    expect(types).toContain("type Capability = 'chat' | 'embedding' | 'tts'")
    expect(types).toContain("type RoutingSection = 'llm' | 'embedding' | 'tts' | 'routes'")
    expect(selection).toContain('is_default_tts: true')
    // 协议/音色/倍速表单已从设置页移除，改在朗读控件配置
    expect(routing).not.toContain('MiMo Chat Audio')
    expect(routing).not.toContain('ttsForm.speed')
    expect(routing).not.toContain('mimo-tts-voices')
  })

  it('saves existing TTS settings explicitly without racing model changes', () => {
    const routing = source('src/components/llm-settings/PersonalModelRouting.vue')
    // picker 内联面板状态与关闭保护收口在 useModelPicker.ts
    const picker = source('src/components/llm-settings/useModelPicker.ts')
    // saveTTSSelection 等模型选择保存方法已抽离到 useModelSelection.ts（Slice 8）
    const selection = source('src/components/llm-settings/useModelSelection.ts')
    const pickerPanel = source('src/components/llm-settings/ModelPickerPanel.vue')

    // 保存与 TTS 选择经事件接线回父级方法
    expect(routing).toContain('@save="() => savePickerSelections(provider)"')
    expect(routing).toContain('@select-tts="(modelName) => selectPendingTTSModel(provider, modelName)"')
    expect(selection).toContain('const saveTTSSelection = async (provider: UserModelProvider)')
    expect(pickerPanel).toContain(':disabled="!provider.is_enabled || isSavingPicker"')
    expect(pickerPanel).toContain("v-if=\"activeSection === 'tts' || isChatPickerDirty\"")
    expect(pickerPanel).toContain("@keydown.esc.stop.prevent=\"!isSavingPicker && emit('close')\"")
    expect(picker).toContain('const requestCloseModelPicker = async () => {')
    expect(picker).toContain("activeSection.value === 'tts' && pendingTTSModelName.value !== initialTTSModelName.value")
    expect(picker).toContain('if (!isChatPickerDirty.value && !isTTSPickerDirty.value)')
    expect(routing).toContain('isStageRoutesDirty.value || isChatPickerDirty.value || isTTSPickerDirty.value')
    expect(picker).toContain('requestAnimationFrame(() => trigger?.focus())')
  })

  it('isolates TTS providers by capability like chat and embedding', () => {
    // activeProviders 派生已抽离到 useSectionMeta.ts（Slice 4），按能力过滤的逻辑随之迁移
    const sectionMeta = source('src/components/llm-settings/useSectionMeta.ts')

    // 语音朗读不再走“显示所有供应商”特例，与文本生成/记忆检索一致按能力过滤
    expect(sectionMeta).not.toContain("activeSection.value === 'tts' ? providers.value")
    expect(sectionMeta).toContain('providerCapabilities(provider)[capability]')
  })
})
