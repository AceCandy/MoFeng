import { createApp, defineComponent, h, nextTick, reactive, ref } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'

import ConversationInput from '@/components/ConversationInput.vue'
import type { UIControl } from '@/api/novel'

const mountConversationInput = (initialControl: UIControl | null) => {
  const state = reactive({
    uiControl: initialControl as UIControl | null,
    loading: false,
    modelValue: '',
  })
  const submit = vi.fn()
  const updateModelValue = vi.fn((value: string) => {
    state.modelValue = value
  })
  const blur = vi.fn()
  const host = document.createElement('div')

  const app = createApp(
    defineComponent({
      setup() {
        return () =>
          h(ConversationInput, {
            uiControl: state.uiControl,
            loading: state.loading,
            modelValue: state.modelValue,
            onSubmit: submit,
            'onUpdate:modelValue': updateModelValue,
            onBlur: blur,
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
    updateModelValue,
    blur,
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

  it('single_choice 选项身份变化时由父层决定是否清空旧草稿', async () => {
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
      expect(nextTextarea.value).toBe('上一轮问题的草稿')
      expect(nextTextarea.disabled).toBe(true)

      state.modelValue = ''
      await nextTick()
      expect(getTextarea(host).value).toBe('')
    } finally {
      app.unmount()
      host.remove()
    }
  })

  it('控件类型真正切换时保留父层草稿并聚焦新输入框', async () => {
    vi.spyOn(window, 'matchMedia').mockImplementation((query) => ({
      matches: query === '(min-width: 834px)',
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }))
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
      expect(refreshedTextarea.value).toBe('待保留草稿')
      expect(refreshedTextarea.disabled).toBe(false)
      expect(document.activeElement).toBe(refreshedTextarea)
    } finally {
      app.unmount()
      host.remove()
    }
  })

  it('移动端控件切换时不强制聚焦', async () => {
    vi.spyOn(window, 'matchMedia').mockImplementation((query) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }))
    const { app, host, state } = mountConversationInput({
      type: 'single_choice',
      options: [{ id: 'opt-1', label: '选项一' }],
    })

    try {
      document.body.appendChild(host)
      await nextTick()
      state.uiControl = { type: 'text_input', placeholder: '请输入新的内容' }
      await nextTick()
      await nextTick()

      expect(document.activeElement).not.toBe(getTextarea(host))
    } finally {
      app.unmount()
      host.remove()
    }
  })

  it('通过 v-model 上报草稿，blur 和发送失败前都不自行清空', async () => {
    const { app, host, state, submit, updateModelValue, blur } = mountConversationInput({
      type: 'text_input',
      placeholder: '继续补充',
    })

    try {
      document.body.appendChild(host)
      await nextTick()
      const textarea = getTextarea(host)
      setDraftText(textarea, '  尚未发送的草稿  ')
      textarea.dispatchEvent(new FocusEvent('blur', { bubbles: true }))
      const form = host.querySelector('form')
      form?.dispatchEvent(new SubmitEvent('submit', { bubbles: true, cancelable: true }))
      await nextTick()

      expect(updateModelValue).toHaveBeenLastCalledWith('  尚未发送的草稿  ')
      expect(state.modelValue).toBe('  尚未发送的草稿  ')
      expect(blur).toHaveBeenCalledOnce()
      expect(submit).toHaveBeenCalledWith({ id: 'text_input', value: '尚未发送的草稿' })
      expect(getTextarea(host).value).toBe('  尚未发送的草稿  ')
    } finally {
      app.unmount()
      host.remove()
    }
  })
})
