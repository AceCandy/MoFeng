// AIMETA P=章节朗读组合函数_分段与播放队列|R=TTS音频_浏览器回退_播放状态_段落进度|NR=不含章节数据查询|E=compose:useChapterReader|X=internal|A=播放状态机|D=vue,api:tts|S=dom,net|RD=./README.ai
import { computed, getCurrentInstance, onBeforeUnmount, readonly, ref, type Ref } from 'vue'

import { getLLMConfigBundle, type LLMConfigBundle, type TTSProtocol } from '@/api/llm'
import { synthesizeSpeech } from '@/api/tts'
import { globalAlert } from '@/composables/useAlert'
import { splitChapterParagraphs } from '@/utils/chapterText'


export type ReaderStatus = 'idle' | 'generating' | 'playing' | 'paused'

interface ChapterReaderDependencies {
  loadConfig?: () => Promise<LLMConfigBundle>
  synthesize?: (
    text: string,
    options?: { voice?: string; speed?: number },
    signal?: AbortSignal,
  ) => Promise<Blob>
  notify?: (message: string, type: 'info' | 'error') => void
}

interface ChapterReader {
  status: Readonly<Ref<ReaderStatus>>
  isBrowserFallback: Readonly<Ref<boolean>>
  /** 是否配了可用的默认 TTS 模型；挂载与每次朗读前刷新，决定走模型还是浏览器回退 */
  hasModelTTS: Readonly<Ref<boolean>>
  /** 默认 TTS 模型的音色名（tts_voice），供朗读控件只读展示 */
  modelVoiceLabel: Readonly<Ref<string>>
  /** 默认 TTS 模型的协议，决定控件音色候选与后端接口 */
  modelProtocol: Readonly<Ref<TTSProtocol>>
  /** 当前选择的模型音色（全局偏好，localStorage），供控件双向绑定 */
  modelVoice: Readonly<Ref<string>>
  /** 当前协议下的可选模型音色候选 */
  modelVoiceOptions: Readonly<Ref<ModelVoiceOption[]>>
  /** 当前朗读到的正文段落下标，-1 表示标题阶段或空闲，与正文 <p> 一一对应 */
  currentParagraphIndex: Readonly<Ref<number>>
  /** 正文段落数，用于展示进度 */
  paragraphCount: Readonly<Ref<number>>
  /** 浏览器朗读音色 URI（空表示自动选），每台机器独立、存 localStorage */
  voiceURI: Readonly<Ref<string>>
  /** 朗读倍速，浏览器与模型 TTS 通用 */
  rate: Readonly<Ref<number>>
  start: (title: string, content: string) => Promise<void>
  pause: () => void
  resume: () => void
  stop: () => void
  setVoiceURI: (uri: string) => void
  setRate: (rate: number) => void
  setModelVoice: (voice: string) => void
  previewVoice: () => Promise<void>
  /** 重新拉取配置，刷新 hasModelTTS / modelVoiceLabel */
  refreshTTSConfig: () => Promise<void>
}

interface PlaybackSegment {
  text: string
  /** 所属正文段落下标，-1 表示标题段（正文里无对应 <p>） */
  paragraphIndex: number
}

