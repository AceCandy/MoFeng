import { describe, expect, it } from 'vitest'
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
  overrides: { generatingChapter?: number | null } = {},
) => {
  const host = document.createElement('div')
  document.body.appendChild(host)
  const selectedChapters: number[] = []
  const app = createApp(WDWorkspace, {
    project,
    selectedChapterNumber,
    generatingChapter: overrides.generatingChapter ?? null,
    evaluatingChapter: null,
    showVersionSelector: false,
    chapterGenerationResult: null,
    selectedVersionIndex: 0,
    availableVersions: [],
    isSelectingVersion: false,
    onSelectChapter: (chapterNumber: number) => selectedChapters.push(chapterNumber),
  })

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

  it('wires locked chapter navigation through the writing desk parent', () => {
    const source = readSource('src/views/WritingDesk.vue')
    const workspaceTag = source.match(/<WDWorkspace[\s\S]*?\/>/)?.[0] ?? ''

    expect(workspaceTag).toContain('@select-chapter="selectChapter"')
  })

  it('keeps generation polling lightweight by refreshing only the selected chapter', () => {
    const source = readSource('src/views/WritingDesk.vue')
    const refetchHelper = source.match(/const refetchChapterIntoProject[\s\S]*?\n}\n\nconst fetchChapterStatus/)?.[0] ?? ''
    const pollingBlock = source.match(/const fetchChapterStatus[\s\S]*?\n}\n\n\/\/ 显示版本详情/)?.[0] ?? ''

    expect(refetchHelper).toContain('refreshProject?: boolean')
    expect(refetchHelper).toContain('if (options.refreshProject)')
    expect(pollingBlock).toContain('refetchChapterIntoProject(chapterNumber, { refreshProject: false })')
  })

  it('keeps the locked chapter light skin on a warm paper palette', () => {
    const source = readSource('src/components/writing-desk/workspace/ChapterEmpty.vue')

    expect(source).toContain(":root[data-theme='light'] .chapter-locked")
    expect(source).toContain('--chapter-locked-accent: #c8a875;')
    expect(source).toContain('--chapter-locked-text: #9e8662;')
    expect(source).toContain('--chapter-locked-muted: #667172;')
    expect(source).toContain('--chapter-locked-action-bg: rgba(250, 246, 237, 0.64);')
  })
})
