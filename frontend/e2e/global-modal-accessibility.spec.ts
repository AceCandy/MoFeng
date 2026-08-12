// AIMETA P=通用弹窗与写作台无障碍浏览器验收|R=axe_焦点生命周期_触控尺寸_主题溢出|NR=不覆盖全站历史无障碍债务|E=test:e2e:accessibility|X=internal|A=accessibility-e2e|D=playwright,axe-core|S=test,dom|RD=../README.ai
import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'

const fixtureBase = 'http://127.0.0.1:6181'
const writingDeskPath = '/projects/project-e2e/write?chapter_number=1'

const resetScenario = async (page: Page, scenario: string) => {
  const response = await page.request.post(`${fixtureBase}/__e2e/scenario`, {
    data: { scenario },
  })
  expect(response.ok()).toBe(true)
}

const expectNoHorizontalOverflow = async (page: Page) => {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
}

const expectTouchTarget = async (target: ReturnType<Page['locator']>) => {
  const box = await target.boundingBox()
  expect(box?.width).toBeGreaterThanOrEqual(43.99)
  expect(box?.height).toBeGreaterThanOrEqual(43.99)
}

const expectAxeClean = async (page: Page, include?: string) => {
  let builder = new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa'])
  if (include) builder = builder.include(include)
  expect((await builder.analyze()).violations).toEqual([])
}

const openAuthenticatedPage = async (page: Page, theme: 'light' | 'dark' = 'light') => {
  await page.addInitScript(() => localStorage.setItem('token', 'e2e-token'))
  await page.goto('/login')
  await page.evaluate((selectedTheme) => {
    localStorage.setItem('mofeng-theme-preference', selectedTheme)
  }, theme)
  await page.goto(writingDeskPath)
  await expect(page.getByRole('main')).toBeVisible()
}

test('登录页通过 axe，口令按钮满足触控尺寸', async ({ page }) => {
  await page.goto('/login')
  const passwordToggle = page.getByRole('button', { name: '显示口令' })
  await expect(passwordToggle).toBeVisible()
  await expectTouchTarget(passwordToggle)
  await expectNoHorizontalOverflow(page)
  await expectAxeClean(page, '.login-page')
})

test('任务日志 dialog 陷住焦点并在关闭后恢复', async ({ page }) => {
  await openAuthenticatedPage(page)
  const trigger = page.getByRole('button', { name: '查看任务日志' })
  await expect(trigger).toBeVisible()
  await expectTouchTarget(trigger)

  await trigger.click()
  const dialog = page.getByRole('dialog', { name: '任务日志' })
  const close = dialog.getByRole('button', { name: '关闭任务日志' })
  await expect(dialog).toBeVisible()
  await expect(close).toBeFocused()
  await expectAxeClean(page, '.m3-ink-modal-box')

  await page.keyboard.press('Shift+Tab')
  await expect(close).toBeFocused()
  await page.keyboard.press('Tab')
  await expect(close).toBeFocused()
  await page.keyboard.press('Escape')
  await expect(dialog).toBeHidden()
  await expect(trigger).toBeFocused()
})

test('写作台浅色和深色主题通过 axe、触控与溢出验收', async ({ page }) => {
  for (const theme of ['light', 'dark'] as const) {
    await resetScenario(page, 'external-retry')
    await openAuthenticatedPage(page, theme)
    await expect(page.locator('html')).toHaveAttribute('data-theme', theme)
    const assistant = page.getByRole('button', { name: /右侧辅助面板/ })
    await expect(assistant).toBeVisible()
    await expectTouchTarget(assistant)
    await expect(page.locator('.writing-desk-page')).toHaveCSS('opacity', '1')
    await expect(page.locator('.writing-desk-assistant-shell')).toHaveCSS('opacity', '1')
    await expectNoHorizontalOverflow(page)
    await expectAxeClean(page, '.wd-ai__panel')
    await expectAxeClean(page, '.chapter-console__pipeline-card')

    const contextStep = page.getByRole('button', {
      name: '整理前文重点剧情、角色状态和本章任务。',
    })
    await contextStep.focus()
    await page.keyboard.press('Enter')
    await expect(page.getByRole('heading', { name: '整理前文', exact: true })).toBeVisible()
  }
})
