# 前端框架主版本升级执行计划

1. 将 marked 升级到 18.0.10，正常更新锁文件；在现有 `ChapterEvaluationPanel` 测试补充 Markdown 渲染与危险 HTML 净化断言，运行该聚焦测试和 type-check。
2. 将 Pinia 升级到 4.0.3，并直接添加 `@vue/devtools-api@8.2.1`；运行使用真实 Pinia 的 API/Query 聚焦测试及 type-check。
3. 将 Vue Router 升级到 5.2.0，把 `router.beforeEach` 改为返回值守卫；运行 type-check，并通过浏览器验证未登录重定向、登录恢复、AppShell 与写作台导航。
4. 运行 `npm ci`、`npm ls --depth=0`、`npm audit`、`npm audit --omit=dev`，禁止 peer 绕过参数。
5. 运行 Vite config 聚焦测试、API check、type-check、完整单测、lint、build 和 bundle budget，记录与当前 JS gzip 545.44 KB / CSS gzip 82.40 KB 的差异。
6. 使用现有 E2E fixture 与独立浏览器 session 冒烟登录、AppShell、写作台编辑器；关闭浏览器和服务并确认端口释放。
7. 运行 `npm outdated`、`git diff --check`、Trellis validate 和独立只读复核；记录合理例外、未验证项与剩余风险。
8. 展示提交计划并等待用户确认；提交后归档子任务，再执行父任务集成验收。

## Verification

- `npm ci`、`npm ls --depth=0`、`npm audit`、`npm audit --omit=dev`、Vite config 测试、`npm run api:check`、`npm run type-check`、`npm run lint`、`npm run build` 均通过，audit 为 0。
- 完整单测 44 个文件、349 个测试通过；marked 聚焦 2 个测试、Pinia 聚焦 4 个文件 46 个测试通过。
- bundle budget 通过：JS gzip 545.44 KB / 600 KB，CSS gzip 82.40 KB / 90 KB，与升级前一致。
- 浏览器验证未登录重定向、登录页、AppShell、项目库、写作台和可编辑 ProseMirror 均通过；无页面错误、无 fixture 未知请求，6173/6181 端口已释放。
- `npm outdated` 仅剩 TypeScript 5.9.3（`openapi-typescript@7.13.0` peer 为 `^5.x`）与 `@types/node` 24.13.3（匹配 Node 24 运行时）；`git diff --check`、Trellis validate 和独立复核通过。

## Remaining Risk

- marked 18 的自定义 tokenizer/renderer 破坏性变化不适用于当前仅调用 `parse`/`setOptions` 的路径；未来若引入扩展需重新核对其 token 契约。
