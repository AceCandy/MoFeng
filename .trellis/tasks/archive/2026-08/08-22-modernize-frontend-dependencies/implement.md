# 前端依赖现代化与安全升级执行计划

1. 激活安全修复子任务，保存升级前审计证据，执行非强制安全修复并完成完整前端门禁。
2. 提交并归档安全修复后，激活兼容更新子任务；升级同主版本直接依赖并核对 remaining outdated 清单。
3. 提交并归档兼容更新后，激活 Node/工具链子任务；统一 Node 24 基线，迁移构建测试工具链，并优先用原生 npm scripts 替代单用途 `npm-run-all2`。
4. 提交并归档工具链后，激活框架主版本子任务；逐项迁移 Vue Router、Pinia、marked 等剩余主版本并做聚焦回归。
5. 每个子任务至少运行：
   - `npm audit` 与 `npm audit --omit=dev`；
   - `npm run api:check`；
   - `npm run type-check`；
   - `npm run test:unit`；
   - `npm run lint`；
   - `npm run build`；
   - `git diff --check` 和独立复核。
6. 工具链与框架主版本子任务额外运行 `npm ci`，启动 Vite 做登录、AppShell、写作台编辑器浏览器冒烟，并在结束前关闭服务。
7. 四项完成后激活父任务，重复完整门禁、核对 `npm outdated` 的兼容例外和 bundle budget，记录未验证项与剩余风险后再归档。

## Approval Gates

- 本规划获批后才启动第一个子任务。
- 每个子任务实施前展示该批最终范围；提交前展示 commit 计划并等待批准。
- 不使用 `--force`，不自动 push。

## Integration Verification

- 四个子任务均按安全修复 → 同主版本更新 → Node/工具链 → 框架主版本的顺序形成独立产品提交并归档。
- 最终 `npm ci` 安装 430 个包且漏洞为 0；`npm ls --depth=0`、两种 audit、Vite config 测试、API check、type-check、lint、build 与 bundle budget 均通过。
- 完整单测在机器高负载下默认并发启动 worker 超时；限制为单 worker 后 44 个文件、349 个测试全部通过，且各子任务此前的默认并发完整门禁已通过。
- 最终 bundle 为 JS gzip 545.44 KB / 600 KB、CSS gzip 82.40 KB / 90 KB；框架子任务的登录、AppShell、写作台编辑器浏览器冒烟通过且服务已关闭。
- `npm outdated` 仅剩 TypeScript 5.9.3（受 `openapi-typescript@7.13.0` 的 `^5.x` peer 限制）与 `@types/node` 24.13.3（匹配 Node 24）；独立集成复核通过。

## Not Verified

- 未在 GitHub 托管 runner 上实际执行三个 CI workflow，未构建完整 Docker 镜像，也未进行真实生产部署验证；已核对 workflow、Dockerfile、Node 镜像 manifest 与本地构建契约。

## Remaining Risk

- CI runner 与生产镜像环境仍可能暴露本地未覆盖的系统级差异。
- 未来若为 marked 引入自定义 tokenizer/renderer，需按 marked 18 的 token 契约单独迁移和回归。
