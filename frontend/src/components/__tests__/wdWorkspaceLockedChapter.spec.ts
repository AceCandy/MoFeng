import { describe, expect, it } from 'vitest'
import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'
import { createApp, nextTick } from 'vue'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import WDWorkspace from '@/components/writing-desk/WDWorkspace.vue'
import type { NovelProject } from '@/api/novel'

const readSource = (relativePath: string) =>
  readFileSync(resolve(process.cwd(), relativePath), 'utf8')

const mountWorkspace = async (
  project: NovelProject,
  selectedChapterNumber: number,
  overrides: {
    generatingChapter?: number | null
    selectedVersionIndex?: number
    availableVersions?: Array<{ content: string; style?: string; metadata?: Record<string, any> }>
  } = {},
) => {
  const host = document.createElement('div')
  document.body.appendChild(host)
  const selectedChapters: number[] = []
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  const app = createApp(WDWorkspace, {
    project,
    selectedChapterNumber,
    generatingChapter: overrides.generatingChapter ?? null,
    evaluatingChapter: null,
    showVersionSelector: false,
    chapterGenerationResult: null,
    selectedVersionIndex: overrides.selectedVersionIndex ?? 0,
    availableVersions: overrides.availableVersions ?? [],
    isSelectingVersion: false,
    onSelectChapter: (chapterNumber: number) => selectedChapters.push(chapterNumber),
  })

  app.use(VueQueryPlugin, { queryClient })
  app.mount(host)
  await nextTick()

  return {
    host,
    selectedChapters,
    unmount: () => {
      app.unmount()
      host.remove()
    },
  }
}

describe('WDWorkspace locked chapter state', () => {
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

  it('keeps retrying failed chapters in the generating view while the retry request is in flight', async () => {
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

    const rendered = await mountWorkspace(project, 1, { generatingChapter: 1 })

    try {
      expect(rendered.host.textContent).toContain('生成进度')
      expect(rendered.host.textContent).toContain('实时草稿预览')
      expect(rendered.host.textContent).not.toContain('第1章生成异常')
      expect(rendered.host.textContent).not.toContain('重试中')
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
      availableVersions: [
        {
          content: '退役冠军林拓站在商业直播表演赛的灯下。\n\n他看见对手穿着旧布鞋，却仍旧把拳架抬得很稳。',
          style: '标准',
        },
      ],
    })

    try {
      expect(rendered.host.textContent).toContain('待确认')
      expect(rendered.host.textContent).toContain('编辑草稿')
      expect(rendered.host.textContent).toContain('确认定稿')
      expect(rendered.host.textContent).toContain('退役冠军林拓站在商业直播表演赛的灯下')
      expect(rendered.host.querySelector('.chapter-paper')).not.toBeNull()
      expect(rendered.host.textContent).toContain('生成进度')
      expect(rendered.host.textContent).toContain('整理前文')
      expect(rendered.host.textContent).toContain('待人工确认')
      expect(rendered.host.textContent).not.toContain('转入后台生成')
      expect(rendered.host.textContent).not.toContain('取消生成')
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

  it('renders the recommended waiting confirmation draft instead of the first non-empty version', async () => {
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
      availableVersions: [
        {
          content: '版本一只是铺垫，冲突还没有真正立起来。',
          style: '标准',
        },
        {
          content: '版本二让林拓在灯下直接迎上对手，是 AI 评审推荐的底稿。',
          style: '强化冲突',
          metadata: { ai_review: { is_best: true } },
        },
      ],
    })

    try {
      expect(rendered.host.textContent).toContain('版本二让林拓在灯下直接迎上对手')
      expect(rendered.host.textContent).not.toContain('版本一只是铺垫')
    } finally {
      rendered.unmount()
    }
  })

  it('wires locked chapter navigation through the writing desk parent', () => {
    const source = readSource('src/views/WritingDesk.vue')
    const workspaceTag = source.match(/<WDWorkspace[\s\S]*?\/>/)?.[0] ?? ''

    expect(workspaceTag).toContain('@select-chapter="selectChapter"')
  })

  it('defaults waiting confirmation selection from the structured recommended version index', () => {
    const source = `${readSource('src/views/WritingDesk.vue')}\n${readSource('src/composables/useWritingDeskVersionDetail.ts')}`

    expect(source).toContain('const resolveRecommendedVersionIndex')
    expect(source).toContain('recommended_version_index')
    expect(source).toContain('metadata?.ai_review?.is_best')
    expect(source).toContain('selectedVersionIndex.value = recommendedIndex')
    expect(source).not.toContain('selectedVersionIndex.value = availableVersions.value.length - 1')
  })

  it('streams generation status instead of polling the selected chapter', () => {
    const source = `${readSource('src/views/WritingDesk.vue')}\n${readSource('src/composables/useWritingDeskProject.ts')}`
    const pollingBlock = source.match(/const fetchChapterStatus[\s\S]*?const selectChapter/)?.[0] ?? ''
    const workspaceSource = readSource('src/components/writing-desk/WDWorkspace.vue')

    expect(pollingBlock).toContain('NovelAPI.subscribeChapterStatus')
    expect(pollingBlock).toContain('upsertChapterInProjectCache(currentProjectId, chapter)')
    expect(workspaceSource).not.toContain('setInterval(() =>')
    expect(workspaceSource).not.toContain('POLLING_INTERVAL_MS')
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

    const rendered = await mountWorkspace(project, 1)
    try {
      expect(rendered.host.querySelector('[aria-label="朗读"]')).not.toBeNull()
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
