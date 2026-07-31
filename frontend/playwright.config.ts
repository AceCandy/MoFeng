// AIMETA P=Playwright章节工作流浏览器门|R=双视口_受管前端与fixture服务|NR=不包含业务fixture或测试场景|E=config:playwright|X=internal|A=playwright-config|D=playwright,vite|S=process|RD=./README.ai
import { defineConfig, devices } from '@playwright/test'

const frontendPort = 6173
const fixturePort = 6181

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 20_000,
  expect: { timeout: 7_000 },
  reporter: [['list'], ['html', { open: 'never' }]],
  outputDir: 'test-results',
  use: {
    baseURL: `http://127.0.0.1:${frontendPort}`,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    {
      name: 'desktop-chromium',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1440, height: 900 },
      },
    },
    {
      name: 'mobile-chromium',
      use: {
        ...devices['Pixel 7'],
        browserName: 'chromium',
      },
    },
  ],
  webServer: [
    {
      command: 'node scripts/e2e-fixture-server.mjs',
      url: `http://127.0.0.1:${fixturePort}/__e2e/health`,
      env: { E2E_FIXTURE_PORT: String(fixturePort) },
      reuseExistingServer: false,
      timeout: 15_000,
    },
    {
      command: 'npm run dev',
      url: `http://127.0.0.1:${frontendPort}`,
      env: {
        BACKEND_PORT: String(fixturePort),
        BACKEND_PROXY_HOST: '127.0.0.1',
        FRONTEND_ALLOWED_HOSTS: '127.0.0.1',
        FRONTEND_HMR_HOST: '127.0.0.1',
        FRONTEND_HOST: '127.0.0.1',
        FRONTEND_PORT: String(frontendPort),
        VITE_ENABLE_VUE_DEVTOOLS: 'false',
      },
      reuseExistingServer: false,
      timeout: 30_000,
    },
  ],
})
