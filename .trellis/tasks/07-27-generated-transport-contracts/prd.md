# 生成 Transport Contracts

## Goal

以 FastAPI OpenAPI 为 HTTP wire schema 的唯一事实源，建立确定性导出、固定版本 TypeScript 生成、运行时 SSE 解码和 CI 漂移/破坏性变更门禁，消除当前 workflow、job、chapter、admin 边界上的手工 DTO 镜像。

## Background

- 当前 `app.openapi()` 生成 OpenAPI `3.1.0`，包含 86 个 paths、110 个 operations 和 92 个 schemas；operationId 当前无缺失或重复，但全仓没有显式 `operation_id=` 或应用级 `generate_unique_id_function`，稳定性依赖 FastAPI 默认实现。
- FastAPI `0.110.0` 的默认 operationId 使用函数名、path 和未排序 method set 的首项；重复 ID 只产生 warning，不会阻止 schema 生成。首批切换必须保持当前 110 个 ID 不变，不能把工具链接入变成未声明的 API rename。
- `app.openapi()` 本身不进入 lifespan，因此不执行数据库 readiness、Prompt preload 或 shutdown；但导出过程仍需固定必填配置与 metadata，避免读取本机环境形成漂移。
- `BackgroundTaskResponse` 和 `BackgroundTaskSnapshotResponse` 已进入 OpenAPI components；`BackgroundTaskEventResponse` 和 `BackgroundTaskCursorResetResponse` 尚未进入。
- `frontend/src/api/novel.ts` 与 `frontend/src/api/admin.ts` 重复定义不同形状的 `Chapter`，导致 `frontend/src/queries/novel.ts` 返回 `Chapter | AdminChapter`。
- `frontend/src/api/tasks.ts` 手写 task/snapshot/event/reset DTO，并在 SSE `message.data` 上直接使用类型断言；外部 JSON 没有 runtime schema/version 校验。
- `openapi-typescript` 仅残留在 `frontend/package-lock.json`，实际锁定 `7.13.0`，但 `package.json` 没有声明依赖或 scripts。
- 当前唯一 CI workflow 只监听 `frontend/**`；后端 router/schema 变更不会触发跨层 contract 检查。

## In Scope

### Canonical artifacts and tooling

- 提交 canonical OpenAPI artifact：`backend/openapi.json`。
- 提交唯一 generated TypeScript artifact：`frontend/src/api/generated/schema.d.ts`。
- 提供一条生成命令和一条只读检查命令；重复执行必须得到相同字节。
- 将 `openapi-typescript` 精确固定为 `7.13.0`。
- 将 `oasdiff` 精确固定为 `1.26.1`，用于 PR base 与当前 OpenAPI artifact 的 semantic breaking gate。

### Backend contract coverage

- 为整个 FastAPI app 建立路由注册顺序/hash seed 无关、首批与现有值兼容的稳定 operationId，并对全部 operations 强制唯一；未来内部函数改名通过显式保留旧 ID 完成兼容 cutover。
- 审计并修正以下首批普通 JSON 边界的显式 Pydantic request/response model：
  - `backend/app/api/routers/writer.py` 的 Chapter workflow start/snapshot/command 以及 Chapter JSON 响应；
  - `backend/app/api/routers/tasks.py` 的 list/detail/snapshot 与 SSE data payload；
  - `backend/app/api/routers/chapter_projections.py` 的 operation/rollout JSON 响应；
  - `backend/app/api/routers/novels.py` 的 Chapter JSON 响应；
  - `backend/app/api/routers/admin.py` 的普通 JSON 管理接口。
- 为 snapshot/task/reset SSE data payload 增加 `schema_version: Literal[1]`，并显式注册对应 OpenAPI components。

### Frontend adoption

