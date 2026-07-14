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


class FakeBufferSource {
  static instances: FakeBufferSource[] = []
  buffer: AudioBuffer | null = null
  playbackRate = { value: 1 }
  onended: (() => void) | null = null

  constructor() {
    FakeBufferSource.instances.push(this)
  }
  connect = vi.fn()
  disconnect = vi.fn()
  start = vi.fn()
  stop = vi.fn()
}


class FakeAudioBuffer {
  duration = 5
  getChannelData() {
    return new Float32Array(1000)
  }
}


class FakeAudioContext {
  static instances: FakeAudioContext[] = []
  currentTime = 0
  state = 'running'
  destination = {}

  constructor() {
    FakeAudioContext.instances.push(this)
  }
  decodeAudioData = vi.fn(async () => new FakeAudioBuffer() as unknown as AudioBuffer)
  createBufferSource = vi.fn(() => new FakeBufferSource() as unknown as AudioBufferSourceNode)
  resume = vi.fn(async () => undefined)
  close = vi.fn(async () => undefined)
}


class FakeAudioElement {
  static instances: FakeAudioElement[] = []
  src = ''
  playbackRate = 1
  preservesPitch: boolean | undefined
  mozPreservesPitch: boolean | undefined
  webkitPreservesPitch: boolean | undefined
  onended: (() => void) | null = null
  onerror: (() => void) | null = null
  currentTime = 0
  duration = 5

  constructor() {
    FakeAudioElement.instances.push(this)
  }
  play = vi.fn(async () => undefined)
  pause = vi.fn()
  load = vi.fn()
  removeAttribute = vi.fn()
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
  FakeBufferSource.instances = []
  FakeAudioContext.instances = []
  FakeAudioElement.instances = []
  browserSpeech.spoken = []
  vi.clearAllMocks()
  // 测试环境 Blob 可能缺 arrayBuffer（Web Audio decodeAudioData 需要），补齐
  if (typeof Blob.prototype.arrayBuffer !== 'function') {
    Blob.prototype.arrayBuffer = function (this: Blob) {
      return Promise.resolve(new ArrayBuffer(this.size || 8))
    }
  }
  Object.defineProperty(window, 'AudioContext', { value: FakeAudioContext, configurable: true, writable: true })
  Object.defineProperty(window, 'Audio', { value: FakeAudioElement, configurable: true, writable: true })
  // jsdom 无 URL.createObjectURL/revokeObjectURL，<audio> 主路径需要，补 stub
  if (typeof URL.createObjectURL !== 'function') {
    URL.createObjectURL = vi.fn(() => 'blob:mock')
  }
  if (typeof URL.revokeObjectURL !== 'function') {
    URL.revokeObjectURL = vi.fn()
  }
  vi.stubGlobal('SpeechSynthesisUtterance', FakeUtterance)
  Object.defineProperty(window, 'speechSynthesis', { value: browserSpeech, configurable: true })
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

  it('prefetches segments ahead of playback and supports pause resume and stop', async () => {
    const synthesize = vi.fn(async (text: string) => new Blob([text], { type: 'audio/mpeg' }))
    const reader = useChapterReader({
      loadConfig: async () => bundle(true),
      synthesize,
      notify: vi.fn(),
    })

    const playback = reader.start('标题', '第一段正文内容必须超过二十个字才不会被合并。\n\n第二段正文内容同样超过二十个字不会被合并呀。')
    await vi.waitFor(() => expect(FakeAudioElement.instances).toHaveLength(1))
    // 逐段合成：标题 + 两段正文 = 3 段，启动即预热这 3 段（PREFETCH_AHEAD=2）
    expect(synthesize).toHaveBeenCalledTimes(3)

    reader.pause()
    expect(reader.status.value).toBe('paused')

    reader.resume()
    expect(reader.status.value).toBe('playing')

    reader.stop()
    expect(reader.status.value).toBe('idle')
    await playback
  })

