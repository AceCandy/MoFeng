import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { pickChineseVoice, useChapterReader } from '@/composables/useChapterReader'


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
  localStorage.clear()
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


describe('useChapterReader', () => {
  it('picks the zh-CN online (Natural) voice over the buggy local Microsoft voice', () => {
    const voices = [
      { name: 'Microsoft Huihui - Chinese (Simplified, PRC)', lang: 'zh-CN' },
      { name: 'Microsoft Kangkang - Chinese (Simplified, PRC)', lang: 'zh-CN' },
      { name: 'Microsoft HiuGaai Online (Natural) - Chinese (Cantonese Traditional)', lang: 'zh-HK' },
      { name: 'Microsoft Xiaoxiao Online (Natural) - Chinese (Mainland)', lang: 'zh-CN' },
      { name: 'Microsoft Yunxi Online (Natural) - Chinese (Mainland)', lang: 'zh-CN' },
    ] as unknown as SpeechSynthesisVoice[]
    Object.defineProperty(window.speechSynthesis, 'getVoices', {
      value: () => voices,
      configurable: true,
    })

    const picked = pickChineseVoice()
    expect(picked?.name).toContain('Xiaoxiao')
    expect(picked?.lang).toBe('zh-CN')
  })

  it('persists voice and rate choices to localStorage', () => {
    const reader = useChapterReader({
      loadConfig: async () => bundle(false),
      synthesize: vi.fn(),
      notify: vi.fn(),
    })
    reader.setVoiceURI('voice-uri-1')
    reader.setRate(1.5)
    expect(reader.voiceURI.value).toBe('voice-uri-1')
    expect(reader.rate.value).toBe(1.5)
    expect(localStorage.getItem('mofeng:reader-voice')).toBe('voice-uri-1')
    expect(localStorage.getItem('mofeng:reader-rate')).toBe('1.5')
  })

  it('previewVoice speaks a sample with the current voice only when idle', () => {
    const voices = [
      { name: 'Microsoft Xiaoxiao Online (Natural)', voiceURI: 'xiaoxiao', lang: 'zh-CN' },
    ] as unknown as SpeechSynthesisVoice[]
    Object.defineProperty(window.speechSynthesis, 'getVoices', {
      value: () => voices,
      configurable: true,
    })
    const reader = useChapterReader({
      loadConfig: async () => bundle(false),
      synthesize: vi.fn(),
      notify: vi.fn(),
    })
    reader.setVoiceURI('xiaoxiao')

    reader.previewVoice()

    expect(browserSpeech.spoken.length).toBe(1)
    expect(browserSpeech.spoken[0].startsWith(' ')).toBe(true)
    expect(browserSpeech.cancel).toHaveBeenCalled()
    expect(reader.status.value).toBe('idle')
  })

  it('previewVoice is a no-op while reading', async () => {
    const reader = useChapterReader({
      loadConfig: async () => bundle(true),
      synthesize: vi.fn(async () => new Blob(['x'])),
      notify: vi.fn(),
    })
    const playback = reader.start('标题', '正文。')
    await vi.waitFor(() => expect(reader.status.value).not.toBe('idle'))
    const spokenBefore = browserSpeech.spoken.length
    reader.previewVoice()
    expect(browserSpeech.spoken.length).toBe(spokenBefore)
    reader.stop()
    await playback
  })

  it('uses browser speech immediately when no default TTS is configured', async () => {
    const reader = useChapterReader({
      loadConfig: async () => bundle(false),
      synthesize: vi.fn(),
      notify: vi.fn(),
    })

    await reader.start('第一章', '正文。')

    expect(browserSpeech.spoken.map((text) => text.trim())).toEqual(['第一章', '正文。'])
    // 每段前置静音填充，规避系统 TTS 裁掉首字
    expect(browserSpeech.spoken.every((text) => text.startsWith(' '))).toBe(true)
    expect(reader.status.value).toBe('idle')
  })

  it('clears the speech queue before each segment to avoid clipped first chars', async () => {
    const reader = useChapterReader({
      loadConfig: async () => bundle(false),
      synthesize: vi.fn(),
      notify: vi.fn(),
    })

    await reader.start('第一章', '第一段。第二段。')

    // 每段 speak 前都应清队列（含 start 初始 stop 的一次），次数不少于 spoken 段数
    expect(browserSpeech.spoken.length).toBeGreaterThanOrEqual(2)
    expect(browserSpeech.cancel).toHaveBeenCalledTimes(
      browserSpeech.spoken.length + 1,
    )
  })

  it('exposes paragraph progress aligned with displayed paragraphs', async () => {
    const reader = useChapterReader({
      loadConfig: async () => bundle(false),
      synthesize: vi.fn(),
      notify: vi.fn(),
    })

    await reader.start('第一章', '段落一。\n\n段落二。')

    // 正文两个段落，与 ChapterContent 展示段落一致，用于高亮与进度
    expect(reader.paragraphCount.value).toBe(2)
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

    expect(browserSpeech.spoken.map((text) => text.trim())).toEqual(['失败段。'])
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