const TTS_LIMIT = 2500
/** 段间留白：Chrome 连续 speak 会裁每段首字，cancel 后留足时间让队列收敛 */
const SEGMENT_GAP_MS = 120
/** 段首静音填充：系统 TTS 会裁掉 utterance 开头若干毫秒，前置空格让被裁的是填充而非正文首字 */
const LEADING_FILLER = ' '
const VOICE_STORAGE_KEY = 'mofeng:reader-voice'
const RATE_STORAGE_KEY = 'mofeng:reader-rate'
/** 模型 TTS 全局音色偏好（朗读控件选择，按协议匹配候选），每台机器独立、存 localStorage */
const MODEL_VOICE_STORAGE_KEY = 'mofeng:reader-model-voice'
interface ModelVoiceOption {
  /** 传后端的音色 id */
  voice: string
  /** 下拉展示名（含性别与语言） */
  label: string
}
// 预置音色 label 标注性别与语言（依据小米 MiMo 与 OpenAI 官方音色说明）
const MIMO_PRESET_VOICES: ModelVoiceOption[] = [
  { voice: '冰糖', label: '冰糖 · 女 · 中文' },
  { voice: '茉莉', label: '茉莉 · 女 · 中文' },
  { voice: '苏打', label: '苏打 · 男 · 中文' },
  { voice: '白桦', label: '白桦 · 男 · 中文' },
  { voice: 'Mia', label: 'Mia · 女 · 英文' },
  { voice: 'Chloe', label: 'Chloe · 女 · 英文' },
  { voice: 'Milo', label: 'Milo · 男 · 英文' },
  { voice: 'Dean', label: 'Dean · 男 · 英文' },
]
const OPENAI_PRESET_VOICES: ModelVoiceOption[] = [
  { voice: 'alloy', label: 'alloy · 中性 · 英文' },
  { voice: 'echo', label: 'echo · 男 · 英文' },
  { voice: 'fable', label: 'fable · 中性 · 英文' },
  { voice: 'onyx', label: 'onyx · 男 · 英文' },
  { voice: 'nova', label: 'nova · 女 · 英文' },
  { voice: 'shimmer', label: 'shimmer · 女 · 英文' },
]
/** 试听固定样例句 */
const PREVIEW_SAMPLE = '墨痕轻染，字字如玉。'

const splitLongUnit = (unit: string, limit: number): string[] => {
  if (unit.length <= limit) return [unit]
  const chunks: string[] = []
  for (let index = 0; index < unit.length; index += limit) {
    chunks.push(unit.slice(index, index + limit))
  }
  return chunks
}

/** 按正文展示段落构建朗读计划：标题段 + 正文段（超长段内部按字数切给 TTS），记录每段所属正文下标 */
const buildPlayback = (
  title: string,
  content: string,
  limit = TTS_LIMIT,
): { segments: PlaybackSegment[]; paragraphCount: number } => {
  const segments: PlaybackSegment[] = []
  for (const chunk of splitLongUnit(title.trim(), limit).filter(Boolean)) {
    segments.push({ text: chunk, paragraphIndex: -1 })
  }
  const paragraphs = splitChapterParagraphs(content)
  paragraphs.forEach((paragraph, index) => {
    for (const chunk of splitLongUnit(paragraph, limit)) {
      segments.push({ text: chunk, paragraphIndex: index })
    }
  })
  return { segments, paragraphCount: paragraphs.length }
}

/** 选中文语音：Windows 本地微软桌面语音在 Edge/Chrome 有裁首字 bug，
 *  优先大陆普通话 zh-CN 的在线神经语音（Edge 命名为 "Online (Natural)"） */
export const pickChineseVoice = (): SpeechSynthesisVoice | null => {
  const voices = window.speechSynthesis?.getVoices?.() ?? []
  if (voices.length === 0) return null
  const mandarin = voices.filter((voice) => {
    const lang = voice.lang?.toLowerCase() ?? ''
    return lang === 'zh-cn' || lang === 'zh'
  })
  const pool = mandarin.length > 0
    ? mandarin
    : voices.filter((voice) => voice.lang?.toLowerCase().startsWith('zh'))
  if (pool.length === 0) return null
  return pool.find((voice) => /natural|neural/i.test(voice.name)) ?? pool[0]
}

