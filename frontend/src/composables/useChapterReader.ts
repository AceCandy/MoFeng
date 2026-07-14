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
  /** 是否走浏览器 speechSynthesis（未配模型或模型失败兜底） */
  isBrowserFallback: Readonly<Ref<boolean>>
  /** 是否配了可用的默认 TTS 模型；挂载与每次朗读前刷新，决定走模型还是浏览器回退 */
  hasModelTTS: Readonly<Ref<boolean>>
  /** 默认 TTS 模型的音色名（tts_voice），供朗读控件只读展示 */
  modelVoiceLabel: Readonly<Ref<string>>
  /** 默认 TTS 模型协议，决定控件音色候选与后端接口 */
  modelProtocol: Readonly<Ref<TTSProtocol>>
  /** 当前选择的模型音色（全局偏好，localStorage），供控件双向绑定 */
  modelVoice: Readonly<Ref<string>>
  /** 当前协议下的可选模型音色候选 */
  modelVoiceOptions: Readonly<Ref<ModelVoiceOption[]>>
  /** 当前朗读到的正文段落区间起点，-1 表示标题阶段或空闲 */
  currentParagraphIndex: Readonly<Ref<number>>
  /** 当前朗读到的正文段落区间终点（短段合并时覆盖多段，单段时等于 currentParagraphIndex） */
  currentParagraphEnd: Readonly<Ref<number>>
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
  /** 所属正文段落区间起点，-1 表示标题段（正文里无对应 <p>） */
  paragraphIndex: number
  /** 所属正文段落区间终点：短段合并时覆盖多段，单段时等于 paragraphIndex */
  paragraphEnd: number
}

const TTS_LIMIT = 2500
/** 短段合并阈值（纯字数）：≤ 此值（去标点后的汉字+字母+数字）的正文段开启合并组、吸收下一段一起合成。
 *  <audio> 对"长段后的短段"会静音（浏览器媒体管道 bug，JS 状态全正常但无声），
 *  合并后短段不单独播放即可规避；合并段覆盖多段高亮（paragraphEnd） */
const SHORT_PARAGRAPH_MERGE_THRESHOLD = 20
/** 合并组续合阈值（纯字数）：合并后纯字数 ≤ 此值才继续吸收下一段（针对"嗯。""啊。"等极短段） */
const MERGE_CONTINUE_THRESHOLD = 10
/** 单个合并组最多段数：达到即关闭，防止极短段无限合并 */
const MERGE_MAX_SEGMENTS = 3
/** 纯字数：去掉标点/符号/空白后的字符数（汉字+字母+数字）；短段与续合阈值按此判断 */
const charCount = (text: string): number => text.replace(/[^\p{Script=Han}\p{L}\p{N}]/gu, '').length
/** 段间停顿：连续段落衔接需要自然换气，同时留白让播放引擎收敛、避免裁首尾音 */
const SEGMENT_GAP_MS = 400
/** 段首静音填充：合成音频会裁掉开头若干毫秒，前置空格让被裁的是填充而非正文首字 */
const LEADING_FILLER = ' '
/** 段尾填充：合成会截断每段末尾若干毫秒，末尾追加句号生成停顿，让被截的是停顿而非正文末字 */
const TRAILING_FILLER = '。'
/** 模型合成预取窗口：当前段播放时向后预取的段数，减少段间卡顿 */
const PREFETCH_AHEAD = 2
/** 有效音频最短时长（秒）：低于此值视为空/损坏音频，避免静默跳过整段 */
const MIN_VALID_AUDIO_SECONDS = 0.2
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

/** 按正文展示段落构建朗读计划：标题段独立；正文段 ≤ SHORT_PARAGRAPH_MERGE_THRESHOLD 时开启合并组
 *  吸收下一段，合并后总长 ≤ MERGE_CONTINUE_THRESHOLD 则继续吸收，最多 MERGE_MAX_SEGMENTS 段
 *  （规避 <audio> 对短音频的静音 bug）；合并段覆盖多段区间高亮（paragraphEnd）。
 *  单段超 TTS 上限时内部切分；记录每段所属正文段落区间 */
