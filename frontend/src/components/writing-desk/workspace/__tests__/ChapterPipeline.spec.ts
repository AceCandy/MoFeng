// AIMETA P=章节进度可访问性测试|R=原生按钮_waiting禁用_当前节点|NR=不测试工作流actor|E=test:component:chapter-pipeline|X=internal|A=ChapterPipeline|D=vitest,vue|S=test|RD=../README.ai
import { createApp, h, type App } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'

import ChapterPipeline from '@/components/writing-desk/workspace/ChapterPipeline.vue'

const mounted: Array<{ app: App; host: HTMLDivElement }> = []
const states: Record<string, string> = { plan: 'done', draft: 'in-progress', review: 'waiting' }

const mountPipeline = () => {
  const host = document.createElement('div')
  document.body.append(host)
  const onSelect = vi.fn()
  const app = createApp({
    render: () => h(ChapterPipeline, {
      pipelineSteps: [
        { key: 'plan', label: '规划' },
        { key: 'draft', label: '起草' },
        { key: 'review', label: '评审' },
      ],
      stepState: (key: string) => ({ tone: states[key], label: states[key] }),
      stepTooltipText: (_key: string, index: number) => `第${index + 1}步`,
      shouldShowManualConfirmBadge: () => false,
      activeStepKey: 'draft',
      onSelect,
    }),
  })
  app.mount(host)
  mounted.push({ app, host })
  return { host, onSelect }
}

afterEach(() => {
  for (const item of mounted.splice(0)) {
    item.app.unmount()
    item.host.remove()
  }
  vi.restoreAllMocks()
})

describe('ChapterPipeline', () => {
  it('使用原生按钮并禁用 waiting 节点', () => {
    const { host, onSelect } = mountPipeline()
    const buttons = [...host.querySelectorAll<HTMLButtonElement>('.chapter-console__pipeline-select')]

    expect(buttons).toHaveLength(3)
    expect(buttons[1]?.getAttribute('aria-current')).toBe('step')
    expect(buttons[2]?.disabled).toBe(true)
    buttons[0]?.click()
    buttons[2]?.click()
    expect(onSelect).toHaveBeenCalledOnce()
    expect(onSelect).toHaveBeenCalledWith('plan', 0)
  })
})