export const useChapterReader = (
  dependencies: ChapterReaderDependencies = {},
): ChapterReader => {
  const loadConfig = dependencies.loadConfig ?? getLLMConfigBundle
  const synthesize = dependencies.synthesize ?? synthesizeSpeech
  const notify = dependencies.notify ?? ((message, type) => globalAlert.showToast(message, type))
  const status = ref<ReaderStatus>('idle')
  const isBrowserFallback = ref(false)
  /** 是否配了可用的默认 TTS 模型；挂载与每次朗读前刷新 */
  const hasModelTTS = ref(false)
  /** 默认 TTS 模型音色名，供控件只读展示 */
  const modelVoiceLabel = ref('默认')
  /** 默认 TTS 模型协议，决定音色候选与后端接口 */
  const modelProtocol = ref<TTSProtocol>('mimo_chat_audio')
  /** 朗读控件选择的模型音色（全局偏好） */
  const modelVoice = ref(
    typeof localStorage !== 'undefined' ? localStorage.getItem(MODEL_VOICE_STORAGE_KEY) ?? '' : '',
  )
  const currentParagraphIndex = ref(-1)
  const paragraphCount = ref(0)
  const storedRate = typeof localStorage !== 'undefined' ? Number(localStorage.getItem(RATE_STORAGE_KEY)) : NaN
  const voiceURI = ref(
    typeof localStorage !== 'undefined' ? localStorage.getItem(VOICE_STORAGE_KEY) ?? '' : '',
  )
  const rate = ref(Number.isFinite(storedRate) && storedRate > 0 ? storedRate : 1)
  let runId = 0
  let abortController: AbortController | null = null
  let audio: HTMLAudioElement | null = null
  let objectUrl: string | null = null
  let resolveCurrentPlayback: (() => void) | null = null
  let previewAudio: HTMLAudioElement | null = null
  let previewUrl: string | null = null

  const releaseAudio = () => {
    if (audio) {
      audio.onended = null
      audio.onerror = null
      audio.pause()
      audio = null
    }
    if (objectUrl) {
      URL.revokeObjectURL(objectUrl)
      objectUrl = null
    }
  }

  // 优先用户在播放条选的音色，否则按 pickChineseVoice 自动选
  const resolveVoice = (): SpeechSynthesisVoice | null => {
    const voices = window.speechSynthesis?.getVoices?.() ?? []
    const matched = voiceURI.value
      ? voices.find((voice) => voice.voiceURI === voiceURI.value)
      : undefined
    return matched ?? pickChineseVoice()
  }

  const setVoiceURI = (uri: string) => {
    voiceURI.value = uri
    if (typeof localStorage !== 'undefined') localStorage.setItem(VOICE_STORAGE_KEY, uri)
  }

  const setRate = (next: number) => {
    if (next > 0) {
      rate.value = next
      if (typeof localStorage !== 'undefined') localStorage.setItem(RATE_STORAGE_KEY, String(next))
    }
  }

  /** 当前协议下的模型音色候选 */
  const modelVoiceOptions = computed(() =>
    modelProtocol.value === 'openai_speech' ? OPENAI_PRESET_VOICES : MIMO_PRESET_VOICES,
  )

  const persistModelVoice = (voice: string) => {
    if (typeof localStorage !== 'undefined') localStorage.setItem(MODEL_VOICE_STORAGE_KEY, voice)
  }

  const setModelVoice = (voice: string) => {
    modelVoice.value = voice
    persistModelVoice(voice)
  }

  /** 拉取配置，更新模型音色相关状态；挂载与每次朗读前调用 */
  const refreshTTSConfig = async () => {
    try {
      const config = await loadConfig()
      const defaultTTS = config.models.find(
        (model) => model.is_enabled && model.is_default_tts && Boolean(model.capabilities.tts),
      )
      hasModelTTS.value = Boolean(defaultTTS)
      modelVoiceLabel.value = defaultTTS?.tts_voice?.trim() || '默认'
      if (defaultTTS?.tts_protocol) {
        modelProtocol.value = defaultTTS.tts_protocol
      }
      // 切换协议后，若已存音色不在新候选内，回退到候选首个
      const options = modelVoiceOptions.value
      if (options.length && !options.some((option) => option.voice === modelVoice.value)) {
        setModelVoice(options[0].voice)
      }
    } catch {
      hasModelTTS.value = false
      modelVoiceLabel.value = '默认'
    }
  }

  const stopPreview = () => {
    if (previewAudio) {
      previewAudio.onended = null
      previewAudio.onerror = null
      previewAudio.pause()
      previewAudio = null
    }
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl)
      previewUrl = null
    }
  }

  /** 试听模型音色：合成固定样例句并播放；借用 status=generating 防重入（按钮随之禁用） */
  const previewModelVoice = async () => {
    stopPreview()
    status.value = 'generating'
    try {
      const blob = await synthesize(
        PREVIEW_SAMPLE,
        { voice: modelVoice.value, speed: rate.value },
        abortController?.signal,
      )
      if (status.value !== 'generating') return
      previewUrl = URL.createObjectURL(blob)
      previewAudio = new Audio(previewUrl)
      previewAudio.playbackRate = rate.value
      const finish = () => {
        stopPreview()
        if (status.value === 'generating') status.value = 'idle'
      }
      previewAudio.onended = finish
      previewAudio.onerror = finish
      void previewAudio.play().catch(() => {
        notify('模型试听失败。', 'error')
        finish()
      })
    } catch {
      notify('模型试听失败。', 'error')
      stopPreview()
      if (status.value === 'generating') status.value = 'idle'
    }
  }

  /** 试听当前音色：仅 idle 可用；配了模型走模型合成，否则浏览器 speechSynthesis */
  const previewVoice = async () => {
    if (status.value !== 'idle') return
    if (hasModelTTS.value) {
      await previewModelVoice()
      return
    }
    const speech = window.speechSynthesis
    if (!speech || typeof SpeechSynthesisUtterance === 'undefined') return
    speech.cancel()
    const utterance = new SpeechSynthesisUtterance(`${LEADING_FILLER}${PREVIEW_SAMPLE}`)
    const voice = resolveVoice()
    if (voice) utterance.voice = voice
    utterance.lang = 'zh-CN'
    utterance.rate = rate.value
    speech.speak(utterance)
  }

  const stop = () => {
    runId += 1
    abortController?.abort()
    abortController = null
    releaseAudio()
    stopPreview()
    window.speechSynthesis?.cancel()
    resolveCurrentPlayback?.()
    resolveCurrentPlayback = null
    status.value = 'idle'
    isBrowserFallback.value = false
    currentParagraphIndex.value = -1
  }

  const playAudio = async (blob: Blob, currentRun: number): Promise<void> => {
    if (currentRun !== runId) return
    releaseAudio()
    objectUrl = URL.createObjectURL(blob)
    audio = new Audio(objectUrl)
    audio.playbackRate = rate.value
    status.value = 'playing'
    await new Promise<void>((resolve, reject) => {
      resolveCurrentPlayback = resolve
      if (!audio) return resolve()
      audio.onended = () => resolve()
      audio.onerror = () => reject(new Error('音频播放失败'))
      void audio.play().catch(reject)
    })
    resolveCurrentPlayback = null
    releaseAudio()
  }

  const playBrowserSegments = async (
    playback: PlaybackSegment[],
    startIndex: number,
    currentRun: number,
  ): Promise<void> => {
    const speech = window.speechSynthesis
    if (!speech || typeof SpeechSynthesisUtterance === 'undefined') {
      notify('当前浏览器不支持语音朗读。', 'error')
      return
    }
    isBrowserFallback.value = true
    for (let index = startIndex; index < playback.length && currentRun === runId; index += 1) {
      status.value = 'playing'
      currentParagraphIndex.value = playback[index].paragraphIndex
      // 清掉上一段在队列里的残留并留白再入队，
      // 规避 Chrome 连续 speak 裁掉每段首字的问题（延时不足会复发）
      speech.cancel()
      await new Promise<void>((resolve) => setTimeout(resolve, SEGMENT_GAP_MS))
      if (currentRun !== runId) return
      await new Promise<void>((resolve, reject) => {
        resolveCurrentPlayback = resolve
        const utterance = new SpeechSynthesisUtterance(`${LEADING_FILLER}${playback[index].text}`)
        const voice = resolveVoice()
        if (voice) utterance.voice = voice
        utterance.lang = 'zh-CN'
        utterance.rate = rate.value
        utterance.onend = () => resolve()
        utterance.onerror = () => reject(new Error('浏览器朗读失败'))
        speech.speak(utterance)
      })
      resolveCurrentPlayback = null
    }
  }

  const playModelSegments = async (playback: PlaybackSegment[], currentRun: number): Promise<void> => {
    const pending = new Map<number, Promise<Blob>>()
    const requestSegment = (index: number): Promise<Blob> => {
      const existing = pending.get(index)
      if (existing) return existing
      const request = synthesize(
        playback[index].text,
        { voice: modelVoice.value, speed: rate.value },
        abortController?.signal,
      )
      // 预取可能早于消费失败，提前附加处理器避免未处理拒绝告警。
      void request.catch(() => undefined)
      pending.set(index, request)
      return request
    }

    for (let index = 0; index < playback.length && currentRun === runId; index += 1) {
      status.value = 'generating'
      currentParagraphIndex.value = playback[index].paragraphIndex
      try {
        const blob = await requestSegment(index)
        if (currentRun !== runId) return
        if (index + 1 < playback.length) {
          requestSegment(index + 1)
        }
        await playAudio(blob, currentRun)
      } catch (error) {
        if (currentRun !== runId) return
        abortController?.abort()
        const reason = error instanceof Error && error.message ? error.message : '未知错误'
        notify(`模型朗读失败（${reason}），已切换浏览器朗读。`, 'info')
        await playBrowserSegments(playback, index, currentRun)
        return
      }
    }
  }

  const start = async (title: string, content: string): Promise<void> => {
    stop()
    const currentRun = runId
    const { segments: playback, paragraphCount: count } = buildPlayback(title, content)
    if (playback.length === 0) return
    paragraphCount.value = count
    currentParagraphIndex.value = -1
    abortController = new AbortController()
    status.value = 'generating'
    await refreshTTSConfig()
    if (currentRun !== runId) return
    try {
      if (hasModelTTS.value) {
        await playModelSegments(playback, currentRun)
      } else {
        await playBrowserSegments(playback, 0, currentRun)
      }
    } catch {
      if (currentRun === runId) {
        notify('语音朗读已中止。', 'error')
      }
    } finally {
      if (currentRun === runId) {
        releaseAudio()
        abortController = null
        status.value = 'idle'
        isBrowserFallback.value = false
        currentParagraphIndex.value = -1
      }
    }
  }

  const pause = () => {
    if (status.value !== 'playing') return
    audio?.pause()
    window.speechSynthesis?.pause()
    status.value = 'paused'
  }

  const resume = () => {
    if (status.value !== 'paused') return
    if (audio) {
      void audio.play()
    } else {
      window.speechSynthesis?.resume()
    }
    status.value = 'playing'
  }

  if (getCurrentInstance()) {
    onBeforeUnmount(stop)
    void refreshTTSConfig()
  }

  return {
    status: readonly(status),
    isBrowserFallback: readonly(isBrowserFallback),
    hasModelTTS: readonly(hasModelTTS),
    modelVoiceLabel: readonly(modelVoiceLabel),
    modelProtocol: readonly(modelProtocol),
    modelVoice: readonly(modelVoice),
    modelVoiceOptions,
    currentParagraphIndex: readonly(currentParagraphIndex),
    paragraphCount: readonly(paragraphCount),
    voiceURI: readonly(voiceURI),
    rate: readonly(rate),
    start,
    pause,
    resume,
    stop,
    setVoiceURI,
    setRate,
    setModelVoice,
    previewVoice,
    refreshTTSConfig,
  }
}
