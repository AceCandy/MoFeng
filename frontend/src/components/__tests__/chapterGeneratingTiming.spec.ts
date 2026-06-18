import { describe, expect, it, vi } from 'vitest'
import { createApp, nextTick } from 'vue'

import ChapterGenerating from '@/components/writing-desk/workspace/ChapterGenerating.vue'
import type { ChapterGenerationTrace } from '@/api/novel'
import { globalAlert } from '@/composables/useAlert'

const flushPromises = async () => {
  await Promise.resolve()
  await Promise.resolve()
}

const mountChapterGenerating = async (
  trace: ChapterGenerationTrace | ChapterGenerationTrace[],
  props: Record<string, unknown> = {},
) => {
  const host = document.createElement('div')
  document.body.appendChild(host)
  const traces = Array.isArray(trace) ? trace : [trace]
  const app = createApp(ChapterGenerating, {
    chapterNumber: 3,
    chapterTitle: '第三章',
    chapterSummary: '主角进入新冲突。',
    status: 'generating',
    generationStep: traces[0]?.node_key ?? 'context_prep',
    generationStepIndex: 1,
    generationStepTotal: 7,
    generationTraces: traces,
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

const clickPipelineStep = async (host: HTMLElement, label: string) => {
  const step = Array.from(host.querySelectorAll('.chapter-console__pipeline-item')).find((item) =>
    item.textContent?.includes(label),
  )
  expect(step).toBeTruthy()
  step?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
  await nextTick()
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
      const failedStep = rendered.host.querySelector('.chapter-console__pipeline-item.is-failed')
      expect(failedStep?.getAttribute('aria-label')).toContain(fullError)
    } finally {
      rendered.unmount()
    }
  })

  it('does not reuse an old successful AI review trace for an evaluation failed node', async () => {
    const rendered = await mountChapterGenerating(
      {
        id: 3,
        node_key: 'quality_review',
        node_label: 'AI评审',
        stage: 'version_review',
        status: 'success',
        uses_llm: true,
        metadata: {
          duration_ms: 2100,
          actions: ['完成历史评审'],
        },
        started_at: '2026-01-01T12:00:00Z',
        ended_at: '2026-01-01T12:00:02.100Z',
        created_at: '2026-01-01T12:00:02.100Z',
      },
      {
        status: 'evaluation_failed',
        generationStep: 'evaluation_failed',
      },
    )

    try {
      const failedStep = rendered.host.querySelector('.chapter-console__pipeline-item.is-failed')
      expect(failedStep?.textContent).toContain('AI评审')
      expect(failedStep?.textContent).toContain('失败')
      expect(failedStep?.getAttribute('aria-label')).toContain('AI评审失败')
      expect(rendered.host.textContent).toContain('状态：失败')
      expect(rendered.host.textContent).toContain('评审节点未返回更具体的失败原因')
      expect(rendered.host.textContent).not.toContain('状态：成功')
    } finally {
      rendered.unmount()
    }
  })

  it('shows retained candidate versions inside the failure card', async () => {
    const rendered = await mountChapterGenerating(
      {
        id: 4,
        node_key: 'quality_review',
        node_label: 'AI评审',
        stage: 'version_review',
        status: 'failed',
        uses_llm: true,
        error: 'AI评审失败：模型返回空结果',
        metadata: {
          duration_ms: 1600,
          actions: ['调用评审模型'],
        },
        started_at: '2026-01-01T12:00:00Z',
        ended_at: '2026-01-01T12:00:01.600Z',
        created_at: '2026-01-01T12:00:01.600Z',
      },
      {
        status: 'evaluation_failed',
        generationStep: 'evaluation_failed',
        availableVersions: [
          { content: '第一版正文，保留了主角和旧线索。', style: '标准' },
          { content: '第二版正文，补强了冲突和结尾悬念。', style: '紧凑' },
        ],
      },
    )

    try {
      expect(rendered.host.textContent).toContain('本轮候选版本仍可查看')
      expect(rendered.host.textContent).toContain('版本 1')
      expect(rendered.host.textContent).toContain('第一版正文')
      expect(rendered.host.textContent).toContain('版本 2')
      expect(rendered.host.textContent).toContain('第二版正文')
    } finally {
      rendered.unmount()
    }
  })

  it('uses AI review retry as the primary action for evaluation failures', async () => {
    const events: string[] = []
    const rendered = await mountChapterGenerating(
      {
        id: 5,
        node_key: 'quality_review',
        node_label: 'AI评审',
        stage: 'version_review',
        status: 'failed',
        uses_llm: true,
        error: 'AI评审失败：模型返回空结果',
        metadata: {
          duration_ms: 1600,
          actions: ['调用评审模型'],
        },
        started_at: '2026-01-01T12:00:00Z',
        ended_at: '2026-01-01T12:00:01.600Z',
        created_at: '2026-01-01T12:00:01.600Z',
      },
      {
        status: 'evaluation_failed',
        generationStep: 'evaluation_failed',
        generatingChapter: null,
        onEvaluateChapter: () => events.push('evaluate'),
        onGenerateChapter: () => events.push('generate'),
      },
    )

    try {
      const buttons = Array.from(rendered.host.querySelectorAll('button'))
      const reviewButton = buttons.find((button) => button.textContent?.includes('重新 AI评审'))
      const regenerateButton = buttons.find((button) =>
        button.textContent?.includes('放弃本轮草稿并重新生成'),
      )

      expect(reviewButton).toBeTruthy()
      expect(regenerateButton).toBeTruthy()
      expect(rendered.host.textContent).not.toContain('重新生成本章')
      expect(rendered.host.textContent).not.toContain('重试生成本章')

      reviewButton?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
      expect(events).toEqual(['evaluate'])
    } finally {
      rendered.unmount()
    }
  })

  it('confirms before abandoning retained drafts to regenerate the chapter', async () => {
    const events: string[] = []
    const confirmSpy = vi.spyOn(globalAlert, 'showConfirm').mockResolvedValue(false)
    const rendered = await mountChapterGenerating(
      {
        id: 6,
        node_key: 'quality_review',
        node_label: 'AI评审',
        stage: 'version_review',
        status: 'failed',
        uses_llm: true,
        error: 'AI评审失败：模型返回空结果',
        metadata: {
          duration_ms: 1600,
          actions: ['调用评审模型'],
        },
        started_at: '2026-01-01T12:00:00Z',
        ended_at: '2026-01-01T12:00:01.600Z',
        created_at: '2026-01-01T12:00:01.600Z',
      },
      {
        status: 'evaluation_failed',
        generationStep: 'evaluation_failed',
        generatingChapter: null,
        onGenerateChapter: () => events.push('generate'),
      },
    )

    try {
      const button = Array.from(rendered.host.querySelectorAll('button')).find((item) =>
        item.textContent?.includes('放弃本轮草稿并重新生成'),
      )

      expect(button).toBeTruthy()

      button?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
      await flushPromises()

      expect(confirmSpy).toHaveBeenCalledWith(
        '重新生成会放弃本轮已生成的候选正文，并用新生成结果替换它们。确认要重新生成本章吗？',
        '放弃本轮草稿',
      )
      expect(events).toEqual([])

      confirmSpy.mockResolvedValue(true)
      button?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
      await flushPromises()

      expect(events).toEqual(['generate'])
    } finally {
      confirmSpy.mockRestore()
      rendered.unmount()
    }
  })

  it('shows stage-specific business outputs for draft, review, refinement and manual confirmation', async () => {
    const rendered = await mountChapterGenerating(
      [
        {
          id: 7,
          node_key: 'draft_generation',
          node_label: '生成正文',
          stage: 'chapter_writing',
          status: 'success',
          uses_llm: true,
          raw_response: '{"content":"AI生成初稿正文"}',
          cleaned_output: 'AI生成初稿正文',
          metadata: {
            duration_ms: 1200,
            actions: ['调用正文生成模型'],
          },
          started_at: '2026-01-01T12:00:00Z',
          ended_at: '2026-01-01T12:00:01.200Z',
          created_at: '2026-01-01T12:00:01.200Z',
        },
        {
          id: 8,
          node_key: 'quality_review',
          node_label: 'AI评审',
          stage: 'version_review',
          status: 'success',
          uses_llm: true,
          metadata: {
            duration_ms: 900,
            actions: ['调用评审模型'],
            output_payload: {
              best_version_index: 0,
              review_summaries: {
                ai_review: {
                  mode: 'single',
                  evaluation: '整体流畅，人物动机明确。',
                  suggestions: '加强结尾钩子。',
                  final_recommendation: '采用唯一版本',
                },
              },
            },
          },
          started_at: '2026-01-01T12:00:01Z',
          ended_at: '2026-01-01T12:00:01.900Z',
          created_at: '2026-01-01T12:00:01.900Z',
        },
        {
          id: 9,
          node_key: 'review_refinement',
          node_label: '修复润色',
          stage: 'chapter_optimization',
          status: 'success',
          uses_llm: true,
          cleaned_output: 'AI修复后的最终正文',
          metadata: {
            duration_ms: 1500,
            actions: ['按评审建议修复润色'],
            output_payload: {
              optimization_notes: '已补强结尾钩子',
              refined_chars: 9,
            },
          },
          started_at: '2026-01-01T12:00:02Z',
          ended_at: '2026-01-01T12:00:03.500Z',
          created_at: '2026-01-01T12:00:03.500Z',
        },
        {
          id: 10,
          node_key: 'save_draft',
          node_label: '保存草稿',
          stage: 'save_draft',
          status: 'success',
          uses_llm: false,
          metadata: {
            duration_ms: 500,
            actions: ['写入候选版本并进入待确认状态'],
            output_payload: {
              status: 'waiting_for_confirm',
            },
          },
          started_at: '2026-01-01T12:00:04Z',
          ended_at: '2026-01-01T12:00:04.500Z',
          created_at: '2026-01-01T12:00:04.500Z',
        },
      ],
      {
        status: 'waiting_for_confirm',
        generationStep: 'waiting_for_confirm',
        readOnly: true,
      },
    )

    try {
      expect(rendered.host.textContent).toContain('待人工确认')
      const pipelineTitles = Array.from(
        rendered.host.querySelectorAll('.chapter-console__pipeline-title'),
      ).map((item) => item.textContent?.trim())
      expect(pipelineTitles).toEqual([
        '整理前文',
        '规划剧情',
        '调用设定',
        '生成正文',
        'AI评审',
        '修复润色',
      ])
      expect(pipelineTitles).not.toContain('待人工确认')

      const refinementStep = Array.from(
        rendered.host.querySelectorAll('.chapter-console__pipeline-item'),
      ).find((item) => item.textContent?.includes('修复润色'))
      expect(refinementStep?.textContent).toContain('待人工确认')

      await clickPipelineStep(rendered.host, '生成正文')
      expect(rendered.host.textContent).toContain('AI生成正文：')
      expect(rendered.host.textContent).toContain('AI生成初稿正文')

      await clickPipelineStep(rendered.host, 'AI评审')
      expect(rendered.host.textContent).toContain('评审结论：')
      expect(rendered.host.textContent).toContain('整体流畅，人物动机明确。')
      expect(rendered.host.textContent).toContain('修改建议：加强结尾钩子。')

      await clickPipelineStep(rendered.host, '修复润色')
      expect(rendered.host.textContent).toContain('AI修复后正文：')
      expect(rendered.host.textContent).toContain('AI修复后的最终正文')
      expect(rendered.host.textContent).toContain('修复说明：已补强结尾钩子')
    } finally {
      rendered.unmount()
    }
  })
})
