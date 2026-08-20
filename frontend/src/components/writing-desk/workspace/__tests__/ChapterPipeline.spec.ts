// AIMETA P=章节进度可访问性测试|R=原生按钮_waiting禁用_当前节点|NR=不测试工作流actor|E=test:component:chapter-pipeline|X=internal|A=ChapterPipeline|D=vitest,vue|S=test|RD=../README.ai
import { createApp, h, type App } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'

import ChapterPipeline from '@/components/writing-desk/workspace/ChapterPipeline.vue'

const mounted: Array<{ app: App; host: HTMLDivElement }> = []
const states: Record<string, string> = { plan: 'done', draft: 'in-progress', review: 'waiting' }

const mountPipeline = (overrides: Record<string, unknown> = {}) => {
  const host = document.createElement('div')
  document.body.append(host)
  const onSelect = vi.fn()
  const onRetryActiveStep = vi.fn()
  const onConfirmManual = vi.fn()
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
      onRetryActiveStep,
      onConfirmManual,
      ...overrides,
    }),
  })
  app.mount(host)
  mounted.push({ app, host })
  return { host, onSelect, onRetryActiveStep, onConfirmManual }
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

  it('展示候选分组、并行投影以及控制和终态类型', () => {
    const v2States: Record<string, string> = {
      generate_candidate_1: 'done',
      generate_candidate_2: 'skipped',
      project_memory: 'done',
      project_rag: 'skipped',
      project_foreshadowing: 'done',
      wait_for_projections: 'in-progress',
      successful: 'waiting',
    }
    const { host } = mountPipeline({
      pipelineSteps: [
        { key: 'generate_candidate_1', label: '候选版本 1', group: 'candidates', groupLabel: '候选版本' },
        { key: 'generate_candidate_2', label: '候选版本 2', group: 'candidates', groupLabel: '候选版本', optional: true },
        { key: 'project_memory', label: '更新记忆快照', group: 'projections', groupLabel: '并行投影', groupMode: 'parallel' },
        { key: 'project_rag', label: '写入章节索引', group: 'projections', groupLabel: '并行投影', groupMode: 'parallel', optional: true },
        { key: 'project_foreshadowing', label: '同步伏笔', group: 'projections', groupLabel: '并行投影', groupMode: 'parallel' },
        { key: 'wait_for_projections', label: '等待投影完成', kind: 'control', group: 'completion', groupLabel: '汇合与完成' },
        { key: 'successful', label: '章节工作流完成', kind: 'terminal', group: 'completion', groupLabel: '汇合与完成' },
      ],
      stepState: (key: string) => ({
        tone: v2States[key],
        label: key === 'generate_candidate_2' ? '仅生成一个候选' : v2States[key],
      }),
      activeStepKey: 'wait_for_projections',
    })

    expect(host.querySelector('[data-group="candidates"]')?.textContent).toContain('候选版本 2')
    expect(host.querySelector('[data-group="projections"]')?.getAttribute('data-mode')).toBe('parallel')
    expect(host.querySelector('[data-group="projections"]')?.textContent).toContain('并行')
    expect(host.querySelector('.is-skipped')?.textContent).toContain('仅生成一个候选')
    expect(host.querySelector('.is-control')?.textContent).toContain('控制')
    expect(host.querySelector('.is-terminal')?.textContent).toContain('终态')
  })

  it('让可重试的失败节点直接承担重试操作', () => {
    const { host, onSelect, onRetryActiveStep } = mountPipeline({
      stepState: (key: string) => ({
        tone: key === 'draft' ? 'failed' : states[key],
        label: key === 'draft' ? '失败' : states[key],
      }),
      canRetryActiveStep: true,
    })
    const retryNode = host.querySelector<HTMLButtonElement>('[data-action="retry-failed-node"]')

    expect(retryNode?.getAttribute('aria-label')).toBe('重试起草')
    expect(retryNode?.querySelector('.chapter-console__pipeline-failed-label')?.textContent).toBe(
      '失败',
    )
    expect(retryNode?.querySelector('.chapter-console__pipeline-retry-label')?.textContent).toBe(
      '重试',
    )
    retryNode?.click()
    expect(onRetryActiveStep).toHaveBeenCalledOnce()
    expect(onSelect).not.toHaveBeenCalled()
  })

  it('提交重试时禁用失败节点，避免重复操作', () => {
    const { host, onRetryActiveStep } = mountPipeline({
      stepState: (key: string) => ({
        tone: key === 'draft' ? 'failed' : states[key],
        label: key === 'draft' ? '失败' : states[key],
      }),
      canRetryActiveStep: true,
      pending: true,
    })
    const retryNode = host.querySelector<HTMLButtonElement>('[data-action="retry-failed-node"]')

    expect(retryNode?.disabled).toBe(true)
    expect(retryNode?.textContent).toContain('提交中')
    retryNode?.click()
    expect(onRetryActiveStep).not.toHaveBeenCalled()
  })

  it('待人工确认节点直接承担确认操作且不重复显示等待状态', () => {
    const { host, onSelect, onConfirmManual } = mountPipeline({
      activeStepKey: 'review',
      canConfirmManual: true,
      shouldShowManualConfirmBadge: (key: string) => key === 'review',
      stepState: (key: string) => ({
        tone: key === 'review' ? 'pending' : states[key],
        label: key === 'review' ? '等待你确认' : states[key],
      }),
    })
    const confirmNode = host.querySelector<HTMLButtonElement>('[data-action="confirm-manual-node"]')

    expect(confirmNode?.disabled).toBe(false)
    expect(confirmNode?.getAttribute('aria-label')).toBe('确认并继续')
    expect(confirmNode?.textContent).toContain('待人工确认')
    expect(confirmNode?.textContent).toContain('确认并继续')
    expect(confirmNode?.textContent).not.toContain('等待你确认')
    confirmNode?.click()
    expect(onConfirmManual).toHaveBeenCalledOnce()
    expect(onSelect).not.toHaveBeenCalled()
  })

  it('确认提交中禁用待人工确认节点', () => {
    const { host, onConfirmManual } = mountPipeline({
      activeStepKey: 'review',
      canConfirmManual: true,
      pending: true,
      shouldShowManualConfirmBadge: (key: string) => key === 'review',
      stepState: (key: string) => ({
        tone: key === 'review' ? 'pending' : states[key],
        label: states[key],
      }),
    })
    const confirmNode = host.querySelector<HTMLButtonElement>('[data-action="confirm-manual-node"]')

    expect(confirmNode?.disabled).toBe(true)
    confirmNode?.click()
    expect(onConfirmManual).not.toHaveBeenCalled()
  })
})
