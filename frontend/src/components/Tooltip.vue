<!-- AIMETA P=工具提示_悬浮提示组件|R=提示信息|NR=不含业务逻辑|E=component:Tooltip|X=internal|A=提示组件|D=vue|S=dom|RD=./README.ai -->
<template>
  <div
    ref="triggerRef"
    class="inline-block"
    @mouseenter="onMouseEnter"
    @mouseleave="onMouseLeave"
    @focusin="onFocusIn"
    @focusout="onFocusOut"
    @touchstart.passive="onTouchStart"
  >
    <slot></slot>
    <Teleport to="body">
      <transition
        enter-active-class="transition ease-out duration-200"
        enter-from-class="transform opacity-0 scale-95"
        enter-to-class="transform opacity-100 scale-100"
        leave-active-class="transition ease-in duration-150"
        leave-from-class="transform opacity-100 scale-100"
        leave-to-class="transform opacity-0 scale-95"
      >
        <div
          v-if="showTooltip && text"
          ref="tooltipRef"
          :id="tooltipId"
          role="tooltip"
          :style="tooltipStyle"
          class="fixed z-50 p-3 text-sm leading-tight text-[var(--md-on-primary)] bg-[var(--md-on-surface)] rounded-lg shadow-lg max-w-xs"
          @mouseenter="onTooltipEnter"
          @mouseleave="onTooltipLeave"
        >
          {{ text }}
        </div>
      </transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, computed, onBeforeUnmount } from 'vue'

interface Props {
  text?: string
  showDelay?: number
}

const props = defineProps<Props>()

const showTooltip = ref(false)
const triggerRef = ref<HTMLElement | null>(null)
const tooltipRef = ref<HTMLElement | null>(null)
const tooltipPosition = ref({ top: 0, left: 0 })
const tooltipId = `tooltip-${Math.random().toString(36).slice(2, 10)}`
const describedTarget = ref<HTMLElement | null>(null)

const tooltipStyle = computed(() => ({
  top: `${tooltipPosition.value.top}px`,
  left: `${tooltipPosition.value.left}px`,
}))

let leaveTimeout: NodeJS.Timeout
let enterTimeout: NodeJS.Timeout
let touchHideTimeout: NodeJS.Timeout

const clearTimers = () => {
  clearTimeout(leaveTimeout)
  clearTimeout(enterTimeout)
  clearTimeout(touchHideTimeout)
}

const bindDescribedBy = (target: HTMLElement | null) => {
  if (!target || !props.text) return
  describedTarget.value = target
  const current = target.getAttribute('aria-describedby')
  if (!current) {
    target.setAttribute('aria-describedby', tooltipId)
    return
  }
  const ids = new Set(current.split(/\s+/).filter(Boolean))
  ids.add(tooltipId)
  target.setAttribute('aria-describedby', Array.from(ids).join(' '))
}

const unbindDescribedBy = () => {
  const target = describedTarget.value
  if (!target) return
  const current = target.getAttribute('aria-describedby')
  if (!current) {
    describedTarget.value = null
    return
  }
  const next = current
    .split(/\s+/)
    .filter(Boolean)
    .filter((id) => id !== tooltipId)
  if (next.length > 0) {
    target.setAttribute('aria-describedby', next.join(' '))
  } else {
    target.removeAttribute('aria-describedby')
  }
  describedTarget.value = null
}

const openTooltip = async () => {
  showTooltip.value = true
  await nextTick()
  updatePosition()
}

const onMouseEnter = () => {
  clearTimeout(leaveTimeout)
  enterTimeout = setTimeout(async () => {
    await openTooltip()
  }, props.showDelay ?? 1000)
}

const onMouseLeave = () => {
  clearTimeout(enterTimeout)
  leaveTimeout = setTimeout(() => {
    showTooltip.value = false
  }, 200)
}

const onFocusIn = (event: FocusEvent) => {
  const target = event.target instanceof HTMLElement ? event.target : null
  clearTimeout(leaveTimeout)
  clearTimeout(enterTimeout)
  bindDescribedBy(target)
  enterTimeout = setTimeout(() => {
    void openTooltip()
  }, 120)
}

const onFocusOut = (event: FocusEvent) => {
  const next = event.relatedTarget
  if (next instanceof Node && triggerRef.value?.contains(next)) {
    return
  }
  clearTimeout(enterTimeout)
  leaveTimeout = setTimeout(() => {
    showTooltip.value = false
    unbindDescribedBy()
  }, 80)
}

const onTouchStart = () => {
  clearTimers()
  void openTooltip()
  touchHideTimeout = setTimeout(() => {
    showTooltip.value = false
    unbindDescribedBy()
  }, 1500)
}

const onTooltipEnter = () => {
  clearTimeout(leaveTimeout)
}

const onTooltipLeave = () => {
  showTooltip.value = false
  unbindDescribedBy()
}

const updatePosition = () => {
  if (!triggerRef.value || !tooltipRef.value) return

  const triggerRect = triggerRef.value.getBoundingClientRect()
  const tooltipRect = tooltipRef.value.getBoundingClientRect()

  let top = triggerRect.top - tooltipRect.height - 8 // 默认在上方，留 8px 间距
  let left = triggerRect.left + (triggerRect.width / 2) - (tooltipRect.width / 2)

  // 如果上方空间不足，则显示在下方
  if (top < 0) {
    top = triggerRect.bottom + 8
  }

  // 如果左侧超出屏幕，则向右对齐
  if (left < 0) {
    left = 8
  }

  // 如果右侧超出屏幕，则向左对齐
  if (left + tooltipRect.width > window.innerWidth) {
    left = window.innerWidth - tooltipRect.width - 8
  }

  tooltipPosition.value = { top, left }
}

onBeforeUnmount(() => {
  clearTimers()
  unbindDescribedBy()
})
</script>
