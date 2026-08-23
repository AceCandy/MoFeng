// AIMETA P=后台任务结果导航测试|R=写作台章节_项目档案_内部任务无导航|NR=不测试AppShell弹窗|E=test:component:task-log-panel|X=internal|A=TaskLogPanel_navigation|D=vitest,vue|S=test|RD=../../README.ai
import { createApp, h, nextTick } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { BackgroundTask } from '@/api/tasks'
import TaskLogPanel from '@/components/shared/TaskLogPanel.vue'

const task = (overrides: Partial<BackgroundTask> = {}): BackgroundTask => ({
  id: 'task-1',
  user_id: 1,
  project_id: 'project-1',
  task_type: 'chapter_workflow',
  title: '生成第一章',
  status: 'succeeded',
  progress: 100,
  log_entries: [],
  created_at: '2026-08-24T08:00:00Z',
  updated_at: '2026-08-24T08:01:00Z',
  ...overrides,
})

const mountPanel = (value: BackgroundTask) => {
  const navigate = vi.fn()
  const host = document.createElement('div')
  const app = createApp({
    render: () => h(TaskLogPanel, { tasks: [value], onNavigate: navigate }),
  })
  app.mount(host)
  document.body.appendChild(host)
  return { app, host, navigate }
}

afterEach(() => {
  document.body.innerHTML = ''
})

describe('TaskLogPanel', () => {
  it('正文任务携带安全章节号回到对应写作台', async () => {
    const mounted = mountPanel(task({ chapter_number: 3 }))
    try {
      await nextTick()
      const selected = mounted.host.querySelector('.task-log-panel__task')
      expect(selected?.getAttribute('aria-current')).toBe('true')
      ;(mounted.host.querySelector('.task-log-panel__navigate') as HTMLButtonElement).click()
      expect(mounted.navigate).toHaveBeenCalledWith({
        name: 'project-write',
        params: { id: 'project-1' },
        query: { chapter_number: '3' },
      })
    } finally {
      mounted.app.unmount()
    }
  })

  it('大纲任务进入项目档案，内部治理任务不伪造导航', async () => {
    const archive = mountPanel(task({ task_type: 'chapter_outline' }))
    try {
      await nextTick()
      ;(archive.host.querySelector('.task-log-panel__navigate') as HTMLButtonElement).click()
      expect(archive.navigate).toHaveBeenCalledWith({
        name: 'project-detail',
        params: { id: 'project-1' },
      })
    } finally {
      archive.app.unmount()
    }

    const internal = mountPanel(task({ task_type: 'chapter_projection_reconcile' }))
    try {
      await nextTick()
      expect(internal.host.querySelector('.task-log-panel__navigate')).toBeNull()
    } finally {
      internal.app.unmount()
    }
  })
})
