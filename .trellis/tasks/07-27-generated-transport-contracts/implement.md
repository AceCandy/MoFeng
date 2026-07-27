# Generated Transport Contracts Implementation Plan

## Steps

- [ ] 审计目标 endpoint 的 `response_model`、Pydantic DTO、operation id 和 OpenAPI 可生成性。
- [ ] 新增安全、确定性的 OpenAPI export command 与 artifact normalization test。
- [ ] 将 `openapi-typescript` 作为显式 pinned devDependency，加入 generate/check scripts。
- [ ] 生成 artifact，建立 API boundary aliases 和 SSE runtime decoder。
- [ ] 按 workflow/job/chapter/admin 顺序替换手写 DTO，保留必要 domain mapper。
- [ ] 加 CI drift gate 和 schema semantic diff review 输出。
- [ ] 更新 type-safety/cross-layer specs，删除本任务产生的 compatibility aliases。

## Validation

```bash
cd frontend
npm run api:generate
npm run api:check
npm run type-check
npm run test:unit
npm run lint
```

后端运行 OpenAPI/export contract tests。生成前后检查 `git diff`，确认没有环境信息进入 artifact。

## Rollback

- backend schema、OpenAPI artifact 和 generated types作为一个发布单元回退。
- 兼容 alias 可以临时恢复 consumer import，但不得恢复字段复制。
- codegen gate 可在工具故障时固定到上一 artifact，不能允许未检查 schema 漂移合入。
