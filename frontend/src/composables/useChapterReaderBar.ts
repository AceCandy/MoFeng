import { computed, onMounted, onUnmounted, ref, watch, type ComputedRef } from 'vue'
import type { ChapterOutline } from '@/api/novel'
import { useChapterReader } from '@/composables/useChapterReader'

// useChapterReaderBar 只消费的 props 子集（结构同构于 WDWorkspaceProps）
interface ReaderBarProps {
  selectedChapterNumber: number | null
}

interface UseChapterReaderBarOptions {
  props: ReaderBarProps
  selectedChapterOutline: ComputedRef<ChapterOutline | null>
  selectedChapterResolvedContent: ComputedRef<string>
}

/**
 * 章节朗读控件（ChapterReaderBar）的状态装配与浏览器音色胶水。
 *
 * 从 WDWorkspace.vue 抽出（行为逐行等价）。持有 useChapterReader 实例，装配朗读控件
 * 所需的播放状态/段落进度/模型音色/浏览器音色候选，并接管朗读相关生命周期（挂载刷新
 * 浏览器音色、卸载与切章时停止朗读）。
 */
export const useChapterReaderBar = (options: UseChapterReaderBarOptions) => {
  const { props, selectedChapterOutline, selectedChapterResolvedContent } = options

  const chapterReader = useChapterReader()
  const readerStatus = chapterReader.status

  // 朗读控件：入口仅在 idle 显示，点击后原地展开为播放条；重置即停止回到入口
  const readerCurrentParagraphIndex = chapterReader.currentParagraphIndex
  const readerCurrentParagraphEnd = chapterReader.currentParagraphEnd
  const readerParagraphCount = chapterReader.paragraphCount
  const readerIsBrowserFallback = chapterReader.isBrowserFallback
  const readerHasModelTTS = chapterReader.hasModelTTS
  const readerModelVoice = chapterReader.modelVoice
  const readerModelVoiceOptions = chapterReader.modelVoiceOptions
  const readerVoiceURI = chapterReader.voiceURI
  const readerRate = chapterReader.rate
  const readerForceBrowser = chapterReader.forceBrowser

  // 浏览器朗读音色：仅在浏览器 fallback 时可选，选项来自本机 getVoices，存 localStorage
  const browserVoiceOptions = ref<SpeechSynthesisVoice[]>([])
  const refreshBrowserVoices = () => {
    browserVoiceOptions.value = (window.speechSynthesis?.getVoices?.() ?? []).filter(
      (voice) => /^zh/i.test(voice.lang) && /natural|neural/i.test(voice.name),
    )
  }
  // 微软在线神经语音英文名 → 中文友好名（带性别/地区），未命中的回退原英文名
  const VOICE_CN_LABEL: Record<string, string> = {
    Xiaoxiao: '晓晓（女）',
    Xiaoyi: '晓伊（女）',
    Yunjian: '云健（男）',
    Yunxi: '云希（男）',
    Yunxia: '云夏（女）',
    Yunyang: '云扬（男）',
    Xiaobei: '晓北（女·东北话）',
    Xiaoni: '晓妮（女·陕西话）',
    HsiaoChen: '晓臻（女·台湾）',
    HsiaoYu: '晓雨（女·台湾）',
    YunJhe: '云哲（男·台湾）',
    HiuGaai: '曉佳（女·粤语）',
    HiuMaan: '曉敏（女·粤语）',
    WanLung: '雲龍（男·粤语）',
  }
  const readerVoiceLabel = (voice: SpeechSynthesisVoice) => {
    const match = voice.name.match(/Microsoft\s+([A-Za-z]+)/i)
    return (match && VOICE_CN_LABEL[match[1]]) || voice.name
  }

  // 悬浮控件音色选项（URI + 清洗后的标签）
  const readerVoiceOptions = computed(() =>
    browserVoiceOptions.value.map((voice) => ({ uri: voice.voiceURI, label: readerVoiceLabel(voice) })),
  )

  // 朗读倍速：浏览器与模型 TTS 通用
  const READER_RATE_OPTIONS = [0.75, 1, 1.25, 1.5, 2]

  const handleReaderStart = () => {
    const chapterTitle = `第${props.selectedChapterNumber}章 ${selectedChapterOutline.value?.title || '未知标题'}`
    void chapterReader.start(chapterTitle, selectedChapterResolvedContent.value)
  }

  const handleReaderPlayPause = () => {
    if (readerStatus.value === 'playing') {
      chapterReader.pause()
      return
    }
    if (readerStatus.value === 'paused') {
      chapterReader.resume()
      return
    }
    if (readerStatus.value === 'generating') {
      chapterReader.stop()
    }
  }

  // 重置：停止朗读，收缩回「准备播放」入口
  const handleReaderReset = () => {
    chapterReader.stop()
  }

  // 切换章节时停止上一章朗读
  watch(
    () => props.selectedChapterNumber,
    () => {
      chapterReader.stop()
    },
  )

  onMounted(() => {
    refreshBrowserVoices()
    window.speechSynthesis?.addEventListener('voiceschanged', refreshBrowserVoices)
  })

  onUnmounted(() => {
    window.speechSynthesis?.removeEventListener('voiceschanged', refreshBrowserVoices)
    chapterReader.stop()
  })

  return {
    chapterReader,
    readerStatus,
    readerCurrentParagraphIndex,
    readerCurrentParagraphEnd,
    readerParagraphCount,
    readerIsBrowserFallback,
    readerHasModelTTS,
    readerModelVoice,
    readerModelVoiceOptions,
    readerVoiceURI,
    readerRate,
    readerForceBrowser,
    readerVoiceOptions,
    READER_RATE_OPTIONS,
    handleReaderStart,
    handleReaderPlayPause,
    handleReaderReset,
  }
}
