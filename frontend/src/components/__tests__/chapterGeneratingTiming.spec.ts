import { describe, expect, it, vi } from 'vitest'
import { createApp, nextTick } from 'vue'

import ChapterGenerating from '@/components/writing-desk/workspace/ChapterGenerating.vue'
import type { ChapterGenerationTrace } from '@/api/novel'
import { globalAlert } from '@/composables/useAlert'
import { formatAiReviewOutputs } from '@/utils/generationTrace'

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
    generationStep: traces[0]?.node_key ?? 'freeze_base_context',
    generationStepIndex: 1,
    generationStepTotal: 7,
    generationTraces: traces,
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
  step?.querySelector<HTMLButtonElement>('.chapter-console__pipeline-select')?.click()
  await nextTick()
}

describe('ChapterGenerating timing inspector', () => {
  it('keeps the allowed cancel action in the progress header and disables it while pending', async () => {
    const onCancel = vi.fn()
    const rendered = await mountChapterGenerating(
      {
        id: 99,
        node_key: 'freeze_base_context',
        node_label: '冻结基础上下文',
        status: 'running',
        uses_llm: false,
        metadata: {},
      },
      { canCancel: true, pending: false, onCancel },
    )

    try {
      const cancelButton = rendered.host.querySelector<HTMLButtonElement>(
        '.chapter-console__pipeline-header-main [data-action="cancel"]',
      )
      expect(cancelButton).not.toBeNull()
      expect(cancelButton?.disabled).toBe(false)
      cancelButton?.click()
      expect(onCancel).toHaveBeenCalledTimes(1)
    } finally {
      rendered.unmount()
    }

    const pending = await mountChapterGenerating(
      {
        id: 100,
        node_key: 'freeze_base_context',
        node_label: '冻结基础上下文',
        status: 'running',
        uses_llm: false,
        metadata: {},
      },
      { canCancel: true, pending: true },
    )
    try {
      expect(pending.host.querySelector<HTMLButtonElement>('[data-action="cancel"]')?.disabled)
        .toBe(true)
    } finally {
      pending.unmount()
    }
  })

  it('marks the incoming connector and current node for running motion', async () => {
    const rendered = await mountChapterGenerating({
      id: 101,
      node_key: 'refine_candidate',
      node_label: '润色推荐版本',
      status: 'running',
      uses_llm: true,
      metadata: {},
    })

    try {
      const current = rendered.host.querySelector('.chapter-console__pipeline-item.is-in-progress')
      expect(current?.textContent).toContain('润色推荐版本')
      expect(current?.previousElementSibling?.classList.contains('is-leading-to-current')).toBe(true)
      expect(current?.classList.contains('is-leading-to-current')).toBe(false)
      expect(rendered.host.querySelector('.chapter-console__pipeline-card')
        ?.classList.contains('has-node-retry')).toBe(false)
    } finally {
      rendered.unmount()
    }
  })

  it('renders the projection fan-out without treating sibling branches as serial', async () => {
    const rendered = await mountChapterGenerating(
      [
        {
          id: 201,
          node_key: 'freeze_base_context',
          node_label: '冻结基础上下文',
          status: 'success',
          uses_llm: false,
          metadata: {},
        },
        {
          id: 202,
          node_key: 'project_memory',
          node_label: '更新记忆快照',
          status: 'success',
          uses_llm: false,
          metadata: {},
        },
        {
          id: 203,
          node_key: 'project_foreshadowing',
          node_label: '同步伏笔',
          status: 'success',
          uses_llm: false,
          metadata: {},
        },
      ],
      {
        status: 'finalizing',
        generationStep: 'wait_for_projections',
      },
    )

    try {
      const projectionGroup = rendered.host.querySelector('[data-group="projections"]')
      expect(projectionGroup?.getAttribute('data-mode')).toBe('parallel')
      expect(projectionGroup?.textContent).toContain('更新记忆快照')
      expect(projectionGroup?.textContent).toContain('写入章节索引')
      expect(projectionGroup?.textContent).toContain('同步伏笔')

      const ragStep = Array.from(
        projectionGroup?.querySelectorAll('.chapter-console__pipeline-item') || [],
      ).find((item) => item.textContent?.includes('写入章节索引'))
      expect(ragStep?.classList.contains('is-skipped')).toBe(true)
      expect(ragStep?.textContent).toContain('已跳过')

      const waitingStep = Array.from(
        rendered.host.querySelectorAll('.chapter-console__pipeline-item'),
      ).find((item) => item.textContent?.includes('等待投影完成'))
      expect(waitingStep?.classList.contains('is-control')).toBe(true)
      expect(waitingStep?.classList.contains('is-in-progress')).toBe(true)
    } finally {
      rendered.unmount()
    }
  })

  it('keeps the displayed recommendation aligned with the structured winner', () => {
    const output = formatAiReviewOutputs({
      id: 0,
      node_key: 'review_candidates',
      node_label: '评审候选版本',
      status: 'success',
      uses_llm: true,
      metadata: {
        output_payload: {
          best_version_index: 1,
          review_summaries: {
            ai_review: {
              mode: 'compare',
              evaluation: '版本1在四个维度上全面优于版本2。',
              final_recommendation: '建议采用版本1。',
              version_reviews: [
                { version_number: 1, overall_review: '版本1仍有明显短板。' },
                { version_number: 2, overall_review: '版本2综合最佳。' },
              ],
            },
          },
        },
      },
    })

    expect(output).toContain('推荐版本：版本 2')
    expect(output).toContain('评审结论：版本2综合最佳。')
    expect(output).toContain('最终建议：采用版本 2')
    expect(output).not.toContain('评审结论：版本1在四个维度上全面优于版本2。')
    expect(output).not.toContain('最终建议：建议采用版本1。')
  })

  it('shows recorded system duration from the active generation trace', async () => {
    const rendered = await mountChapterGenerating({
      id: 1,
      node_key: 'freeze_base_context',
      node_label: '冻结基础上下文',
      stage: 'freeze_base_context',
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
    const fullError = '润色推荐版本失败：模型返回 JSON 解析错误，真实错误需要完整保留给前端查看'
    const rendered = await mountChapterGenerating(
      {
        id: 2,
        node_key: 'refine_candidate',
        node_label: '润色推荐版本',
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
        generationStep: 'failed|error=润色推荐版本失败：模型返回 JSON 解析错误',
      },
    )

    try {
      const failedStep = rendered.host.querySelector('.chapter-console__pipeline-item.is-failed')
      expect(failedStep?.querySelector('.chapter-console__pipeline-select')?.getAttribute('aria-label'))
        .toContain(fullError)
    } finally {
      rendered.unmount()
    }
  })

  it('does not reuse an old successful AI review trace for an evaluation failed node', async () => {
    const rendered = await mountChapterGenerating(
      {
        id: 3,
        node_key: 'review_candidates',
        node_label: '评审候选版本',
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
      expect(failedStep?.textContent).toContain('评审候选版本')
      expect(failedStep?.textContent).toContain('失败')
      expect(failedStep?.querySelector('.chapter-console__pipeline-select')?.getAttribute('aria-label'))
        .toContain('评审候选版本失败')
      expect(rendered.host.textContent).toContain('状态：失败')
      expect(rendered.host.textContent).toContain('评审节点未返回更具体的失败原因')
      expect(rendered.host.textContent).not.toContain('状态：成功')
    } finally {
      rendered.unmount()
    }
  })

  it('keeps candidate selection outside the read-only trace replay', async () => {
    const rendered = await mountChapterGenerating(
      {
        id: 4,
        node_key: 'review_candidates',
        node_label: '评审候选版本',
        stage: 'version_review',
        status: 'failed',
        uses_llm: true,
        error: '评审候选版本失败：模型返回空结果',
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
      },
    )

    try {
      expect(rendered.host.textContent).toContain('只读回溯')
      expect(rendered.host.querySelector('[role="radiogroup"]')).toBeNull()
      expect(rendered.host.textContent).not.toContain('本轮候选版本仍可查看')
    } finally {
      rendered.unmount()
    }
  })

  it('keeps evaluation recovery commands out of the trace replay', async () => {
    const rendered = await mountChapterGenerating(
      {
        id: 5,
        node_key: 'review_candidates',
        node_label: '评审候选版本',
        stage: 'version_review',
        status: 'failed',
        uses_llm: true,
        error: '评审候选版本失败：模型返回空结果',
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
      },
    )

    try {
      expect(rendered.host.querySelector('.chapter-console__actions')).toBeNull()
      expect(rendered.host.querySelector('.chapter-console__pipeline-retry')).toBeNull()
      expect(rendered.host.textContent).not.toContain('重新 评审候选版本')
      expect(rendered.host.textContent).not.toContain('放弃本轮草稿并重新生成')
      expect(rendered.host.textContent).not.toContain('重新生成本章')
      expect(rendered.host.textContent).not.toContain('重试生成本章')
    } finally {
      rendered.unmount()
    }
  })

  it('keeps failed evaluation traces inspectable without legacy regeneration actions', async () => {
    const fullError = '评审候选版本失败：模型返回空结果'
    const rendered = await mountChapterGenerating(
      {
        id: 6,
        node_key: 'review_candidates',
        node_label: '评审候选版本',
        stage: 'version_review',
        status: 'failed',
        uses_llm: true,
        error: fullError,
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
      },
    )

    try {
      await clickPipelineStep(rendered.host, '评审候选版本')
      expect(rendered.host.textContent).toContain('状态：失败')
      expect(rendered.host.textContent).toContain(fullError)
      expect(rendered.host.textContent).not.toContain('放弃本轮草稿并重新生成')
    } finally {
      rendered.unmount()
    }
  })

  it('retries the selected failed external node only when the snapshot allows it', async () => {
    const onRetryExternal = vi.fn()
    let resolveConfirmation: ((confirmed: boolean) => void) | undefined
    const confirmation = new Promise<boolean>((resolve) => {
      resolveConfirmation = resolve
    })
    const confirmSpy = vi.spyOn(globalAlert, 'showConfirm').mockReturnValue(confirmation)
    const traces: ChapterGenerationTrace[] = [
      {
        id: 60,
        node_key: 'generate_candidate_1',
        node_label: '候选版本 1',
        stage: 'chapter_writing',
        status: 'failed',
        uses_llm: true,
        error: '历史正文生成失败',
        metadata: {},
      },
      {
        id: 61,
        node_key: 'review_candidates',
        node_label: '评审候选版本',
        stage: 'version_review',
        status: 'failed',
        uses_llm: true,
        error: '评审候选版本失败：外部模型返回结果不确定',
        metadata: {
          duration_ms: 1600,
          actions: ['调用评审模型'],
        },
      },
    ]
    const rendered = await mountChapterGenerating(traces, {
      status: 'failed',
      generationStep: 'review_candidates',
      allowedCommands: ['retry_external'],
      retryActivityKey: 'wf:review_candidates:stable-key',
      onRetryExternal,
    })

    try {
      expect(rendered.host.querySelector('[data-action="retry-external-node"]')).toBeNull()
      await clickPipelineStep(rendered.host, '评审候选版本')
      const retryButton = rendered.host.querySelector<HTMLButtonElement>(
        '[data-action="retry-external-node"]',
      )
      expect(retryButton?.textContent).toContain('重试')
      expect(retryButton?.getAttribute('aria-label')).toBe('使用上一节点结果重试评审候选版本')
      expect(retryButton?.disabled).toBe(false)
      expect(retryButton?.closest('.chapter-console__pipeline-item')?.textContent)
        .toContain('评审候选版本')
      expect(retryButton?.closest('.chapter-console__pipeline-card')
        ?.classList.contains('has-node-retry')).toBe(true)

      retryButton?.closest('.chapter-console__pipeline-node-retry-trigger')
        ?.dispatchEvent(new MouseEvent('mouseenter'))
      await new Promise((resolve) => setTimeout(resolve, 260))
      await nextTick()
      expect(document.body.querySelector('[role="tooltip"]')?.textContent)
        .toContain('使用上一节点的结果重新执行当前节点')

      retryButton?.click()
      retryButton?.click()
      await nextTick()
      expect(confirmSpy).toHaveBeenCalledTimes(1)
      expect(retryButton?.disabled).toBe(true)
      resolveConfirmation?.(true)
      await vi.waitFor(() => expect(onRetryExternal)
        .toHaveBeenCalledWith('wf:review_candidates:stable-key'))

      await clickPipelineStep(rendered.host, '候选版本 1')
      await vi.waitFor(() => {
        expect(rendered.host.querySelector('[data-action="retry-external-node"]')).toBeNull()
      })
    } finally {
      confirmSpy.mockRestore()
      rendered.unmount()
    }

    for (const props of [
      { allowedCommands: [], retryActivityKey: 'wf:review_candidates:stable-key' },
      { allowedCommands: ['retry_external'], retryActivityKey: null },
    ]) {
      const unavailable = await mountChapterGenerating(traces[1], {
        status: 'failed',
        generationStep: 'review_candidates',
        ...props,
      })
      try {
        await clickPipelineStep(unavailable.host, '评审候选版本')
        expect(unavailable.host.querySelector('[data-action="retry-external-node"]')).toBeNull()
      } finally {
        unavailable.unmount()
      }
    }

    const pending = await mountChapterGenerating(traces[1], {
      status: 'failed',
      generationStep: 'review_candidates',
      allowedCommands: ['retry_external'],
      retryActivityKey: 'wf:review_candidates:stable-key',
      pending: true,
    })
    try {
      await clickPipelineStep(pending.host, '评审候选版本')
      expect(pending.host.querySelector<HTMLButtonElement>(
        '[data-action="retry-external-node"]',
      )?.disabled).toBe(true)
    } finally {
      pending.unmount()
    }
  })

  it('shows stage-specific business outputs for draft, review, refinement and manual confirmation', async () => {
    const rendered = await mountChapterGenerating(
      [
        {
          id: 7,
          node_key: 'generate_candidate_1',
          node_label: '候选版本 1',
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
          node_key: 'review_candidates',
          node_label: '评审候选版本',
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
          node_key: 'refine_candidate',
          node_label: '润色推荐版本',
          stage: 'chapter_optimization',
          status: 'success',
          uses_llm: true,
          cleaned_output: 'AI修复后的最终正文',
          metadata: {
            duration_ms: 1500,
            actions: ['按评审建议润色推荐版本'],
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
          node_key: 'persist_drafts',
          node_label: '保存候选草稿',
          stage: 'persist_drafts',
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
        '冻结基础上下文',
        '检索章节上下文',
        '规划章节任务',
        '候选版本 1',
        '候选版本 2',
        '评审候选版本',
        '润色推荐版本',
        '增强正文',
        '修复一致性',
        '优化文风',
        '扩写正文',
        '压缩超长正文',
        '保存候选草稿',
        '等待选择版本',
        '定稿章节版本',
        '生成章节梳理',
        '更新记忆快照',
        '写入章节索引',
        '同步伏笔',
        '等待投影完成',
        '汇合投影结果',
        '章节工作流完成',
      ])
      expect(pipelineTitles).not.toContain('待人工确认')

      const candidateGroup = rendered.host.querySelector('[data-group="candidates"]')
      expect(candidateGroup?.getAttribute('data-mode')).toBe('parallel')
      expect(candidateGroup?.textContent).toContain('并行')

      const selectionStep = Array.from(
        rendered.host.querySelectorAll('.chapter-console__pipeline-item'),
      ).find((item) => item.textContent?.includes('等待选择版本'))
      expect(selectionStep?.textContent).toContain('待人工确认')

      await clickPipelineStep(rendered.host, '候选版本 1')
      expect(rendered.host.textContent).toContain('AI生成正文：')
      expect(rendered.host.textContent).toContain('AI生成初稿正文')

      await clickPipelineStep(rendered.host, '评审候选版本')
      expect(rendered.host.textContent).toContain('评审结论：')
      expect(rendered.host.textContent).toContain('整体流畅，人物动机明确。')
      expect(rendered.host.textContent).toContain('修改建议：加强结尾钩子。')

      await clickPipelineStep(rendered.host, '润色推荐版本')
      expect(rendered.host.textContent).toContain('AI修复后正文：')
      expect(rendered.host.textContent).toContain('AI修复后的最终正文')
      expect(rendered.host.textContent).toContain('修复说明：已补强结尾钩子')
    } finally {
      rendered.unmount()
    }
  })
})
