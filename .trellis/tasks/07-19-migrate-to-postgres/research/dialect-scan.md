# MySQL/SQLite Dialect 代码调研报告（子 agent A 产出）

> 调研范围：`backend/app/` + `backend/alembic/`（排除 `__pycache__`）。未扫 `tests/`。为 PG 迁移评估 dialect 耦合。

## 一、整体 dialect 耦合程度：中

判断依据：

1. **业务查询层干净**：`services/`、`repositories/`、`api/routers/` 几乎全走 SQLAlchemy ORM（`select`/`update`/`delete`/`func.count`/`func.max`），未发现业务路径里有 `text()` 原生 SQL。唯一运行时 `dialect.name` 分支在 `finalize_service.py`，且只用于 SQLite 兼容补丁。
2. **没有高危 dialect 专属 SQL 语法**：未发现 `JSON_EXTRACT`/`JSON_UNQUOTE`/`MATCH ... AGAINST`/`ON UPDATE CURRENT_TIMESTAMP`/`AUTO_INCREMENT`/`ENGINE=`/`CHARSET`/`COLLATE`/`utf8mb4`/`PRAGMA`/`AUTOINCREMENT` keyword 等硬编码方言 SQL。
3. **dialect 耦合集中在"入口层"**：`config.py`（DB_PROVIDER 白名单 + 连接串生成）、`init_db.py`（建库流程）、`session.py`（连接池二分支）、`baseline migration`（`mysql.LONGTEXT()` variant + `sa.text('(CURRENT_TIMESTAMP)')` server_default）、2 处运行时 dialect 分支判断。
4. **模型层用 `with_variant` 机制**做跨 dialect 适配（`BIGINT_PK_TYPE`、`LONG_TEXT_TYPE`），本身为多 dialect 设计，PG 多数自动 fallback。
5. 未达"重"：无深度嵌入业务的 dialect 代码；未达"轻"：入口层有 MySQL 硬编码（反引号、`information_schema.schemata` 语义假设），且 `DB_PROVIDER` 白名单根本不支持 PG。

## 二、按风险从高到低排序

### 高风险（阻塞，必须改才能连通 PG）

#### H1. DB_PROVIDER 白名单不含 PG
- `backend/app/core/config.py:223-224`
- `if candidate not in {"mysql", "sqlite"}: raise ValueError("DB_PROVIDER 仅支持 mysql 或 sqlite")`
- 改：白名单加 `"postgresql"`；同步检查 L67 description 文案。

#### H2. sqlalchemy_database_uri 连接串生成无 PG 分支
- `backend/app/core/config.py:243-280`（L260-270 sqlite、L272-280 mysql）
- 改：新增 `postgresql` 分支生成 `postgresql+asyncpg://...`；新增 PG 配置字段，或复用 `database_url`（L246 已支持透传 `DATABASE_URL`，最省事）。

#### H3. CREATE DATABASE 使用 MySQL 反引号
- `backend/app/db/init_db.py:126`
- `await conn.execute(text(f"CREATE DATABASE \`{database}\`"))`
- 改：PG 用双引号 `"{database}"`；注意 PG `CREATE DATABASE` 不能在事务内，当前已用 `isolation_level="AUTOCOMMIT"`（L117）规避，兼容。

#### H4. information_schema.schemata 语义差异
- `backend/app/db/init_db.py:121-124`
- `SELECT 1 FROM information_schema.schemata WHERE schema_name = :db`
- MySQL 里 schema ≈ database；PG 的 schemata 查的是 schema（命名空间），不是 database。
- 改：PG 查 `pg_database WHERE datname = :db`，或 try/except `CREATE DATABASE` duplicate 错误。

#### H5. 缺少 PG 异步驱动依赖
- `backend/requirements.txt:4-5`（asyncmy / aiosqlite，无 asyncpg）
- 改：新增 `asyncpg`（或 `psycopg[binary]`）。

### 中风险（可运行但有行为差异，需验证/小幅调整）

#### M1. 运行时 dialect 分支：SQLite 显式分配主键 id
- `backend/app/services/finalize_service.py:401-406`
- `if self.db.get_bind().dialect.name == "sqlite":` 显式 `max(id)+1`
- PG 兼容：是（不进此分支）。验证 PG 下 BigInteger+autoincrement 由 SQLAlchemy 用 IDENTITY/SERIAL，CharacterState 插入 id 自动生成正常。

#### M2. BIGINT_PK_TYPE variant 未覆盖 PG
- `novel.py:14`、`project_memory.py:21`、`memory_layer.py:18`、`foreshadowing.py:15`、`chapter_blueprint.py:24`、`chapter_generation_trace.py`（L35 引用）
- `BigInteger().with_variant(Integer, "sqlite")`
- PG 兼容：是（fallback 到 BigInteger，SQLAlchemy 自动用 IDENTITY 列）。验证 PG 版本 ≥ 10。

