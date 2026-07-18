# 迁移主库到 PostgreSQL

## Goal

将 MoFeng 主业务库从 MySQL/SQLite 双后端扩展为**三后端并存**（mysql / sqlite / postgresql），新增 PostgreSQL 作为可选生产后端，保留 mysql/sqlite 不下线、可回滚。**是新增选项，不是替换。**

## Background

来源：2026-07-19 技术栈审查 + PostgreSQL 迁移深度调研（见 `research/`）。

- 现状：`DB_PROVIDER` 仅 `mysql`/`sqlite`（`backend/app/core/config.py:223` 硬限制），驱动 `asyncmy`+`aiosqlite`。
- 业务层零 `text()` 原生 SQL（全 ORM），baseline migration 用 `with_variant` 跨库适配，dialect 耦合度"中"，集中在入口层 3 文件。
- **现在是迁移成本最低的窗口期**：baseline 仅 1 个版本、业务层零原生 SQL、Enum 列全用 String 存储（规避 PG `CREATE TYPE` 陷阱）。
- 既有技术债 H6（FK 类型 `String(255)` vs `String(36)` 不匹配）**无论是否迁移都该修**。

## Requirements

- `DB_PROVIDER=postgresql` 可连通，`asyncpg` 驱动，`alembic upgrade head` 能在空 PG 库建全表。
- 入口层改造：config（白名单 + uri 分支）、init_db（CREATE DATABASE dialect + pg_database 查询）、requirements（asyncpg）。
- 修复 H6：`memory_layer.py` 4 处 FK `String(255)` -> `String(36)` + 新 alembic 迁移。
- 修复 M1：`memory_layer.py` 7 处 `DateTime` 统一为 `timezone=True`。
- 部署：docker-compose 新增 postgres profile，env 新增 `POSTGRES_*` 配置。
- 数据迁移：MySQL 现有数据可迁至 PG（pgloader），序列同步。
- mysql/sqlite 分支保留，可随时切回（回滚能力）。
- 向量服务（libsql）不动，与主库解耦。

## 非目标（Out of Scope）

- 不替换 mysql 为 PG（新增选项，非切换）。
- 不换 libsql 向量为 pgvector（独立后续工作，见 `design.md`）。
- 不做 JSON->JSONB 优化（M5，可选，不改能跑）。
- 不升级 FastAPI/redis-py 等无关依赖。

## 子任务地图

parent 拥有源需求 + 跨 child AC + 最终集成 review。child 各自 PRD-only，`task.py start` 前补 `design.md` + `implement.md`。子任务间依赖写在此处，非树位置隐含。

| child | 交付物 | 独立验证 | 依赖 |
|---|---|---|---|
| `02-fix-model-fk-datetime` | H6 FK 类型 + M1 DateTime 时区 + 新 alembic 迁移 | 三后端 alembic upgrade head 通过 + 既有测试绿 | 无（**无论是否迁移都该修，可最先做**） |
| `01-pg-code-connect` | config/init_db/requirements 入口层 + asyncpg | `DB_PROVIDER=postgresql` 连通 + alembic upgrade head 建表 | 无 |
| `03-pg-deploy-config` | compose postgres profile + env `POSTGRES_*` | `docker compose --profile postgres up` 建库 + 健康检查 | 01 |
| `04-pg-data-migration-verify` | pgloader 脚本 + 序列同步 + PG 集成测试 profile + 静态测试 dialect 处理 + 真机验证 | 数据校对一致 + 关键流程端到端绿 | 01 / 02 / 03 |

## Acceptance Criteria（跨 child）

- [ ] `DB_PROVIDER=postgresql` 启动后端，`alembic upgrade head` 在空 PG 库建全表，无错误。
- [ ] `memory_layer.py` FK 类型与 `novel_projects.id` 一致（`String(36)`），三后端建表均通过。
- [ ] `memory_layer.py` DateTime 全 `timezone=True`，跨表时间比较语义一致。
- [ ] `docker compose --profile postgres up` 拉起 PG + app，健康检查通过。
- [ ] MySQL 现有数据经 pgloader 迁至 PG，行数 + 关键表抽样校对一致，序列 setval 同步。
- [ ] 新增 PG 集成测试 profile，覆盖 sqlite 盲区（类型严格性 / JSON / 大小写敏感 / 事务隔离）。
- [ ] 4 个读 MySQL 方言 `.sql` 的静态测试提供 PG 版本或改读 alembic。
- [ ] 真机端到端：章节生成 7 步流水线、评审、伏笔追踪、RAG 检索全跑通。
- [ ] mysql/sqlite 分支仍可用（回归不破）。
- [ ] 向量服务（libsql）行为不变。

## Notes

- 优先级：H6（FK 修复）无论是否迁移都该修，可优先独立做。
- 回滚：保留 mysql 分支，配置层不删，数据迁移期保留 MySQL 原库 7-30 天。
- 风险分级见 `design.md`。
- 本 parent 不直接实现，实现由各 child 承载；parent 拥有最终集成 review。
- 关联调研：`research/migration-core-review.md`（核心复核）、`research/dialect-scan.md`（dialect 全量）、`research/models-vector-test-deploy.md`（外围影响面）。
