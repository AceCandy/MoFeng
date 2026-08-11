# Q1 规划证据

## 当前质量命令

- 后端 `pyproject.toml`：Black/Ruff 行宽 100；Ruff 选择 `E4/E7/E9/F/I` 并排除
  `alembic/versions`；mypy 仅检查 durable chapter workflow/job 文件。
- 前端 `package.json`：`api:check`、eslint、vue-tsc、Vitest、Vite build/budget 和
  Playwright 均已有脚本，不需新增 runner。
- Playwright：`workers=1`、`retries=0`，desktop Chromium 与 Pixel 7 Chromium 两个项目；
  runner 管理 fixture server（6181）与 Vite（6173）。

## 已确认的浏览器契约

- `writing-desk-workflow.spec.ts` 当前用 `.chapter-workflow` 定位状态面板。
- `ChapterWorkflowPanel.vue` 已提供动态 `role=status|alert`、对应 `aria-live`、
  `aria-atomic` 和状态 heading；Q1 优先改用这些现有语义，不先改生产 DOM。
- fixture 必须匹配当前 API/SSE decoder；未知请求由 fixture stats 暴露，不能给生产代码
  增加只服务旧 fixture 的兼容分支。

## 环境与耗时

- 后端全量 pytest 未设置 `TEST_POSTGRES_URL` 时会通过 Testcontainers 启动
  `pgvector/pgvector:pg16`，需要 Docker，不能用 SQLite 替代 PostgreSQL 语义证据。
- Playwright 首次安装 Chromium/系统依赖需要网络；测试异常后需检查 `test-results`、
  `playwright-report` 和残留 web server。
- pip/npm advisory、Trivy、registry、真实发布 digest 和生产恢复副本属于 R1/部署验收，
  不纳入 Q1 修复范围。
