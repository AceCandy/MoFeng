import { afterEach, describe, expect, it, vi } from 'vitest'
import { createApp, defineComponent, h, computed, nextTick, ref } from 'vue'

import { useAiMenu } from '@/composables/useAiMenu'

/**
 * useAiMenu 在 setup 内注册 onMounted/onUnmounted（document 外部点击监听），
 * 故用一个最小 host 组件挂载（createApp + app.mount），不依赖 @vue/test-utils。
 * host 用 render 函数渲染 trigger/panel/menu-item，供 ref 绑定与键盘 focus 测试。
 */
function mountUseAiMenu(
  options: {
    disabled?: boolean
    contentView?: boolean
    bodyExpose?: Record<string, ReturnType<typeof vi.fn>>
  } = {},
) {
  const bag = { menu: null as ReturnType<typeof useAiMenu> | null }
  const host = defineComponent({
    setup() {
      const bodyComponentRef = ref(options.bodyExpose ?? null)
      const menu = useAiMenu({
        isAiMenuDisabled: computed(() => options.disabled ?? false),
        isChapterContentView: computed(() => options.contentView ?? true),
        bodyComponentRef,
      })
      bag.menu = menu
      return () =>
        h('div', { ref: menu.aiMenuRef }, [
          h('button', { ref: menu.aiMenuTriggerRef, id: 'ai-trigger' }, 'trigger'),
          menu.showAiMenu.value
            ? h(
                'div',
                { ref: menu.aiMenuPanelRef, onKeydown: menu.handleAiMenuKeydown },
                [0, 1, 2, 3].map((i) =>
                  h(
                    'button',
                    { ref: (el: unknown) => menu.registerAiMenuItemRef(el, i) },
                    `item${i}`,
                  ),
                ),
              )
            : null,
        ])
    },
  })
  const app = createApp(host)
  const div = document.createElement('div')
  document.body.appendChild(div)
  app.mount(div)
  cleanupFns.push(() => {
    app.unmount()
    div.remove()
  })
  return bag.menu!
}

const cleanupFns: Array<() => void> = []
afterEach(() => {
  while (cleanupFns.length) cleanupFns.pop()!()
})

describe('useAiMenu', () => {
  it('toggleAiMenu 开关菜单', async () => {
    const menu = mountUseAiMenu()
    expect(menu.showAiMenu.value).toBe(false)
    menu.toggleAiMenu()
    await nextTick()
    expect(menu.showAiMenu.value).toBe(true)
    menu.toggleAiMenu()
    expect(menu.showAiMenu.value).toBe(false)
  })

  it('toggleAiMenu 受 isAiMenuDisabled 守卫', () => {
    const menu = mountUseAiMenu({ disabled: true })
    menu.toggleAiMenu()
    expect(menu.showAiMenu.value).toBe(false)
  })

  it('closeAiMenu 收起菜单', async () => {
    const menu = mountUseAiMenu()
    menu.toggleAiMenu()
    await nextTick()
    menu.closeAiMenu()
    expect(menu.showAiMenu.value).toBe(false)
  })

  it('closeAiMenu(restoreFocus=true) 把焦点还给 trigger', async () => {
    const menu = mountUseAiMenu()
    menu.toggleAiMenu()
    await nextTick()
    menu.closeAiMenu(true)
    expect(menu.showAiMenu.value).toBe(false)
    expect(document.activeElement).toBe(menu.aiMenuTriggerRef.value)
  })

  it('handleLayeredOptimize 在正文视图下调 openOptimizerPanel 并收起菜单', () => {
    const openOptimizerPanel = vi.fn()
    const menu = mountUseAiMenu({ contentView: true, bodyExpose: { openOptimizerPanel } })
    menu.toggleAiMenu()
    menu.handleLayeredOptimize()
    expect(openOptimizerPanel).toHaveBeenCalledOnce()
    expect(menu.showAiMenu.value).toBe(false)
  })

  it('handleLayeredOptimize 在非正文视图下不触发优化器（但仍收起菜单）', () => {
    const openOptimizerPanel = vi.fn()
    const menu = mountUseAiMenu({ contentView: false, bodyExpose: { openOptimizerPanel } })
    menu.toggleAiMenu()
    menu.handleLayeredOptimize()
    expect(openOptimizerPanel).not.toHaveBeenCalled()
    expect(menu.showAiMenu.value).toBe(false)
  })

  it('handlePolishContent 以润色预设触发 openOptimizerPanelWithPreset', () => {
    const openOptimizerPanelWithPreset = vi.fn()
    const menu = mountUseAiMenu({ bodyExpose: { openOptimizerPanelWithPreset } })
    menu.handlePolishContent()
    expect(openOptimizerPanelWithPreset).toHaveBeenCalledWith({
      dimension: 'dialogue',
      notes: '请优先润色正文表达，让叙述更顺滑、更有画面感。',
    })
  })

  it('handleAdjustRhythm 以节奏预设触发 openOptimizerPanelWithPreset', () => {
    const openOptimizerPanelWithPreset = vi.fn()
    const menu = mountUseAiMenu({ bodyExpose: { openOptimizerPanelWithPreset } })
    menu.handleAdjustRhythm()
    expect(openOptimizerPanelWithPreset).toHaveBeenCalledWith({
      dimension: 'rhythm',
      notes: '请重点调整章节节奏，控制信息密度与推进速度。',
    })
  })

  it('handleRewriteStyle 以改写文风预设触发 openOptimizerPanelWithPreset', () => {
    const openOptimizerPanelWithPreset = vi.fn()
    const menu = mountUseAiMenu({ bodyExpose: { openOptimizerPanelWithPreset } })
    menu.handleRewriteStyle()
    expect(openOptimizerPanelWithPreset).toHaveBeenCalledWith({
      dimension: 'dialogue',
      notes: '请在不改变剧情事实的前提下改写文风，统一语气并提升辨识度。',
    })
  })

  it('exportContentAsTxt 调用正文组件的 exportCurrentChapterAsTxt', () => {
    const exportCurrentChapterAsTxt = vi.fn()
    const menu = mountUseAiMenu({ bodyExpose: { exportCurrentChapterAsTxt } })
    menu.exportContentAsTxt()
    expect(exportCurrentChapterAsTxt).toHaveBeenCalledOnce()
  })

  it('Escape 关闭菜单并把焦点还给 trigger', async () => {
    const menu = mountUseAiMenu()
    menu.toggleAiMenu()
    await nextTick()
    menu.handleAiMenuKeydown(new KeyboardEvent('keydown', { key: 'Escape' }))
    expect(menu.showAiMenu.value).toBe(false)
    expect(document.activeElement).toBe(menu.aiMenuTriggerRef.value)
  })

  it('Tab 关闭菜单（不回归焦点）', async () => {
    const menu = mountUseAiMenu()
    menu.toggleAiMenu()
    await nextTick()
    menu.handleAiMenuKeydown(new KeyboardEvent('keydown', { key: 'Tab' }))
    expect(menu.showAiMenu.value).toBe(false)
  })

  it('菜单打开时点击外部（document）自动收起', async () => {
    const menu = mountUseAiMenu()
    menu.toggleAiMenu()
    await nextTick()
    expect(menu.showAiMenu.value).toBe(true)
    document.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    expect(menu.showAiMenu.value).toBe(false)
  })
})
