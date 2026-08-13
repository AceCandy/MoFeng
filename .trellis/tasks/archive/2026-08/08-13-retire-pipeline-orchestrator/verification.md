# 验证记录

## 行为验证

- PostgreSQL HTTP 与 durable workflow 目标集：98 passed。
- 退役后静态、部署及上下文契约目标集：60 passed。
- 独立复核修正后的 HTTP/context/release 回归：20 passed。
- 前端 `novel.spec.ts`：2 passed。

## 静态检查

- Backend Ruff：通过。
- Backend `compileall`：通过。
- Frontend `npm run type-check`：通过。
- Frontend `npm run lint -- --no-fix`：通过。
- `git diff --check`：通过。
- 生产代码、部署配置和 Trellis spec 的旧 orchestrator、runner、start gate、legacy job handler 残留扫描：无结果。

## 独立复核

- 未发现 P1/P2 生产逻辑问题。
- 确认 writer 入口只走 durable compatibility service，worker registry 只注册 `chapter_workflow`。
- 确认旧式 retry 无 durable run 时返回 409，不创建 legacy job。
- 指出的旧规范引用和测试 `if True:` 残留已修复，并完成上述 20-test 回归。

## 未验证与剩余风险

- 未运行整个仓库的全量后端/前端测试，只运行了与退役边界、durable workflow 和前端任务契约相关的目标集。
- 测试仅出现项目已有的 Pydantic、testcontainers 和 passlib 弃用警告。
- 删除不包含数据库迁移；回滚可直接恢复本次提交，既有 trace 表与 migration 保持不变。
