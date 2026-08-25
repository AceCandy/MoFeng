// AIMETA P=写作台紧凑控件测试|R=更多菜单_朗读悬浮球展开收起|NR=不测试语音合成实现|E=test:writing-desk-controls|X=internal|A=ChapterToolbar_ChapterReaderBar|D=vitest,vue|S=test|RD=../README.ai
import { createApp, nextTick } from 'vue'
import { describe, expect, it } from 'vitest'

import ChapterReaderBar from '@/components/writing-desk/ChapterReaderBar.vue'
import ChapterToolbar from '@/components/writing-desk/workspace/ChapterToolbar.vue'

const mount = (component: Parameters<typeof createApp>[0], props: Record<string, unknown>) => {
  const host = document.createElement('div')
  document.body.appendChild(host)
  const app = createApp(component, props)
  app.mount(host)
  return { app, host }
}

describe('writing desk compact controls', () => {
  it('keeps secondary chapter actions in a native more menu', () => {
    const rendered = mount(ChapterToolbar, {
      chapterNumber: 1,
      isFinalizedSuccessful: true,
      hasSelectedChapterContent: true,
      isChapterContentView: true,
      isAiMenuDisabled: false,
      bodyComponentRef: null,
      assistantOpen: false,
    })

    expect(rendered.host.querySelector('details')).not.toBeNull()
    expect(rendered.host.querySelector('summary')?.textContent?.trim()).toBe('更多')
    expect(rendered.host.querySelector('.writing-workspace__tool-btn--edit')?.textContent?.trim()).toBe(
      '编辑',
    )
    rendered.app.unmount()
    rendered.host.remove()
  })

  it('expands the reader ball on hover and collapses it with Escape', async () => {
    const rendered = mount(ChapterReaderBar, {
      status: 'idle',
      isBrowserFallback: false,
      hasModelTTS: false,
      modelVoice: '',
      modelVoiceOptions: [],
      currentParagraphIndex: -1,
      paragraphCount: 0,
      voiceURI: '',
      rate: 1,
      forceBrowser: false,
      voiceOptions: [],
      rateOptions: [0.8, 1, 1.2],
    })
    const root = rendered.host.querySelector<HTMLElement>('.reader-float')
    const trigger = rendered.host.querySelector<HTMLButtonElement>('.reader-float__btn--main')

    expect(root).not.toBeNull()
    expect(trigger?.getAttribute('aria-expanded')).toBe('false')
    expect(rendered.host.querySelector('.reader-float__panel')).toBeNull()

    root?.dispatchEvent(new MouseEvent('mouseenter'))
    await nextTick()
    expect(trigger?.getAttribute('aria-expanded')).toBe('true')
    expect(rendered.host.querySelector('.reader-float__panel')).not.toBeNull()

    root?.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    await nextTick()
    expect(trigger?.getAttribute('aria-expanded')).toBe('false')
    expect(rendered.host.querySelector('.reader-float__panel')).toBeNull()
    rendered.app.unmount()
    rendered.host.remove()
  })
})
