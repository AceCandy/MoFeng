import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { splitSpeechText, useChapterReader } from '@/composables/useChapterReader'


class FakeUtterance {
  text: string
  onend: (() => void) | null = null
  onerror: (() => void) | null = null

  constructor(text: string) {
    this.text = text
  }
}


class FakeAudio {
  static instances: FakeAudio[] = []
  src: string
  onended: (() => void) | null = null
  onerror: (() => void) | null = null
  paused = false

  constructor(src: string) {
    this.src = src
    FakeAudio.instances.push(this)
  }

  play = vi.fn(async () => undefined)
  pause = vi.fn(() => {
    this.paused = true
  })
}


const browserSpeech = {
  spoken: [] as string[],
  cancel: vi.fn(),
  pause: vi.fn(),
  resume: vi.fn(),
  speak: vi.fn((utterance: FakeUtterance) => {
    browserSpeech.spoken.push(utterance.text)
    queueMicrotask(() => utterance.onend?.())
  }),
}


const bundle = (configured: boolean) => ({
  legacy: null,
  providers: [],
  stage_routes: [],
  models: configured
    ? [
        {
          id: 1,
          user_id: 7,
          provider_id: 2,
          display_name: '朗读模型',
          model_name: 'tts-model',
          capabilities: { tts: true },
          context_window: null,
          is_default_chat: false,
          is_default_embedding: false,
          is_default_tts: true,
          tts_protocol: 'openai_speech' as const,
          tts_voice: 'alloy',
          tts_speed: 1,
          is_enabled: true,
          sort_order: 0,
        },
      ]
    : [],
})


beforeEach(() => {
  FakeAudio.instances = []
  browserSpeech.spoken = []
  vi.clearAllMocks()
  vi.stubGlobal('Audio', FakeAudio)
  vi.stubGlobal('SpeechSynthesisUtterance', FakeUtterance)
  Object.defineProperty(window, 'speechSynthesis', { value: browserSpeech, configurable: true })
  Object.defineProperty(URL, 'createObjectURL', {
    value: vi.fn(() => `blob:${FakeAudio.instances.length + 1}`),
    configurable: true,
  })
  Object.defineProperty(URL, 'revokeObjectURL', { value: vi.fn(), configurable: true })
})


afterEach(() => {
  vi.unstubAllGlobals()
})


describe('splitSpeechText', () => {
  it('keeps title first and respects paragraph and sentence boundaries', () => {
    const segments = splitSpeechText('第一章 风起', '第一段。第二句！\n\n第三段。', 8)

    expect(segments[0]).toBe('第一章 风起')
    expect(segments.slice(1).join('')).toBe('第一段。第二句！第三段。')
    expect(segments.every((segment) => segment.length <= 8)).toBe(true)
  })

  it('hard splits a sentence longer than the limit', () => {
    const segments = splitSpeechText('', '一'.repeat(21), 10)

    expect(segments.map((segment) => segment.length)).toEqual([10, 10, 1])
  })
})


describe('useChapterReader', () => {
  it('uses browser speech immediately when no default TTS is configured', async () => {
    const reader = useChapterReader({
      loadConfig: async () => bundle(false),
      synthesize: vi.fn(),
      notify: vi.fn(),
    })

    await reader.start('第一章', '正文。')

    expect(browserSpeech.spoken).toEqual(['第一章', '正文。'])
    expect(reader.status.value).toBe('idle')
  })

  it('prefetches one model segment and supports pause resume and stop', async () => {
    const synthesize = vi.fn(async (text: string) => new Blob([text], { type: 'audio/mpeg' }))
    const reader = useChapterReader({
      loadConfig: async () => bundle(true),
      synthesize,
      notify: vi.fn(),
    })

    const playback = reader.start('标题', '第一段。\n\n第二段。')
    await vi.waitFor(() => expect(FakeAudio.instances).toHaveLength(1))
    expect(synthesize).toHaveBeenCalledTimes(2)

    reader.pause()
    expect(reader.status.value).toBe('paused')
    expect(FakeAudio.instances[0].pause).toHaveBeenCalled()

    reader.resume()
    expect(reader.status.value).toBe('playing')
    expect(FakeAudio.instances[0].play).toHaveBeenCalledTimes(2)

    reader.stop()
    expect(reader.status.value).toBe('idle')
    expect(URL.revokeObjectURL).toHaveBeenCalled()
    await playback
  })

  it('continues from the failed model segment with browser speech', async () => {
    const synthesize = vi
      .fn()
      .mockResolvedValueOnce(new Blob(['title'], { type: 'audio/mpeg' }))
      .mockRejectedValueOnce(new Error('upstream failed'))
    const notify = vi.fn()
    const reader = useChapterReader({
      loadConfig: async () => bundle(true),
      synthesize,
      notify,
    })

    const playback = reader.start('标题', '失败段。')
    await vi.waitFor(() => expect(FakeAudio.instances).toHaveLength(1))
    FakeAudio.instances[0].onended?.()
    await playback

    expect(browserSpeech.spoken).toEqual(['失败段。'])
    expect(notify).toHaveBeenCalledWith('模型朗读失败（upstream failed），已切换浏览器朗读。', 'info')
  })

  it('reports unavailable browser speech without leaving an active state', async () => {
    Object.defineProperty(window, 'speechSynthesis', { value: undefined, configurable: true })
    const notify = vi.fn()
    const reader = useChapterReader({
      loadConfig: async () => bundle(false),
      synthesize: vi.fn(),
      notify,
    })

    await reader.start('标题', '正文。')

    expect(reader.status.value).toBe('idle')
    expect(notify).toHaveBeenCalledWith('当前浏览器不支持语音朗读。', 'error')
  })
})
