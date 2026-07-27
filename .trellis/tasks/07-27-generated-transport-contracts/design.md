# Generated Transport Contracts Design

## Pipeline

```text
FastAPI app.openapi()
  -> deterministic openapi.json
  -> pinned openapi-typescript
  -> frontend/src/api/generated/openapi.d.ts
  -> small domain aliases/mappers
  -> src/api methods -> queries -> UI/statechart
```

export command 只构造 app 并调用 `openapi()`，不进入 lifespan，不连接 DB，不执行 bootstrap。对 schema keys 进行稳定排序并固定 OpenAPI metadata，避免无意义 diff。

## Type Ownership

- generated file 不手改。
- API module 可以导出可读 alias，例如 `type Chapter = components['schemas']['ChapterRead']`，但不得复制字段。
- 只有 UI 确实需要不同 shape 时才建立 mapper；mapper 输入/输出都有类型和测试。
- domain model 不直接泄露 `paths` 索引细节到所有组件，集中在 API contract boundary。

## SSE

FastAPI 普通 OpenAPI 不描述每个 event-stream frame。后端仍用 Pydantic 定义 `JobEventEnvelope` 判别联合，并把 schema 注册到 OpenAPI components。前端生成静态 type 后，在 `api/events` 单一入口执行最小 runtime validation；失败事件不进入 statechart，并触发 snapshot resync/安全错误。

## CI

脚本建议：

- `backend ... export-openapi`
- `frontend npm run api:generate`
- `frontend npm run api:check`：在临时/工作树重生成后 `git diff --exit-code`。

CI review 输出 schema semantic diff 摘要；artifact 本身提交仓库，开发和生产构建不依赖在线 backend。

## Migration

按 domain 迁移：先 workflow/job/chapter，再 admin 引用。兼容 alias 让 consumer 分批替换，最后删除重复 interface。禁止同时保留两个同名但不同 shape 的 `Chapter`。

## Rollback

generated artifact 与 backend schema 在同一 commit/版本发布。回滚两者一起回退；后端在兼容窗口接受/返回旧字段，不能只回滚前端 artifact。
