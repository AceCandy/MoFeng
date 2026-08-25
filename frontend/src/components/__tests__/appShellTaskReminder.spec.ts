// AIMETA P=应用布局任务提醒行为测试|R=状态聚合_已读持久化_用户隔离|NR=不测试后端任务流|E=test:AppShellTaskReminder|X=test|A=vitest|D=vue,jsdom|S=dom,storage|RD=./README.ai
import { createApp, defineComponent, nextTick, reactive, ref, type Component, type Ref } from 'vue'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

import type { BackgroundTask } from '@/api/tasks'

const tasks = ref<BackgroundTask[]>([])
const streamedTasks = ref<BackgroundTask[] | null>(null)
const authState = reactive({
  user: { id: 1, username: 'tester', is_admin: false },
  logout: vi.fn(),
})
const push = vi.fn()
const invalidateQueries = vi.fn()

vi.mock('vue-router', () => ({
  RouterLink: defineComponent({ template: '<a><slot /></a>' }),
  useRoute: () => reactive({ name: 'workspace-entry', params: {} }),
  useRouter: () => ({ push }),
}))

vi.mock('@tanstack/vue-query', () => ({
  useQueryClient: () => ({ invalidateQueries }),
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => authState,
}))

vi.mock('@/stores/novel', () => ({
  useNovelStore: () => reactive({ isAssistantPanelVisible: false }),
}))

vi.mock('@/queries/auth', () => ({ clearAuthQueryCache: vi.fn() }))
vi.mock('@/queries/tasks', () => ({
  useTasksQuery: () => ({ data: tasks, isFetching: ref(false) }),
  useTaskStream: () => ({
    sseBackgroundTasks: streamedTasks,
    isTaskStreamActive: ref(false),
    isTaskStreamConnected: ref(false),
    startTaskStream: vi.fn(),
  }),
}))
vi.mock('@/queries/novel', () => ({
  novelQueryKeys: {
    projects: () => ['novels'],
    detail: (id: string) => ['novels', id],
  },
  useNovelProjectsQuery: () => ({ data: ref([]) }),
  useNovelProjectQuery: () => ({ data: ref(null) }),
  useImportNovelMutation: () => ({ mutateAsync: vi.fn() }),
}))
vi.mock('@/composables/useAlert', () => ({
  globalAlert: { showConfirm: vi.fn() },
}))
vi.mock('@/components/shared/GlobalModalContainer.vue', () => ({
  default: defineComponent({ template: '<section data-testid="task-modal"><slot /></section>' }),
}))
vi.mock('@/components/shared/TaskLogPanel.vue', () => ({
  default: defineComponent({ template: '<div>task log</div>' }),
}))

let AppShell: Component
const mountedApps: Array<() => void> = []

const task = (id: string, status: BackgroundTask['status']): BackgroundTask => ({
  id,
  user_id: authState.user.id,
  task_type: 'test',
  title: id,
  status,
  progress: status === 'succeeded' ? 100 : 0,
  log_entries: [],
  created_at: '2026-07-23T00:00:00Z',
  updated_at: '2026-07-23T00:00:00Z',
})

const mountShell = async () => {
  const root = document.createElement('div')
  document.body.appendChild(root)
  const app = createApp(AppShell)
  app.mount(root)
  await nextTick()
  mountedApps.push(() => {
    app.unmount()
    root.remove()
  })
  return root
}

const taskButton = (root: HTMLElement) =>
  root.querySelector<HTMLButtonElement>('.app-shell__task-button')!

const reminderDot = (root: HTMLElement) =>
  root.querySelector<HTMLElement>('.app-shell__task-status-dot')

beforeAll(async () => {
  AppShell = (await import('@/components/shared/AppShell.vue')).default
})

beforeEach(() => {
  localStorage.clear()
  invalidateQueries.mockClear()
  tasks.value = []
  streamedTasks.value = null
  authState.user = { id: 1, username: 'tester', is_admin: false }
})

afterEach(() => {
  while (mountedApps.length) mountedApps.pop()!()
})

describe('AppShell task reminder', () => {
  it('首次任务快照只建立大纲完成基线', async () => {
    const completedOutline = {
      ...task('outline-1', 'succeeded'),
      task_type: 'chapter_outline',
      project_id: 'project-1',
    }
    tasks.value = [completedOutline]
    await mountShell()

    expect(invalidateQueries).not.toHaveBeenCalled()

    tasks.value = [
      completedOutline,
      {
        ...task('outline-2', 'succeeded'),
        task_type: 'chapter_outline',
        project_id: 'project-1',
      },
    ]
    await nextTick()

    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ['novels'] })
    expect(invalidateQueries).toHaveBeenCalledWith({
      queryKey: ['novels', 'project-1'],
      exact: true,
    })
  })

  it('ignores queued tasks and keeps the running count after opening the log', async () => {
    tasks.value = [task('queued', 'queued'), ...Array.from({ length: 10 }, (_, i) => task(`run-${i}`, 'running'))]
    const root = await mountShell()

    expect(root.querySelector('.app-shell__task-count')?.textContent?.trim()).toBe('9+')
    expect(reminderDot(root)).toBeNull()
    expect(taskButton(root).getAttribute('aria-label')).toBe('查看任务日志，10 个任务执行中')

    taskButton(root).click()
    await nextTick()

    expect(root.querySelector('.app-shell__task-count')?.textContent?.trim()).toBe('9+')
  })

  it('prioritizes failed results and clears terminal reminders on click', async () => {
    tasks.value = [task('success-1', 'succeeded'), task('failed-1', 'failed')]
    const root = await mountShell()

    expect(reminderDot(root)?.classList.contains('is-success')).toBe(false)
    expect(taskButton(root).getAttribute('aria-label')).toBe('查看任务日志，有任务执行失败')

    taskButton(root).click()
    await nextTick()

    expect(reminderDot(root)).toBeNull()
    expect(JSON.parse(localStorage.getItem('mofeng-task-read:1') ?? '[]')).toEqual([
      'success-1',
      'failed-1',
    ])
  })

  it('restores read results, shows later completions, and isolates users', async () => {
    localStorage.setItem('mofeng-task-read:1', JSON.stringify(['success-1']))
    tasks.value = [task('success-1', 'succeeded')]
    const root = await mountShell()

    expect(reminderDot(root)).toBeNull()

    tasks.value = [...tasks.value, task('success-2', 'succeeded')]
    await nextTick()
    expect(reminderDot(root)?.classList.contains('is-success')).toBe(true)
    expect(taskButton(root).getAttribute('aria-label')).toBe('查看任务日志，有任务执行完成')

    authState.user = { id: 2, username: 'other', is_admin: false }
    await nextTick()
    expect(reminderDot(root)?.classList.contains('is-success')).toBe(true)
  })

  it('tolerates malformed or unavailable localStorage without blocking the task log', async () => {
    localStorage.setItem('mofeng-task-read:1', '{broken')
    tasks.value = [task('failed-1', 'failed')]
    const root = await mountShell()
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('storage disabled', 'SecurityError')
    })

    expect(reminderDot(root)).not.toBeNull()
    taskButton(root).click()
    await nextTick()

    expect(reminderDot(root)).toBeNull()
    expect(document.body.querySelector('[data-testid="task-modal"]')).not.toBeNull()
  })
})
