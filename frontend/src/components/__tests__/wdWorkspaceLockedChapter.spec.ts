import { describe, expect, it } from 'vitest'
import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'
import { createApp, nextTick } from 'vue'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import WDWorkspace from '@/components/writing-desk/WDWorkspace.vue'
import type { ChapterVersionSelection, NovelProject } from '@/api/novel'
import type { ChapterWorkflowCommand, ChapterWorkflowNodeKey } from '@/api/chapterWorkflow'
import type { ChapterWorkflowActorPhase } from '@/composables/useChapterWorkflowActor'

const readSource = (relativePath: string) =>
  readFileSync(resolve(process.cwd(), relativePath), 'utf8')

const mountWorkspace = async (
  project: NovelProject,
  selectedChapterNumber: number,
  overrides: {
    selectedVersionIndex?: number
    availableVersions?: Array<{ content: string; style?: string; metadata?: Record<string, unknown> }>
    workflowPhase?: ChapterWorkflowActorPhase
    workflowRunId?: string | null
    workflowNodeKey?: ChapterWorkflowNodeKey | null
    workflowProgress?: number | null
    workflowAllowedCommands?: ChapterWorkflowCommand[]
    workflowCandidates?: ChapterVersionSelection[]
    workflowPending?: boolean
    workflowError?: string | null
  } = {},
) => {
  const host = document.createElement('div')
  document.body.appendChild(host)
  const selectedChapters: number[] = []
  const selectedWorkflowVersions: number[] = []
  const shownVersionDetails: number[] = []
  let workflowRetryCount = 0
  let evaluationDetailCount = 0
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  const app = createApp(WDWorkspace, {
    project,
    selectedChapter:
      project.chapters.find((chapter) => chapter.chapter_number === selectedChapterNumber) ?? null,
    selectedChapterNumber,
    selectedVersionIndex: overrides.selectedVersionIndex ?? 0,
    availableVersions: overrides.availableVersions ?? [],
    workflowPhase: overrides.workflowPhase ?? 'idle',
    workflowRunId: overrides.workflowRunId ?? null,
    workflowNodeKey: overrides.workflowNodeKey ?? null,
    workflowProgress: overrides.workflowProgress ?? null,
    workflowTransport: 'disconnected',
    workflowAllowedCommands: overrides.workflowAllowedCommands ?? [],
    workflowPending: overrides.workflowPending ?? false,
    workflowError: overrides.workflowError ?? null,
    workflowRetryActivityKey: null,
    workflowCandidates: overrides.workflowCandidates ?? [],
    onSelectChapter: (chapterNumber: number) => selectedChapters.push(chapterNumber),
    onWorkflowSelectVersion: (versionId: number) => selectedWorkflowVersions.push(versionId),
    onShowVersionDetail: (versionIndex: number) => shownVersionDetails.push(versionIndex),
    onShowEvaluationDetail: () => {
      evaluationDetailCount += 1
    },
    onWorkflowRetry: () => {
      workflowRetryCount += 1
    },
  })

  app.use(VueQueryPlugin, { queryClient })
  app.mount(host)
  await nextTick()

  return {
    host,
    selectedChapters,
    selectedWorkflowVersions,
    shownVersionDetails,
    getWorkflowRetryCount: () => workflowRetryCount,
    getEvaluationDetailCount: () => evaluationDetailCount,
    unmount: () => {
      app.unmount()
      host.remove()
    },
  }
}

