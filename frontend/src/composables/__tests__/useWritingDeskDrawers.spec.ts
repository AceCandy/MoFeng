import { createApp, defineComponent, nextTick } from 'vue'
import { createPinia } from 'pinia'
import { afterEach, describe, expect, it } from 'vitest'

import { useWritingDeskDrawers } from '../useWritingDeskDrawers'

const originalInnerWidth = window.innerWidth

const setInnerWidth = (width: number) => {
  Object.defineProperty(window, 'innerWidth', {
    configurable: true,
    writable: true,
    value: width,
  })
}

afterEach(() => {
  setInnerWidth(originalInnerWidth)
})

describe('useWritingDeskDrawers', () => {
  it('移动抽屉打开时按 Escape 会统一关闭', async () => {
    setInnerWidth(390)
    let drawers: ReturnType<typeof useWritingDeskDrawers> | null = null
    const app = createApp(
      defineComponent({
        setup() {
          drawers = useWritingDeskDrawers({ loadAssistantPanel: () => undefined })
          return () => null
        },
      }),
    )
    const container = document.createElement('div')
    const trigger = document.createElement('button')
    document.body.appendChild(trigger)
    app.use(createPinia())
    app.mount(container)

    try {
      await nextTick()
      if (!drawers) throw new Error('抽屉状态未初始化')
      trigger.focus()
      drawers.toggleSidebarDrawer()
      expect(drawers.isSidebarDrawerOpen.value).toBe(true)

      const event = new KeyboardEvent('keydown', { key: 'Escape', cancelable: true })
      window.dispatchEvent(event)
      await nextTick()

      expect(event.defaultPrevented).toBe(true)
      expect(drawers.isSidebarDrawerOpen.value).toBe(false)
      expect(document.activeElement).toBe(trigger)
    } finally {
      app.unmount()
      container.remove()
      trigger.remove()
    }
  })
})
