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

