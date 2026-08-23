// AIMETA P=跨设备创作连续性浏览器验收|R=草稿恢复_最后写入_轮次推进_减动效|NR=不测试实时协作或冲突合并|E=test:e2e:creation-continuity|X=internal|A=creation-context-e2e|D=playwright|S=test,net,storage|RD=../README.ai
import { expect, test, type APIRequestContext, type Page } from '@playwright/test'

const fixtureBase = 'http://127.0.0.1:6181'
const inspirationPath = '/inspiration?project_id=project-e2e'
const writingDeskPath = '/projects/project-e2e/write'

const resetScenario = async (request: APIRequestContext) => {
  const response = await request.post(`${fixtureBase}/__e2e/scenario`, {
    data: { scenario: 'creation-continuity' },
  })
  expect(response.ok()).toBe(true)
}

const advanceInspiration = async (request: APIRequestContext) => {
  const response = await request.post(`${fixtureBase}/__e2e/event`, {
    data: { action: 'advance-inspiration' },
  })
  expect(response.ok()).toBe(true)
}

const openInspiration = async (page: Page) => {
  await page.addInitScript(() => localStorage.setItem('token', 'e2e-token'))
  await page.goto(inspirationPath)
  const textarea = page.getByRole('textbox', { name: '输入内容' })
  await expect(textarea).toBeVisible()
  return textarea
}

const waitForDraftPatch = (page: Page) => page.waitForResponse((response) =>
  response.request().method() === 'PATCH'
  && response.url().endsWith('/api/creation-contexts/project-e2e')
  && response.ok(),
)

const openWritingDesk = async (page: Page, explicitChapter = false) => {
  await page.addInitScript(() => localStorage.setItem('token', 'e2e-token'))
  await page.goto(explicitChapter ? `${writingDeskPath}?chapter_number=1` : writingDeskPath)
  await expect(page.getByRole('button', { name: 'AI 评审反馈' })).toBeVisible()
}

test('设备 A 的同轮次后写草稿在设备 B 恢复，推进后旧稿消失', async ({ browser, page, request }) => {
  await resetScenario(request)
  const deviceB = await browser.newContext()
  const pageB = await deviceB.newPage()

  try {
    const textareaA = await openInspiration(page)
    const firstPatch = waitForDraftPatch(page)
    await textareaA.fill('设备 A 的第一版草稿')
    await firstPatch

    const textareaB = await openInspiration(pageB)
    await expect(textareaB).toHaveValue('设备 A 的第一版草稿')

    const lastPatch = waitForDraftPatch(page)
    await textareaA.fill('设备 A 的最后写入')
    await lastPatch
    await pageB.reload()
    await expect(pageB.getByRole('textbox', { name: '输入内容' })).toHaveValue('设备 A 的最后写入')

    await advanceInspiration(request)
    await pageB.reload()
    await expect(pageB.getByRole('textbox', { name: '输入内容' })).toHaveValue('')

    const stage = page.locator(
      '.app-shell__stage-sign:visible, .app-shell__project-mobile-stage:visible',
    )
    await expect(stage).toHaveText('灵感采集')
  } finally {
    await deviceB.close()
  }

  const stats = await request.get(`${fixtureBase}/__e2e/stats`).then((response) => response.json())
  expect(stats.unknownRequests).toEqual([])
})

test('减少动态效果时阶段签与任务入口保持静态可用', async ({ page, request }) => {
  await resetScenario(request)
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await openInspiration(page)

  const stage = page.locator(
    '.app-shell__stage-sign:visible, .app-shell__project-mobile-stage:visible',
  )
  await expect(stage).toHaveText('灵感采集')
  await expect(page.locator('.app-shell__task-button')).toBeVisible()
  expect(await page.locator('.app-shell__task-button').evaluate(
    (element) => getComputedStyle(element).transitionDuration,
  )).toBe('0s')
})

test('离线输入先保存在本机，恢复联网后自动同步', async ({ page, request }) => {
  await resetScenario(request)
  const textarea = await openInspiration(page)
  await page.context().setOffline(true)

  try {
    await textarea.fill('离线时不能丢失的草稿')
    await expect(page.getByText('已保存在本机，联网后同步')).toBeVisible()

    const patch = waitForDraftPatch(page)
    await page.context().setOffline(false)
    await patch
    await expect(page.getByText('已保存在本机，联网后同步')).toHaveCount(0)

    const response = await request.get(`${fixtureBase}/api/creation-contexts`)
    const contexts = await response.json()
    expect(contexts[0]?.inspiration_draft).toBe('离线时不能丢失的草稿')
  } finally {
    await page.context().setOffline(false)
  }
})

test('设备 B 恢复设备 A 的章节与写作台分区', async ({ browser, page, request }) => {
  await resetScenario(request)
  const deviceB = await browser.newContext()
  const pageB = await deviceB.newPage()

  try {
    await openWritingDesk(page, true)
    const sectionPatch = page.waitForResponse((response) => {
      if (
        response.request().method() !== 'PATCH'
        || !response.url().endsWith('/api/creation-contexts/project-e2e')
      ) return false
      return response.request().postDataJSON()?.desk_section === 'evaluation'
    })
    await page.getByRole('button', { name: 'AI 评审反馈' }).click()
    await sectionPatch

    await openWritingDesk(pageB)
    await expect(pageB.getByRole('button', { name: 'AI 评审反馈' })).toHaveClass(/is-active/)
    const contexts = await request.get(`${fixtureBase}/api/creation-contexts`).then(
      (response) => response.json(),
    )
    expect(contexts[0]).toMatchObject({
      chapter_number: 1,
      desk_section: 'evaluation',
      surface: 'writing',
    })
  } finally {
    await deviceB.close()
  }
})
