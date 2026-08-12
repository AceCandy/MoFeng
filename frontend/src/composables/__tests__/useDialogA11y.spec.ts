// AIMETA P=对话框焦点契约测试|R=初始焦点_Tab环_焦点恢复_多实例滚动锁|NR=不测试具体弹窗视觉|E=test:composable:dialog-a11y|X=internal|A=useDialogA11y|D=vitest,vue|S=test|RD=../README.ai
import { createApp, defineComponent, nextTick, ref, type App } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { useDialogA11y } from '@/composables/useDialogA11y'

const mounted: Array<{ app: App; host: HTMLDivElement }> = []

const mountDialog = (onClose = vi.fn()) => {
  const trigger = document.createElement('button')
  const dialog = document.createElement('div')
  const first = document.createElement('button')
  const last = document.createElement('button')
  dialog.tabIndex = -1
  dialog.append(first, last)
  document.body.append(trigger, dialog)
  trigger.focus()
  for (const element of [first, last]) {
    vi.spyOn(element, 'getClientRects').mockReturnValue([{} as DOMRect])
  }

  const active = ref(true)
  const dialogRef = ref<HTMLElement | null>(dialog)
  const host = document.createElement('div')
  document.body.append(host)
  const app = createApp(defineComponent({
    setup() {
      useDialogA11y({ active, dialogRef, onClose })
      return () => null
    },
  }))
  app.mount(host)
  mounted.push({ app, host })
  return { active, app, dialog, first, host, last, onClose, trigger }
}

afterEach(() => {
  for (const item of mounted.splice(0)) {
    item.app.unmount()
    item.host.remove()
  }
  document.body.replaceChildren()
  document.body.style.overflow = ''
  vi.restoreAllMocks()
})

describe('useDialogA11y', () => {
  it('管理初始焦点、Tab 环、Escape 和焦点恢复', async () => {
    const harness = mountDialog()
    await nextTick()
    expect(document.activeElement).toBe(harness.first)
    expect(document.body.style.overflow).toBe('hidden')

    harness.last.focus()
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true }))
    expect(document.activeElement).toBe(harness.first)
    harness.first.focus()
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', shiftKey: true, bubbles: true, cancelable: true }))
    expect(document.activeElement).toBe(harness.last)

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    expect(harness.onClose).toHaveBeenCalledOnce()
    harness.active.value = false
    await nextTick()
    expect(document.activeElement).toBe(harness.trigger)
    expect(document.body.style.overflow).toBe('')
  })

  it('多实例关闭一个时继续保持 body lock', async () => {
    const first = mountDialog()
    const second = mountDialog()
    await nextTick()
    first.active.value = false
    await nextTick()
    first.app.unmount()
    first.host.remove()
    mounted.splice(mounted.findIndex((item) => item.app === first.app), 1)
    expect(document.body.style.overflow).toBe('hidden')
    second.active.value = false
    await nextTick()
    expect(document.body.style.overflow).toBe('')
  })
})
