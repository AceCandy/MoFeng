// AIMETA P=章节朗读组合函数_分段与播放队列|R=TTS音频_浏览器回退_播放状态|NR=不含章节数据查询|E=compose:useChapterReader|X=internal|A=播放状态机|D=vue,api:tts|S=dom,net|RD=./README.ai
import { getCurrentInstance, onBeforeUnmount, readonly, ref, type Ref } from 'vue'

import { getLLMConfigBundle, type LLMConfigBundle } from '@/api/llm'
import { synthesizeSpeech } from '@/api/tts'
import { globalAlert } from '@/composables/useAlert'


export type ReaderStatus = 'idle' | 'generating' | 'playing' | 'paused'

interface ChapterReaderDependencies {
  loadConfig?: () => Promise<LLMConfigBundle>
  synthesize?: (text: string, signal?: AbortSignal) => Promise<Blob>
  notify?: (message: string, type: 'info' | 'error') => void
}

interface ChapterReader {
  status: Readonly<Ref<ReaderStatus>>
  isBrowserFallback: Readonly<Ref<boolean>>
  start: (title: string, content: string) => Promise<void>
  pause: () => void
  resume: () => void
  stop: () => void
}

const splitLongUnit = (unit: string, limit: number): string[] => {
  if (unit.length <= limit) return [unit]
  const chunks: string[] = []
  for (let index = 0; index < unit.length; index += limit) {
    chunks.push(unit.slice(index, index + limit))
  }
  return chunks
}

const splitBody = (content: string, limit: number): string[] => {
  const result: string[] = []
  const paragraphs = content.split(/\n+/).map((part) => part.trim()).filter(Boolean)
  for (const paragraph of paragraphs) {
    const sentences = paragraph.match(/[^。！？!?；;]+[。！？!?；;]?/g) ?? [paragraph]
    let current = ''
    for (const sentence of sentences.map((part) => part.trim()).filter(Boolean)) {
      if (sentence.length > limit) {
        if (current) result.push(current)
        result.push(...splitLongUnit(sentence, limit))
        current = ''
      } else if (!current || current.length + sentence.length <= limit) {
        current += sentence
      } else {
        result.push(current)
        current = sentence
      }
    }
    if (current) result.push(current)
  }
  return result
}

export const splitSpeechText = (title: string, content: string, limit = 2500): string[] => {
  const normalizedLimit = Math.max(1, Math.floor(limit))
  return [
    ...splitLongUnit(title.trim(), normalizedLimit).filter(Boolean),
    ...splitBody(content, normalizedLimit),
  ]
}

export const useChapterReader = (
  dependencies: ChapterReaderDependencies = {},
): ChapterReader => {
  const loadConfig = dependencies.loadConfig ?? getLLMConfigBundle
  const synthesize = dependencies.synthesize ?? synthesizeSpeech
  const notify = dependencies.notify ?? ((message, type) => globalAlert.showToast(message, type))
  const status = ref<ReaderStatus>('idle')
  const isBrowserFallback = ref(false)
  let runId = 0
  let abortController: AbortController | null = null
  let audio: HTMLAudioElement | null = null
  let objectUrl: string | null = null
  let resolveCurrentPlayback: (() => void) | null = null

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

  const stop = () => {
    runId += 1
    abortController?.abort()
    abortController = null
    releaseAudio()
    window.speechSynthesis?.cancel()
    resolveCurrentPlayback?.()
    resolveCurrentPlayback = null
    status.value = 'idle'
    isBrowserFallback.value = false
  }

  const playAudio = async (blob: Blob, currentRun: number): Promise<void> => {
    if (currentRun !== runId) return
    releaseAudio()
    objectUrl = URL.createObjectURL(blob)
    audio = new Audio(objectUrl)
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
    segments: string[],
    startIndex: number,
    currentRun: number,
  ): Promise<void> => {
    const speech = window.speechSynthesis
    if (!speech || typeof SpeechSynthesisUtterance === 'undefined') {
      notify('当前浏览器不支持语音朗读。', 'error')
      return
    }
    isBrowserFallback.value = true
    for (let index = startIndex; index < segments.length && currentRun === runId; index += 1) {
      status.value = 'playing'
      await new Promise<void>((resolve, reject) => {
        resolveCurrentPlayback = resolve
        const utterance = new SpeechSynthesisUtterance(segments[index])
        utterance.onend = () => resolve()
        utterance.onerror = () => reject(new Error('浏览器朗读失败'))
        speech.speak(utterance)
      })
      resolveCurrentPlayback = null
    }
  }

  const playModelSegments = async (segments: string[], currentRun: number): Promise<void> => {
    const pending = new Map<number, Promise<Blob>>()
    const requestSegment = (index: number): Promise<Blob> => {
      const existing = pending.get(index)
      if (existing) return existing
      const request = synthesize(segments[index], abortController?.signal)
      // 预取可能早于消费失败，提前附加处理器避免未处理拒绝告警。
      void request.catch(() => undefined)
      pending.set(index, request)
      return request
    }

    for (let index = 0; index < segments.length && currentRun === runId; index += 1) {
      status.value = 'generating'
      try {
        const blob = await requestSegment(index)
        if (currentRun !== runId) return
        if (index + 1 < segments.length) {
          requestSegment(index + 1)
        }
        await playAudio(blob, currentRun)
      } catch (error) {
        if (currentRun !== runId) return
        abortController?.abort()
        const reason = error instanceof Error && error.message ? error.message : '未知错误'
        notify(`模型朗读失败（${reason}），已切换浏览器朗读。`, 'info')
        await playBrowserSegments(segments, index, currentRun)
        return
      }
    }
  }

  const start = async (title: string, content: string): Promise<void> => {
    stop()
    const currentRun = runId
    const segments = splitSpeechText(title, content)
    if (segments.length === 0) return
    abortController = new AbortController()
    status.value = 'generating'
    let configured = false
    try {
      const config = await loadConfig()
      configured = config.models.some(
        (model) => model.is_enabled && model.is_default_tts && Boolean(model.capabilities.tts),
      )
    } catch {
      configured = false
    }
    if (currentRun !== runId) return
    try {
      if (configured) {
        await playModelSegments(segments, currentRun)
      } else {
        await playBrowserSegments(segments, 0, currentRun)
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
  }

  return {
    status: readonly(status),
    isBrowserFallback: readonly(isBrowserFallback),
    start,
    pause,
    resume,
    stop,
  }
}