- 将 `frontend/src/api/novel.ts`、`admin.ts`、`tasks.ts` 以及相应 query consumers 的首批 wire DTO 替换为 generated aliases。
- 删除 `Chapter | AdminChapter` 和重复字段声明；同一 backend `Chapter` schema 只对应一个 TypeScript wire type。
- SSE decoder 以 `unknown` 为输入，验证版本、outer event kind、cursor/reset 字段及 reducer 所依赖的 task/snapshot 字段后才交给 query cache 或后续 statechart。
- 保留现有 `src/api/http.ts`、认证、timeout、错误归一化、Vue Query cache 和 polling fallback。

### CI and governance

- 新增独立 transport-contract workflow，同时监听相关 backend schema/router/app、canonical artifacts、frontend API/generated/tooling 和 workflow 文件。
- CI 运行 backend OpenAPI contract tests、`api:check`、前端 decoder/ownership tests、type-check 和 lint。
- PR 上对 base/current `backend/openapi.json` 执行 `oasdiff breaking --fail-on ERR`；ERR 阻断，WARN/INFO 保留为 review 输出。
- 更新项目 specs，将首批迁移域从“手工镜像”切换为 generated transport + domain mapping 规则。

## Requirements

- CONTRACT-1：`python -m app.openapi_export` 不启动 server/lifespan、不连接数据库、不执行 bootstrap，并以满足 Settings 校验的固定非敏感 sentinel 配置完成导出。
- CONTRACT-2：exporter 使用 canonical JSON 排序、固定 metadata、UTF-8 和单一末尾换行；`--check` 只比较字节并在漂移时非零退出。
- CONTRACT-3：首批 operationId 精确复现现有 FastAPI 单 method 命名，只将 method 选择改为确定性并加入 fail-closed 唯一性检查；函数改名属于显式 contract change，若仅为内部重构必须先固定旧 `operation_id`。
- CONTRACT-4：首批普通 JSON endpoint 必须使用显式 Pydantic request/response model；动态 dict、文件流和不准确 schema 不得为追求覆盖率而伪装成强类型。
- CONTRACT-5：generated artifact 是首批 HTTP DTO 的唯一字段定义；API module 只允许从 generated `components`/`operations` 建 alias，不得复制 object shape。
- CONTRACT-6：`openapi-typescript` 自动生成的 DO NOT EDIT header 保持原样；不得增加会破坏其 `--check` 字节比较的 post-process。
- CONTRACT-7：snapshot/task/reset 三种 state-bearing payload 包含 `schema_version=1`；SSE 与 HTTP snapshot 都通过同一 runtime decoder，未知版本或畸形数据不得进入 cache/reducer/statechart，必须触发同 scope snapshot resync 或受控错误/polling fallback。
- CONTRACT-8：OpenAPI 只描述 `text/event-stream` 媒体类型和 data payload components，不把 SSE `id/event/data` 文本 framing 伪装成 JSON response body。
- CONTRACT-9：CI 同时执行 byte drift gate 与 semantic breaking gate；前者不能替代后者，后者也不能替代生成物一致性检查。
- CONTRACT-10：schema、generated artifact 和 aliases 作为一个发布单元；字段删除、required 收紧或类型变窄必须在兼容窗口内保留旧字段/adapter。
- CONTRACT-11：artifact 和 CI output 不得包含 secret、真实数据库连接串、测试账号、本机绝对路径或私有 event/activity payload。
- CONTRACT-12：新增 focused guard，阻止已迁移 schema 在 `src/api/*` 中重新出现结构化手写声明。
- CONTRACT-13：类型迁移遵循 expand -> cutover -> contract：先增加 generated artifact/同名 alias，再逐域切换 consumers，确认无旧引用后删除字段副本；同名 alias 是 source compatibility adapter，wire behavior 不双写也不变更。

## Acceptance Criteria

