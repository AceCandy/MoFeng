# 统一 Node 与构建工具链执行计划

1. 更新 `package.json`：Node engine、目标工具链版本、Node 24 类型/tsconfig，删除 `npm-run-all2` 并改用原生串行 build script。
2. 更新 `tsconfig.node.json`、三个 GitHub Actions Node 配置和 Docker 前端构建镜像到 Node 24.15.0。
3. 使用 npm 正常解析锁文件；禁止 `--force` 与 `--legacy-peer-deps`，运行 `npm ls --depth=0` 检查 peer/engine。
4. 运行 `npm ci`、`npm audit`、`npm audit --omit=dev` 与 Vite config 聚焦测试。
5. 运行 API check、type-check、完整单测、lint、build 和 bundle budget，比较上一批 JS gzip 565.09 KB / CSS gzip 82.16 KB。
6. 启动 Vite，使用浏览器冒烟检查登录页、AppShell 与写作台编辑器；结束前关闭服务。
7. 执行 `git diff --check` 和独立复核，记录未验证项、软预警及剩余风险；提交前展示 commit 计划并等待批准。

## Verification

- `npm ci`、`npm ls --depth=0`、`npm audit`、`npm audit --omit=dev`：通过，0 vulnerabilities，无 invalid/peer 冲突。
- Vite config 聚焦测试、`npm run api:check`、`npm run type-check`、`npm run test:unit`、`npm run lint`、`npm run build`：通过；44 个文件、348 个单测通过。
- Vite 8.2.2 构建预算：JS gzip 545.44 KB / 600 KB，CSS gzip 82.40 KB / 90 KB，无软预警。
- `agent-browser`：登录页、AppShell、写作台与真实 TipTap 可编辑区冒烟通过；fixture 未发现未知请求；浏览器和本地服务已关闭，6173/6181 端口已释放。
- `docker buildx imagetools inspect node:24.15.0-slim`：通过，确认 amd64、arm64 等目标 manifest 存在。
- `git diff --check` 与 `task.py validate`：通过。

## Not Verified / Remaining Risk

- 未在 GitHub 托管环境实际运行三个 workflow，也未执行完整 Docker 镜像构建；本地配置、依赖门禁与远端 Node 镜像 manifest 已验证。
- TypeScript 6/7 仍受 `openapi-typescript@7.13.0` 的 TypeScript `^5.x` peer 约束，按已批准决策保持 5.9.3。
- `marked`、Pinia、Vue Router 的主版本升级属于下一子任务，本任务不处理。
