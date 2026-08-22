import { nextTick, onBeforeUnmount, watch, type Ref } from 'vue'

interface UseDialogA11yOptions {
  active: Ref<boolean>
  dialogRef: Ref<HTMLElement | null>
  onClose?: () => void
  initialFocusRef?: Ref<HTMLElement | null>
  closeOnEscape?: boolean
  trapFocus?: boolean
  lockBodyScroll?: boolean
  restoreFocus?: boolean
}

const FOCUSABLE_SELECTOR = [
  'a[href]',
  'area[href]',
  'button:not([disabled])',
  'input:not([disabled]):not([type="hidden"])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  'iframe',
  'object',
  'embed',
  '[tabindex]:not([tabindex="-1"])',
  '[contenteditable="true"]',
].join(',')

let bodyScrollLockCount = 0
let originalBodyOverflow = ''
const inertBackgroundElements = new Map<HTMLElement, { count: number; wasInert: boolean }>()

const lockBodyScroll = () => {
  if (bodyScrollLockCount === 0) {
    originalBodyOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
  }
  bodyScrollLockCount += 1
}

const unlockBodyScroll = () => {
  if (bodyScrollLockCount <= 0) return
  bodyScrollLockCount -= 1
  if (bodyScrollLockCount === 0) {
    document.body.style.overflow = originalBodyOverflow
  }
}

const retainInert = (element: HTMLElement) => {
  const existing = inertBackgroundElements.get(element)
  if (existing) {
    existing.count += 1
    return
  }
  inertBackgroundElements.set(element, { count: 1, wasInert: element.inert === true })
  element.inert = true
}

const releaseInert = (element: HTMLElement) => {
  const existing = inertBackgroundElements.get(element)
  if (!existing) return
  existing.count -= 1
  if (existing.count > 0) return
  element.inert = existing.wasInert
  inertBackgroundElements.delete(element)
}

const collectBackgroundElements = (dialog: HTMLElement) => {
  const elements = new Set<HTMLElement>()
  let current: HTMLElement | null = dialog
  while (current && current !== document.body) {
    const container: HTMLElement | null = current.parentElement
    if (!container) break
    for (const sibling of container.children) {
      if (sibling !== current && sibling instanceof HTMLElement) {
        elements.add(sibling)
      }
    }
    current = container
  }
  return [...elements]
}

const isVisible = (element: HTMLElement) => {
  if (element.hasAttribute('hidden')) return false
  if (element.getAttribute('aria-hidden') === 'true') return false
  const style = window.getComputedStyle(element)
  if (style.display === 'none' || style.visibility === 'hidden') return false
  return element.getClientRects().length > 0
}

const getFocusableElements = (container: HTMLElement) => {
  return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)).filter(isVisible)
}

export const useDialogA11y = ({
  active,
  dialogRef,
  onClose,
  initialFocusRef,
  closeOnEscape = true,
  trapFocus = true,
  lockBodyScroll: shouldLockBodyScroll = true,
  restoreFocus = true,
}: UseDialogA11yOptions) => {
  let previousActiveElement: HTMLElement | null = null
  let isActivated = false
  let backgroundElements: HTMLElement[] = []

  const closeDialog = () => {
    onClose?.()
  }

  // 打开对话框后优先聚焦显式焦点元素，其次回退到第一个可聚焦元素。
  const focusInitialTarget = () => {
    const dialog = dialogRef.value
    if (!dialog) return

    const explicitTarget =
      initialFocusRef?.value ||
      (dialog.querySelector('[data-dialog-initial-focus]') as HTMLElement | null)

    if (explicitTarget && !explicitTarget.hasAttribute('disabled')) {
      explicitTarget.focus()
      return
    }

    const focusable = getFocusableElements(dialog)
    if (focusable.length > 0) {
      focusable[0].focus()
      return
    }

    if (dialog.tabIndex < 0) {
      dialog.tabIndex = -1
    }
    dialog.focus()
  }

  const prepareDialog = async () => {
    await nextTick()
    if (!isActivated || !dialogRef.value) return
    backgroundElements = collectBackgroundElements(dialogRef.value)
    backgroundElements.forEach(retainInert)
    focusInitialTarget()
  }

  // 统一处理 Esc 关闭与 Tab 焦点陷阱，避免焦点逃逸到背景页面。
  const onDocumentKeydown = (event: KeyboardEvent) => {
    if (!active.value) return
    const dialog = dialogRef.value
    if (!dialog) return

    if (closeOnEscape && event.key === 'Escape') {
      event.preventDefault()
      closeDialog()
      return
    }

    if (!trapFocus || event.key !== 'Tab') return

    const focusable = getFocusableElements(dialog)
    if (focusable.length === 0) {
      event.preventDefault()
      dialog.focus()
      return
    }

    const first = focusable[0]
    const last = focusable[focusable.length - 1]
    const activeElement = document.activeElement as HTMLElement | null

    if (!activeElement || !dialog.contains(activeElement)) {
      event.preventDefault()
      if (event.shiftKey) {
        last.focus()
      } else {
        first.focus()
      }
      return
    }

    if (event.shiftKey && activeElement === first) {
      event.preventDefault()
      last.focus()
      return
    }

    if (!event.shiftKey && activeElement === last) {
      event.preventDefault()
      first.focus()
    }
  }

  const activate = () => {
    if (isActivated) return
    isActivated = true
    previousActiveElement = document.activeElement as HTMLElement | null
    if (shouldLockBodyScroll) {
      lockBodyScroll()
    }
    document.addEventListener('keydown', onDocumentKeydown)
    void prepareDialog()
  }

  const deactivate = () => {
    if (!isActivated) return
    isActivated = false
    document.removeEventListener('keydown', onDocumentKeydown)
    if (shouldLockBodyScroll) {
      unlockBodyScroll()
    }
    backgroundElements.forEach(releaseInert)
    backgroundElements = []

    if (
      restoreFocus &&
      previousActiveElement &&
      document.contains(previousActiveElement) &&
      typeof previousActiveElement.focus === 'function'
    ) {
      previousActiveElement.focus()
    }
    previousActiveElement = null
  }

  watch(
    active,
    (isActive) => {
      if (isActive) {
        activate()
      } else {
        deactivate()
      }
    },
    { immediate: true },
  )

  onBeforeUnmount(() => {
    deactivate()
  })
}