- [x] AC-1：`npm run api:generate` 顺序写出两个 canonical artifacts；backend exporter 使用原子替换，任一步失败均非零退出并允许留下可见的“backend 已更新/frontend 尚旧”diff，连续成功两次后 `git diff` 为空，`npm run api:check` 全程只读且成功。
- [x] AC-2：backend tests 证明 OpenAPI 导出不调用 lifespan/DB，输出重复字节一致，且不包含配置 sentinel、连接串或当前工作目录。
- [x] AC-3：全部 OpenAPI operations 都有唯一 operationId；接入前后当前 110 个排序 ID 的 golden SHA256 均为 `18f9fcb2944270ab91d2fdbf3e4e552b891e4e56d7925cb9079484ef12c60aa2`，method set/hash seed/注册顺序变化不改变 ID，人工构造多 method route 或重复 ID 会失败；显式旧 ID 能保护内部函数改名。
- [x] AC-4：OpenAPI components 包含 `BackgroundTaskResponse`、`BackgroundTaskSnapshotResponse`、`BackgroundTaskEventResponse`、`BackgroundTaskCursorResetResponse`，三种 SSE data payload 都要求 `schema_version=1`。
- [x] AC-5：`novel.ts` 与 `admin.ts` 不再重复声明 Chapter，`queries/novel.ts` 不再返回 `Chapter | AdminChapter`；`tasks.ts` 不再手写已迁移 task/event shapes。
- [x] AC-6：decoder tests 覆盖合法 SSE snapshot/task/reset、HTTP snapshot、畸形 JSON shape、未知 schema version 和未知 outer event；无效数据不会更新 cache/reducer。
- [x] AC-7：仅修改 backend in-scope schema/router 而不更新 artifacts 时 transport CI 失败；更新 artifacts 后 byte drift gate 通过。
- [x] AC-8：从已有 baseline 删除 response 字段或新增 required request 字段时 `oasdiff` gate 非零；首次引入 artifact 时只建立 baseline，并明确输出 bootstrap 状态。
- [x] AC-9：artifact 不使用 oasdiff 尚不支持的 `$dynamicRef`/`$dynamicAnchor` 或 `components.pathItems`；若未来出现，contract test 直接失败而非默默漏检。
- [x] AC-10：相关 backend focused tests、frontend unit tests、type-check、lint、ruff、black check、mypy/compile check 全部通过，且独立复核无未解释的 contract drift。
- [x] AC-11：frontend/backend/cross-layer specs 已更新，后续新增或修改首批 DTO 只改 Pydantic schema、重生成 artifact，不再复制 TypeScript fields。
- [x] AC-12：迁移测试证明原有 exported type names 和 HTTP field names 保持不变；每个域完成 alias cutover 后无旧结构声明/旧 import，且删除旧声明前所有 consumers 已通过 type-check。

## Compatibility And Dependencies

- durable Chapter workflow 已完成并稳定，满足本任务前置依赖。
- 本任务必须先于 `07-27-writing-desk-statechart` 完成，statechart 只消费已验证的 generated wire types/SSE decoder。
- 首次应用级 generator 必须保持当前 110 个 operationId 值不变。后续函数重命名先通过显式旧 ID adapter 保持兼容；真正的 ID rename 按 expand/cutover/contract 单独批准并由 semantic gate 阻断未兼容变更。
- `schema_version` 是 SSE/HTTP snapshot payload 的 additive field；旧客户端可忽略，新客户端必须验证。

## Out Of Scope

- 不自动生成 Vue Query hooks、HTTP client、组件 props 或 UI domain model。
- 不替换 `src/api/http.ts`、认证、timeout、错误归一化或 polling fallback。
- 不迁移 `updates.py` 的动态 dict、`analytics.py` 缺少 decorator response model 的接口、文件/下载流或 `novels.py` 的业务 SSE framing。
- 不把全部 legacy `any`、全部 API domain 或全部 UI model 纳入本次迁移；只清理本任务触及且属于首批 contract 的声明。
- 不进行数据库 schema/data migration，不改变 workflow/job/chapter 业务状态机，不生成 SDK。
- 不引入在线 schema 服务；CI 只使用仓库 artifacts 和校验和固定的本地 CLI binary。
