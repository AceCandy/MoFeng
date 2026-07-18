# PG 代码连通 执行计划

design 见同目录 `design.md`。分 3 阶段，每阶段独立验证。所有改动为入口层新增分支，mysql/sqlite 路径不动。

## 前置确认

- [ ] 02 已归档：`memory_layer.py` FK `String(36)` + DateTime `timezone=True` + migration `03bb4c218e9e666ec466d0a3` 已在 head（PG 建 FK 不再因类型不匹配失败）。
- [ ] 本地有 `postgres:16` 镜像 + docker（PG 实测用临时容器）。
- [ ] 宿主 5432 PG 不动（pg_hba 不允许 localhost，且不该改宿主配置）。

## 阶段 1: 依赖 + config（H5 + H1 + H2）

- [ ] `backend/requirements.txt` L5 `aiosqlite` 后加 `asyncpg==0.30.0`
- [ ] `backend/app/core/config.py`：
  - L67 `db_provider` description -> `"数据库类型，支持 mysql、sqlite 或 postgresql"`
  - L73 `mysql_database` 后、L74 `sqlite_db_path` 前加 5 个 `postgres_*` 字段（host/port=5432/user=postgres/password=""/database=mofeng）
  - L223 白名单 -> `{"mysql", "sqlite", "postgresql"}`
  - L224 错误信息 -> `"DB_PROVIDER 仅支持 mysql、sqlite 或 postgresql"`
  - L272 mysql 分支前插入 postgresql uri 分支（`postgresql+asyncpg://`，`quote_plus` 密码，函数内 import 与 mysql 分支对称）
- 验证：
  - `cd backend && .venv/bin/pip install asyncpg==0.30.0` 成功
  - `DB_PROVIDER=postgresql .venv/bin/python -c "from app.core.config import Settings; s=Settings(DB_PROVIDER='postgresql',SECRET_KEY='x',POSTGRES_PASSWORD='p'); print(s.sqlalchemy_database_uri)"` 输出 `postgresql+asyncpg://postgres:p@localhost:5432/mofeng`
  - `DB_PROVIDER=postgresql`（无 POSTGRES_*）用默认值生成 uri，不报错
  - `DB_PROVIDER=mysql` / `DB_PROVIDER=sqlite` 仍生成原 uri（白名单通过、分支不变）
  - `DB_PROVIDER=oracle` 抛 `ValueError`（白名单拒绝）

## 阶段 2: init_db + env docstring + spec（H3 + H4 + M6 + spec）

- [ ] `backend/app/db/init_db.py` L121-126：dialect 分支（PG 查 `pg_database`+双引号 CREATE；MySQL 保留 `information_schema.schemata`+反引号）
- [ ] `backend/alembic/env.py` L1 docstring -> `async 适配 aiosqlite/asyncmy/asyncpg`
- [ ] `.trellis/spec/backend/database-guidelines.md` "Engine and session" 段：`MySQL enables pool_pre_ping` -> `MySQL and PostgreSQL enable pool_pre_ping`
- 验证：
  - grep 确认 init_db mysql 路径（`information_schema.schemata` + 反引号）仍在 else 分支未删
  - env.py docstring 含 asyncpg

## 阶段 3: PG 实测 + sqlite/mysql 回归

### PG 实测（临时容器）

- [ ] `docker run -d --name mofeng-pg-test -e POSTGRES_PASSWORD=mofeng_test -e POSTGRES_USER=mofeng -e POSTGRES_DB=mofeng -p 5433:5432 postgres:16`
- [ ] 等 `pg_isready -h localhost -p 5433` accepting
- [ ] 设 env（DB_PROVIDER=postgresql, POSTGRES_HOST=localhost, POSTGRES_PORT=5433, POSTGRES_USER=mofeng, POSTGRES_PASSWORD=mofeng_test, POSTGRES_DATABASE=mofeng_pg_test, SECRET_KEY=x）跑 `cd backend && .venv/bin/alembic upgrade head`
- [ ] 验证：
  - `alembic upgrade head` 无错误，建全表
  - `psql -h localhost -p 5433 -U mofeng -d mofeng_pg_test -c '\dt'` 含 34 业务表 + alembic_version（H3 CREATE DATABASE 走通：mofeng_pg_test 库被建）
  - `alembic current` == `03bb4c218e9e666ec466d0a3`
  - `alembic downgrade base && alembic upgrade head` 往返通过（baseline 在 PG 可达）
- [ ] 清理：`docker stop mofeng-pg-test && docker rm mofeng-pg-test`

### sqlite/mysql 回归

- [ ] `cd backend && .venv/bin/python -m pytest -q` 全绿（sqlite 为主）
- [ ] `DB_PROVIDER=mysql` config 加载不报错（白名单通过，uri 分支未动）
- [ ] 确认 mysql/sqlite 分支代码 diff 为零（仅新增 PG elif/分支）

## Review Gate

- design.md + implement.md + prd.md 三件套 review 通过后 `task.py start`。
- trellis-check 子代理独立复核：diff surgical（mysql/sqlite 路径零改动）+ PG 实测证据 + 回归绿。

## 回滚点

- 阶段 1 后：config/requirements 改动，mysql/sqlite 未动，`git checkout` 即回。
- 阶段 2 后：init_db dialect 分支，mysql 走 else 不变，`git checkout` 即回。
- 阶段 3 后：PG 容器已清理，无残留；代码 revert 即回。
- 全程无数据迁移、无不可逆副作用。
