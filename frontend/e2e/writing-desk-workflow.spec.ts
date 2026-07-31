// AIMETA P=写作台章节工作流浏览器验收|R=恢复_命令_SSE重放_契约与ARIA|NR=不覆盖后端执行器或视觉基线|E=test:e2e:writing-desk-workflow|X=internal|A=writing-desk-workflow-e2e|D=playwright|S=test,net,dom|RD=../README.ai
import { expect, test, type APIRequestContext, type Page } from '@playwright/test'

const fixtureBase = 'http://127.0.0.1:6181'
const writingDeskPath = '/projects/project-e2e/write?chapter_number=1'

interface E2EStats {
  currentRequests: number
  startRequests: number
  workflowConnections: number
  lastEventIds: Array<string | null>
  commands: Array<{
    type?: string
    payload?: Record<string, unknown>
  }>
  unknownRequests: string[]
}

const browserErrors = new WeakMap<Page, string[]>()

const resetScenario = async (request: APIRequestContext, scenario: string) => {
  const response = await request.post(`${fixtureBase}/__e2e/scenario`, {
    data: { scenario },
  })
  expect(response.ok()).toBe(true)
}

const emitFixtureEvent = async (request: APIRequestContext, action: string) => {
  const response = await request.post(`${fixtureBase}/__e2e/event`, {
    data: { action },
  })
  expect(response.ok()).toBe(true)
}

const readStats = async (request: APIRequestContext): Promise<E2EStats> => {
  const response = await request.get(`${fixtureBase}/__e2e/stats`)
  expect(response.ok()).toBe(true)
  return response.json() as Promise<E2EStats>
}

const openWritingDesk = async (page: Page) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'e2e-token')
  })
  await page.goto(writingDeskPath)
  const panel = page.locator('.chapter-workflow')
  await expect(panel).toBeVisible()
  return panel
}

const expectStatus = async (
  panel: ReturnType<Page['locator']>,
  title: string,
  role: 'status' | 'alert' = 'status',
) => {
  await expect(panel).toHaveAttribute('role', role)
  await expect(panel).toHaveAttribute('aria-live', role === 'alert' ? 'assertive' : 'polite')
  await expect(panel.getByRole('heading', { name: title })).toBeVisible()
}

test.beforeEach(async ({ page }) => {
  const errors: string[] = []
  browserErrors.set(page, errors)
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(`console: ${message.text()}`)
  })
  page.on('pageerror', (error) => errors.push(`pageerror: ${error.message}`))
})

test.afterEach(async ({ page, request }) => {
  const stats = await readStats(request)
  expect.soft(stats.unknownRequests).toEqual([])
  expect.soft(browserErrors.get(page) ?? []).toEqual([])
})

test('current 为空时只启动一个 durable 工作流', async ({ page, request }) => {
  await resetScenario(request, 'current-null-start')
  const panel = await openWritingDesk(page)
  await expectStatus(panel, '尚未开始生成')

  await panel.getByRole('button', { name: '开始生成' }).click()
  await expectStatus(panel, '章节生成中')
  await expect.poll(async () => (await readStats(request)).startRequests).toBe(1)
})

test('waiting 先守住无候选状态，再随事实刷新提交真实候选 ID', async ({ page, request }) => {
  await resetScenario(request, 'waiting-refresh')
  const panel = await openWritingDesk(page)
  await expectStatus(panel, '请选择候选版本')
  await expect(panel.getByText('候选版本同步中')).toBeVisible()
  await expect(panel.locator('[data-action="select"]')).toHaveCount(0)

  await emitFixtureEvent(request, 'waiting-ready')
  await expect(panel.getByRole('radio', { name: '候选版本 1' })).toBeVisible()
  await panel.getByRole('button', { name: '选定并继续' }).click()
  await expectStatus(panel, '正在提交正文')

  const stats = await readStats(request)
  expect(stats.commands.at(-1)).toMatchObject({
    type: 'select',
    payload: { selected_version_id: 701 },
  })
})

