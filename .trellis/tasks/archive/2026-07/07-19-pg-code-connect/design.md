# PG 代码连通 技术设计

parent: `07-19-migrate-to-postgres`。本 child 只做**入口层连通**：让 `DB_PROVIDER=postgresql` 能生成正确的 `postgresql+asyncpg://` 连接串、init_db 能在 PG 上建库、alembic 能在空 PG 库建全表。**不碰 model/migration**（02 已修 H6/M1）、**不碰部署 env/compose**（03 范围）、**不碰数据迁移**（04 范围）。

调研依据：parent `research/dialect-scan.md`（H1-H5+M6）、`research/migration-core-review.md`（核心复核）、parent `design.md`（H 分级）。下文行号以 2026-07-19 磁盘真实内容为准。

## 1. 现状（真实代码）

### config.py（`backend/app/core/config.py`）

- L59-63 `database_url: Optional[str]`：透传字段。`sqlalchemy_database_uri`（L246-258）**优先**走它，`make_url` 解析后 `URL.create` 重建，**已支持任意 drivername**（含 `postgresql+asyncpg://`）。
- L64-68 `db_provider`：默认 `mysql`，description "仅支持 mysql 或 sqlite"。
- L69-73 `mysql_host/port/user/password/database`：5 个分散字段。
- L74-78 `sqlite_db_path`。
- L219-225 `_normalize_db_provider`：白名单 `{"mysql", "sqlite"}`，**显式拒绝其他** -> H1。
- L243-280 `sqlalchemy_database_uri`：
  - L246-258 `database_url` 透传分支（已兼容 PG）✓
  - L260-270 sqlite 分支
  - L272-280 mysql 分支（**非 sqlite 默认走这里**，PG 若无独立分支会误生成 `mysql+asyncmy://`）-> H2
- L282-285 `is_sqlite_backend`：`get_backend_name() == "sqlite"`。PG 下返回 False ✓。

### init_db.py（`backend/app/db/init_db.py`）

- L88-127 `_ensure_database_exists`：sqlite 分支（建父目录）vs 非 sqlite 分支。
- L121-124 `SELECT 1 FROM information_schema.schemata WHERE schema_name = :db`：MySQL 里 schema≈database，**PG 的 schemata 查的是命名空间非 database** -> H4。
- L126 `text(f"CREATE DATABASE \`{database}\`")`：反引号 MySQL 语法，**PG 不兼容** -> H3。
- L115-118 `isolation_level="AUTOCOMMIT"`：PG CREATE DATABASE 同样要求事务外 ✓。
- L130-164 alembic 配置/upgrade：dialect 无关 ✓。

### alembic/env.py（`backend/alembic/env.py`）

- L1 docstring "async 适配 aiosqlite/asyncmy" -> M6 文档更新。
- L21 `config.set_main_option("sqlalchemy.url", settings.sqlalchemy_database_uri)`：用应用配置的 uri，dialect 无关 ✓。
- L45 `async_engine_from_config`：按 drivername 自动选驱动，只要 uri 是 `postgresql+asyncpg://` 即自动用 asyncpg，**主体无需改** ✓。

### requirements.txt

- L4 `asyncmy`、L5 `aiosqlite`，**无 asyncpg** -> H5。

### session.py（`backend/app/db/session.py`）

- L10-20：`is_sqlite_backend` 为 True 用 `NullPool`+`check_same_thread=False`；else（MySQL）`pool_pre_ping=True`+`pool_recycle=3600`。PG 走 else ✓，`check_same_thread` 不会加到 PG。**无需改代码**（L19 注释 "MySQL 场景" 现含 PG，属轻微过时，留 follow-up，不在本 child 改）。

## 2. 方案

### H1 — db_provider 白名单加 postgresql

`config.py:219-225`：
```python
if candidate not in {"mysql", "sqlite", "postgresql"}:
    raise ValueError("DB_PROVIDER 仅支持 mysql、sqlite 或 postgresql")
```
同步 L67 description：`"数据库类型，仅支持 mysql 或 sqlite"` -> `"数据库类型，支持 mysql、sqlite 或 postgresql"`。

### H2 — sqlalchemy_database_uri 加 postgresql 分支 + postgres_* 字段

**方案选择**：parent design §H2 给了两个选项（加 postgres_* 字段+分支 / 复用 database_url 透传）。选**前者**，理由：

- `database_url` 透传虽已支持 PG，但要求运维填完整连接串；与 mysql 的分散字段配置风格不对称。
- 若只靠透传、不加分支，`DB_PROVIDER=postgresql` 且未设 `DATABASE_URL` 时会静默走 mysql 分支生成 `mysql+asyncmy://`，报错指向 mysql 难排查 -> **不可靠**。
- 加 `postgres_*` 字段 + 分支与 `mysql_*` 对称，可维护性最好。

