import { describe, expect, it } from 'vitest'
import { createApp, nextTick } from 'vue'

import ChapterGenerating from '@/components/writing-desk/workspace/ChapterGenerating.vue'
import type { ChapterGenerationTrace } from '@/api/novel'

const mountChapterGenerating = async (
  trace: ChapterGenerationTrace,
  props: Record<string, unknown> = {},
) => {
  const host = document.createElement('div')
  document.body.appendChild(host)
  const app = createApp(ChapterGenerating, {
    chapterNumber: 3,
    chapterTitle: '第三章',
    chapterSummary: '主角进入新冲突。',
    status: 'generating',
    generationStep: trace.node_key,
    generationStepIndex: 1,
    generationStepTotal: 7,
    generationTraces: [trace],
    generatingChapter: 3,
    ...props,
  })

  app.mount(host)
  await nextTick()

  return {
    host,
    unmount: () => {
      app.unmount()
      host.remove()
    },
  }
}

describe('ChapterGenerating timing inspector', () => {
  it('shows recorded system duration from the active generation trace', async () => {
    const rendered = await mountChapterGenerating({
      id: 1,
      node_key: 'context_prep',
      node_label: '整理前文',
      stage: 'context_prep',
      status: 'success',
      uses_llm: false,
      metadata: {
        duration_ms: 2500,
        actions: ['读取前文章节'],
      },
      started_at: '2026-01-01T12:00:00Z',
      ended_at: '2026-01-01T12:00:02.500Z',
      created_at: '2026-01-01T12:00:02.500Z',
    })

    try {
      expect(rendered.host.textContent).toContain('系统耗时：2.5 秒')
    } finally {
      rendered.unmount()
    }
  })

  it('shows the full failed trace error in the failure card after refresh', async () => {
    const fullError = '修复润色失败：模型返回 JSON 解析错误，真实错误需要完整保留给前端查看'
    const rendered = await mountChapterGenerating(
      {
        id: 2,
        node_key: 'review_refinement',
        node_label: '修复润色',
        stage: 'chapter_optimization',
        status: 'failed',
        uses_llm: true,
        error: fullError,
        metadata: {
          duration_ms: 1800,
          actions: ['调用模型输出最终正文'],
        },
        started_at: '2026-01-01T12:00:00Z',
        ended_at: '2026-01-01T12:00:01.800Z',
        created_at: '2026-01-01T12:00:01.800Z',
      },
      {
        status: 'failed',
        generationStep: 'failed|error=修复润色失败：模型返回 JSON 解析错误',
      },
    )

    try {
      const reason = rendered.host.querySelector('.chapter-console__failed-reason-inline')
      expect(reason?.textContent).toContain(fullError)
    } finally {
      rendered.unmount()
    }
  })
})
