# P0 技术设计

## H1 foreshadowing 越权修复

### 现状
foreshadowing.py 6 端点（create/list/resolve/reminders/dismiss/analysis）仅 `Depends(get_current_user)`，未调 `ensure_project_owner`。ForeshadowingService 方法不接收 user_id，纯按 project_id/foreshadowing_id 操作。

### 设计
1. **启用状态**：list 端点前端 `novel.ts:698` 在用 -> 保留并补校验。5 个死端点（create/resolve/reminders/dismiss/analysis）前端无调用 -> 删除（消除越权写口）。
2. **list 端点**：路由层先 `await novel_service.ensure_project_owner(project_id, current_user.id)`（越权抛 404，与审计 #14 一致），再调 service。
3. **service 层**：get_foreshadowings 不需改（路由层已校验归属，service 按 project_id 查即安全）。
4. **5 死端点删除**：连带删 ForeshadowingService 中无其他引用的对应方法（create_foreshadowing/resolve_foreshadowing/get_active_reminders/dismiss_reminder/analyze_foreshadowings），需 codegraph_callers 确认。

### 决策
- 5 死端点删除而非补校验保留（无前端调用 + 越权写口，删除最安全）。

## H2 analytics_enhanced.py 删除

直接 `git rm backend/app/api/routers/analytics_enhanced.py`。routers/__init__.py 无 import（审计确认）。删除后启动验证。

## H3 默认管理员密码

### 设计
1. `deploy/.env.example:77` -> `ADMIN_DEFAULT_PASSWORD=your-admin-password-change-me`（占位符）
2. `deploy/docker-compose.yml:23` -> `${ADMIN_DEFAULT_PASSWORD:?ADMIN_DEFAULT_PASSWORD must be set}`（与 SECRET_KEY 一致强制）
3. `backend/app/core/config.py:71` -> 保留 Field 但扩展 `assert_production_security`：校验 admin_default_password 非默认值（复用 `_WEAK_SECRET_KEYS` 机制），生产环境用默认值启动即 assert 失败
4. 清理泄露：`backend/env.example:37`、`deploy/scripts/deploy_docker.sh:155`、`docs/DEPLOYMENT.md:223` 改占位符
5. `init_db.py:51` 用 admin_default_password 创建管理员逻辑保留，config 校验保证非默认

### 测试
- assert_production_security 在默认密码时抛错
- init_db 用配置密码创建管理员

## H4 finalize_chapter 静默数据损坏

### 现状
finalize_service.py:187-256 try 块内 4 次 LLM 调用后才 commit。内层 `_update_*` `except Exception: return None` 吞异常。success=True 但快照字段可能全 None。

### 设计
1. **解耦 LLM 与 DB 事务**：短事务完成必要 DB 读 -> commit/释放；4 次 LLM 调用在事务外（不持有写 session）；结果拿到后新开短事务写快照 -> commit。
2. **内层不静默**：`_update_*` 返回结果或抛出，外层聚合。LLM 失败时 `result['success']=False` 并记录失败项。
3. **success 严格语义**：success=True 当且仅当核心字段（global_summary/character_states/plot_arcs/chapter_summary）至少有有效值写入；部分失败加 `partial_success` 字段。
4. **连接池**：LLM 调用不持有 session -> 不独占连接。

### 决策
- 最小化改动：保持 finalize 流程逻辑，只改事务边界 + 异常处理 + success 语义，不重写整个流程。
- 部分失败：用 partial_success + 严格 success。

### 测试
- LLM 超时/503 时 finalize 返回 success=False 或 partial_success，不静默
- 成功路径快照字段非空
- mock 验证 commit 时机（LLM 调用前已 commit 读事务）

## H5 consistency_service async 修复

### 现状
consistency_service.py:347-401 `_get_check_context` 用 `self.db.query(...)` 同步 API，async 路径抛 MissingGreenlet。self.db 是 AsyncSession 的 sync_session。

### 设计
1. `_get_check_context` 改 `await self.session.execute(select(...))` + `.scalars().first()/.all()`
2. `self.db` -> `self.session`（统一 AsyncSession）
3. 调用方 `pipeline_orchestrator.py:3162` / `review.py:78` 的 sync_session 传递改为直接传 AsyncSession
4. 补 `POST /api/review/consistency` 集成测试

### 测试
- /api/review/consistency 不再 500，返回正常结构
- _get_check_context 各分支查询正确

## 测试策略
- 每条 H 补单元/集成测试
- 后端 pytest 全绿（含新测试）
- H1-H5 均后端，但仍跑前端四件套确认无回归

## 回滚
- 每条 H 独立 commit，可单独 revert
- H3 配置改动影响部署：docker-compose `:?` 强制要求部署方设密码，需在 DEPLOYMENT.md 说明