新增 5 字段（L73 `mysql_database` 之后、L74 `sqlite_db_path` 之前）：
```python
postgres_host: str = Field(default="localhost", env="POSTGRES_HOST", description="PostgreSQL 主机名")
postgres_port: int = Field(default=5432, env="POSTGRES_PORT", description="PostgreSQL 端口")
postgres_user: str = Field(default="postgres", env="POSTGRES_USER", description="PostgreSQL 用户名")
postgres_password: str = Field(default="", env="POSTGRES_PASSWORD", description="PostgreSQL 密码")
postgres_database: str = Field(default="mofeng", env="POSTGRES_DATABASE", description="PostgreSQL 数据库名称")
```

uri 分支（L272 mysql 分支之前插入）：
```python
if self.db_provider == "postgresql":
    # PostgreSQL 分支：统一对密码进行 URL 编码，避免特殊字符破坏连接串
    from urllib.parse import quote_plus
    encoded_password = quote_plus(self.postgres_password)
    database = (self.postgres_database or "").strip("/")
    return (
        f"postgresql+asyncpg://{self.postgres_user}:{encoded_password}"
        f"@{self.postgres_host}:{self.postgres_port}/{database}"
    )

# MySQL 分支：统一对密码进行 URL 编码，避免特殊字符破坏连接串
from urllib.parse import quote_plus
...
```

**优先级**：`database_url`（L246，透传）> `db_provider` 分支。设了 `DATABASE_URL` 仍优先透传（覆盖分散字段），与现有行为一致。

**quote_plus 重复 import**：postgresql 与 mysql 分支各自函数内 `import quote_plus`，与现有 mysql 分支风格对称，不提模块顶（surgical，不改进相邻代码）。

### H3 — CREATE DATABASE dialect 分支

`init_db.py:121-126`：
```python
backend = url.get_backend_name()
if backend == "postgresql":
    exists_sql = "SELECT 1 FROM pg_database WHERE datname = :db"
    create_sql = f'CREATE DATABASE "{database}"'
else:
    exists_sql = "SELECT 1 FROM information_schema.schemata WHERE schema_name = :db"
    create_sql = f"CREATE DATABASE `{database}`"
exists = await conn.execute(text(exists_sql), {"db": database})
if exists.first() is None:
    await conn.execute(text(create_sql))
```

- PG 用双引号标识符 `"{database}"`，MySQL 保留反引号。
- `database` 名 f-string 拼接：CREATE DATABASE 不支持参数绑定（PG/MySQL 均不支持），与现有 mysql 反引号写法一致。`database` 来自环境变量（运维可控，非用户输入），不额外做字符转义（与 mysql 分支对称）。

### H4 — 库存在性查询改 pg_database

并入 H3 的 dialect 分支（PG 查 `pg_database WHERE datname`，MySQL 保留 `information_schema.schemata`）。

### H5 — requirements.txt 加 asyncpg

L5 `aiosqlite==0.21.0` 之后加：
```
asyncpg==0.30.0
```
（SQLAlchemy 2.0 async PG 事实标准；0.30.0 与 SQLAlchemy 2.0.44 兼容。若 pip 安装失败再调版本。）

### M6 — alembic/env.py docstring

L1：`"""Alembic 迁移环境（async 适配 aiosqlite/asyncmy）。"""` -> `"""Alembic 迁移环境（async 适配 aiosqlite/asyncmy/asyncpg）。"""`

### spec — database-guidelines.md

"Engine and session" 段：`MySQL enables pool_pre_ping and pool_recycle=3600` -> `MySQL and PostgreSQL enable pool_pre_ping and pool_recycle=3600`（else 分支现正式含 PG，描述应准确）。

## 3. 三方言分析

| 路径 | sqlite | mysql | postgresql |
|---|---|---|---|
| `db_provider` 白名单 | ✓ 不变 | ✓ 不变 | ✓ 新增通过 |
| `sqlalchemy_database_uri`（无 DATABASE_URL） | sqlite 分支（不变） | mysql 分支（不变） | **新 postgresql 分支** |
| `sqlalchemy_database_uri`（有 DATABASE_URL） | 透传（不变） | 透传（不变） | 透传（不变） |
| `is_sqlite_backend` | True | False | False（走 else） |
| `session.py` 引擎参数 | NullPool+check_same_thread | pool_pre_ping+recycle | **pool_pre_ping+recycle**（else，不变） |
| `_ensure_database_exists` 库查询 | sqlite 分支（建目录） | information_schema.schemata（不变） | **pg_database** |
| CREATE DATABASE | sqlite 分支跳过 | 反引号（不变） | **双引号** |
| alembic upgrade head | aiosqlite | asyncmy | **asyncpg**（drivername 自动） |

