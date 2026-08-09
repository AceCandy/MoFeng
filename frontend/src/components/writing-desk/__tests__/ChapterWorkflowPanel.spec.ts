// AIMETA P=章节工作流状态面板测试|R=状态文案_allowed命令_候选ID与风险确认|NR=不测试actor或HTTP|E=test:component:ChapterWorkflowPanel|X=internal|A=ChapterWorkflowPanel|D=vitest,vue|S=test|RD=../README.ai
import { createApp, h, nextTick, reactive, type App } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { ChapterVersionSelection } from '@/api/novel'
import ChapterWorkflowPanel from '@/components/writing-desk/ChapterWorkflowPanel.vue'
import { globalAlert } from '@/composables/useAlert'

const candidates: ChapterVersionSelection[] = [
  {
    id: 41,
    content: '第一份候选正文',
    version_label: 'v1',
    workflow_run_id: '11111111-1111-4111-8111-111111111111',
  },
  {
    id: 42,
    content: '第二份候选正文',
    version_label: 'v2',
    workflow_run_id: '11111111-1111-4111-8111-111111111111',
  },
]

const mounted: Array<{ app: App; host: HTMLDivElement }> = []

const mountPanel = (
  overrides: Record<string, unknown> = {},
  listeners: Record<string, (...args: unknown[]) => void> = {},
) => {
  const host = document.createElement('div')
  document.body.append(host)
  const app = createApp({
    render: () => h(ChapterWorkflowPanel, {
      phase: 'waitingForSelection',
      transport: 'connected',
      allowedCommands: ['select', 'cancel'],
      pending: false,
      error: null,
      retryActivityKey: null,
      candidates,
      ...overrides,
      ...listeners,
    }),
  })
  app.mount(host)
  mounted.push({ app, host })
  return host
}

afterEach(() => {
  for (const item of mounted.splice(0)) {
    item.app.unmount()
    item.host.remove()
  }
  vi.restoreAllMocks()
})

