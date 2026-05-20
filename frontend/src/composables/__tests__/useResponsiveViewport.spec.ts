import { createApp, defineComponent, nextTick } from 'vue'
import { afterEach, describe, expect, it } from 'vitest'

import { useResponsiveViewport } from '../useResponsiveViewport'

const originalInnerWidth = window.innerWidth

const setInnerWidth = (width: number) => {
  Object.defineProperty(window, 'innerWidth', {
    configurable: true,
    writable: true,
    value: width,
  })
}

const mountViewportHarness = () => {
  let viewportState: ReturnType<typeof useResponsiveViewport> | null = null
  const container = document.createElement('div')

  const app = createApp(
    defineComponent({
      setup() {
        viewportState = useResponsiveViewport()
        return () => null
      },
    }),
  )

  app.mount(container)

  if (!viewportState) {
    throw new Error('useResponsiveViewport 没有返回状态')
  }

  return {
    app,
    container,
    viewportState,
  }
}

afterEach(() => {
  setInnerWidth(originalInnerWidth)
})

describe('useResponsiveViewport', () => {
  it('会基于当前窗口宽度初始化断点状态', async () => {
    setInnerWidth(900)

    const { app, container, viewportState } = mountViewportHarness()

    try {
      await nextTick()

      expect(viewportState.width.value).toBe(900)
      expect(viewportState.tier.value).toBe('tablet')
      expect(viewportState.isMobile.value).toBe(false)
      expect(viewportState.isTablet.value).toBe(true)
      expect(viewportState.isDesktop.value).toBe(false)
    } finally {
      app.unmount()
      container.remove()
    }
  })

  it('会在 resize 后切换到新的断点', async () => {
    setInnerWidth(900)

    const { app, container, viewportState } = mountViewportHarness()

    try {
      await nextTick()

      setInnerWidth(390)
      window.dispatchEvent(new Event('resize'))
      await nextTick()

      expect(viewportState.width.value).toBe(390)
      expect(viewportState.tier.value).toBe('mobile')
      expect(viewportState.isMobile.value).toBe(true)
      expect(viewportState.isTablet.value).toBe(false)
      expect(viewportState.isDesktop.value).toBe(false)
    } finally {
      app.unmount()
      container.remove()
    }
  })
})
