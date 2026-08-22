// AIMETA P=墨风编辑器契约测试|R=段落换行_描红落墨_撤销重做_只读|NR=不测试视觉布局|E=test:component:mofeng-editor|X=internal|A=vitest,vue|D=vue,tiptap|S=test|RD=../README.ai
import { createApp, h, nextTick, type App } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'

import MofengEditor from '@/components/writing-desk/editor/MofengEditor.vue'

const mounted: Array<{ app: App; host: HTMLDivElement }> = []

const mountEditor = (props: Record<string, unknown>) => {
  const host = document.createElement('div')
  document.body.append(host)
  const app = createApp({ render: () => h(MofengEditor, props) })
  app.mount(host)
  mounted.push({ app, host })
  return host
}

afterEach(() => {
  for (const item of mounted.splice(0)) {
    item.app.unmount()
    item.host.remove()
  }
})

describe('MofengEditor contracts', () => {
  it('keeps paragraphs, hard breaks, miaohong and undo after replacing StarterKit', async () => {
    const host = mountEditor({ modelValue: '甲\n乙\n\n丙', provenance: 'ai' })
    await vi.waitFor(() => expect(host.querySelector('.ProseMirror')).not.toBeNull())

    const surface = host.querySelector<HTMLElement>('.ProseMirror')
    expect(surface?.querySelectorAll('p')).toHaveLength(2)
    expect(surface?.querySelectorAll('br')).toHaveLength(1)
    expect(surface?.querySelectorAll('[data-miaohong]')).toHaveLength(3)

    host.querySelector<HTMLButtonElement>('[aria-label="全文落墨"]')?.click()
    await nextTick()
    expect(surface?.querySelectorAll('[data-miaohong]')).toHaveLength(0)

    surface?.dispatchEvent(new KeyboardEvent('keydown', { key: 'z', ctrlKey: true, bubbles: true }))
    await nextTick()
    expect(surface?.querySelectorAll('[data-miaohong]')).toHaveLength(3)

    surface?.dispatchEvent(new KeyboardEvent('keydown', { key: 'y', ctrlKey: true, bubbles: true }))
    await nextTick()
    expect(surface?.querySelectorAll('[data-miaohong]')).toHaveLength(0)
  })

  it('keeps readonly semantics', async () => {
    const host = mountEditor({ modelValue: '只读正文', readonly: true })
    await vi.waitFor(() => expect(host.querySelector('.ProseMirror')).not.toBeNull())

    const surface = host.querySelector<HTMLElement>('.ProseMirror')
    expect(surface?.getAttribute('contenteditable')).toBe('false')
    expect(surface?.getAttribute('aria-readonly')).toBe('true')
  })
})
