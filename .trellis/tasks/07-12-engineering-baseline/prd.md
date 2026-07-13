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

## Progress

已完成并落盘：#15 Alembic（`dd7c65e`）/ #16 章节并发唯一约束 / #17 验证码下沉 Redis / #18 Celery engine 复用 / #19 .gitignore / #20 ESLint 分层门禁+CI（`500741d`）/ #21 鉴权收敛 http.ts / #23 OpenAPI codegen / #24 client.spec。验证依据：后端 pytest 191 + 前端 vitest 120。

**#22 按风险切三 slice 推进（见 `design.md` / `implement.md`），任务已 `task.py start`（in_progress）**：
- ✅ **Slice A `cleanVersionContent` 去重**（已完成 + 验证绿）：删 5 处逐字副本（WritingDesk/WDWorkspace/WDVersionDetailModal/VersionSelector/ChapterContent），统一 `import { cleanVersionContent } from '@/utils/chapter'`。5 副本与权威版逐行等价（已比对）。验证：`vue-tsc --noEmit` exit 0 + `vitest run` 120/120 绿（含 uiAuditRegression 34 / wdWorkspaceLockedChapter 10 / chapterDraftFinalizeStatic 8）+ ESLint 0 error（7 warning 均为 pre-existing 分层越界，非本次引入）。diff +5/−204。**Acceptance 第 4 项后半句「cleanVersionContent 仅 utils 一处定义」已达成。**
- 🔄 **Slice B** WDWorkspace composable 抽取（4 个，每会话 1 个）：✅ `useEditChapterModal` 已抽出 → `composables/useEditChapterModal.ts`（90 行），WDWorkspace 净 −31 行，vue-tsc/vitest 120 绿；⏳ 剩 `useVersionResolver`/`useChapterStatus`/`useAiMenu`。契约见 `design.md` Slice B 表。
- ⏳ **Slice C** 乐观更新规范化（TanStack 三段式）—— 前置 research 定位直接突变缓存的 mutation。

> Slice B/C 未完成，Acceptance 第 4 项前半句「5 大组件 <500 行」仍需跨会话达成。
