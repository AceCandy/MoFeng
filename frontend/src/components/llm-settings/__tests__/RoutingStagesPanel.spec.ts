// AIMETA P=正文节点路由面板测试|R=节点覆盖_能力过滤_独立与共用路由|NR=不测试API保存|E=test:component:RoutingStagesPanel|X=internal|A=model-routing|D=vitest,vue|S=test|RD=../README.ai
import { createApp, h, nextTick, reactive, type App } from 'vue'
import { afterEach, describe, expect, it } from 'vitest'

import type { UserAIModel } from '@/api/llm'
import RoutingStagesPanel from '@/components/llm-settings/RoutingStagesPanel.vue'

const mounted: Array<{ app: App; host: HTMLDivElement }> = []

const model = (
  id: number,
  displayName: string,
  capability: 'chat' | 'embedding',
  isDefault = false,
): UserAIModel => ({
  id,
  user_id: 1,
  provider_id: capability === 'chat' ? 10 : 20,
  display_name: displayName,
  model_name: displayName,
  capabilities: { [capability]: true },
  context_window: null,
  is_default_chat: capability === 'chat' && isDefault,
  is_default_embedding: capability === 'embedding' && isDefault,
  is_default_tts: false,
  tts_protocol: null,
  tts_voice: null,
  tts_speed: 1,
  is_enabled: true,
  sort_order: id,
  input_price_per_million: null,
  output_price_per_million: null,
  cached_input_price_per_million: null,
  cache_write_input_price_per_million: null,
  pricing_currency: null,
})

const chatDefault = model(1, 'Chat Default', 'chat', true)
const chatOverride = model(2, 'Chat Override', 'chat')
const embeddingDefault = model(3, 'Embedding Default', 'embedding', true)
const embeddingOverride = model(4, 'Embedding Override', 'embedding')

const mountPanel = () => {
  const host = document.createElement('div')
  document.body.append(host)
  const routeSelections = reactive<Record<string, string>>({})
  const app = createApp({
    render: () =>
      h(RoutingStagesPanel, {
        routeSelections,
        enabledChatModels: [chatDefault, chatOverride],
        primaryChatModel: chatDefault,
        enabledEmbeddingModels: [embeddingDefault, embeddingOverride],
        defaultEmbeddingModel: embeddingDefault,
        providerName: (providerId: number) => `Provider ${providerId}`,
        onUpdateSelection: (stageKey: string, value: string) => {
          routeSelections[stageKey] = value
        },
      }),
  })
  app.mount(host)
  mounted.push({ app, host })
  return { host, routeSelections }
}

afterEach(() => {
  for (const item of mounted.splice(0)) {
    item.app.unmount()
    item.host.remove()
  }
})

describe('RoutingStagesPanel', () => {
  it('按正文 DAG 展示全部节点并区分无模型节点', () => {
    const { host } = mountPanel()

    expect(host.querySelectorAll('.model-routing__workflow-node')).toHaveLength(30)
    expect(host.querySelector('[data-node="freeze_base_context"]')?.textContent).toContain(
      '无模型调用',
    )
    expect(
      host.querySelector('[data-node="freeze_base_context"] .model-routing__route-select'),
    ).toBeNull()
    expect(host.querySelector('[data-group="candidates"]')?.getAttribute('data-mode')).toBe(
      'parallel',
    )
  })

  it('按 capability 隔离模型并显示具体默认模型', () => {
    const { host } = mountPanel()
    const chatSelect = host.querySelector<HTMLSelectElement>(
      '[data-node="plan_chapter"] .model-routing__route-select',
    )
    const embeddingSelect = host.querySelector<HTMLSelectElement>(
      '[data-node="project_rag"] .model-routing__route-select',
    )

    expect(chatSelect?.textContent).toContain('主模型：Chat Default · Provider 10')
    expect(chatSelect?.textContent).toContain('Chat Override')
    expect(chatSelect?.textContent).not.toContain('Embedding Override')
    expect(embeddingSelect?.textContent).toContain('当前检索模型：Embedding Default · Provider 20')
    expect(embeddingSelect?.textContent).toContain('Embedding Override')
    expect(embeddingSelect?.textContent).not.toContain('Chat Override')
  })

  it('让候选版本独立选模并保持其他共用 stage 同步', async () => {
    const { host, routeSelections } = mountPanel()
    const candidate1 = host.querySelector<HTMLSelectElement>('[data-stage="chapter_writing_1"]')
    const candidate2 = host.querySelector<HTMLSelectElement>('[data-stage="chapter_writing_2"]')

    expect(candidate1).not.toBeNull()
    expect(candidate2).not.toBeNull()
    candidate1!.value = '2'
    candidate1!.dispatchEvent(new Event('change'))
    await nextTick()

    expect(routeSelections.chapter_writing_1).toBe('2')
    expect(routeSelections.chapter_writing_2).toBeUndefined()
    expect(candidate2?.value).toBe('')
    expect(host.querySelector('[data-node="generate_candidate_1"]')?.textContent).not.toContain(
      '共用路由',
    )

    const sharedSelects = [
      ...host.querySelectorAll<HTMLSelectElement>('[data-stage="chapter_optimization"]'),
    ]
    expect(sharedSelects).toHaveLength(6)
    sharedSelects[0]!.value = '2'
    sharedSelects[0]!.dispatchEvent(new Event('change'))
    await nextTick()

    expect(routeSelections.chapter_optimization).toBe('2')
    expect(sharedSelects[1]?.value).toBe('2')
  })

  it('把通用模型调用放在其他功能而不是正文节点', () => {
    const { host } = mountPanel()

    expect(host.querySelector('[data-node="general_chat"]')).toBeNull()
    expect(host.querySelector('.model-routing__other-groups')?.textContent).toContain('通用模型调用')
    expect(host.querySelector('.model-routing__other-groups')?.textContent).toContain('general_chat')
  })
})
