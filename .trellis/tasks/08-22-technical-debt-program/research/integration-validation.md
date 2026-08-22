# 跨任务集成验证记录

## 任务树与范围

- 8 个子任务均位于 `.trellis/tasks/archive/2026-08/`，`task.json` 状态均为 `completed`，完成日期均为 `2026-08-22`。
- 8 个归档目录均通过 `task.py validate`，子任务 PRD 不再含未勾选验收项。
- `08-22-converge-auth-http-client` 与 `08-22-tighten-frontend-boundary-types` 的 PRD 原先漏勾验收框；对应 validation、research、journal 和提交证据已证明验收完成，本次只修正勾选状态。
- 父任务集成阶段没有修改 `backend/app`、`backend/tests`、`frontend/src`、前端 HTML 或 Vite 配置。

## 前端门禁

最后一个子任务完成后、父任务尚未产生任何产品 diff 时执行：

- `cd frontend && npm run type-check`：通过。
- `cd frontend && npm run test:unit`：43 个测试文件、347 个测试通过。
- `cd frontend && npm run lint`：通过。
- `cd frontend && npm run build`：生产构建与 bundle budget 通过。

非阻塞预警：

- CSS 单文件 `index-*.css` gzip 25.14 KB，高于 24 KB 预警线、低于 26 KB 硬上限。
- JS 总 gzip 580.36 KB，高于 560 KB 预警线、低于 600 KB 硬上限。

## 后端门禁

- `cd backend && .venv/bin/ruff check app tests`：通过。
- Pydantic v2 warnings-as-error 聚焦门禁：22 个测试通过，目标 `PydanticDeprecatedSince20` 告警为零。
- 快速 profile：467 个测试通过、237 个 PostgreSQL 测试跳过、1 个既有失败。
- PostgreSQL profile（Testcontainers `pgvector/pgvector:pg16` 回退）：236 个测试通过、468 个快速测试跳过、1 个既有失败；临时容器已删除，运行后无 pgvector/Testcontainers 容器残留。

完整 profile 没有被表述为全绿，两个失败均早于本技术债计划且不在 8 个子任务改动范围：

1. `test_openapi_inventory_and_operation_ids_preserve_the_baseline`：运行时 88 个 paths，测试基线为 87；同一失败已记录在 `08-22-modernize-pydantic-v2/research/validation.md`。基线最后更新于 2026-07-31，8 个子任务未新增 API 路径或修改该测试。
2. `test_workflow_transition_adapter_maps_ambiguity_cancel_and_failure`：运行时在 `activity.started` 后正确持久化 `activity.ambiguous`，测试仍期望旧的 4 事件序列。生产事件写入来自 2026-08-16 的 `b8ea221`，测试期望来自 2026-07-30；8 个子任务未修改 durable job 事件链。

两套 pytest profile均报告第三方 `passlib` 导入 Python `crypt` 的弃用预警；它不是本次 Pydantic 迁移目标，且没有被静默忽略。

## 技术债回归扫描

以下精确扫描均为零命中：

- `backend/app` 中目标 `@validator`、`@root_validator`、class-based `Config`。
- `frontend/src/api/auth.ts` 中直接 `fetch`、私有 `AbortController`/timer、`authRequest` 和独立错误解析。
- 前端边界类型清单中的 24 个显式 `any`、忽略指令和替代断言。
- 7 个遗留编辑器中的 runtime-options props、字符串数组 emits 和目标显式 `any`。
- `check_and_create_reminders`、`create_reminder`、`get_unresolved_foreshadowings`、`ACTIVE_FORESHADOWING_STATUSES`。
- 活跃前端源码、HTML、Vite 配置与前端 spec 中对 `frontend/src/assets/base.css` 的失效引用；目标文件不存在。

## 未执行与剩余风险

- 父任务未重新执行真实浏览器视觉回归；被删除的 CSS 文件没有样式规则，类型、单测与生产构建覆盖了入口完整性。
- 父任务未连接真实后端执行登录/注册；认证请求、响应头、错误和超时契约由 Vitest 覆盖，子任务已明确记录该限制。
- 父任务 PostgreSQL 集成使用 Testcontainers 回退，没有再次运行外部 `TEST_POSTGRES_URL` 入口；第 1 子任务已分别验证外部服务与容器入口，第 6 子任务已核对实际 PostgreSQL schema。
- 两个既有测试基线漂移、第三方 `crypt` 弃用预警及前端 bundle 软预警仍需独立任务处理；本父任务不扩大范围修复。

## 结论

父计划列出的 8 项技术债均已完成并通过各自相关门禁，跨任务扫描未发现这些债务回归。仓库整体仍有上述明确记录的既有测试基线与软预警，因此本结论不等同于“全仓不存在任何技术债”。
