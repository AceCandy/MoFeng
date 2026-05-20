import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import { resolveResponsiveTier, type ResponsiveTier } from '@/constants/responsive'

const getViewportWidth = () => (typeof window === 'undefined' ? 0 : window.innerWidth)

export function useResponsiveViewport() {
  const width = ref(getViewportWidth())

  const syncWidth = () => {
    width.value = getViewportWidth()
  }

  const tier = computed<ResponsiveTier>(() => resolveResponsiveTier(width.value))
  const isMobile = computed(() => tier.value === 'mobile')
  const isTablet = computed(() => tier.value === 'tablet')
  const isDesktop = computed(() => tier.value === 'desktop')

  onMounted(() => {
    // 首次挂载时先同步一次真实视口，避免首屏停留在默认值。
    syncWidth()
    // 之后只监听窗口 resize，保持断点状态跟着视口变化。
    window.addEventListener('resize', syncWidth)
  })

  onBeforeUnmount(() => {
    window.removeEventListener('resize', syncWidth)
  })

  return {
    width,
    tier,
    isMobile,
    isTablet,
    isDesktop,
  }
}
