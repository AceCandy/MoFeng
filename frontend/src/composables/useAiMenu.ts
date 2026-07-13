import { nextTick, onMounted, onUnmounted, ref, type ComputedRef, type Ref } from 'vue'

/** 章节正文组件对外暴露的优化器/导出方法（与 WDWorkspace 内 ChapterContentExpose 同构） */
type BodyComponentExpose = {
  openOptimizerPanel?: () => void
  openOptimizerPanelWithPreset?: (preset?: { dimension?: string; notes?: string }) => void
  exportCurrentChapterAsTxt?: () => void
}

interface UseAiMenuOptions {
  /** AI 菜单是否禁用（生成中且非正文视图时禁用） */
  isAiMenuDisabled: ComputedRef<boolean>
  /** 当前是否处于章节正文视图（决定优化菜单项是否生效） */
  isChapterContentView: ComputedRef<boolean>
  /** 章节正文组件实例引用（触发优化器面板/导出） */
  bodyComponentRef: Ref<BodyComponentExpose | null>
}

/**
 * AI 菜单的状态、键盘/聚焦交互与外部点击收起。
 *
 * 从 WDWorkspace.vue 抽出（行为逐行等价）。内部注册 onMounted/onUnmounted
 * 监听 document click 以实现外部点击收起，故必须在组件 setup 顶层同步调用。
 */
export const useAiMenu = ({
  isAiMenuDisabled,
  isChapterContentView,
  bodyComponentRef,
}: UseAiMenuOptions) => {
  const aiMenuRef = ref<HTMLElement | null>(null)
  const aiMenuPanelRef = ref<HTMLElement | null>(null)
  const aiMenuTriggerRef = ref<HTMLButtonElement | null>(null)
  const aiMenuItemRefs = ref<Array<HTMLElement | null>>([])
  const aiMenuId = 'wd-workspace-ai-menu'
  const showAiMenu = ref(false)

  const resolveMenuElement = (element: unknown) => {
    if (element instanceof HTMLElement) {
      return element
    }
    if (element && typeof element === 'object' && '$el' in element) {
      const componentElement = (element as { $el?: unknown }).$el
      if (componentElement instanceof HTMLElement) {
        return componentElement
      }
    }
    return null
  }

  const registerAiMenuItemRef = (element: unknown, index: number) => {
    aiMenuItemRefs.value[index] = resolveMenuElement(element)
  }

  const getEnabledMenuItems = (items: Array<HTMLElement | null>) => {
    return items.filter((item) => item && !item.hasAttribute('disabled')) as HTMLElement[]
  }

  const focusMenuItemAtIndex = (items: Array<HTMLElement | null>, targetIndex: number) => {
    const enabledItems = getEnabledMenuItems(items)
    if (enabledItems.length === 0) return
    const safeIndex = ((targetIndex % enabledItems.length) + enabledItems.length) % enabledItems.length
    enabledItems[safeIndex]?.focus()
  }

  const focusFirstMenuItem = (items: Array<HTMLElement | null>) => {
    focusMenuItemAtIndex(items, 0)
  }

  const handleAiMenuKeydown = (event: KeyboardEvent) => {
    handleMenuKeydown(event, aiMenuItemRefs.value, closeAiMenu)
  }

  const handleMenuKeydown = (
    event: KeyboardEvent,
    items: Array<HTMLElement | null>,
    closeMenu: (restoreFocus?: boolean) => void,
  ) => {
    const enabledItems = getEnabledMenuItems(items)
    if (enabledItems.length === 0) return

    const activeElement = document.activeElement as HTMLElement | null
    const currentIndex = enabledItems.findIndex((item) => item === activeElement)

    if (event.key === 'Escape') {
      event.preventDefault()
      closeMenu(true)
      return
    }

    if (event.key === 'Tab') {
      closeMenu()
      return
    }

    if (event.key === 'ArrowDown') {
      event.preventDefault()
      focusMenuItemAtIndex(enabledItems, currentIndex + 1)
      return
    }

    if (event.key === 'ArrowUp') {
      event.preventDefault()
      focusMenuItemAtIndex(enabledItems, currentIndex - 1)
      return
    }

    if (event.key === 'Home') {
      event.preventDefault()
      focusMenuItemAtIndex(enabledItems, 0)
      return
    }

    if (event.key === 'End') {
      event.preventDefault()
      focusMenuItemAtIndex(enabledItems, enabledItems.length - 1)
    }
  }

  const closeAiMenu = (restoreFocus: boolean = false) => {
    showAiMenu.value = false
    if (restoreFocus) {
      aiMenuTriggerRef.value?.focus()
    }
  }

  const toggleAiMenu = () => {
    if (isAiMenuDisabled.value) return
    showAiMenu.value = !showAiMenu.value
    if (showAiMenu.value) {
      nextTick(() => {
        focusFirstMenuItem(aiMenuItemRefs.value)
      })
    }
  }

  const openContentOptimizer = () => {
    bodyComponentRef.value?.openOptimizerPanel?.()
  }

  const openContentOptimizerWithPreset = (preset?: { dimension?: string; notes?: string }) => {
    bodyComponentRef.value?.openOptimizerPanelWithPreset?.(preset)
  }

  const exportContentAsTxt = () => {
    bodyComponentRef.value?.exportCurrentChapterAsTxt?.()
  }

  const handleLayeredOptimize = () => {
    closeAiMenu()
    if (!isChapterContentView.value) return
    openContentOptimizer()
  }

  const handlePolishContent = () => {
    closeAiMenu()
    if (!isChapterContentView.value) return
    openContentOptimizerWithPreset({
      dimension: 'dialogue',
      notes: '请优先润色正文表达，让叙述更顺滑、更有画面感。',
    })
  }

  const handleAdjustRhythm = () => {
    closeAiMenu()
    if (!isChapterContentView.value) return
    openContentOptimizerWithPreset({
      dimension: 'rhythm',
      notes: '请重点调整章节节奏，控制信息密度与推进速度。',
    })
  }

  const handleRewriteStyle = () => {
    closeAiMenu()
    if (!isChapterContentView.value) return
    openContentOptimizerWithPreset({
      dimension: 'dialogue',
      notes: '请在不改变剧情事实的前提下改写文风，统一语气并提升辨识度。',
    })
  }

  const handleAiMenuOutsideClick = (event: MouseEvent) => {
    const targetNode = event.target as Node | null
    if (!targetNode) return
    if (showAiMenu.value && !aiMenuRef.value?.contains(targetNode)) {
      showAiMenu.value = false
    }
  }

  onMounted(() => {
    document.addEventListener('click', handleAiMenuOutsideClick)
  })

  onUnmounted(() => {
    document.removeEventListener('click', handleAiMenuOutsideClick)
  })

  return {
    aiMenuRef,
    aiMenuPanelRef,
    aiMenuTriggerRef,
    aiMenuItemRefs,
    aiMenuId,
    showAiMenu,
    registerAiMenuItemRef,
    handleAiMenuKeydown,
    toggleAiMenu,
    closeAiMenu,
    handleLayeredOptimize,
    handlePolishContent,
    handleAdjustRhythm,
    handleRewriteStyle,
    exportContentAsTxt,
  }
}
