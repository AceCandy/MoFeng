# 技术设计

## Boundary

Q1 只恢复现有质量命令的事实基线。它不新增发布门禁，也不处理依赖 advisory；R1 在 Q1
全绿后复用这些命令。所有失败先以当前工作树实测为准，再按根因落入对应批次。

```text
重新测量
   |
   +-> pytest 行为/测试隔离修复
   +-> ruff 语义问题 -> import 排序
   +-> Black 纯机械格式化
   +-> 前端静态门 -> Playwright fixture/selector
   |
   v
同一工作树执行完整质量门 -> 独立复核 -> 交给 R1
```

## Backend Strategy

1. 全量 pytest 先保留完整失败摘要。生产行为错误修实现；过时字符串/结构断言改为行为断言；
   依赖本机版本、时钟或外部服务的测试改用隔离 fixture。
2. ruff 先处理 `F`/语法类问题，再单独处理 `I` import 排序。只删除本次确认无调用方的
   符号，不借机重构相邻代码。
3. 行为和静态问题稳定后，对 `app tests` 运行 Black。该批次不修改 Alembic revisions，
   不夹带逻辑变更。
4. mypy 沿用 pyproject 的现有 `files` 列表；最终报告明确为 durable workflow/job scoped。
5. PostgreSQL 语义测试继续使用真实 PostgreSQL。未提供 `TEST_POSTGRES_URL` 时，现有
   Testcontainers fixture 可启动 `pgvector/pgvector:pg16`；SQLite 不能替代该证据。

## Frontend Strategy

1. 先验证 `api:check`、eslint、vue-tsc、Vitest 和 build，避免在浏览器层调试编译错误。
2. Playwright 保留 `workers=1`、`retries=0` 和 desktop/mobile 两个项目。
3. `writing-desk-workflow.spec.ts` 保留对 `ChapterWorkflowPanel` 的 role、`aria-live` 和状态
   heading 契约。实测确认 Playwright locator 会跨 Vue 重渲染重新解析；失败根因是
   `WDWorkspace` 在运行、提交、投影和成功阶段卸载面板。生产装配应覆盖面板已有文案支持的
   全部阶段，不通过改 selector 或放宽断言隐藏缺失 DOM。
4. fixture server 只修正与当前 API/SSE decoder 不一致的响应、事件和路由；生产代码不能为
   旧 fixture 增加兼容分支。
5. 每次失败先检查 browser console、pageerror 和 fixture `unknownRequests`，再判断是 fixture、
   selector 还是产品行为问题。

## Commit And Rollback Shape

- pytest/业务行为修复按根因形成小提交，并运行对应 focused test 后再跑全量。
- ruff 语义清理、import 排序分别提交。
- Black 是单独的纯机械提交，可独立回滚。
- Playwright fixture/测试修复与必要的最小生产装配修复放在同一前端契约提交。
- 任一批次导致既有通过项回归时，先回到上一绿点，不把补丁叠到不明状态上。

## Operational Risks

- 全量 pytest 可能拉取并启动 PostgreSQL Testcontainers；需可用 Docker。
- Playwright 会启动 fixture server 与 Vite；首次安装 Chromium/系统依赖需要网络。
- 所有由测试启动的服务由 runner 管理；异常退出后仍需检查并清理容器与报告目录。
- npm/pip advisory 服务、Trivy、registry、生产 PostgreSQL 副本不属于 Q1 本地完成证据。
