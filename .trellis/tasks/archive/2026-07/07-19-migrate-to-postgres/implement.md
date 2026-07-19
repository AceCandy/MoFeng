# 迁移 PostgreSQL 执行计划

分 4 阶段（对应 4 child），每阶段独立验证、可回滚。parent 不直接实现，由 child 承载。阶段 2（H6 修复）无依赖且无论是否迁移都该修，建议最先做。

## 阶段 2: model 修复（child `02-fix-model-fk-datetime`，无依赖，可最先）

- [ ] `memory_layer.py:43/97/134/170` FK `String(255)` -> `String(36)`
- [ ] `memory_layer.py:84/85/122/157/158/186/187` `DateTime` 加 `timezone=True`
- [ ] 新 alembic 迁移脚本（alter column type + 时区统一）
- 验证：三后端 `alembic upgrade head` 通过 + 既有 pytest 绿 + H6 数据完整性
- 回滚：`git revert` 迁移 + model
- review gate：三件套 review 后 `task.py start`

## 阶段 1: 代码连通（child `01-pg-code-connect`，无依赖）

- [ ] `requirements.txt` 加 `asyncpg`
- [ ] `config.py:223` 白名单加 `postgresql`
- [ ] `config.py` 新增 `postgres_*` 字段 + uri 分支（或复用 `database_url` 透传）
- [ ] `init_db.py:126` CREATE DATABASE dialect 分支（PG 双引号）
- [ ] `init_db.py:121` `pg_database` 查询分支
- [ ] `alembic/env.py:1` docstring 更新
- 验证：`pip install asyncpg` + `DB_PROVIDER=postgresql alembic upgrade head` 空库建表 + 现有 sqlite/mysql 测试绿
- 回滚：`git revert`，mysql/sqlite 分支未动

## 阶段 3: 部署配置（child `03-pg-deploy-config`，依赖 01）

- [ ] `deploy/docker-compose.yml` 新增 postgres service（`profile: postgres`, `postgres:16-alpine`, healthcheck `pg_isready`）
- [ ] app 环境变量加 `POSTGRES_*`
- [ ] volumes 加 `pg-data`
- [ ] `deploy/.env.example` + `backend/env.example` 加 `POSTGRES_*` 段
- 验证：`docker compose --profile postgres up` 建库 + 健康检查 + app 连通 PG
- 回滚：移除 profile，mysql/sqlite compose 不动

## 阶段 4: 数据迁移与验证（child `04-pg-data-migration-verify`，依赖 01/02/03）

- [ ] pgloader 配置脚本
- [ ] 序列 `setval` 同步
- [ ] 数据校对（行数 + 关键表抽样）
- [ ] PG 集成测试 profile（conftest 按 `DATABASE_URL` 切 PG）
- [ ] 4 个静态测试处理 MySQL 方言 `.sql`（改读 alembic 或提供 PG 版）
- [ ] 真机端到端：章节生成 / 评审 / 伏笔 / RAG
- 验证：数据校对一致 + PG 集成测试绿 + 真机关键流程绿
- 回滚：保留 MySQL 原库，切回 `DB_PROVIDER=mysql`

## Review Gate

- 每个 child `task.py start` 前 review 该 child 的 `prd.md` / `design.md` / `implement.md`。
- parent 集成 review：所有 child AC 达成 + 跨 child 验收（prd AC）+ mysql/sqlite 回归不破 + 向量服务行为不变。
- 验证命令（后端）：`cd backend && .venv/bin/python -m pytest -q`（memory + 不依赖外部服务套件）。
- 验证命令（前端）：`cd frontend && npx vitest run`（迁移不涉及前端，回归用）。
- PG 集成：`DATABASE_URL=postgresql+asyncpg://... .venv/bin/python -m pytest -q -m pg_integration`（阶段 4 新增 marker）。

## 顺序建议

阶段 2（H6，独立，无论是否迁移都修）-> 阶段 1（代码连通）-> 阶段 3（部署）-> 阶段 4（数据迁移+验证）。每阶段独立 commit，可单独回滚。
