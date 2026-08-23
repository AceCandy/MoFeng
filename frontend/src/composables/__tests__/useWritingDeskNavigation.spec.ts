// AIMETA P=写作台章节恢复优先级测试|R=query优先_上下文延迟_首次写回|NR=不测试路由replace或服务端PATCH|E=test:composable:writing-desk-navigation|X=internal|A=useWritingDeskNavigation_entry|D=vitest,vue-router|S=test|RD=../README.ai
import { computed, createApp, defineComponent, nextTick, ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { NovelProject } from '@/api/novel'
import { useWritingDeskNavigation } from '@/composables/useWritingDeskNavigation'

const routeState = vi.hoisted(() => ({
  route: { query: {} as Record<string, string | undefined> },
}))

vi.mock('vue-router', () => ({
  useRoute: () => routeState.route,
}))

const project = {
  id: 'project-1',
  title: '章节恢复',
  initial_prompt: '',
  conversation_history: [],
  chapters: [
    { chapter_number: 1, title: '第一章', summary: '', goals: '', generation_status: 'successful' },
    { chapter_number: 2, title: '第二章', summary: '', goals: '', generation_status: 'successful' },
  ],
} as NovelProject

const mountNavigation = (preferredChapterNumber: number | null) => {
  const contextReady = ref(false)
  const selectedChapterNumber = ref<number | null>(null)
  const selectedVersionIndex = ref(4)
  const selectChapter = vi.fn((chapterNumber: number) => {
    selectedChapterNumber.value = chapterNumber
    selectedVersionIndex.value = 0
  })
  const app = createApp(defineComponent({
    setup() {
      useWritingDeskNavigation({
        projectId: () => project.id,
        project: computed(() => project),
        selectedChapterNumber,
        selectedVersionIndex,
        selectChapter,
        contextReady: () => contextReady.value,
        preferredChapterNumber: () => preferredChapterNumber,
      })
      return () => null
    },
  }))
  app.mount(document.createElement('div'))
  return { app, contextReady, selectChapter, selectedChapterNumber }
}

describe('useWritingDeskNavigation', () => {
  beforeEach(() => {
    routeState.route.query = {}
  })

  it('等待上下文后首次按服务端章节定位并经过统一选择入口', async () => {
    const mounted = mountNavigation(2)
    try {
      expect(mounted.selectChapter).not.toHaveBeenCalled()
      mounted.contextReady.value = true
      await nextTick()

      expect(mounted.selectChapter).toHaveBeenCalledOnce()
      expect(mounted.selectChapter).toHaveBeenCalledWith(2)
      expect(mounted.selectedChapterNumber.value).toBe(2)
    } finally {
      mounted.app.unmount()
    }
  })

  it('显式 query 高于服务端上下文章节', async () => {
    routeState.route.query = { chapter_number: '1' }
    const mounted = mountNavigation(2)
    try {
      mounted.contextReady.value = true
      await nextTick()
      expect(mounted.selectChapter).toHaveBeenCalledWith(1)
    } finally {
      mounted.app.unmount()
    }
  })
})
