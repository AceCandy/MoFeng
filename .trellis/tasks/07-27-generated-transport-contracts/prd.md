# 生成 Transport Contracts

## Goal

以 FastAPI OpenAPI 为 HTTP wire schema 的唯一事实源，确定性生成 TypeScript 类型并建立 drift gate，删除前端 API 模块之间以及前后端之间的手工 DTO 镜像。

## Background

- `Chapter` 在 `frontend/src/api/novel.ts:309-335` 和 `frontend/src/api/admin.ts:66-85` 重复定义。
- 项目规范当前明确承认前端类型是手工镜像，字段变更需要多处同步：`.trellis/spec/frontend/type-safety.md`、`.trellis/spec/guides/cross-layer-thinking-guide.md`。
- `openapi-typescript` 已出现在 lockfile，但 package scripts/devDependencies 尚未形成可执行 codegen 与 CI gate。

## Requirements

- CONTRACT-1：提供不启动 server/lifespan 的确定性 FastAPI OpenAPI export 命令，输出不含环境密钥或机器路径。
- CONTRACT-2：使用固定版本 `openapi-typescript` 生成受版本控制的 TypeScript artifact。
- CONTRACT-3：后端所有纳入迁移的 endpoint 使用显式 Pydantic request/response model、稳定 operation id 和可生成的判别字段。
- CONTRACT-4：generated wire types 是 HTTP DTO 的唯一 TS 定义；`novel.ts`、`admin.ts`、`tasks.ts` 不得重声明相同 schema。
- CONTRACT-5：手写 `src/api/*` 只拥有 HTTP 调用与明确 domain mapping，不修改字段语义或私自扩展 wire type。
- CONTRACT-6：SSE JobEvent envelope 在 OpenAPI components 中可生成，入口使用 `unknown` + runtime decoder 校验 schema version/type/payload。
- CONTRACT-7：CI 重导出、重生成并检查 clean diff；schema 或 generated artifact 漂移直接失败。
- CONTRACT-8：生成物变更必须经过语义 diff review；breaking change 在兼容窗口内有旧字段/adapter。

## Dependencies

- 在 durable Chapter workflow API 稳定后实施，避免反复生成未定稿 contract。
- 必须在 WritingDesk statechart 前完成，让 machine 直接消费生成类型。

## Acceptance Criteria

- [ ] 单条命令从当前 FastAPI app 导出 schema 并生成同字节 TypeScript artifact，重复运行 git diff 为空。
- [ ] 修改一个后端 Chapter/JobEvent schema 而不更新生成物时 CI 失败。
- [ ] `novel.ts` 与 `admin.ts` 不再重复声明 Chapter wire DTO，API/query/component type-check 通过。
- [ ] SSE decoder 拒绝未知/畸形 payload，并对可忽略的新 schema version 有明确策略。
- [ ] OpenAPI artifact 和生成物不包含 secret、真实连接串、测试账号或本机绝对路径。
- [ ] 相关前端规范从“手工镜像”更新为 generated transport + domain mapping contract。

## Out Of Scope

- 不自动生成 Vue Query hooks、组件 props 或 UI domain model。
- 不替换现有 `src/api/http.ts`、auth、timeout 和错误归一化。
- 不为未迁移的动态/文件流 endpoint 强行生成不准确类型。