const buildPlayback = (
  title: string,
  content: string,
  limit = TTS_LIMIT,
): { segments: PlaybackSegment[]; paragraphCount: number } => {
  const segments: PlaybackSegment[] = []
  for (const chunk of splitLongUnit(title.trim(), limit).filter(Boolean)) {
    segments.push({ text: chunk, paragraphIndex: -1, paragraphEnd: -1 })
  }
  const paragraphs = splitChapterParagraphs(content)
  // 逐段合并：≤ 阈值的段开启合并组吸收下一段；首段无条件吸收，后续需合并组总长 ≤ 续合阈值；
  // 吸收后若已"够长"(> 续合阈值)或达段数上限则关闭组；末尾未关闭的合并组回并到上一段
  const merged: { text: string; start: number; end: number }[] = []
  let group: { text: string; start: number; end: number; count: number } | null = null
  const closeGroup = () => {
    if (group) {
      merged.push({ text: group.text, start: group.start, end: group.end })
      group = null
    }
  }
  paragraphs.forEach((paragraph, index) => {
    if (group) {
      // count===1 时无条件吸收（首段 ≤ 阈值触发）；之后需合并组总长 ≤ 续合阈值才继续
      const canAbsorb = group.count === 1 || charCount(group.text) <= MERGE_CONTINUE_THRESHOLD
      if (group.count < MERGE_MAX_SEGMENTS && canAbsorb) {
        group.text = `${group.text}\n${paragraph}`
        group.end = index
        group.count += 1
        // 吸收后已够长或达上限：立即关闭，避免末尾过度回并到上一段
        if (group.count >= MERGE_MAX_SEGMENTS || charCount(group.text) > MERGE_CONTINUE_THRESHOLD) {
          closeGroup()
        }
        return
      }
      closeGroup()
    }
    if (charCount(paragraph) <= SHORT_PARAGRAPH_MERGE_THRESHOLD) {
      group = { text: paragraph, start: index, end: index, count: 1 }
    } else {
      merged.push({ text: paragraph, start: index, end: index })
    }
  })
  if (group) {
    if (merged.length > 0) {
      const last = merged[merged.length - 1]
      last.text = `${last.text}\n${group.text}`
      last.end = group.end
    } else {
      merged.push({ text: group.text, start: group.start, end: group.end })
    }
  }
  for (const unit of merged) {
    for (const chunk of splitLongUnit(unit.text, limit)) {
      segments.push({ text: chunk, paragraphIndex: unit.start, paragraphEnd: unit.end })
    }
  }
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

/** <audio> 元素解码/播放失败时抛出，触发兜底切回 Web Audio */
class AudioDecodeError extends Error {
  constructor() {
    super('audio element playback failed')
    this.name = 'AudioDecodeError'
  }
}

export const useChapterReader = (
  dependencies: ChapterReaderDependencies = {},
): ChapterReader => {
  const loadConfig = dependencies.loadConfig ?? getLLMConfigBundle
  const synthesize = dependencies.synthesize ?? synthesizeSpeech
  const notify = dependencies.notify ?? ((message, type) => globalAlert.showToast(message, type))
  const status = ref<ReaderStatus>('idle')
  /** 是否走浏览器 speechSynthesis（未配模型或模型失败兜底） */
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
  const currentParagraphEnd = ref(-1)
  const paragraphCount = ref(0)
  const storedRate = typeof localStorage !== 'undefined' ? Number(localStorage.getItem(RATE_STORAGE_KEY)) : NaN
  const voiceURI = ref(
    typeof localStorage !== 'undefined' ? localStorage.getItem(VOICE_STORAGE_KEY) ?? '' : '',
  )
  const rate = ref(Number.isFinite(storedRate) && storedRate > 0 ? storedRate : 1)
  let runId = 0
  let abortController: AbortController | null = null
  // 模型段播放：主路径用 <audio> 元素（preservesPitch 保调，变速不变调）；
  // <audio> 解码失败的段落兜底回 Web Audio（decodeAudioData 更宽容、能出声但变调）。
  // 后端已把上游 wav 标准化为 16-bit PCM，<audio> 主路径通常不再静音。
  let audioCtx: AudioContext | null = null
  let bufferSource: AudioBufferSourceNode | null = null
  let decodedBuffer: AudioBuffer | null = null
  let startedAt = 0
  let startOffset = 0
  let bufferEndedHandler: (() => void) | null = null
  // 外部强制结束当前播放（stop/换段调用），视为正常完成；audio/webaudio/浏览器三路共用
  let resolvePlayback: (() => void) | null = null
  // 当前模型段播放后端：'audio' 主路径，'webaudio' 兜底；浏览器朗读路径不经过此处
  let activeBackend: 'audio' | 'webaudio' | null = null
  let audioEl: HTMLAudioElement | null = null
  let currentObjectUrl: string | null = null
  let previewEl: HTMLAudioElement | null = null
  // 试听 <audio> 的 objectURL：finish/fail/stopPreview 三处都会 revoke，防打断时泄漏
  let previewObjectUrl: string | null = null

  const getAudioContext = (): AudioContext | null => {
    const Ctor = window.AudioContext
    if (!Ctor) return null
    if (!audioCtx) audioCtx = new Ctor()
    return audioCtx
  }

  const stopBufferSource = () => {
    if (bufferSource) {
      bufferSource.onended = null
      try {
        bufferSource.stop()
      } catch {
        // 已停止
      }
      bufferSource.disconnect()
      bufferSource = null
    }
  }

  // <audio> 主路径保调：preservesPitch 设 true（含历史前缀兼容），变速不变调
  const setPreservePitch = (el: HTMLAudioElement) => {
    const prefixed = el as HTMLAudioElement & {
      preservesPitch?: boolean
      mozPreservesPitch?: boolean
      webkitPreservesPitch?: boolean
    }
    prefixed.preservesPitch = true
    prefixed.mozPreservesPitch = true
    prefixed.webkitPreservesPitch = true
  }

  const getAudioElement = (): HTMLAudioElement | null => {
    if (typeof window === 'undefined' || typeof window.Audio !== 'function') return null
    if (!audioEl) {
      audioEl = new Audio()
      setPreservePitch(audioEl)
    }
    return audioEl
  }

  /** 释放 <audio> 元素：清监听、暂停、移除 src 触发卸载、revoke objectURL */
  const stopAudioElement = () => {
    if (audioEl) {
      audioEl.onended = null
      audioEl.onerror = null
      audioEl.pause()
      audioEl.removeAttribute('src')
      audioEl.load()
      audioEl = null
    }
    if (currentObjectUrl) {
      URL.revokeObjectURL(currentObjectUrl)
      currentObjectUrl = null
    }
  }

  /** 当前已播放秒数：用于暂停续播与空音频判定 */
  const getElapsed = (): number => {
    if (!audioCtx || !decodedBuffer) return 0
    const elapsed = bufferSource ? audioCtx.currentTime - startedAt : 0
    return Math.min(startOffset + Math.max(0, elapsed), decodedBuffer.duration)
  }

  const releasePlayback = () => {
    bufferEndedHandler = null
    stopBufferSource()
    stopAudioElement()
    decodedBuffer = null
    activeBackend = null
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
    if (previewEl) {
      previewEl.onended = null
      previewEl.onerror = null
      previewEl.pause()
      previewEl.removeAttribute('src')
      previewEl.load()
      previewEl = null
    }
    if (previewObjectUrl) {
      URL.revokeObjectURL(previewObjectUrl)
      previewObjectUrl = null
    }
  }

  /** 试听模型音色：合成固定样例句并用 <audio> 播放（保调）；借用 status=generating 防重入（按钮随之禁用） */
  const previewModelVoice = async () => {
    stopPreview()
    status.value = 'generating'
    try {
      const blob = await synthesize(PREVIEW_SAMPLE, { voice: modelVoice.value }, abortController?.signal)
      if (status.value !== 'generating') return
      if (typeof window === 'undefined' || typeof window.Audio !== 'function') {
        notify('模型试听失败。', 'error')
        if (status.value === 'generating') status.value = 'idle'
        return
      }
      const el = new Audio()
      setPreservePitch(el)
      el.playbackRate = rate.value
      const url = URL.createObjectURL(blob)
      previewObjectUrl = url
      el.src = url
      const finish = () => {
        URL.revokeObjectURL(url)
        previewObjectUrl = null
        if (previewEl === el) previewEl = null
        if (status.value === 'generating') status.value = 'idle'
      }
      const fail = () => {
        URL.revokeObjectURL(url)
        previewObjectUrl = null
        if (previewEl === el) previewEl = null
        notify('模型试听失败。', 'error')
        if (status.value === 'generating') status.value = 'idle'
      }
      el.onended = finish
      el.onerror = fail
      previewEl = el
      el.play().catch(fail)
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
    releasePlayback()
    stopPreview()
    window.speechSynthesis?.cancel()
    resolvePlayback?.()
    resolvePlayback = null
    status.value = 'idle'
    isBrowserFallback.value = false
    currentParagraphIndex.value = -1
    currentParagraphEnd.value = -1
  }

  /** 主路径：用 <audio> 元素播放（preservesPitch 保调）；error 时抛 AudioDecodeError 触发兜底 */
  const playWithAudioElement = (blob: Blob, currentRun: number): Promise<void> => {
    status.value = 'playing'
    return new Promise<void>((resolve, reject) => {
      const el = getAudioElement()
      if (!el) {
        reject(new Error('当前浏览器不支持音频播放'))
        return
      }
      if (currentObjectUrl) URL.revokeObjectURL(currentObjectUrl)
      currentObjectUrl = URL.createObjectURL(blob)
      el.src = currentObjectUrl
      el.playbackRate = rate.value
      let settled = false
      const cleanup = () => {
        el.onended = null
        el.onerror = null
      }
      // stop/换段时外部强制结束 → 视为正常完成
      resolvePlayback = () => {
        if (settled) return
        settled = true
        cleanup()
        resolve()
      }
      el.onended = () => {
        if (settled || currentRun !== runId) return
        settled = true
        cleanup()
        resolve()
      }
      el.onerror = () => {
        if (settled || currentRun !== runId) return
        settled = true
        cleanup()
        reject(new AudioDecodeError())
      }
      el.play().catch(() => {
        if (settled || currentRun !== runId) return
        settled = true
        cleanup()
        reject(new AudioDecodeError())
      })
    })
  }

  /** 兜底路径：用 Web Audio（decodeAudioData）播放，能出声但变速会变调 */
  const playWithWebAudio = async (blob: Blob, currentRun: number): Promise<void> => {
    if (currentRun !== runId) return
    stopBufferSource()
    const ctx = getAudioContext()
    if (!ctx) {
      throw new Error('当前浏览器不支持音频播放')
    }
    if (ctx.state === 'suspended') void ctx.resume()
    let buffer: AudioBuffer
    try {
      buffer = await ctx.decodeAudioData(await blob.arrayBuffer())
    } catch {
      throw new Error('音频解码失败')
    }
    if (currentRun !== runId) return
    decodedBuffer = buffer
    startOffset = 0
    status.value = 'playing'
    await new Promise<void>((resolve, reject) => {
      resolvePlayback = resolve
      let finished = false
      bufferEndedHandler = () => {
        if (finished) return
        finished = true
        const elapsed = getElapsed()
        // 空音频未真正播放就 ended：用实际播放进度兜底，避免静默跳过整段
        if (elapsed < MIN_VALID_AUDIO_SECONDS) {
          reject(new Error('返回的音频为空或损坏'))
          return
        }
        resolve()
      }
      const source = ctx.createBufferSource()
      source.buffer = buffer
      source.playbackRate.value = rate.value
      source.connect(ctx.destination)
      source.onended = () => bufferEndedHandler?.()
      bufferSource = source
      startedAt = ctx.currentTime
      try {
        source.start()
      } catch {
        reject(new Error('音频播放失败'))
      }
    })
    resolvePlayback = null
    stopBufferSource()
  }

  /** 播放一段模型音频：<audio> 主路径（保调）→ error 则兜底 Web Audio（能出声） */
  const playAudio = async (blob: Blob, currentRun: number): Promise<void> => {
    activeBackend = 'audio'
    try {
      await playWithAudioElement(blob, currentRun)
    } catch (error) {
      if (currentRun !== runId) return
      if (error instanceof AudioDecodeError) {
        activeBackend = 'webaudio'
        await playWithWebAudio(blob, currentRun)
      } else {
        throw error
      }
    }
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
    // 浏览器朗读路径不经过 audio/webaudio 后端，置空让 pause/resume 只走 speechSynthesis
    activeBackend = null
    for (let index = startIndex; index < playback.length && currentRun === runId; index += 1) {
      status.value = 'playing'
      currentParagraphIndex.value = playback[index].paragraphIndex
      currentParagraphEnd.value = playback[index].paragraphEnd
      // 清掉上一段在队列里的残留并留白再入队，
      // 规避 Chrome 连续 speak 裁掉每段首字的问题（延时不足会复发）
      speech.cancel()
      await new Promise<void>((resolve) => setTimeout(resolve, SEGMENT_GAP_MS))
      if (currentRun !== runId) return
      await new Promise<void>((resolve, reject) => {
        resolvePlayback = resolve
        const utterance = new SpeechSynthesisUtterance(`${LEADING_FILLER}${playback[index].text}`)
        const voice = resolveVoice()
        if (voice) utterance.voice = voice
        utterance.lang = 'zh-CN'
        utterance.rate = rate.value
        utterance.onend = () => resolve()
        utterance.onerror = () => reject(new Error('浏览器朗读失败'))
        speech.speak(utterance)
      })
      resolvePlayback = null
    }
  }

  const playModelSegments = async (playback: PlaybackSegment[], currentRun: number): Promise<void> => {
    const pending = new Map<number, Promise<Blob>>()
    const requestSegment = (index: number): Promise<Blob> => {
      const existing = pending.get(index)
      if (existing) return existing
      const request = synthesize(
        `${LEADING_FILLER}${playback[index].text}${TRAILING_FILLER}`,
        { voice: modelVoice.value },
        abortController?.signal,
      )
      // 预取可能早于消费失败，提前附加处理器避免未处理拒绝告警。
      void request.catch(() => undefined)
      pending.set(index, request)
      return request
    }

    // 启动即预热窗口内段落，避免"读完一段才开始合成下一段"的等待
    for (let preload = 0; preload <= PREFETCH_AHEAD && preload < playback.length; preload += 1) {
      requestSegment(preload)
    }

    for (let index = 0; index < playback.length && currentRun === runId; index += 1) {
      status.value = 'generating'
      currentParagraphIndex.value = playback[index].paragraphIndex
      currentParagraphEnd.value = playback[index].paragraphEnd
      try {
        const blob = await requestSegment(index)
        if (currentRun !== runId) return
        // 维持预取窗口：当前段已就绪，补一段到窗口尾部
        const lookahead = index + PREFETCH_AHEAD + 1
        if (lookahead < playback.length) {
          requestSegment(lookahead)
        }
        await playAudio(blob, currentRun)
        if (currentRun !== runId) return
        // 段间留白：连续 source 切换会裁掉上段尾音与下段首音
        if (index + 1 < playback.length) {
          await new Promise<void>((resolve) => setTimeout(resolve, SEGMENT_GAP_MS))
        }
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
    currentParagraphEnd.value = -1
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
        releasePlayback()
        abortController = null
        status.value = 'idle'
        isBrowserFallback.value = false
        currentParagraphIndex.value = -1
        currentParagraphEnd.value = -1
      }
    }
  }

  const pause = () => {
    if (status.value !== 'playing') return
    // 按当前播放后端分派：audio 直接 pause（currentTime 自动记忆），webaudio 记 offset 后停 source
    if (activeBackend === 'audio' && audioEl) {
      audioEl.pause()
    } else if (activeBackend === 'webaudio' && bufferSource && audioCtx) {
      startOffset = getElapsed()
      stopBufferSource()
    }
    window.speechSynthesis?.pause()
    status.value = 'paused'
  }

  const resume = () => {
    if (status.value !== 'paused') return
    if (activeBackend === 'audio' && audioEl) {
      void audioEl.play()
    } else if (activeBackend === 'webaudio' && decodedBuffer && audioCtx) {
      if (audioCtx.state === 'suspended') void audioCtx.resume()
      const source = audioCtx.createBufferSource()
      source.buffer = decodedBuffer
      source.playbackRate.value = rate.value
      source.connect(audioCtx.destination)
      source.onended = () => bufferEndedHandler?.()
      bufferSource = source
      startedAt = audioCtx.currentTime
      try {
        source.start(0, startOffset)
      } catch {
        // 恢复失败视为播放结束
        bufferEndedHandler?.()
      }
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
    currentParagraphEnd: readonly(currentParagraphEnd),
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
