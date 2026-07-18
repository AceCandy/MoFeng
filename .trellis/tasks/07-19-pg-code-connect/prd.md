# PG 代码连通

## Goal

让 `DB_PROVIDER=postgresql` 可连通后端，`asyncpg` 驱动，`alembic upgrade head` 能在空 PG 库建全表。parent: `07-19-migrate-to-postgres`。

## Requirements

- `requirements.txt` 加 `asyncpg`（H5）
- `config.py:223` db_provider 白名单加 `postgresql`（H1）
- `config.py` 新增 `postgres_*` 字段 + `sqlalchemy_database_uri` 的 postgresql 分支生成 `postgresql+asyncpg://`（H2）；或最小改动复用 `database_url` 透传
- `init_db.py:126` CREATE DATABASE dialect 分支：PG 用双引号 `"{db}"`，MySQL 保留反引号（H3）
- `init_db.py:121` 库存在性查询：PG 改查 `pg_database WHERE datname=:db`（H4）
- `alembic/env.py:1` docstring 更新含 asyncpg（M6）

## Acceptance Criteria

- [ ] `pip install asyncpg` 成功，`DB_PROVIDER=postgresql` 启动后端不报错
- [ ] `alembic upgrade head` 在空 PG 库建全 34 表，无错误
- [ ] 现有 sqlite/mysql 测试全绿（回归不破）
- [ ] mysql/sqlite 分支行为不变（DB_PROVIDER 切换互不影响）

## Notes

- 技术细节见 parent `design.md`（H1-H5、M6）与 `research/dialect-scan.md`。
- 依赖：无。可独立推进。
- `task.py start` 前补 `design.md` + `implement.md`。