#### M3. baseline migration 的 server_default `sa.text('(CURRENT_TIMESTAMP)')`
- `a53385d06521_baseline.py` 共 38 处（L35/L44/L45/L58/L76/L77/L92/L93/L115/L116/L131/L132/L149/L150/L205/L206/L235/L254/L255/L273/L274/L289/L290/L301/L314/L315/L376/L377/L415/L437/L498/L499/L511/L512/L528/L529/L545/L546/L559）
- PG 兼容：是（支持 CURRENT_TIMESTAMP，带括号合法；返回 timestamptz 与 `DateTime(timezone=True)` 匹配）。验证时区语义一致性。

#### M4. SQLite naive 时间假设补丁
- `backend/app/services/novel_service.py:965-972` `_to_utc_if_possible`
- `if value.tzinfo is None: return value.replace(tzinfo=timezone.utc)`（假设 SQLite naive 即 UTC）
- PG 兼容：是（PG 返回 aware timestamptz，走 `astimezone` 分支，行为正确）。无需改。

#### M5. is_sqlite_backend 二分支连接配置
- `backend/app/db/session.py:10-20`
- sqlite：`NullPool`+`check_same_thread=False`；else（MySQL）：`pool_pre_ping=True`+`pool_recycle=3600`
- PG 兼容：是（走 else，`check_same_thread` 不会加到 PG）。验证 `is_sqlite_backend` 在 PG 下返回 False。无需改。

#### M6. alembic env docstring
- `backend/alembic/env.py:1` "async 适配 aiosqlite/asyncmy"
- PG 兼容：是（docstring 仅文档；主体 dialect 无关）。改文档含 asyncpg（可选）。

#### M7. HttpUrl 转 str 注释误导
- `backend/app/services/llm_config_service.py:254-259`
- 注释声称 sqlite 无法写 HttpUrl，实际是 Pydantic HttpUrl 对象 vs SQLAlchemy Text 列适配（dialect 无关）
- 改：注释改为"HttpUrl 对象无法直接写入 Text 列"（dialect 无关），代码不动。

### 低风险（PG 自动兼容，无需改）

- **L1 LONG_TEXT_TYPE variant**：`novel.py:15`、`chapter_blueprint.py:25`、`project_memory.py:22`、`foreshadowing.py:16`、`writer_persona.py:22`、`faction.py:21` 定义；使用处 `novel.py:73,95,219`、`chapter_blueprint.py:122`、`project_memory.py:45,90`、`foreshadowing.py:30,84,110`、`faction.py:37`、`writer_persona.py`。PG fallback 到 Text -> PG TEXT 无限长。
- **L2 baseline `mysql.LONGTEXT()` variant（13 处）**：L33/L199/L229/L287/L299/L308/L429/L430/L431/L432/L480/L523/L541。PG fallback 到 Text。
- **L3 模型层 `func.now()` / `onupdate=func.now()`**：遍布 models 约 40+ 处。PG 原生支持 `now()`。
- **L4 `sa.JSON()`**：baseline 约 30 处。PG 用 JSON（非 JSONB），可用。
- **L5 `DateTime(timezone=True)`**：映射 TIMESTAMPTZ。
- **L6 `autoincrement=True` / `ForeignKey` / `ondelete='CASCADE'`/`'SET NULL'`**：SQLAlchemy 跨 dialect 处理。
- **L7 `isolation_level="AUTOCOMMIT"`**（init_db 建库引擎 L117）：PG CREATE DATABASE 同样要求事务外。

### 独立向量库（与主库 PG 迁移无关，需说明）

#### V1. libsql 向量库使用 SQLite 方言 SQL
- `backend/app/services/vector_store_service.py`
  - L91-122 `CREATE TABLE IF NOT EXISTS rag_chunks/rag_summaries`（`id TEXT PRIMARY KEY`、`embedding BLOB NOT NULL`、`created_at INTEGER DEFAULT (unixepoch())`）
  - L150-161 `SELECT ... vector_distance_cosine(embedding, :query) AS distance FROM rag_chunks ...`
  - L212-220 同上（rag_summaries）
  - L265-329 `INSERT INTO rag_chunks/rag_summaries`
- 走 `libsql_client.create_client`（L72），与主业务库 `DB_PROVIDER` 解耦。
- 迁移主库到 PG 不影响向量库。换 pgvector 需单独重写 SQL（`vector_distance_cosine`->`<=>`，`BLOB`->`vector`），独立后续工作。

## 三、迁移改造最小工作集

1. 必须改（连通性）：H5（asyncpg）-> H1（白名单）-> H2（连接串）-> H3（反引号）-> H4（pg_database）。
2. 建议验证（行为一致性）：M1/M2（PG BigInteger 自增）、M3（时区）、M4（naive 假设）。
3. 可选清理：M6（docstring）、M7（注释）。
4. 无需动：所有 L 类、M5。

**结论**：业务层零改动，改造集中在 `config.py` + `init_db.py` + `requirements.txt` 三文件入口层，预计 < 50 行代码改动即可连通 PG。baseline migration 与模型层因 `with_variant` 机制设计良好，PG 下自动 fallback 兼容，无需改迁移文件。
