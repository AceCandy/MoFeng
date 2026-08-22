// AIMETA P=章节评审反馈面板测试|R=工作流评审公共契约_可见内容|NR=不测试评审生成或HTTP|E=test:component:ChapterEvaluationPanel|X=internal|A=ChapterEvaluationPanel|D=vitest,vue|S=test|RD=../README.ai
import { createApp, h, type App } from 'vue'
import { afterEach, describe, expect, it } from 'vitest'

import ChapterEvaluationPanel from '@/components/writing-desk/workspace/ChapterEvaluationPanel.vue'

const mounted: Array<{ app: App; host: HTMLDivElement }> = []

afterEach(() => {
  for (const item of mounted.splice(0)) {
    item.app.unmount()
    item.host.remove()
  }
})

describe('ChapterEvaluationPanel', () => {
  it('显示章节工作流持久化的评审结果', () => {
    const host = document.createElement('div')
    document.body.append(host)
    const app = createApp({
      render: () => h(ChapterEvaluationPanel, {
        evaluation: JSON.stringify({
          best_choice: 2,
          reason_for_choice: '第二版结构更完整',
          evaluation: {
            version2: {
              pros: ['伏笔衔接自然'],
              cons: ['结尾略快'],
              overall_review: '综合表现最佳',
              scores: { coherence: 86 },
            },
          },
        }),
      }),
    })
    app.mount(host)
    mounted.push({ app, host })

    expect(host.textContent).toContain('最佳推荐：版本 2')
    expect(host.textContent).toContain('第二版结构更完整')
    expect(host.textContent).toContain('版本 2 评估')
    expect(host.textContent).toContain('综合表现最佳')
    expect(host.textContent).toContain('coherence')
    expect(host.textContent).toContain('86 分')
    expect(host.textContent).toContain('伏笔衔接自然')
    expect(host.textContent).toContain('结尾略快')
  })

  it('渲染并净化 Markdown 评阅反馈', () => {
    const host = document.createElement('div')
    document.body.append(host)
    const app = createApp({
      render: () => h(ChapterEvaluationPanel, {
        evaluation: JSON.stringify({ feedback: '**综合表现最佳**<img src="x" onerror="alert(1)">' }),
      }),
    })
    app.mount(host)
    mounted.push({ app, host })

    expect(host.querySelector('strong')?.textContent).toBe('综合表现最佳')
    expect(host.querySelector('img')?.hasAttribute('onerror')).toBe(false)
  })
})
