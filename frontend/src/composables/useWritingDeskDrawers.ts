import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useResponsiveViewport } from '@/composables/useResponsiveViewport'
import { useNovelStore } from '@/stores/novel'
import { desktopMin, mobileMax } from '@/constants/responsive'

const SIDEBAR_DRAWER_BREAKPOINT = mobileMax
const ASSISTANT_DRAWER_BREAKPOINT = desktopMin - 1
const ASSISTANT_PANEL_VISIBILITY_STORAGE_KEY = 'mofeng.writingDesk.assistant.visible'

interface UseWritingDeskDrawersOptions {
  /** 切换辅助面板时预加载 WDAssistantPanel（父侧 lazy import loader） */
  loadAssistantPanel: () => void
}

/**
 * 写作台 drawer 管理：侧栏抽屉 / 助手栏抽屉 / 助手面板可见性的开关、互斥与持久化。
 *
 * 从 WritingDesk.vue 抽出（行为逐行等价）。内部注册 onMounted 恢复持久化的
 * 助手面板可见性，故必须在组件 setup 顶层同步调用。
 */
export const useWritingDeskDrawers = ({ loadAssistantPanel }: UseWritingDeskDrawersOptions) => {
  const viewport = useResponsiveViewport()
  const viewportWidth = computed(() => viewport.width.value)
  const novelStore = useNovelStore()

  const isSidebarDrawerOpen = ref(false)
  const isAssistantDrawerOpen = ref(false)
  let lastDrawerTrigger: HTMLElement | null = null

  const persistAssistantPanelVisibility = (visible: boolean) => {
    if (typeof window === 'undefined') return
    try {
      window.localStorage.setItem(ASSISTANT_PANEL_VISIBILITY_STORAGE_KEY, visible ? '1' : '0')
    } catch (error) {
      console.warn('保存辅助信息面板状态失败:', error)
    }
  }

  const isAssistantPanelVisible = computed({
    get: () => novelStore.isAssistantPanelVisible,
    set: (val) => {
      novelStore.isAssistantPanelVisible = val
      persistAssistantPanelVisibility(val)
    },
  })

  const restoreAssistantPanelVisibility = () => {
    if (typeof window === 'undefined') return
    try {
      const stored = window.localStorage.getItem(ASSISTANT_PANEL_VISIBILITY_STORAGE_KEY)
      if (stored === '0') {
        isAssistantPanelVisible.value = false
      } else if (stored === '1') {
        isAssistantPanelVisible.value = true
      }
    } catch (error) {
      console.warn('读取辅助信息面板状态失败:', error)
    }
  }

  const useSidebarDrawer = computed(() => viewportWidth.value <= SIDEBAR_DRAWER_BREAKPOINT)
  const useAssistantDrawer = computed(() => viewportWidth.value <= ASSISTANT_DRAWER_BREAKPOINT)
  const assistantToggleActive = computed(() =>
    useAssistantDrawer.value ? isAssistantDrawerOpen.value : isAssistantPanelVisible.value,
  )

  const isDrawerBackdropVisible = computed(
    () =>
      (useSidebarDrawer.value && isSidebarDrawerOpen.value) ||
      (useAssistantDrawer.value && isAssistantDrawerOpen.value),
  )

  const closeAllDrawers = () => {
    const shouldRestoreFocus = isDrawerBackdropVisible.value
    isSidebarDrawerOpen.value = false
    isAssistantDrawerOpen.value = false
    if (shouldRestoreFocus && lastDrawerTrigger) {
      const trigger = lastDrawerTrigger
      lastDrawerTrigger = null
      void nextTick(() => trigger.focus())
    }
  }

  const handleDrawerKeydown = (event: KeyboardEvent) => {
    if (event.key !== 'Escape' || !isDrawerBackdropVisible.value) return
    event.preventDefault()
    closeAllDrawers()
  }

  const toggleSidebarDrawer = () => {
    if (!useSidebarDrawer.value) return
    if (!isSidebarDrawerOpen.value && document.activeElement instanceof HTMLElement) {
      lastDrawerTrigger = document.activeElement
    }
    isSidebarDrawerOpen.value = !isSidebarDrawerOpen.value
    if (isSidebarDrawerOpen.value) {
      isAssistantDrawerOpen.value = false
    }
  }

  const toggleAssistantDrawer = () => {
    if (!useAssistantDrawer.value) return
    void loadAssistantPanel()
    if (!isAssistantDrawerOpen.value && document.activeElement instanceof HTMLElement) {
      lastDrawerTrigger = document.activeElement
    }
    isAssistantDrawerOpen.value = !isAssistantDrawerOpen.value
    if (isAssistantDrawerOpen.value && useSidebarDrawer.value) {
      isSidebarDrawerOpen.value = false
    }
  }

  const toggleAssistantVisibility = () => {
    if (useAssistantDrawer.value) {
      toggleAssistantDrawer()
      return
    }
    void loadAssistantPanel()
    isAssistantPanelVisible.value = !isAssistantPanelVisible.value
    persistAssistantPanelVisibility(isAssistantPanelVisible.value)
  }

  // 离开移动抽屉断点时收起抽屉，避免桌面态残留打开的抽屉
  watch(
    () => useSidebarDrawer.value,
    (enabled) => {
      if (!enabled) {
        isSidebarDrawerOpen.value = false
      }
    },
    { immediate: true },
  )

  watch(
    () => useAssistantDrawer.value,
    (enabled) => {
      if (!enabled) {
        isAssistantDrawerOpen.value = false
      }
    },
    { immediate: true },
  )

  onMounted(() => {
    restoreAssistantPanelVisibility()
    window.addEventListener('keydown', handleDrawerKeydown)
  })

  onBeforeUnmount(() => {
    window.removeEventListener('keydown', handleDrawerKeydown)
  })

  return {
    isSidebarDrawerOpen,
    isAssistantDrawerOpen,
    isAssistantPanelVisible,
    useSidebarDrawer,
    useAssistantDrawer,
    assistantToggleActive,
    isDrawerBackdropVisible,
    closeAllDrawers,
    toggleSidebarDrawer,
    toggleAssistantVisibility,
  }
}
