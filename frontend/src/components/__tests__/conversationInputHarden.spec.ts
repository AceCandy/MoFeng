import { createApp, defineComponent, h, nextTick, reactive, ref } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'

import ConversationInput from '@/components/ConversationInput.vue'
import type { UIControl } from '@/api/novel'

const mountConversationInput = (initialControl: UIControl | null) => {
  const state = reactive({
    uiControl: initialControl as UIControl | null,
    loading: false,
  })
  const submit = vi.fn()
  const host = document.createElement('div')

  const app = createApp(
    defineComponent({
      setup() {
        return () =>
          h(ConversationInput, {
            uiControl: state.uiControl,
            loading: state.loading,
            onSubmit: submit,
          })
      },
    }),
  )

  app.mount(host)

  return {
    app,
    host,
    state,
    submit,
  }
}

const getTextarea = (host: HTMLElement) => {
  const textarea = host.querySelector('textarea') as HTMLTextAreaElement | null
  if (!textarea) {
    throw new Error('未找到 ConversationInput 文本框')
  }
  return textarea
}

const getManualInputButton = (host: HTMLElement) => {
  const button = Array.from(host.querySelectorAll('button')).find((node) => node.textContent?.includes('我要输入')) as HTMLButtonElement | undefined
  if (!button) {
    throw new Error('未找到「我要输入」按钮')
  }
  return button
}

const triggerClick = (element: HTMLElement) => {
  element.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, composed: true }))
}

const setDraftText = (textarea: HTMLTextAreaElement, value: string) => {
  textarea.value = value
  textarea.dispatchEvent(new Event('input', { bubbles: true }))
}

afterEach(() => {
  document.body.innerHTML = ''
})

describe('ConversationInput harden', () => {
  it('同一 single_choice 控件深层刷新时保留手动草稿且不退出手动输入', async () => {
    const { app, host, state } = mountConversationInput({
      type: 'single_choice',
      options: [
        { id: 'opt-1', label: '选项一' },
      ],
    })

    try {
      document.body.appendChild(host)
      await nextTick()

      const manualButton = getManualInputButton(host)
      triggerClick(manualButton)
      await nextTick()

      const textarea = getTextarea(host)
      expect(textarea.disabled).toBe(false)
      setDraftText(textarea, '我想自己输入这段草稿')
      await nextTick()

      const refreshedTextarea = getTextarea(host)
      expect(refreshedTextarea.value).toBe('我想自己输入这段草稿')
      expect(refreshedTextarea.disabled).toBe(false)

      state.uiControl = {
        type: 'single_choice',
        options: [
          { id: 'opt-1', label: '选项一（刷新）' },
        ],
        placeholder: '刷新后的占位文案',
      }
      await nextTick()

      const refreshedTextareaAfterRefresh = getTextarea(host)
      expect(refreshedTextareaAfterRefresh.value).toBe('我想自己输入这段草稿')
      expect(refreshedTextareaAfterRefresh.disabled).toBe(false)
      expect(document.activeElement).toBe(refreshedTextareaAfterRefresh)
    } finally {
      app.unmount()
      host.remove()
    }
  })

  it('single_choice 选项身份变化时重置旧草稿', async () => {
    const { app, host, state } = mountConversationInput({
      type: 'single_choice',
      options: [
        { id: 'opt-1', label: '选项一' },
      ],
    })

    try {
      document.body.appendChild(host)
      await nextTick()

      triggerClick(getManualInputButton(host))
      await nextTick()

      const textarea = getTextarea(host)
      setDraftText(textarea, '上一轮问题的草稿')
      await nextTick()

      state.uiControl = {
        type: 'single_choice',
        options: [
          { id: 'next-1', label: '新问题选项' },
        ],
      }
      await nextTick()

      const nextTextarea = getTextarea(host)
      expect(nextTextarea.value).toBe('')
      expect(nextTextarea.disabled).toBe(true)
    } finally {
      app.unmount()
      host.remove()
    }
  })

  it('控件类型真正切换时会重置草稿并聚焦新输入框', async () => {
    const { app, host, state } = mountConversationInput({
      type: 'single_choice',
      options: [
        { id: 'opt-1', label: '选项一' },
      ],
    })

    try {
      document.body.appendChild(host)
      await nextTick()

      const manualButton = getManualInputButton(host)
      triggerClick(manualButton)
      await nextTick()

      const textarea = getTextarea(host)
      expect(textarea.disabled).toBe(false)
      setDraftText(textarea, '待保留草稿')
      await nextTick()

      state.uiControl = {
        type: 'text_input',
        placeholder: '请输入新的内容',
      }
      await nextTick()
      await nextTick()

      const refreshedTextarea = getTextarea(host)
      expect(refreshedTextarea.value).toBe('')
      expect(refreshedTextarea.disabled).toBe(false)
      expect(document.activeElement).toBe(refreshedTextarea)
    } finally {
      app.unmount()
      host.remove()
    }
  })
})
