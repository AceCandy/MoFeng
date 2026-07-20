# P0 安全与数据完整性修复

## Goal

修复审计确认的 5 条 high 级问题（安全漏洞 + 数据完整性），消除默认凭据、越权、静默数据损坏、live 路由 500、死文件引爆点。

## Requirements

### H1 foreshadowing 6 端点 IDOR（backend/app/api/routers/foreshadowing.py:84）
- 6 端点未校验项目归属，越权读他人伏笔 + 跨项目篡改状态（上轮"越权404"的遗漏）
- 修法：5 个前端无调用的死端点删除（与 P1 协同）；保留的 list 端点补 `ensure_project_owner`；service 层补 user_id
- 需先确认 foreshadowing 功能启用状态（list 端点前端 novel.ts:698 在用）

### H2 analytics_enhanced.py 死文件（backend/app/api/routers/analytics_enhanced.py:18）
- 509 行未注册 + import 三个不存在的 service，注册即 ImportError
- 修法：整文件删除

### H3 默认管理员密码三处硬编码（deploy/.env.example:77）
- `ChangeMe123!` 在 .env.example + docker-compose + config.py 三处兜底 + 3 处文档泄露
- 修法：.env.example 改占位符；docker-compose 改 `:?` 强制；config.py 去默认或 assert 校验；清理 3 处泄露

### H4 finalize_chapter 静默数据损坏（backend/app/services/finalize_service.py:158）
- 持有 DB 会话跨 4 次 LLM + 异常被吞，`success=True` 但记忆/状态/快照全空 + 连接池独占
- 修法：LLM 调用不持有写事务；内层 except 不静默；success 反映真实状态；缩短 session 持有

### H5 consistency_service 必 500（backend/app/services/consistency_service.py:347）
- async 路径用 sync `Session.query` 抛 MissingGreenlet，`/api/review/consistency` 必崩
- 修法：sync query 改 `await session.execute(select(...))`；补路由集成测试

## 约束

- 不改变对外正常行为（除修复漏洞本身）
- 每条修复补测试覆盖
- 越权统一抛 404（与审计 #14 一致）

## Acceptance Criteria

- [ ] H1: 保留端点补归属校验，越权返回 404，补测试
- [ ] H2: analytics_enhanced.py 删除，应用启动正常
- [ ] H3: 默认密码三处消除，docker-compose `:?` 强制，assert_production_security 校验，3 处泄露清理
- [ ] H4: finalize 失败时 success=False（或明确部分失败），不静默；DB session 不跨 LLM 长持有；补测试
- [ ] H5: /api/review/consistency 不再 500，补集成测试
- [ ] 后端 pytest 全绿 + 前端 vue-tsc/vitest/eslint/build 全绿
- [ ] 独立语义化提交

## 来源

审计报告 `docs/audit-governance-2026-07-19.md` H1-H5
