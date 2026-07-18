# 03-pg-deploy-config 实施计划

## 前置确认

- [x] 01-pg-code-connect 已归档（config.py 有 `postgres_*` 字段 + uri 分支 + 白名单）
- [x] docker 可用（29.1.3 + compose v5.0.0）
- [x] postgres:16 镜像已缓存（alpine 版验证时 pull）
- [x] parent design.md 约定 `postgres:16-alpine` + `pg_isready` + `pg-data`
- [x] env 命名决策：方案 A（`POSTGRES_DATABASE` 统一，pg 镜像 `POSTGRES_DB` 映射）

## 阶段 1: compose 编排

- [ ] `deploy/docker-compose.yml` 加 `pg` service（profile postgres, postgres:16-alpine, pg-data, pg_isready healthcheck）
- [ ] `app` environment 加 `POSTGRES_HOST/PORT/USER/PASSWORD/DATABASE`
- [ ] volumes 加 `pg-data`
- 验证：`docker compose config` 语法 OK + pg service 出现 + app POSTGRES_* 注入

## 阶段 2: env.example

- [ ] `deploy/.env.example`：DB_PROVIDER 注释加 postgresql + B3 PostgreSQL 段（内置+外部）
- [ ] `backend/env.example`：DB_PROVIDER 注释加 postgresql + PostgreSQL 段
- 验证：`rg POSTGRES_` 两文件 + DB_PROVIDER 注释含 postgresql

## 阶段 3: 验证（AC1-4）

- [ ] AC1：`docker compose --profile postgres up -d pg` + healthcheck 绿
- [ ] AC2：`docker compose config` 验证 app env + host python 连 pg 容器 `alembic upgrade head` 建全表
- [ ] AC3：`docker compose config` + `git diff` 验证 mysql/sqlite 零改动
- [ ] AC4：env.example 含完整 POSTGRES_*

## Review Gate

- 三件套 review 后 `task.py start`
- 实现 + 验证绿后 trellis-check 子代理独立复核

## 回滚点

- 阶段1后：compose 改动 `git checkout deploy/docker-compose.yml`
- 阶段2后：env.example 改动 `git checkout`
- commit 前不 push，可整体 revert
