import { describe, expect, it } from 'vitest'
import type { UserAIModel, UserModelProvider } from '@/api/llm'
import {
  capabilityForSection,
  createModelPayload,
  createProviderCapabilities,
  groupModelsByProvider,
  modelDisplayName,
} from '../llm-settings/modelRoutingHelpers'

const provider = { id: 42 } as UserModelProvider

describe('capabilityForSection', () => {
  it('maps each routing section to its capability', () => {
    expect(capabilityForSection('llm')).toBe('chat')
    expect(capabilityForSection('routes')).toBe('chat')
    expect(capabilityForSection('embedding')).toBe('embedding')
    expect(capabilityForSection('tts')).toBe('tts')
  })
})

describe('modelDisplayName', () => {
  it('falls back to 未设置 when no model is set', () => {
    expect(modelDisplayName(undefined)).toBe('未设置')
  })

  it('prefers display_name over model_name', () => {
    expect(
      modelDisplayName({ display_name: '展示名', model_name: '内部名' } as UserAIModel),
    ).toBe('展示名')
  })

  it('falls back to model_name when display_name is empty', () => {
    expect(
      modelDisplayName({ display_name: '', model_name: '内部名' } as UserAIModel),
    ).toBe('内部名')
  })
})

describe('createProviderCapabilities', () => {
  it('flags only the active capability as true', () => {
    expect(createProviderCapabilities('chat')).toEqual({
      chat: true,
      embedding: false,
      tts: false,
    })
    expect(createProviderCapabilities('embedding')).toEqual({
      chat: false,
      embedding: true,
      tts: false,
    })
    expect(createProviderCapabilities('tts')).toEqual({
      chat: false,
      embedding: false,
      tts: true,
    })
  })
})

describe('groupModelsByProvider', () => {
  it('groups models under their provider id by capability', () => {
    const models = [
      { provider_id: 1, model_name: 'a', capabilities: { chat: true, embedding: false, tts: false } },
      { provider_id: 1, model_name: 'b', capabilities: { chat: false, embedding: true, tts: false } },
      { provider_id: 2, model_name: 'c', capabilities: { chat: true, embedding: false, tts: false } },
    ] as UserAIModel[]

    expect(groupModelsByProvider(models, 'chat')).toEqual({
      1: [models[0]],
      2: [models[2]],
    })
    expect(groupModelsByProvider(models, 'embedding')).toEqual({ 1: [models[1]] })
    expect(groupModelsByProvider(models, 'tts')).toEqual({})
  })
})

describe('createModelPayload', () => {
  it('marks the first chat model as default when none exists', () => {
    const payload = createModelPayload(provider, 'gpt-4', 'chat', false)

    expect(payload.is_default_chat).toBe(true)
    expect(payload.is_default_embedding).toBe(false)
    expect(payload.is_default_tts).toBe(false)
    expect(payload.capabilities).toEqual({ chat: true, embedding: false })
    expect(payload.tts_protocol).toBeNull()
    expect(payload.is_enabled).toBe(true)
    expect(payload.display_name).toBe('gpt-4')
  })

  it('does not override an existing primary chat model', () => {
    const payload = createModelPayload(provider, 'gpt-4', 'chat', true)

    expect(payload.is_default_chat).toBe(false)
  })

  it('builds a default embedding model payload', () => {
    const payload = createModelPayload(provider, 'text-embed', 'embedding', true)

    expect(payload.is_default_embedding).toBe(true)
    expect(payload.is_default_chat).toBe(false)
    expect(payload.is_default_tts).toBe(false)
    expect(payload.capabilities).toEqual({ chat: false, embedding: true, tts: false })
    expect(payload.tts_protocol).toBeNull()
  })

  it('pins the TTS payload to mimo_chat_audio without a voice/speed form', () => {
    const payload = createModelPayload(provider, 'mimo-tts', 'tts', true)

    expect(payload.is_default_tts).toBe(true)
    expect(payload.tts_protocol).toBe('mimo_chat_audio')
    expect(payload.tts_voice).toBeNull()
    expect(payload.tts_speed).toBe(1.0)
    expect(payload.capabilities).toEqual({ chat: false, embedding: false, tts: true })
  })
})