  it('keeps each mid-size paragraph whole without splitting at the merge target', async () => {
    const synthesize = vi.fn(async (text: string) => new Blob([text], { type: 'audio/mpeg' }))
    const reader = useChapterReader({
      loadConfig: async () => bundle(true),
      synthesize,
      notify: vi.fn(),
    })

    // 两段正文均介于合并阈值(400)与 TTS 上限(2500)之间：应各自独占一条合成请求，
    // 且整段送合成、绝不在段落内部切片（硬约束：不切断段落）
    const longA = '首段标记' + '正文内容'.repeat(130)
    const longB = '末段标记' + '正文内容'.repeat(130)
    const playback = reader.start('标题', `${longA}\n\n${longB}`)
    await vi.waitFor(() => expect(FakeAudioElement.instances).toHaveLength(1))
    // 标题 + 两段独占正文 = 3 次请求；每段以完整原文送合成（前后仅填充空格与句号）
    expect(synthesize).toHaveBeenCalledTimes(3)
    expect(synthesize.mock.calls.some((call) => call[0] === ` ${longA}。`)).toBe(true)
    expect(synthesize.mock.calls.some((call) => call[0] === ` ${longB}。`)).toBe(true)
    reader.stop()
    await playback
  })

  it('merges short paragraphs (under threshold) into the next to avoid audio silence', async () => {
    const synthesize = vi.fn(async (text: string) => new Blob([text], { type: 'audio/mpeg' }))
    const reader = useChapterReader({
      loadConfig: async () => bundle(true),
      synthesize,
      notify: vi.fn(),
    })
    // 长段 + 短段(<15) + 长段：短段并入后一段，不单独合成（规避 <audio> 对短音频的静音 bug）
    const longA = '这是第一段足够长不会被合并的正文内容测试呀。'
    const short = '他笑了。'
    const longB = '这是第三段足够长不会被合并的正文内容测试呀。'
    const playback = reader.start('标题', `${longA}\n\n${short}\n\n${longB}`)
    await vi.waitFor(() => expect(FakeAudioElement.instances).toHaveLength(1))
    // 标题 + longA + (short+longB 合并) = 3 次请求；short 不单独成段
    expect(synthesize).toHaveBeenCalledTimes(3)
    expect(synthesize.mock.calls.some((call) => call[0] === ` ${short}。`)).toBe(false)
    // short 并入 longB：换行连接，前后填充空格与句号
    expect(synthesize.mock.calls.some((call) => call[0] === ` ${short}\n${longB}。`)).toBe(true)
    reader.stop()
    await playback
  })

  it('merges a trailing short paragraph back into the previous segment', async () => {
    const synthesize = vi.fn(async (text: string) => new Blob([text], { type: 'audio/mpeg' }))
    const reader = useChapterReader({
      loadConfig: async () => bundle(true),
      synthesize,
      notify: vi.fn(),
    })
    // 长段 + 末尾短段：末尾短段无下一段可合并，回并到上一段一起合成
    const longA = '这是第一段足够长不会被合并的正文内容测试呀。'
    const trailing = '他走了。'
    const playback = reader.start('标题', `${longA}\n\n${trailing}`)
    await vi.waitFor(() => expect(FakeAudioElement.instances).toHaveLength(1))
    // 标题 + (longA+trailing 合并) = 2 次请求；trailing 不单独成段
    expect(synthesize).toHaveBeenCalledTimes(2)
    expect(synthesize.mock.calls.some((call) => call[0] === ` ${trailing}。`)).toBe(false)
    expect(synthesize.mock.calls.some((call) => call[0] === ` ${longA}\n${trailing}。`)).toBe(true)
    reader.stop()
    await playback
  })

