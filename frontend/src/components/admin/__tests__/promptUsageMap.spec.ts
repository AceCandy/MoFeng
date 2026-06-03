import { createApp, nextTick } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'

import PromptUsageMap from '@/components/admin/PromptUsageMap.vue'

const queryState = vi.hoisted(() => ({
  prompts: [
    {
      id: 1,
      name: 'concept',
      title: '概念对话提示词',
      content: '请将用户灵感整理为结构化追问，并判断蓝图准备状态。',
      tags: ['blueprint'],
    },
  ],
  refetch: vi.fn(),
}))

vi.mock('@/queries/admin', async () => {
  const { ref } = await import('vue')

  return {
    useAdminPromptsQuery: () => ({
      data: ref(queryState.prompts),
      isLoading: ref(false),
      isFetching: ref(false),
      error: ref(null),
      refetch: queryState.refetch,
    }),
  }
})

const mountPromptUsageMap = () => {
  const host = document.createElement('div')
  document.body.appendChild(host)

  const app = createApp(PromptUsageMap)
  app.mount(host)

  return { app, host }
}

const click = (element: HTMLElement) => {
  element.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }))
}

afterEach(() => {
  document.body.innerHTML = ''
  queryState.refetch.mockClear()
})

describe('PromptUsageMap', () => {
  it('点击数据库 Prompt 名称后展开并收起正文预览', async () => {
    const { app, host } = mountPromptUsageMap()

    try {
      await nextTick()

      expect(host.textContent).not.toContain('请将用户灵感整理为结构化追问')

      const conceptButton = Array.from(host.querySelectorAll('button')).find(
        (button) => button.textContent?.trim() === 'concept',
      )

      if (!conceptButton) {
        throw new Error('未找到 concept 提示词展开按钮')
      }

      click(conceptButton)
      await nextTick()

      expect(host.textContent).toContain('概念对话提示词')
      expect(host.textContent).toContain('请将用户灵感整理为结构化追问，并判断蓝图准备状态。')

      click(conceptButton)
      await nextTick()

      expect(host.textContent).not.toContain('请将用户灵感整理为结构化追问')
    } finally {
      app.unmount()
      host.remove()
    }
  })
})