mysql/sqlite 行为完全不变（仅 PG 走新分支）。PG 分支为新增 elif/else，不影响现有路径。

## 4. 边界与风险

- **database_url 透传优先**：运维若同时设 `DATABASE_URL` 和 `POSTGRES_*`，`DATABASE_URL` 胜出。与现有 mysql 行为一致（非新引入）。
- **CREATE DATABASE 标识符注入**：`database` 含 `"`（PG）或 `` ` ``（MySQL）理论上可注入，但来自运维环境变量、非用户输入，且现有 mysql 分支同样不转义。保持对称，不额外加固。
- **PG 用户建库权限**：`CREATE DATABASE` 要求连接用户有 CREATEDB 权限。容器验证用 superuser（POSTGRES_USER 默认 superuser），生产部署需确保 app 用户有建库权或预建库（03 部署配置关注）。
- **asyncpg 版本**：pin `0.30.0`。若与 SQLAlchemy 2.0.44 或 Python 版本不兼容，implement 时调整为 `>=0.29.0`。
- **baseline 在 PG 的可达性**：02 已确认 baseline `with_variant` 机制 PG 自动 fallback（LONGTEXT->Text、Integer->BigInteger IDENTITY、CURRENT_TIMESTAMP 合法、JSON 可用）。本 child 验证时实测 `alembic upgrade head` 在空 PG 库建全表确认。
- **不引入 postgres_* validator**：与 mysql_* 一致（mysql_* 也无 validator），保持 Pydantic V1 `@validator` 风格不扩散（research B 提的 `@validator`->`@field_validator` 迁移是独立技术债，不在本 child）。

## 5. 验证策略

### PG 实测（临时容器，验证后清理）

宿主 5432 PG 的 pg_hba 不允许 localhost 连接（不该改宿主配置）。用临时容器：
```bash
docker run -d --name mofeng-pg-test \
  -e POSTGRES_PASSWORD=mofeng_test -e POSTGRES_USER=mofeng \
  -e POSTGRES_DB=mofeng -p 5433:5432 postgres:16
```
设 env：`DB_PROVIDER=postgresql`、`POSTGRES_HOST=localhost`、`POSTGRES_PORT=5433`、`POSTGRES_USER=mofeng`、`POSTGRES_PASSWORD=mofeng_test`、`POSTGRES_DATABASE=mofeng_pg_test`（**不存在**，触发 H3 CREATE DATABASE + H4 pg_database 查询路径）。

验证：
1. `alembic upgrade head`（或跑 init_db）在空 PG 库建全表，无错误。
2. 建后查 `pg_database` 确认 `mofeng_pg_test` 已建（H3/H4 路径走通）。
3. 查表数：`\dt` 应含 34 业务表 + `alembic_version`。
4. `alembic downgrade base` + `alembic upgrade head` 往返（验证 baseline 在 PG 可达）。
5. `alembic current` == `03bb4c218e9e666ec466d0a3`（02 的 head）。

验证后清理：`docker stop mofeng-pg-test && docker rm mofeng-pg-test`。

### sqlite/mysql 回归

- `cd backend && .venv/bin/python -m pytest -q`（现有套件，sqlite 为主）全绿。
- `DB_PROVIDER=mysql` 启动路径不报错（白名单/uri 分支不变，仅 grep 确认 mysql 分支代码未动）。
- `DB_PROVIDER=sqlite` 测试套件绿（已含）。

### 代码 review

- config.py：白名单 / 5 字段 / uri 分支 / description 文案。
- init_db.py：dialect 分支逻辑（PG vs MySQL 路径正确）。
- env.py docstring。
- requirements.txt asyncpg。

## 6. 回滚

`git revert` 本 child commit。mysql/sqlite 分支代码未动，回滚后 `DB_PROVIDER` 仅 mysql/sqlite，行为与迁移前完全一致。无数据迁移（04 才做），无不可逆副作用。

## 7. spec 更新

- `database-guidelines.md` "Engine and session" 段 1 处（MySQL -> MySQL and PostgreSQL）。
- 不动 `index.md`（01 是加功能，不新增债务项）。
- env.example / compose 在 03。

## 8. 不做清单（Out of Scope）

- model / migration（02 已做 H6/M1）。
- session.py 代码改动（else 分支自动兼容；L19 注释过时留 follow-up）。
- env.example / docker-compose `POSTGRES_*`（03）。
- pgloader 数据迁移 / PG 集成测试 profile / 静态测试 dialect 处理（04）。
- JSON->JSONB 优化（parent 非目标 M5）。
- `@validator`->`@field_validator` 迁移（research B 独立技术债）。
- HttpUrl 注释修正（M7，独立 follow-up）。
- baseline sqlite `use_alter` 预存问题（02 发现的独立 follow-up）。
- database-guidelines Celery 失效引用（02 发现的独立 follow-up）。