test('断线后携带 cursor 重连并重放最新事实', async ({ page, request }) => {
  await resetScenario(request, 'disconnect-replay')
  const panel = await openWritingDesk(page)
  await expectStatus(panel, '章节生成中')
  await expect(panel.getByText('实时连接已中断，正在重连。')).toBeVisible()
  await expectStatus(panel, '请选择候选版本')

  await expect.poll(async () => (await readStats(request)).workflowConnections).toBeGreaterThanOrEqual(2)
  const stats = await readStats(request)
  expect(stats.lastEventIds[1]).toBe('10')
})

test('重复点击不会产生第二个 start 请求', async ({ page, request }) => {
  await resetScenario(request, 'duplicate-click')
  const panel = await openWritingDesk(page)
  const start = panel.getByRole('button', { name: '开始生成' })

  await start.evaluate((button) => {
    button.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    button.dispatchEvent(new MouseEvent('click', { bubbles: true }))
  })
  await expectStatus(panel, '章节生成中')
  expect((await readStats(request)).startRequests).toBe(1)
})

test('旧 cursor 事件不会覆盖已接受的新事实', async ({ page, request }) => {
  await resetScenario(request, 'stale-event')
  const panel = await openWritingDesk(page)
  await emitFixtureEvent(request, 'stale-success')
  await expectStatus(panel, '章节工作流已完成')
  const currentRequests = (await readStats(request)).currentRequests

  await emitFixtureEvent(request, 'stale-event')
  await page.waitForTimeout(150)
  await expectStatus(panel, '章节工作流已完成')
  expect((await readStats(request)).currentRequests).toBe(currentRequests)
})

test('projection pending 只提交 retry_projection', async ({ page, request }) => {
  await resetScenario(request, 'projection-retry')
  const panel = await openWritingDesk(page)
  await expectStatus(panel, '正文已提交')

  await panel.getByRole('button', { name: '重试同步' }).click()
  await expectStatus(panel, '章节生成中')
  expect((await readStats(request)).commands.at(-1)?.type).toBe('retry_projection')
})

test('外部重试必须确认重复调用风险并携带确认字段', async ({ page, request }) => {
  await resetScenario(request, 'external-retry')
  const panel = await openWritingDesk(page)
  await expectStatus(panel, '本轮需要处理', 'alert')

  await panel.getByRole('button', { name: '确认风险并重试' }).click()
  const dialog = page.getByRole('dialog', { name: '确认外部重试风险' })
  await expect(dialog).toBeVisible()
  await dialog.getByRole('button', { name: '确定' }).click()
  await expectStatus(panel, '章节生成中')

  expect((await readStats(request)).commands.at(-1)).toMatchObject({
    type: 'retry_external',
    payload: {
      activity_key: 'generate-candidates:attempt-1',
      acknowledge_possible_duplicate: true,
    },
  })
})

test('已取消运行可以用新 run 重新开始', async ({ page, request }) => {
  await resetScenario(request, 'cancelled-restart')
  const panel = await openWritingDesk(page)
  await expectStatus(panel, '本轮已取消')

  await panel.getByRole('button', { name: '开始生成' }).click()
  await expectStatus(panel, '章节生成中')
  expect((await readStats(request)).startRequests).toBe(1)
})

test('superseded 运行自动跟随 successor', async ({ page, request }) => {
  await resetScenario(request, 'superseded-follow')
  const panel = await openWritingDesk(page)
  await expectStatus(panel, '章节生成中')
  await expect.poll(async () => (await readStats(request)).currentRequests).toBeGreaterThanOrEqual(2)
})

test('不支持的契约版本进入 fatal，显式 resync 后才恢复', async ({ page, request }) => {
  await resetScenario(request, 'fatal-contract')
  const panel = await openWritingDesk(page)
  await expectStatus(panel, '章节状态暂不可信', 'alert')
  await expect(panel).toContainText('章节工作流数据版本不受支持')

  await panel.getByRole('button', { name: '重新同步' }).click()
  await expectStatus(panel, '尚未开始生成')
  await expect.poll(async () => (await readStats(request)).currentRequests).toBe(2)
})
