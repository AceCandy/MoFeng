# PG 部署配置技术设计

parent: `07-19-migrate-to-postgres`。依赖 `01-pg-code-connect`（已归档，config.py 已有 `postgres_*` 字段 + uri 分支 + 白名单）。

## 1. 现状

### deploy/docker-compose.yml
- `app` service（L1-77）：`DB_PROVIDER` 默认 `sqlite`（L16），`MYSQL_*` env（L19-23），无 `POSTGRES_*`
- `db` service（L80-105）：`mysql:8.0`，`profile: mysql`，healthcheck `mysqladmin ping`，volume `mysql-data:/var/lib/mysql`
- `redis` service（L108-120）：`profile: redis`
- volumes（L122-126）：`mysql-data`、`sqlite-data`
- networks（L128-130）：`app-network`

### deploy/.env.example
- B 数据库段（L48-85）：`DB_PROVIDER=sqlite`（L51 注释"可选值: sqlite, mysql"），B1 SQLite，B2 MySQL（内置方案一 + 外部方案二）

### backend/env.example
- `DB_PROVIDER=sqlite`（L12 注释"可选 mysql / sqlite"），MySQL 段（L45-50），SQLite 段（L52-53）

01 已完成 config 层：`postgres_host/port/user/password/database` 5 字段（env `POSTGRES_HOST/PORT/USER/PASSWORD/DATABASE`）+ `postgresql+asyncpg://` uri 分支 + 白名单。03 只需 compose/env 注入这些变量，**不改 config.py / init_db.py / env.py**。

## 2. 方案

### 2.1 env 命名统一（关键决策）

PG 官方镜像要求 env `POSTGRES_DB`；config.py（01 成果）字段 env 是 `POSTGRES_DATABASE`。两者不一致。

| 方案 | env.example 用户写 | pg service | app environment |
|---|---|---|---|
| A（选） | `POSTGRES_DATABASE` | `POSTGRES_DB: ${POSTGRES_DATABASE:-mofeng}` 映射 | `POSTGRES_DATABASE: ${POSTGRES_DATABASE:-mofeng}` 直传 |
| B | `POSTGRES_DB` | `POSTGRES_DB: ${POSTGRES_DB:-mofeng}` 直传 | `POSTGRES_DATABASE: ${POSTGRES_DB:-mofeng}` 映射 |

选 **A**：env 变量名与 config.py 一致（`POSTGRES_DATABASE`），用户只写一份，无困惑；PG 镜像的 `POSTGRES_DB` 是实现细节，compose 映射吸收。`POSTGRES_USER`/`POSTGRES_PASSWORD` 两边同名，无需映射。

### 2.2 deploy/docker-compose.yml

新增 `pg` service（参考 `db`/mysql 模式，插在 redis service 前）：
```yaml
  # PostgreSQL 数据库服务（通过 profile postgres 启用）
  pg:
    image: postgres:16-alpine
    container_name: mofeng-pg
    profiles:
      - postgres
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-mofeng}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?请设置数据库密码}
      POSTGRES_DB: ${POSTGRES_DATABASE:-mofeng}
      TZ: Asia/Shanghai
    volumes:
      - pg-data:/var/lib/postgresql/data
    restart: unless-stopped
    networks:
      - app-network
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "${POSTGRES_USER:-mofeng}", "-d", "${POSTGRES_DATABASE:-mofeng}"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s
```

`app` service environment 加 `POSTGRES_*`（在 `MYSQL_DATABASE` 后，L23 后）：
```yaml
      POSTGRES_HOST: ${POSTGRES_HOST:-pg}
      POSTGRES_PORT: ${POSTGRES_PORT:-5432}
      POSTGRES_USER: ${POSTGRES_USER:-mofeng}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?请设置数据库密码}
      POSTGRES_DATABASE: ${POSTGRES_DATABASE:-mofeng}
```

volumes 加 `pg-data`（L122-126 段）：
```yaml
  pg-data:
    driver: local
```

### 2.3 deploy/.env.example

B 段 DB_PROVIDER 注释（L51）加 postgresql：
```
# [必需] 选择数据库类型。可选值: "sqlite", "mysql", "postgresql"。
```

加 B3 PostgreSQL 段（在 B2 MySQL 后，L85 后）：
```
# --- B3. PostgreSQL 配置 (可选) ---
# 如果您希望使用 PostgreSQL，请先将上方的 DB_PROVIDER 设置为 "postgresql"。
# 启动命令: DB_PROVIDER=postgresql docker compose --profile postgres up -d
#
# 注意：以下变量由 docker-compose.yml 中的 `pg` 服务与应用容器共同使用。
POSTGRES_HOST=pg                 # 使用内置服务时，请勿修改此项
POSTGRES_PORT=5432
POSTGRES_USER=mofeng
POSTGRES_PASSWORD=your-database-password-change-me
POSTGRES_DATABASE=mofeng

# ▼▼▼ 连接到外部的 PostgreSQL 数据库 ▼▼
# 启动命令: DB_PROVIDER=postgresql docker compose up -d
# POSTGRES_HOST=host.docker.internal
# POSTGRES_PORT=5432
# POSTGRES_USER=your-external-db-user
# POSTGRES_PASSWORD=your-external-db-password
# POSTGRES_DATABASE=your-external-db-name
```

