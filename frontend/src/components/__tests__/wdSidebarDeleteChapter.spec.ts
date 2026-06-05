import { describe, expect, it, vi } from 'vitest'
import { createApp, nextTick } from 'vue'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import WDSidebar from '@/components/writing-desk/WDSidebar.vue'
import type { NovelProject } from '@/api/novel'

const readSource = (relativePath: string) =>
  readFileSync(resolve(process.cwd(), relativePath), 'utf8')

const baseProject: NovelProject = {
  id: 'novel-delete',
  title: '删章规则',
  initial_prompt: '',
  conversation_history: [],
  blueprint: {
    chapter_outline: [
      { chapter_number: 1, title: '旧章', summary: '已经完成但不是最近一章' },
      { chapter_number: 2, title: '最近成稿', summary: '最近一个已完成章节' },
      { chapter_number: 3, title: '当前待写', summary: '已解锁但未生成' },
      { chapter_number: 4, title: '未解锁', summary: '前序未完成导致未解锁' },
    ],
  },
  chapters: [
    {
      chapter_number: 1,
      title: '旧章',
      summary: '已经完成但不是最近一章',
      real_summary: null,
      content: '正文',
      versions: ['正文'],
      evaluation: '评审',
      generation_status: 'successful',
    },
    {
      chapter_number: 2,
      title: '最近成稿',
      summary: '最近一个已完成章节',
      real_summary: null,
      content: '正文',
      versions: ['正文'],
      evaluation: '评审',
      generation_status: 'successful',
    },
    {
      chapter_number: 3,
      title: '当前待写',
      summary: '已解锁但未生成',
      real_summary: null,
      content: null,
      versions: null,
      evaluation: null,
      generation_status: 'not_generated',
    },
  ],
}

const mountSidebar = async (project: NovelProject = baseProject) => {
  const host = document.createElement('div')
  document.body.appendChild(host)
  const deletedRequests: Array<number | number[]> = []
  const app = createApp(WDSidebar, {
    project,
    selectedChapterNumber: 3,
    generatingChapter: null,
    evaluatingChapter: null,
    isGeneratingOutline: false,
    onDeleteChapter: (chapterNumbers: number | number[]) => deletedRequests.push(chapterNumbers),
  })

  app.mount(host)
  await nextTick()

  return {
    host,
    deletedRequests,
    unmount: () => {
      app.unmount()
      host.remove()
    },
  }
}

describe('WDSidebar chapter deletion affordance', () => {
  it('offers deletion only for deletable chapters and emits the selected chapter number', async () => {
    Element.prototype.scrollIntoView = vi.fn()
    const rendered = await mountSidebar()

    try {
      const buttons = Array.from(rendered.host.querySelectorAll('button'))
      expect(buttons.find((button) => button.getAttribute('aria-label') === '删除第1章')).toBeUndefined()

      const deleteSecond = buttons.find(
        (button) => button.getAttribute('aria-label') === '删除第2章及全部产物',
      )
      const deleteThird = buttons.find(
        (button) => button.getAttribute('aria-label') === '删除第3章及后续未生成大纲',
      )
      const deleteFourth = buttons.find(
        (button) => button.getAttribute('aria-label') === '删除第4章大纲',
      )

      expect(deleteSecond).toBeTruthy()
      expect(deleteThird).toBeTruthy()
      expect(deleteFourth).toBeTruthy()

      deleteSecond?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
      deleteThird?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
      deleteFourth?.dispatchEvent(new MouseEvent('click', { bubbles: true }))

      expect(rendered.deletedRequests).toEqual([[2, 3, 4], [3, 4], [4]])
    } finally {
      rendered.unmount()
    }
  })

  it('keeps destructive confirmation copy explicit for completed chapter artifacts', () => {
    const source = readSource('src/views/WritingDesk.vue')
    const apiSource = `${readSource('src/api/novel.ts')}\n${readSource('src/queries/novel.ts')}`

    expect(source).toContain('正文、版本、评审、生成 trace 和向量数据等全部产物')
    expect(source).toContain('showConfirmInput')
    expect(apiSource).toContain('delete_artifacts_confirmed')
    expect(apiSource).toContain('confirmation_text')
    expect(source).toContain('删除章节及产物')
    expect(source).toContain('删除章节大纲')
  })
})
