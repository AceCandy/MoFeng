# 工程基线补齐（Alembic/分层门禁/鉴权收敛/并发）

## Goal

前后端工程纪律 + 可靠性补齐。从"单人能跑"过渡到"团队可维护、上线可靠"。前端数据层工业级但执行漂移（分层越界、鉴权重复、无 codegen）；后端缺迁移工具、并发与多进程兼容有坑。

来源：2026-07-12 多专家审查报告（`docs/mofeng-audit-report-2026-07-12.html`）字节前端、快手前端总监、阿里后端、滴滴架构师。

## Requirements

- 后端引入 Alembic，冻结当前 schema 为 baseline 迁移，废弃 `create_all` + 手写 ALTER。
- 章节并发安全：`(project_id, chapter_number)` 唯一约束 + 生成并发限流。
- 验证码/限频、SSE 状态、Celery engine 等"多进程/轮询 DB"问题下沉 Redis / 改 Pub/Sub / 复用 engine。
- 前端分层门禁：ESLint `no-restricted-imports` 禁止组件直连 `@/api` + 前端 CI（type-check/vitest/budget）。
- 鉴权 401 / Authorization 收敛到 `api/http.ts` 单一拦截器。
- 拆巨型组件、乐观更新规范化、删重复逻辑；补 i18n、前端监控、OpenAPI codegen；清 AIMETA。

## 子任务（追踪于会话 TaskList）

- 后端：#15 引入 Alembic；#16 章节并发安全（唯一约束+限流）；#17 验证码/限频下沉 Redis；#18 SSE 改 Pub/Sub + Celery engine 修复；#19 生产部署加固 + 代码卫生。
- 前端：#20 分层门禁 ESLint+CI；#21 鉴权收敛 http 层；#22 拆巨型组件 + 乐观更新规范化 + 删重复；#23 i18n + 监控 + codegen + 清 AIMETA；#24 性能/卫生/测试。

## Acceptance Criteria

- [ ] `alembic upgrade head` 可从空库建到当前 schema；`_ensure_schema_updates` 可废弃。
- [ ] CI 拦截 components/views 直连 `@/api`；全局 `status === 401` 仅 `http.ts` 一处。
- [ ] 并发生成同一章不产生重复行；验证码多 worker 一致；SSE 不再每秒查 DB。
- [ ] 5 个最大前端组件拆至 <500 行；`cleanVersionContent` 仅 `utils` 一处定义。

## Notes

- 建议排在路线图**阶段一止血 + 阶段二工程化（2-4 周）**。
- 本任务为审查后的**整理产出，未进入实现**。属复杂任务，实现需 `task.py start` 后补 `design.md` / `implement.md`。
- 关联报表：第叁/肆章（前端）、第伍/陆章（后端）、第贰章 P0 看板·工程基线。