### 2.4 backend/env.example

DB_PROVIDER 注释（L12）加 postgresql：
```
# 数据库类型，可选 mysql / sqlite / postgresql
```

加 PostgreSQL 段（在 MySQL 段后，L50 后）：
```
# PostgreSQL 数据库连接（仅在 DB_PROVIDER=postgresql 时生效）
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=mofeng
POSTGRES_PASSWORD=123456
POSTGRES_DATABASE=mofeng
```

## 3. 与 mysql service 对称性

| 维度 | mysql (`db`) | postgres (`pg`) |
|---|---|---|
| image | mysql:8.0 | postgres:16-alpine |
| profile | mysql | postgres |
| container_name | mofeng-db | mofeng-pg |
| env | MYSQL_ROOT/DATABASE/USER/PASSWORD | POSTGRES_USER/PASSWORD/DATABASE（pg 镜像 POSTGRES_DB 映射） |
| volume | mysql-data:/var/lib/mysql | pg-data:/var/lib/postgresql/data |
| healthcheck | mysqladmin ping | pg_isready |
| network/TZ | app-network / Asia/Shanghai | 同 |

app env `MYSQL_*` 与 `POSTGRES_*` 并列，结构对称。`POSTGRES_PASSWORD` 用 `:?` 必填，与 `MYSQL_PASSWORD` 一致（内置/外部都要求）。

## 4. 边界与风险

- **POSTGRES_HOST 默认 `pg`**：内置场景 service 名；外部场景用户改（与 `MYSQL_HOST` 默认 `db` 对称）。
- **profile 不互斥**：compose 不阻止同时启 `mysql`+`postgres` profile，但 `DB_PROVIDER` 只能一值。文档说明二选一，不强制 compose 层互斥（避免过度设计）。
- **postgres:16-alpine vs 现有缓存 postgres:16**：验证时 pull alpine（更小，无功能差异）。parent design 约定 alpine。
- **POSTGRES_DB 映射**：用户不感知 `POSTGRES_DB`，只写 `POSTGRES_DATABASE`，compose 映射给 PG 镜像。
- **healthcheck `pg_isready`**：不需密码，`-U` + `-d` 即可测连接接受。PG 16 alpine 自带。

## 5. 验证策略（分层）

### AC1：pg service up + 健康检查
- `docker compose --profile postgres up -d pg`（只起 pg，不 build app）
- 等 healthcheck `pg_isready` 绿（`start_period: 30s`）
- `docker compose ps pg` 确认 `healthy`

### AC2：app 连通 PG（分层降级）
- **配置层**：`docker compose config` 验证 `app.environment` 注入 `POSTGRES_HOST/PORT/USER/PASSWORD/DATABASE` 且值正确，`pg` service `POSTGRES_DB` 映射自 `POSTGRES_DATABASE`
- **运行层**（复用 01 模式）：host python 连 pg 容器（compose pg service 无 host 端口映射，取容器 IP 直连 `172.x:5432`）+ `DATABASE_URL=postgresql+asyncpg://... alembic upgrade head` 建全表，证明 config + asyncpg + baseline 建表端到端正确
- **降级理由**：01 已证 host python + asyncpg 端到端连通 + 建表；03 增量是 compose 编排（pg service + app env 注入），`docker compose config` + host python 连 pg 容器覆盖增量；app 容器完整 build+run 需 Dockerfile 多阶段前端 build（重），核心验证不依赖
- **可选增强**：若环境允许，build app + `docker compose --profile postgres up -d` + app healthcheck（curl `/api/health`）绿

### AC3：mysql/sqlite 回归不破
- `docker compose config` 验证 `mysql`/`redis` profile 与 `db`/`redis` service 未受改动
- `git diff deploy/docker-compose.yml` 确认 `db`/mysql service、`mysql-data`/`sqlite-data` volumes 零改动

### AC4：env.example 完整
- `deploy/.env.example` + `backend/env.example` 含 `POSTGRES_HOST/PORT/USER/PASSWORD/DATABASE` + DB_PROVIDER 注释含 `postgresql`

## 6. 回滚

- compose：移除 `pg` service + app `POSTGRES_*` env + `pg-data` volume（`git revert`）
- env.example：移除 `POSTGRES_*` 段（`git revert`）
- mysql/sqlite compose/env 零改动，回滚无副作用

## 7. spec 更新

无。`database-guidelines.md` 仅 L9 提到 MySQL and PostgreSQL（01 已改），无 DB_PROVIDER 选项列表或部署段。03 改 `deploy/` 配置文件，非编码规范。

## 8. 不做清单

- 不改 config.py / init_db.py / env.py（01 已完成）
- 不改 Dockerfile / requirements.txt（app 镜像构建与 DB 选择无关，asyncpg 01 已加）
- 不做 app 容器完整 build+run（重，降级为 host python + docker compose config）
- 不做 pgloader / 数据迁移（阶段4）
- 不做 PG 集成测试 profile / 静态测试 dialect（阶段4）
- 不强制 mysql/pg profile 互斥（文档说明即可，避免过度设计）
