// AIMETA P=遗留蓝图编辑器契约测试|R=v-model克隆_弹窗保存payload|NR=不测试蓝图API与视觉样式|E=test:component:legacy-editors|X=internal|A=vitest,vue|D=vue|S=test|RD=../README.ai
import { createApp, h, nextTick, type App } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'

import BlueprintEditModal from '@/components/BlueprintEditModal.vue'
import FactionsEditor from '@/components/FactionsEditor.vue'

const mounted: Array<{ app: App; host: HTMLDivElement }> = []

const mount = (component: Parameters<typeof h>[0], props: Record<string, unknown>) => {
  const host = document.createElement('div')
  document.body.append(host)
  const app = createApp({ render: () => h(component, props) })
  app.mount(host)
  mounted.push({ app, host })
  return host
}

afterEach(() => {
  for (const item of mounted.splice(0)) {
    item.app.unmount()
    item.host.remove()
  }
  document.body.style.overflow = ''
  vi.restoreAllMocks()
})

describe('legacy blueprint editor contracts', () => {
  it('clones array props before emitting v-model updates', async () => {
    const source = [{ name: '旧阵营', description: '旧描述' }]
    const onUpdate = vi.fn()
    const host = mount(FactionsEditor, {
      modelValue: source,
      'onUpdate:modelValue': onUpdate,
    })
    await nextTick()

    const input = host.querySelector<HTMLInputElement>('input')
    expect(input).not.toBeNull()
    if (!input) return
    input.value = '新阵营'
    input.dispatchEvent(new Event('input', { bubbles: true }))
    await nextTick()

    expect(source[0].name).toBe('旧阵营')
    expect(onUpdate.mock.calls.at(-1)?.[0]).toEqual([
      { name: '新阵营', description: '旧描述' },
    ])
  })

  it('keeps the modal save payload field and content shape', async () => {
    const onSave = vi.fn()
    const host = mount(BlueprintEditModal, {
      show: true,
      title: '完整梗概',
      field: 'full_synopsis',
      content: '旧梗概',
      onSave,
    })
    await nextTick()

    const textarea = host.querySelector<HTMLTextAreaElement>('textarea')
    expect(textarea).not.toBeNull()
    if (!textarea) return
    textarea.value = '新梗概'
    textarea.dispatchEvent(new Event('input', { bubbles: true }))
    host.querySelectorAll<HTMLButtonElement>('.blueprint-edit-modal__actions button')[1]?.click()

    expect(onSave).toHaveBeenCalledWith({ field: 'full_synopsis', content: '新梗概' })
  })

  it('keeps every array item when saving without edits', async () => {
    const content = [{ chapter_number: 1, title: '第一章', summary: '开端' }]
    const onSave = vi.fn()
    const host = mount(BlueprintEditModal, {
      show: true,
      title: '章节大纲',
      field: 'chapter_outline',
      content,
      onSave,
    })
    await nextTick()

    host.querySelectorAll<HTMLButtonElement>('.blueprint-edit-modal__actions button')[1]?.click()

    expect(onSave).toHaveBeenCalledWith({ field: 'chapter_outline', content })
  })
})
