// AIMETA P=全站P1界面回归|R=九页最终视觉_长内容滚动_双视口|NR=不做像素截图对比|E=test:e2e:ui-p1|X=internal|A=ui-p1-e2e|D=playwright|S=test,dom|RD=../README.ai
import { expect, test, type Page } from '@playwright/test'

const fixtureBase = 'http://127.0.0.1:6181'

const setAuthMode = async (page: Page, mode: 'user' | 'admin') => {
  const response = await page.request.post(`${fixtureBase}/__e2e/auth`, { data: { mode } })
  expect(response.ok()).toBe(true)
  await page.addInitScript(() => localStorage.setItem('token', 'e2e-token'))
}

const expectNoHorizontalOverflow = async (page: Page) => {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
}

const expectFlatSurface = async (page: Page, selector: string) => {
  await expect(page.locator(selector).first()).toBeVisible()
  expect(await page.locator(selector).first().evaluate((element) => {
    const style = getComputedStyle(element)
    return style.backgroundImage === 'none' && style.boxShadow === 'none'
  })).toBe(true)
}

const expectSansChrome = async (page: Page, selector: string) => {
  const fontFamily = await page.locator(selector).first().evaluate(
    (element) => getComputedStyle(element).fontFamily,
  )
  expect(fontFamily.toLowerCase().replaceAll('sans-serif', '')).not.toMatch(/kai|serif/)
}

const expectContentReachesEnd = async (page: Page, selector: string) => {
  const result = await page.locator(selector).first().evaluate(async (target) => {
    const probe = document.createElement('div')
    probe.style.height = '1800px'
    probe.style.flex = '0 0 1800px'
    probe.setAttribute('data-scroll-probe', '')
    target.append(probe)

    const candidates: Element[] = []
    for (let element: Element | null = target; element; element = element.parentElement) {
      candidates.push(element)
    }
    if (document.scrollingElement) candidates.push(document.scrollingElement)

    const owner = candidates.find((element) => {
      const overflowY = getComputedStyle(element).overflowY
      return /(auto|scroll)/.test(overflowY) && element.scrollHeight > element.clientHeight
    }) ?? document.scrollingElement

    if (!owner) {
      probe.remove()
      return false
    }

    owner.scrollTop = owner.scrollHeight
    await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()))
    const reachedEnd = owner.scrollTop + owner.clientHeight >= owner.scrollHeight - 2
    probe.remove()
    return reachedEnd
  })
  expect(result).toBe(true)
}

test('九个主页面保持最终视觉且无横向溢出', async ({ page }) => {
  await page.goto('/login')
  await expectFlatSurface(page, '.login-panel')
  await expectSansChrome(page, '.auth-intro__kind')
  await expect(page.locator('.login-page')).toHaveCSS('background-color', 'rgb(23, 55, 207)')
  await expectNoHorizontalOverflow(page)

  await page.goto('/register')
  await expectFlatSurface(page, '.register-panel')
  await expectSansChrome(page, '.auth-intro__kind')
  await expect(page.locator('.register-page')).toHaveCSS('background-color', 'rgb(23, 55, 207)')
  await expectNoHorizontalOverflow(page)

  await setAuthMode(page, 'user')
  for (const [path, selector] of [
    ['/workspace', '.workspace-page'],
    ['/inspiration?project_id=project-e2e', '.inspiration-page'],
    ['/projects/project-e2e', '.detail-shell'],
    ['/projects/project-e2e/write?chapter_number=1', '.writing-desk-page'],
    ['/settings', '.settings-page'],
  ] as const) {
    await page.goto(path)
    await expect(page.locator(selector)).toBeVisible()
    await expectNoHorizontalOverflow(page)
  }

  await expectFlatSurface(page, '.settings-center')

  await setAuthMode(page, 'admin')
  for (const [path, selector] of [
    ['/admin', '.admin-console'],
    ['/admin/novels/project-e2e', '.detail-shell'],
  ] as const) {
    await page.goto(path)
    await expect(page.locator(selector)).toBeVisible()
    await expectNoHorizontalOverflow(page)
  }
  await expectFlatSurface(page, '.detail-shell__content-surface')
})

test('详情、灵感和写作长内容都能滚动到末尾', async ({ page }, testInfo) => {
  await setAuthMode(page, 'user')

  if (testInfo.project.name === 'desktop-chromium') {
    await page.setViewportSize({ width: 1024, height: 600 })
  }

  await page.goto('/projects/project-e2e')
  await expectContentReachesEnd(page, '.detail-shell__content-surface')

  await page.goto('/inspiration?project_id=project-e2e')
  await expectContentReachesEnd(page, '.inspiration-chat__messages')

  await page.goto('/projects/project-e2e/write?chapter_number=1')
  await expectContentReachesEnd(page, '.writing-workspace__body')
  await expectNoHorizontalOverflow(page)
})

test('账户菜单通过路由进入设置、安全与管理页', async ({ page }) => {
  await setAuthMode(page, 'user')
  await page.goto('/workspace')
  await page.getByTitle('查看阁主菜单').click()
  await expect(page.getByRole('link', { name: /AI 设置/ })).toBeVisible()
  await expect(page.getByRole('link', { name: /账户与安全/ })).toBeVisible()
  await expect(page.getByRole('link', { name: /管理后台/ })).toHaveCount(0)
  await expect(page.getByText('提示词用量', { exact: true })).toHaveCount(0)

  await page.getByRole('link', { name: /AI 设置/ }).click()
  await expect(page).toHaveURL(/\/settings\?tab=llm$/)
  await expect(page.getByRole('dialog', { name: '个人设置' })).toHaveCount(0)

  await page.getByTitle('查看阁主菜单').click()
  await page.getByRole('link', { name: /账户与安全/ }).click()
  await expect(page).toHaveURL(/\/account\/security$/)
  await expect(page.getByRole('heading', { name: '账户与安全' })).toBeVisible()

  await setAuthMode(page, 'admin')
  await page.goto('/workspace')
  await page.getByTitle('查看阁主菜单').click()
  await page.getByRole('link', { name: /管理后台/ }).click()
  await expect(page).toHaveURL(/\/admin$/)
})

test('设置分区支持深链接与浏览器前进后退', async ({ page }) => {
  await setAuthMode(page, 'user')
  await page.goto('/settings?tab=llm')
  await page.getByRole('tab', { name: /记忆检索/ }).click()
  await expect(page).toHaveURL(/\/settings\?tab=embedding$/)
  await expect(page.getByRole('tab', { name: /记忆检索/ })).toHaveAttribute('aria-selected', 'true')

  await page.goBack()
  await expect(page).toHaveURL(/\/settings\?tab=llm$/)
  await expect(page.getByRole('tab', { name: /文本生成/ })).toHaveAttribute('aria-selected', 'true')

  await page.goForward()
  await expect(page).toHaveURL(/\/settings\?tab=embedding$/)
  await expectNoHorizontalOverflow(page)
})
