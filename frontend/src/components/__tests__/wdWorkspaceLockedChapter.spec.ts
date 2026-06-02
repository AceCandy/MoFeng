import { describe, expect, it } from 'vitest'
import { createApp, nextTick } from 'vue'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import WDWorkspace from '@/components/writing-desk/WDWorkspace.vue'
import type { NovelProject } from '@/api/novel'

const readSource = (relativePath: string) =>
  readFileSync(resolve(process.cwd(), relativePath), 'utf8')

const mountWorkspace = async (project: NovelProject, selectedChapterNumber: number) => {
  const host = document.createElement('div')
  document.body.appendChild(host)
  const selectedChapters: number[] = []
  const app = createApp(WDWorkspace, {
    project,
    selectedChapterNumber,
    generatingChapter: null,
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
      expect(rendered.host.textContent).toContain('故事尚未推进到这里')
      expect(rendered.host.textContent).toContain('请先完成前置章节内容。')
      expect(rendered.host.textContent).toContain('当前章节将在所需章节完成后自动解锁。')
      expect(rendered.host.textContent).toContain('前往待完成章节')
      expect(rendered.host.querySelector('[role="toolbar"][aria-label="章节操作"]')).toBeNull()
      expect(rendered.host.textContent).not.toContain('编辑正文')
      expect(rendered.host.textContent).not.toContain('AI优化')

      const gotoButton = Array.from(rendered.host.querySelectorAll('button')).find((button) =>
        button.textContent?.includes('前往待完成章节'),
      )
      expect(gotoButton).toBeTruthy()

      gotoButton?.dispatchEvent(new MouseEvent('click', { bubbles: true }))

      expect(rendered.selectedChapters).toEqual([1])
    } finally {
      rendered.unmount()
    }
  })

  it('wires locked chapter navigation through the writing desk parent', () => {
    const source = readSource('src/views/WritingDesk.vue')
    const workspaceTag = source.match(/<WDWorkspace[\s\S]*?\/>/)?.[0] ?? ''

    expect(workspaceTag).toContain('@select-chapter="selectChapter"')
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