  it('caps consecutive tiny paragraphs at the merge limit (3 segments)', async () => {
    const synthesize = vi.fn(async (text: string) => new Blob([text], { type: 'audio/mpeg' }))
    const reader = useChapterReader({
      loadConfig: async () => bundle(true),
      synthesize,
      notify: vi.fn(),
    })
    // 四个连续极短段 + 长段：前三个极短段(各 2 字)合并到上限(3 段)即停，
    // 第四个极短段另起合并组并吸收后面的长段（验证 3 段上限：达上限即停，不再吸收下一段）
    const tiny1 = '嗯。'
    const tiny2 = '啊。'
    const tiny3 = '哦。'
    const tiny4 = '诶。'
    const long = '这是一段足够长的正文内容不会被合并到短段组里。'
    const playback = reader.start('标题', `${tiny1}\n\n${tiny2}\n\n${tiny3}\n\n${tiny4}\n\n${long}`)
    await vi.waitFor(() => expect(FakeAudioElement.instances).toHaveLength(1))
    // 标题 + (tiny1+tiny2+tiny3 达上限合并) + (tiny4+long) = 3 次请求
    expect(synthesize).toHaveBeenCalledTimes(3)
    // 前三个极短段合成一条（3 段上限，不再吸收 tiny4）
    expect(synthesize.mock.calls.some((call) => call[0] === ` ${tiny1}\n${tiny2}\n${tiny3}。`)).toBe(true)
    // tiny4 没有单独合成，而是和 long 合并
    expect(synthesize.mock.calls.some((call) => call[0] === ` ${tiny4}。`)).toBe(false)
    expect(synthesize.mock.calls.some((call) => call[0] === ` ${tiny4}\n${long}。`)).toBe(true)
    reader.stop()
    await playback
  })

  it('merges by character count excluding punctuation (含标点 >20 但纯字数 ≤20 仍合并)', async () => {
    const synthesize = vi.fn(async (text: string) => new Blob([text], { type: 'audio/mpeg' }))
    const reader = useChapterReader({
      loadConfig: async () => bundle(true),
      synthesize,
      notify: vi.fn(),
    })
    // 阈值按纯字数（去标点）判断：这句含标点 22、纯汉字 19，仍应合并（旧含标点口径会判 >20 不合并）
    const exact = '经纪人看着我的表情，把后半句话，咽回去了啊。' // length=22, 纯字数=19
    const long = '这是一段足够长的正文内容不会被合并的测试用例。'
    const playback = reader.start('标题', `${exact}\n\n${long}`)
    await vi.waitFor(() => expect(FakeAudioElement.instances).toHaveLength(1))
    // 标题 + (exact+long 合并) = 2 次请求；exact 不单独成段
    expect(synthesize).toHaveBeenCalledTimes(2)
    expect(synthesize.mock.calls.some((call) => call[0] === ` ${exact}。`)).toBe(false)
    expect(synthesize.mock.calls.some((call) => call[0] === ` ${exact}\n${long}。`)).toBe(true)
    reader.stop()
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
    await vi.waitFor(() => expect(FakeAudioElement.instances).toHaveLength(1))
    // 标题段 <audio> 正常播完
    FakeAudioElement.instances[0].onended?.()
    await playback

    expect(browserSpeech.spoken.map((text) => text.trim())).toEqual(['失败段。'])
    expect(notify).toHaveBeenCalledWith('模型朗读失败（upstream failed），已切换浏览器朗读。', 'info')
  })

  it('falls back to web audio on <audio> error, then to browser on empty audio', async () => {
    const synthesize = vi.fn(async () => new Blob(['x'], { type: 'audio/wav' }))
    const notify = vi.fn()
    const reader = useChapterReader({
      loadConfig: async () => bundle(true),
      synthesize,
      notify,
    })

    const playback = reader.start('标题', '正文。')
    await vi.waitFor(() => expect(FakeAudioElement.instances).toHaveLength(1))
    // 主路径 <audio> 解码失败 → 兜底 Web Audio
    FakeAudioElement.instances[0].onerror?.()
    await vi.waitFor(() => expect(FakeBufferSource.instances).toHaveLength(1))
    // Web Audio 兜底也拿到空音频（currentTime 仍为 0，elapsed < 阈值）→ 抛错 → 切浏览器
    FakeBufferSource.instances[0].onended?.()
    await playback

    expect(browserSpeech.spoken.map((text) => text.trim())).toEqual(['标题', '正文。'])
    expect(notify).toHaveBeenCalledWith(
      '模型朗读失败（返回的音频为空或损坏），已切换浏览器朗读。',
      'info',
    )
  })