describe('ChapterWorkflowPanel', () => {
  it('waiting 无候选时显示同步中且没有可提交的选版按钮', () => {
    const host = mountPanel({ candidates: [] })

    expect(host.querySelector('[role="status"]')?.textContent).toContain('候选版本同步中')
    expect(host.querySelector('[role="radiogroup"]')).toBeNull()
    expect(host.querySelector('[data-action="select"]')).toBeNull()
  })

  it('选择候选时提交真实版本 ID 而非数组下标', async () => {
    const onSelectVersion = vi.fn()
    const host = mountPanel({}, { onSelectVersion })
    const radios = host.querySelectorAll<HTMLButtonElement>('[role="radio"]')

    radios[1]?.click()
    await nextTick()
    host.querySelector<HTMLButtonElement>('[data-action="select"]')?.click()

    expect(radios[1]?.getAttribute('aria-checked')).toBe('true')
    expect(onSelectVersion).toHaveBeenCalledWith(42)
  })

  it('候选预览剥离优化器 JSON 包装', async () => {
    const onPreviewCandidate = vi.fn()
    const wrappedCandidates: ChapterVersionSelection[] = [
      {
        ...candidates[0],
        content: '```json\n{"optimized_content":"正常正文"}\n```',
      },
    ]
    const host = mountPanel({ candidates: wrappedCandidates }, { onPreviewCandidate })
    await nextTick()

    const preview = host.querySelector('.chapter-workflow__candidate-preview')
    expect(preview?.textContent).toContain('正常正文')
    expect(preview?.textContent).not.toContain('optimized_content')
    expect(onPreviewCandidate).toHaveBeenLastCalledWith('正常正文')
  })

  it('候选支持方向键循环、Home/End 和焦点同步', async () => {
    const onSelectVersion = vi.fn()
    const host = mountPanel({}, { onSelectVersion })
    const radios = [...host.querySelectorAll<HTMLButtonElement>('[role="radio"]')]

    const expectSelected = (index: number) => {
      expect(radios.map((radio) => radio.getAttribute('aria-checked')))
        .toEqual(index === 0 ? ['true', 'false'] : ['false', 'true'])
      expect(radios.map((radio) => radio.tabIndex))
        .toEqual(index === 0 ? [0, -1] : [-1, 0])
      expect(document.activeElement).toBe(radios[index])
    }
    const press = async (index: number, key: string) => {
      const event = new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true })
      radios[index]?.dispatchEvent(event)
      await nextTick()
      expect(event.defaultPrevented).toBe(true)
    }

    radios[0]?.focus()
    expectSelected(0)
    await press(0, 'Home')
    expectSelected(0)
    await press(0, 'ArrowRight')
    expectSelected(1)
    await press(1, 'ArrowDown')
    expectSelected(0)
    await press(0, 'ArrowUp')
    expectSelected(1)
    await press(1, 'ArrowLeft')
    expectSelected(0)
    await press(0, 'End')
    expectSelected(1)
    await press(1, 'End')
    expectSelected(1)
    await press(1, 'Home')
    expectSelected(0)
    await press(0, 'ArrowRight')
    host.querySelector<HTMLButtonElement>('[data-action="select"]')?.click()
    expect(onSelectVersion).toHaveBeenCalledWith(42)
  })

  it('候选集合切换后不会提交已失效的旧版本 ID', async () => {
    const onSelectVersion = vi.fn()
    const overrides = reactive<{ candidates: ChapterVersionSelection[] }>({ candidates })
    const host = mountPanel(overrides, { onSelectVersion })

    host.querySelectorAll<HTMLButtonElement>('[role="radio"]')[1]?.click()
    await nextTick()
    overrides.candidates = [
      {
        id: 99,
        content: '新运行的唯一候选正文',
        version_label: 'new-v1',
        workflow_run_id: '22222222-2222-4222-8222-222222222222',
      },
    ]
    await nextTick()

    const currentRadio = host.querySelector<HTMLButtonElement>('[role="radio"]')
    expect(currentRadio?.getAttribute('aria-checked')).toBe('true')
    host.querySelector<HTMLButtonElement>('[data-action="select"]')?.click()
    expect(onSelectVersion).toHaveBeenCalledWith(99)
    expect(onSelectVersion).not.toHaveBeenCalledWith(42)
  })

  it('只显示 allowed_commands 对应的恢复动作', () => {
    const host = mountPanel({
      phase: 'projectionPending',
      allowedCommands: ['retry_projection'],
      candidates: [],
    })

    expect(host.textContent).toContain('正文已提交')
    expect(host.querySelector('[data-action="retry-projection"]')).not.toBeNull()
    expect(host.querySelector('[data-action="retry"]')).toBeNull()
    expect(host.querySelector('[data-action="cancel"]')).toBeNull()
  })

  it('外部重试必须确认可能重复调用的风险', async () => {
    const onRetryExternal = vi.fn()
    vi.spyOn(globalAlert, 'showConfirm').mockResolvedValue(false)
    const host = mountPanel({
      phase: 'failed',
      allowedCommands: ['retry_external', 'cancel'],
      error: '外部模型返回结果不确定',
      retryActivityKey: 'wf:generate_candidates:stable-key',
      candidates: [],
    }, { onRetryExternal })

    host.querySelector<HTMLButtonElement>('[data-action="retry-external"]')?.click()
    await nextTick()
    expect(onRetryExternal).not.toHaveBeenCalled()

    vi.mocked(globalAlert.showConfirm).mockResolvedValue(true)
    host.querySelector<HTMLButtonElement>('[data-action="retry-external"]')?.click()
    await vi.waitFor(() => expect(onRetryExternal)
      .toHaveBeenCalledWith('wf:generate_candidates:stable-key'))
  })

  it('fatal 使用 alert 语义并提供重新同步', () => {
    const host = mountPanel({
      phase: 'fatal',
      allowedCommands: [],
      error: '章节工作流数据格式无效',
      candidates: [],
    })

    expect(host.querySelector('[role="alert"]')?.textContent)
      .toContain('章节状态暂不可信')
    expect(host.querySelector('[data-action="resync"]')).not.toBeNull()
  })
})
