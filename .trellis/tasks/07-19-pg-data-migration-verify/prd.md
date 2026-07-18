# PG 数据迁移与验证

## Goal

MySQL 现有数据迁移至 PG，新增 PG 集成测试 profile，处理静态测试 dialect 耦合，真机端到端验证。parent: `07-19-migrate-to-postgres`。

## Requirements

- pgloader 配置脚本（MySQL -> PG，自动类型映射）
- 序列 `setval` 同步（自增列迁移后）
- 数据校对（行数 + 关键表抽样）
- PG 集成测试 profile（conftest 按 `DATABASE_URL` 切 PG，覆盖 sqlite 盲区：类型严格性/JSON/大小写/事务隔离）
- 4 个静态测试处理 MySQL 方言 `.sql`（`test_tts_model_configuration` / `test_chapter_generation_trace_service` / `test_prompt_database_migration_static` / `test_dev_script_static`）：改读 alembic 或提供 PG 版
- 真机端到端：章节生成 7 步流水线 / 评审 / 伏笔追踪 / RAG 检索

## Acceptance Criteria

- [ ] MySQL 数据经 pgloader 迁至 PG，行数 + 关键表抽样校对一致
- [ ] 序列 setval 同步，新插入 id 连续不冲突
- [ ] PG 集成测试 profile 跑通，覆盖 sqlite 盲区
- [ ] 4 个静态测试在 PG 下绿
- [ ] 真机端到端关键流程全跑通
- [ ] 向量服务（libsql）行为不变

## Notes

- 技术细节见 parent `design.md`（数据迁移方案/验证策略）与 `research/models-vector-test-deploy.md` 第 3 节。
- 依赖：`01-pg-code-connect` / `02-fix-model-fk-datetime` / `03-pg-deploy-config`（H6 必须先修，否则 PG 建表失败）。
- `task.py start` 前补 `design.md` + `implement.md`。