  it('resumes playback on <audio> error via web audio fallback', async () => {
    const synthesize = vi.fn(async (text: string) => new Blob([text], { type: 'audio/mpeg' }))
    const reader = useChapterReader({
      loadConfig: async () => bundle(true),
      synthesize,
      notify: vi.fn(),
    })

    const playback = reader.start('标题', '正文。')
    await vi.waitFor(() => expect(FakeAudioElement.instances).toHaveLength(1))
    // 标题段 <audio> 失败 → 兜底 Web Audio 接管
    FakeAudioElement.instances[0].onerror?.()
    await vi.waitFor(() => expect(FakeBufferSource.instances).toHaveLength(1))
    expect(reader.status.value).toBe('playing')
    // 推进时长让 Web Audio 视为有效音频，标题段经兜底正常播完
    FakeAudioContext.instances[0].currentTime = 5
    FakeBufferSource.instances[0].onended?.()
    // 标题段结束 → 正文段回到 <audio> 主路径并推进
    await vi.waitFor(() => expect(reader.currentParagraphIndex.value).toBe(0))
    FakeAudioElement.instances[0].onended?.()
    reader.stop()
    await playback
  })

  it('pauses resumes and stops on the web audio fallback path', async () => {
    const synthesize = vi.fn(async (text: string) => new Blob([text], { type: 'audio/mpeg' }))
    const reader = useChapterReader({
      loadConfig: async () => bundle(true),
      synthesize,
      notify: vi.fn(),
    })

    const playback = reader.start('标题', '正文。')
    await vi.waitFor(() => expect(FakeAudioElement.instances).toHaveLength(1))
    // 标题段 <audio> 失败 → 兜底 Web Audio 接管
    FakeAudioElement.instances[0].onerror?.()
    await vi.waitFor(() => expect(FakeBufferSource.instances).toHaveLength(1))
    expect(reader.status.value).toBe('playing')

    reader.pause()
    expect(reader.status.value).toBe('paused')
    // webaudio 暂停会 stop 当前 source（activeBackend='webaudio' 分派）
    expect(FakeBufferSource.instances[0].stop).toHaveBeenCalled()

    reader.resume()
    expect(reader.status.value).toBe('playing')
    // 续播重建 source（instances 长到 2，从 startOffset 接续）
    await vi.waitFor(() => expect(FakeBufferSource.instances).toHaveLength(2))

    reader.stop()
    expect(reader.status.value).toBe('idle')
    await playback
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

  it('refreshTTSConfig exposes the default TTS model availability and its voice', async () => {
    const reader = useChapterReader({
      loadConfig: async () => bundle(true),
      synthesize: vi.fn(),
      notify: vi.fn(),
    })
    await reader.refreshTTSConfig()
    expect(reader.hasModelTTS.value).toBe(true)
    expect(reader.modelVoiceLabel.value).toBe('alloy')

    const unconfigured = useChapterReader({
      loadConfig: async () => bundle(false),
      synthesize: vi.fn(),
      notify: vi.fn(),
    })
    await unconfigured.refreshTTSConfig()
    expect(unconfigured.hasModelTTS.value).toBe(false)
    expect(unconfigured.modelVoiceLabel.value).toBe('默认')
  })

  it('previewVoice synthesizes a sample with the model voice when configured', async () => {
    const synthesize = vi.fn(async () => new Blob(['x'], { type: 'audio/mpeg' }))
    const reader = useChapterReader({
      loadConfig: async () => bundle(true),
      synthesize,
      notify: vi.fn(),
    })
    await reader.refreshTTSConfig()

    reader.previewVoice()

    await vi.waitFor(() =>
      expect(synthesize).toHaveBeenCalledWith(
        '墨痕轻染，字字如玉。',
        expect.objectContaining({ voice: 'alloy' }),
        undefined,
      ),
    )
    // 配了模型时不走浏览器 speech
    expect(browserSpeech.spoken.length).toBe(0)
    reader.stop()
  })
})