describe('WDWorkspace locked chapter state', () => {
  it('hides the duplicate running banner and isolates live draft preview to the current run', async () => {
    const project: NovelProject = {
      id: 'novel-running-preview',
      title: '全网退役',
      initial_prompt: '',
      conversation_history: [],
      blueprint: {
        chapter_outline: [
          { chapter_number: 1, title: '一招', summary: '林拓重新站上擂台。' },
        ],
      },
      chapters: [
        {
          chapter_number: 1,
          title: '一招',
          summary: '林拓重新站上擂台。',
          real_summary: null,
          content: null,
          versions: ['上一轮遗留草稿'],
          evaluation: null,
          generation_status: 'generating',
        },
      ],
    }

    const withoutCandidate = await mountWorkspace(project, 1, {
      availableVersions: [{ content: '上一轮遗留草稿' }],
      workflowPhase: 'running',
      workflowRunId: 'current-run',
      workflowNodeKey: 'freeze_context',
      workflowAllowedCommands: ['cancel'],
    })
    try {
      expect(withoutCandidate.host.querySelector('.chapter-workflow')).toBeNull()
      expect(withoutCandidate.host.textContent).not.toContain('章节生成中')
      expect(withoutCandidate.host.querySelector('[data-action="cancel"]')).not.toBeNull()
      expect(withoutCandidate.host.querySelector('.chapter-console__preview-card')).toBeNull()
    } finally {
      withoutCandidate.unmount()
    }

    const withCandidate = await mountWorkspace(project, 1, {
      availableVersions: [{ content: '上一轮遗留草稿' }],
      workflowPhase: 'running',
      workflowRunId: 'current-run',
      workflowNodeKey: 'generate_candidates',
      workflowCandidates: [
        {
          id: 601,
          content: '当前轮次刚生成的新草稿',
          version_label: '版本一',
          workflow_run_id: 'current-run',
        },
      ],
    })
    try {
      const preview = withCandidate.host.querySelector('.chapter-console__preview-card')
      expect(preview?.textContent).toContain('当前轮次刚生成的新草稿')
      expect(preview?.textContent).not.toContain('上一轮遗留草稿')
    } finally {
      withCandidate.unmount()
    }
  })

  it('hides chapter tools and sends the writer to the first unfinished prerequisite chapter', async () => {
    const project: NovelProject = {
      id: 'novel-1',
      title: '全网退役',
      initial_prompt: '',
      conversation_history: [],
      blueprint: {
        chapter_outline: [
          {
            chapter_number: 1,
            title: '前置契约',
            summary: '陆青衣递来渡口合约。',
          },
          {
            chapter_number: 2,
            title: '全网退役',
            summary: '林拓从拳馆离开，故事尚未推进到这里。',
          },
        ],
      },
      chapters: [
        {
          chapter_number: 1,
          title: '前置契约',
          summary: '陆青衣递来渡口合约。',
          real_summary: null,
          content: null,
          versions: null,
          evaluation: null,
          generation_status: 'not_generated',
        },
      ],
    }

    const rendered = await mountWorkspace(project, 2)

    try {
      expect(rendered.host.textContent).toContain('故事还未抵达这一章')
      expect(rendered.host.textContent).toContain('请先完成前面的待写章节，完成后本章将自动解锁。')
      expect(rendered.host.textContent).toContain('前往第1章：前置契约')
      expect(rendered.host.querySelector('[role="toolbar"][aria-label="章节操作"]')).toBeNull()
      expect(rendered.host.textContent).not.toContain('编辑正文')
      expect(rendered.host.textContent).not.toContain('AI优化')

      const gotoButton = Array.from(rendered.host.querySelectorAll('button')).find((button) =>
        button.textContent?.includes('前往第1章：前置契约'),
      )
      expect(gotoButton).toBeTruthy()

      gotoButton?.dispatchEvent(new MouseEvent('click', { bubbles: true }))

      expect(rendered.selectedChapters).toEqual([1])
    } finally {
      rendered.unmount()
    }
  })

  it('routes failed recovery through the allowed workflow retry command', async () => {
    const project: NovelProject = {
      id: 'novel-1',
      title: '全网退役',
      initial_prompt: '',
      conversation_history: [],
      blueprint: {
        chapter_outline: [
          {
            chapter_number: 1,
            title: '一招',
            summary: '林拓重新站上擂台。',
          },
        ],
      },
      chapters: [
        {
          chapter_number: 1,
          title: '一招',
          summary: '林拓重新站上擂台。',
          real_summary: null,
          content: null,
          versions: null,
          evaluation: null,
          generation_status: 'failed',
          generation_step: '字数仅 1365，低于最低要求 2200（容错阈值 1870）。请重试。',
        },
      ],
    }

    const rendered = await mountWorkspace(project, 1, {
      workflowPhase: 'failed',
      workflowAllowedCommands: ['retry'],
      workflowError: '候选生成未完成',
    })

    try {
      expect(rendered.host.textContent).toContain('本轮需要处理')
      expect(rendered.host.textContent).toContain('候选生成未完成')
      const retryButton = rendered.host.querySelector<HTMLButtonElement>('[data-action="retry"]')
      expect(retryButton).not.toBeNull()
      retryButton?.click()
      expect(rendered.getWorkflowRetryCount()).toBe(1)
    } finally {
      rendered.unmount()
    }
  })

  it('renders waiting confirmation draft content when the chapter body only exists in versions', async () => {
    const project: NovelProject = {
      id: 'novel-1',
      title: '全网退役',
      initial_prompt: '',
      conversation_history: [],
      blueprint: {
        chapter_outline: [
          {
            chapter_number: 1,
            title: '一招',
            summary: '林拓在直播擂台上重新出手。',
          },
        ],
      },
      chapters: [
        {
          chapter_number: 1,
          title: '一招',
          summary: '林拓在直播擂台上重新出手。',
          real_summary: null,
          content: null,
          versions: null,
          evaluation: null,
          generation_status: 'waiting_for_confirm',
          status_updated_at: '2026-06-09T14:42:00',
          generation_step: 'waiting_for_confirm',
          generation_traces: [
            {
              id: 101,
              node_key: 'context_prep',
              node_label: '整理前文',
              status: 'success',
              uses_llm: false,
              metadata: {
                duration_ms: 1300,
                input_payload: { chapter_number: 1 },
                actions: ['读取前文章节与项目记忆'],
                output_payload: { summary: '前文上下文整理完成' },
              },
            },
            {
              id: 102,
              node_key: 'save_draft',
              node_label: '保存草稿',
              status: 'success',
              uses_llm: false,
              metadata: {
                duration_ms: 900,
                actions: ['写入候选版本并保留待确认状态'],
                output_payload: { status: 'waiting_for_confirm' },
              },
            },
          ],
        },
      ],
    }

    const rendered = await mountWorkspace(project, 1, {
      workflowPhase: 'waitingForSelection',
      workflowAllowedCommands: ['select', 'cancel'],
      workflowCandidates: [
        {
          id: 301,
          content: '退役冠军林拓站在商业直播表演赛的灯下。\n\n他看见对手穿着旧布鞋，却仍旧把拳架抬得很稳。',
          version_label: '版本一',
          workflow_run_id: 'run-1',
        },
      ],
      availableVersions: [
        {
          content: '退役冠军林拓站在商业直播表演赛的灯下。\n\n他看见对手穿着旧布鞋，却仍旧把拳架抬得很稳。',
          style: '标准',
        },
      ],
    })

    try {
      expect(rendered.host.textContent).toContain('待选版本')
      expect(rendered.host.textContent).toContain('请选择候选版本')
      expect(rendered.host.textContent).not.toContain('确认定稿')
      expect(rendered.host.textContent).toContain('退役冠军林拓站在商业直播表演赛的灯下')
      expect(rendered.host.querySelector('.chapter-paper')).not.toBeNull()
      expect(rendered.host.querySelectorAll('[data-provenance="ai"]')).toHaveLength(1)
      expect(rendered.host.querySelector('[data-provenance="ink"]')).toBeNull()
      expect(rendered.host.querySelector('.chapter-jiege-divider')).toBeNull()
      expect(rendered.host.textContent).toContain('生成进度')
      expect(rendered.host.textContent).toContain('整理前文')
      expect(rendered.host.textContent).toContain('待人工确认')
      expect(rendered.host.textContent).not.toContain('转入后台生成')
      expect(rendered.host.textContent).not.toContain('取消生成')
      const cancelButtons = rendered.host.querySelectorAll('[data-action="cancel"]')
      expect(cancelButtons).toHaveLength(1)
      expect(cancelButtons[0]?.closest('.chapter-console__pipeline-header-main')).not.toBeNull()
      const pipelineTitles = Array.from(
        rendered.host.querySelectorAll('.chapter-console__pipeline-title'),
      ).map((item) => item.textContent?.trim())
      expect(pipelineTitles[pipelineTitles.length - 1]).toBe('修复润色')
      expect(pipelineTitles).not.toContain('待人工确认')

      const contextStep = Array.from(
        rendered.host.querySelectorAll('.chapter-console__pipeline-item'),
      ).find((item) => item.textContent?.includes('整理前文'))
      expect(contextStep).toBeTruthy()

      contextStep?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
      await nextTick()

      expect(rendered.host.textContent).toContain('节点详情')
      expect(rendered.host.textContent).toContain('读取前文章节与项目记忆')
      expect(rendered.host.textContent).toContain('前文上下文整理完成')
    } finally {
      rendered.unmount()
    }
  })

  it('shows the current workflow node instead of traces left by the previous run', async () => {
    const project: NovelProject = {
      id: 'novel-1',
      title: '全网退役',
      initial_prompt: '',
      conversation_history: [],
      blueprint: {
        chapter_outline: [
          { chapter_number: 1, title: '一招', summary: '林拓重新站上擂台。' },
        ],
      },
      chapters: [
        {
          chapter_number: 1,
          title: '一招',
          summary: '林拓重新站上擂台。',
          real_summary: null,
          content: null,
          versions: null,
          evaluation: null,
          generation_status: 'waiting_for_confirm',
          generation_step: 'waiting_for_confirm',
          generation_traces: [
            {
              id: 202,
              node_key: 'waiting_for_selection',
              node_label: '等待选择版本',
              status: 'success',
              uses_llm: false,
              metadata: { run_id: 'previous-run' },
            },
            {
              id: 203,
              node_key: 'context_prep',
              node_label: '整理前文',
              status: 'success',
              uses_llm: false,
              metadata: {
                output_payload: { summary: '这是无法确认归属的上一轮轨迹' },
              },
            },
            {
              id: 204,
              node_key: 'freeze_context',
              node_label: '冻结章节上下文',
              status: 'running',
              uses_llm: false,
              metadata: {
                run_id: 'current-run',
                input_payload: { chapter_number: 1 },
                actions: ['开始执行冻结章节上下文'],
                output_payload: { status: '正在检索章节上下文' },
              },
            },
          ],
        },
      ],
    }

    for (const workflow of [
      {
        workflowPhase: 'submitting',
        workflowRunId: null,
        workflowNodeKey: null,
        workflowProgress: null,
      },
      {
        workflowPhase: 'running',
        workflowRunId: 'current-run',
        workflowNodeKey: 'freeze_context',
        workflowProgress: 0,
      },
    ] as const) {
      const rendered = await mountWorkspace(project, 1, workflow)

      try {
        const contextStep = Array.from(
          rendered.host.querySelectorAll('.chapter-console__pipeline-item'),
        ).find((item) => item.textContent?.includes('整理前文'))

        expect(contextStep?.classList.contains('is-in-progress')).toBe(true)
        expect(rendered.host.textContent).not.toContain('待人工确认')
        expect(rendered.host.textContent).not.toContain('这是无法确认归属的上一轮轨迹')
        if (workflow.workflowRunId === null) {
          expect(rendered.host.textContent).toContain('暂未收到 整理前文 的真实运行记录')
        } else {
          expect(rendered.host.textContent).toContain('开始执行冻结章节上下文')
          expect(rendered.host.textContent).toContain('正在检索章节上下文')
          expect(rendered.host.textContent).not.toContain('暂未收到 整理前文 的真实运行记录')
        }
      } finally {
        rendered.unmount()
      }
    }
  })

  it('submits the selected durable candidate id instead of an array index', async () => {
    const project: NovelProject = {
      id: 'novel-1',
      title: '全网退役',
      initial_prompt: '',
      conversation_history: [],
      blueprint: {
        chapter_outline: [
          {
            chapter_number: 1,
            title: '一招',
            summary: '林拓在直播擂台上重新出手。',
          },
        ],
      },
      chapters: [
        {
          chapter_number: 1,
          title: '一招',
          summary: '林拓在直播擂台上重新出手。',
          real_summary: null,
          content: null,
          versions: null,
          evaluation: null,
          generation_status: 'waiting_for_confirm',
          generation_step: 'waiting_for_confirm',
          generation_traces: [
            {
              id: 201,
              node_key: 'save_draft',
              node_label: '保存草稿',
              status: 'success',
              uses_llm: false,
              metadata: {
                input_payload: { recommended_version_index: 1 },
                metrics: { recommended_version_index: 1 },
              },
            },
          ],
        },
      ],
    }

    const rendered = await mountWorkspace(project, 1, {
      workflowPhase: 'waitingForSelection',
      workflowAllowedCommands: ['select'],
      workflowCandidates: [
        {
          id: 401,
          content: '版本一只是铺垫，冲突还没有真正立起来。',
          version_label: '版本一',
          workflow_run_id: 'run-2',
        },
        {
          id: 909,
          content: '版本二让林拓在灯下直接迎上对手，是 AI 评审推荐的底稿。',
          version_label: '版本二',
          workflow_run_id: 'run-2',
        },
      ],
    })

    try {
      const candidates = rendered.host.querySelectorAll<HTMLButtonElement>('[role="radio"]')
      candidates[1]?.click()
      rendered.host.querySelector<HTMLButtonElement>('[data-action="select"]')?.click()
      expect(rendered.selectedWorkflowVersions).toEqual([909])
    } finally {
      rendered.unmount()
    }
  })

  it('keeps version and evaluation detail entry points reachable after cutover', async () => {
    const evaluation = JSON.stringify({
      best_choice: 1,
      reason_for_choice: '人物动机更完整。',
      evaluation: {
        version1: { overall_review: '可采用', pros: ['节奏清晰'], cons: [] },
      },
    })
    const project: NovelProject = {
      id: 'novel-1',
      title: '全网退役',
      initial_prompt: '',
      conversation_history: [],
      blueprint: {
        chapter_outline: [
          { chapter_number: 1, title: '一招', summary: '林拓重新站上擂台。' },
        ],
      },
      chapters: [
        {
          chapter_number: 1,
          title: '一招',
          summary: '林拓重新站上擂台。',
          real_summary: null,
          content: '林拓抬起拳架。',
          versions: ['林拓抬起拳架。'],
          evaluation,
          generation_status: 'successful',
        },
      ],
    }
    const rendered = await mountWorkspace(project, 1, {
      workflowPhase: 'succeeded',
      availableVersions: [{ content: '林拓抬起拳架。', style: '标准' }],
    })

    try {
      const tabs = Array.from(rendered.host.querySelectorAll<HTMLButtonElement>(
        '.writing-workspace__tab-btn',
      ))
      tabs.find((button) => button.textContent?.includes('查看版本'))?.click()
      await nextTick()

      const versionDetailButton = Array.from(rendered.host.querySelectorAll<HTMLButtonElement>(
        'button',
      )).find((button) => button.textContent?.includes('版本详情'))
      expect(versionDetailButton).toBeTruthy()
      versionDetailButton?.click()
      expect(rendered.shownVersionDetails).toEqual([0])

      tabs.find((button) => button.textContent?.includes('AI 评审反馈'))?.click()
      await nextTick()

      const evaluationDetailButton = Array.from(rendered.host.querySelectorAll<HTMLButtonElement>(
        'button',
      )).find((button) => button.textContent?.includes('评审详情'))
      expect(evaluationDetailButton).toBeTruthy()
      evaluationDetailButton?.click()
      expect(rendered.getEvaluationDetailCount()).toBe(1)

      const deskSource = readSource('src/views/WritingDesk.vue')
      const workspaceTag = deskSource.match(/<WDWorkspace[\s\S]*?\/>/)?.[0] ?? ''
      expect(workspaceTag).toContain('@show-version-detail="showVersionDetail"')
      expect(workspaceTag).toContain('@show-evaluation-detail="openEvaluationDetailModal"')
    } finally {
      rendered.unmount()
    }
  })

  it('wires locked chapter navigation through the writing desk parent', () => {
    const source = readSource('src/views/WritingDesk.vue')
    const workspaceTag = source.match(/<WDWorkspace[\s\S]*?\/>/)?.[0] ?? ''

    expect(workspaceTag).toContain('@select-chapter="selectChapter"')
  })

  it('filters candidate versions to the current workflow run', () => {
    const source = readSource('src/views/WritingDesk.vue')

    expect(source).toContain('candidate.workflow_run_id === runId')
    expect(source).toContain("submitCommand('select', { selected_version_id: versionId })")
    expect(source).not.toContain('selected_version_index')
  })

  it('uses the workflow actor transport instead of the legacy chapter stream', () => {
    const source = `${readSource('src/views/WritingDesk.vue')}\n${readSource('src/composables/useWritingDeskProject.ts')}`
    const workspaceSource = readSource('src/components/writing-desk/WDWorkspace.vue')

    expect(source).toContain('useChapterWorkflowActor(')
    expect(source).toContain('useChapterWorkflowActorPorts()')
    expect(source).not.toContain('NovelAPI.subscribeChapterStatus')
    expect(source).not.toContain('fetchChapterStatus')
    expect(workspaceSource).toContain('ChapterWorkflowPanel')
    expect(workspaceSource).not.toContain('setInterval(() =>')
    expect(workspaceSource).not.toContain("emit('fetchChapterStatus')")
  })

  it('keeps the locked chapter light skin on a warm paper palette', () => {
    const source = readSource('src/components/writing-desk/workspace/ChapterEmpty.vue')

    expect(source).toContain(":root[data-theme='light'] .chapter-locked")
    expect(source).toContain('--chapter-locked-accent: #c8a875;')
    expect(source).toContain('--chapter-locked-text: #9e8662;')
    expect(source).toContain('--chapter-locked-muted: #667172;')
    expect(source).toContain('--chapter-locked-action-bg: rgba(250, 246, 237, 0.64);')
  })

  it('shows the reading control only for finalized chapter content', async () => {
    const project: NovelProject = {
      id: 'novel-1',
      title: '全网退役',
      initial_prompt: '',
      conversation_history: [],
      blueprint: {
        chapter_outline: [
          { chapter_number: 1, title: '一招', summary: '林拓重新站上擂台。' },
        ],
      },
      chapters: [
        {
          chapter_number: 1,
          title: '一招',
          summary: '林拓重新站上擂台。',
          real_summary: null,
          content: '林拓抬起拳架。',
          versions: null,
          evaluation: null,
          generation_status: 'successful',
        },
      ],
    }

    const rendered = await mountWorkspace(project, 1, {
      workflowPhase: 'waitingForSelection',
      workflowCandidates: [
        {
          id: 501,
          content: '灯下的新候选正文。',
          version_label: '版本一',
          workflow_run_id: 'run-3',
        },
      ],
    })
    try {
      expect(rendered.host.querySelector('[aria-label="朗读"]')).not.toBeNull()
      expect(rendered.host.querySelector('[data-provenance="ink"]')).not.toBeNull()
      expect(rendered.host.querySelector('[data-provenance="ai"]')).not.toBeNull()
    } finally {
      rendered.unmount()
    }
  })

  it('hides the reading control while only candidate content exists', async () => {
    const project: NovelProject = {
      id: 'novel-1',
      title: '全网退役',
      initial_prompt: '',
      conversation_history: [],
      blueprint: {
        chapter_outline: [{ chapter_number: 1, title: '一招', summary: '林拓重新站上擂台。' }],
      },
      chapters: [
        {
          chapter_number: 1,
          title: '一招',
          summary: '林拓重新站上擂台。',
          real_summary: null,
          content: null,
          versions: null,
          evaluation: null,
          generation_status: 'waiting_for_confirm',
        },
      ],
    }

    const rendered = await mountWorkspace(project, 1, {
      availableVersions: [{ content: '待确认候选正文' }],
      workflowPhase: 'waitingForSelection',
    })
    try {
      expect(rendered.host.querySelector('[aria-label="朗读"]')).toBeNull()
      expect(rendered.host.querySelector('[data-provenance="ink"]')?.textContent)
        .toContain('待确认候选正文')
    } finally {
      rendered.unmount()
    }
  })

  it('wires the reading toolbar to playback state and chapter cleanup', () => {
    // reader 胶水（chapterReader 实例 + handleReader* + 朗读生命周期）随 useChapterReaderBar 抽至 composable，断言改读 composable 源码
    const source = readSource('src/composables/useChapterReaderBar.ts')

    expect(source).toContain('useChapterReader()')
    expect(source).toContain("readerStatus.value === 'playing'")
    expect(source).toContain("readerStatus.value === 'paused'")
    expect(source).toContain('chapterReader.pause()')
    expect(source).toContain('chapterReader.resume()')
    expect(source).toContain('chapterReader.stop()')
    expect(source).toContain('selectedChapterOutline.value?.title')
  })
})
