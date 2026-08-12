// AIMETA P=通用弹窗可访问性测试|R=dialog名称_关闭命令_焦点生命周期|NR=不测试业务弹窗内容|E=test:component:global-modal|X=internal|A=GlobalModalContainer|D=vitest,vue|S=test|RD=../README.ai
import { createApp, h, nextTick, type App } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'

import GlobalModalContainer from '@/components/shared/GlobalModalContainer.vue'

const mounted: Array<{ app: App; host: HTMLDivElement }> = []

const mountModal = (props: Record<string, unknown> = {}) => {
  const host = document.createElement('div')
  document.body.append(host)
  const onClose = vi.fn()
  const app = createApp({
    render: () => h(GlobalModalContainer, { title: '任务日志', onClose, ...props }),
  })
  app.mount(host)
  mounted.push({ app, host })
  return { host, onClose }
}

afterEach(() => {
  for (const item of mounted.splice(0)) {
    item.app.unmount()
    item.host.remove()
  }
  document.body.style.overflow = ''
  vi.restoreAllMocks()
})

describe('GlobalModalContainer', () => {
  it('提供具名 dialog 和默认可见关闭按钮', async () => {
    const { host, onClose } = mountModal()
    await nextTick()

    const dialog = host.querySelector<HTMLElement>('[role="dialog"]')
    const title = host.querySelector('h2')
    const close = host.querySelector<HTMLButtonElement>('button[aria-label="关闭任务日志"]')
    expect(dialog?.getAttribute('aria-labelledby')).toBe(title?.id)
    expect(close).not.toBeNull()
    expect(document.body.style.overflow).toBe('hidden')

    close?.click()
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('Escape 和遮罩点击沿用 close emit', () => {
    const { host, onClose } = mountModal()
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    host.querySelector<HTMLElement>('.m3-ink-modal-overlay')?.click()
    expect(onClose).toHaveBeenCalledTimes(2)
  })
})
