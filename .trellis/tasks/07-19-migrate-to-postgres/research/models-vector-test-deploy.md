# PG 迁移外围影响面调研（子 agent B 产出）

## 1. ORM 模型类型审查

### 1.1 主键自增策略（3 类）

**A. String 主键（UUID/业务键，PG 无差异）**
- `novel.py:35` `NovelProject.id = String(36) PK`
- `novel.py:86-88` `NovelBlueprint.project_id` FK 作 PK
- `constitution.py:30-32` `NovelConstitution.project_id` FK 作 PK
- `llm_config.py:13` `LLMConfig.user_id` PK
- `ai_model_config.py:78-79` `UserAIStageRoute` 复合 PK (user_id+stage)
- `background_task.py:18` `BackgroundTask.id = String(36) PK`
- `admin_setting.py:13`、`system_config.py:13`、`usage_metric.py:13` 三个 KV 表 `key` PK

**B. `BigInteger().with_variant(Integer, "sqlite") + autoincrement=True`（PG 友好）**
- 定义：`novel.py:14`、`chapter_blueprint.py:24`、`chapter_generation_trace.py:11`、`memory_layer.py:18`、`foreshadowing.py:15`、`project_memory.py:21`
- 使用：`novel.py:69/108/127/142/164/214/239`、`chapter_blueprint.py:64/153`、`chapter_generation_trace.py:35`、`memory_layer.py:42/96/133/169`、`foreshadowing.py:24/78/104/130/150`、`project_memory.py:36/81`
- PG 注意：PG 走默认 BigInteger -> PG 10+ 生成 IDENTITY。无 MySQL AUTO_INCREMENT 依赖。需 PG ≥ 10。

**C. 纯 `Integer + autoincrement=True`（未用 with_variant）**
- `ai_model_config.py:16/48`、`faction.py:29/70/107/136`、`writer_persona.py:30`、`user.py:16`、`prompt.py:16`、`update_log.py:15`
- PG 注意：Integer 单列 PK -> SERIAL。无差异。`user.py:16` 未显式 autoincrement，依赖默认行为，PG 同样 SERIAL。

### 1.2 JSON 类型（PG 最需关注）

- 通用 `sqlalchemy.JSON` 约 47 处（baseline 统计），分布于 `novel.py:74/96/116/148-150/220`、`chapter_blueprint.py:105/114/125/139/168`、`memory_layer.py:61-83`(10+)、`foreshadowing.py:32/46-48/111/162/166`、`project_memory.py:53/65/93/96/105`、`background_task.py:29/30/32`、`constitution.py:60/61/64/66/69/79`、`faction.py:42/46/50/52/56/57/60/90/97`、`writer_persona.py:42/50/51/66/69-74/77/78/81`、`ai_model_config.py:23/53`
- PG 注意：当前 DDL 生成 `JSON`（文本存储），**不是 `JSONB`**。功能可用，但失去 JSONB 的 GIN 索引、`@>` 包含查询、键去重、查询性能。
- 建议：`JSON().with_variant(JSONB, "postgresql")`（保持 sqlite/mysql 兼容），或在 PG 侧建表达式索引。不改也能跑。

### 1.3 Enum 字段（零阻力）

- Python enum 定义于 `chapter_blueprint.py:28-52`（SuspenseDensity/ForeshadowingOp/ChapterFunction）、`memory_layer.py:21-31`（CharacterStateType）
- **但列定义全部用 `String(32) + default=Enum.value` 存储**（如 `chapter_blueprint.py:75-78`、`88-91`）
- 全局 `rg "Enum\("` 列实际使用 = **0 处**
- PG 注意：无需 `CREATE TYPE`，枚举值以字符串存储，跨库零差异。已规避的陷阱。

### 1.4 DateTime 时区（有一处不一致）

- 绝大多数用 `DateTime(timezone=True) + server_default=func.now() + onupdate=func.now()`（`novel.py:40-41/76/97-98/173/178-179/222/245` 等）
- **例外**：`memory_layer.py:84/85/122/157/158/186/187` 共 7 处用 `DateTime`（**不带 timezone=True**）+ `default=datetime.utcnow`（Python 侧）
- PG 注意：`DateTime(timezone=True)` -> TIMESTAMPTZ（推荐）；`DateTime` -> TIMESTAMP WITHOUT TIME ZONE。memory_layer 这 4 张表（character_states/timeline_events/causal_chains/story_time_trackers）与其他表时区语义混用，跨表 JOIN 时间比较会出问题。**建议统一为 `DateTime(timezone=True)`**。
- baseline `server_default=sa.text('(CURRENT_TIMESTAMP)')`（L35 等）：PG 合法，PG 推荐写法是 `now()`。

### 1.5 String / Text / Boolean / Float

- `String(length)` -> PG VARCHAR(length)，无差异
- `LONG_TEXT_TYPE = Text().with_variant(LONGTEXT, "mysql")`（`novel.py:15` 等 6 处定义）：PG fallback 到 TEXT（无长度限制），与 MySQL LONGTEXT 等价。用于章节正文 `ChapterVersion.content` 等长文本，OK。
- `Boolean` -> PG BOOLEAN（MySQL TINYINT(1)），无差异
- `Float` -> PG FLOAT/REAL，无差异（如 `ai_model_config.py:60` tts_speed）

### 1.6 外键 ondelete（一处类型不匹配隐患）

- `ondelete="CASCADE"` 大量；`ondelete="SET NULL"`：`novel.py:176`、`foreshadowing.py:36`、`memory_layer.py:115/147/148`
- **PG 严格性隐患**：PG 要求 FK 列类型与被引用列类型**完全一致**，MySQL 较宽松。
  - `memory_layer.py:43/97/134/170` `project_id = Column(String(255), ForeignKey("novel_projects.id"))`，而 `novel.py:35` `NovelProject.id = String(36)` -- **String(255) vs String(36) 不匹配**，PG 建表报错或警告。需统一为 `String(36)`。
  - `memory_layer.py:44` `character_id = Column(BigInteger, ForeignKey("blueprint_characters.id"))`，被引用 BIGINT_PK_TYPE（PG 下 BigInteger）-- 一致，OK。
- `novel.py:216` `use_alter=True` 处理循环 FK（chapters ↔ chapter_versions），PG 下 use_alter 正常工作。

### 1.7 Index / UniqueConstraint

- `novel.py:160-162` `UniqueConstraint(project_id, chapter_number)`
- `chapter_generation_trace.py:30-33` 两个复合 Index
- 各 `index=True` 列（`foreshadowing.py:25/35`、`background_task.py:19/24/25/27`）
- PG 注意：完全支持，无差异。

### 1.8 Alembic baseline 跨库兼容性

- `a53385d06521_baseline.py`（635 行，34 个 op.create_table，autogenerate 生成）
- L12 `from sqlalchemy.dialects import mysql` + L33 `sa.Text().with_variant(mysql.LONGTEXT(), 'mysql')`：PG fallback 到 Text，OK
- L29 `sa.BigInteger().with_variant(sa.Integer(), 'sqlite')`：PG 走 BigInteger，OK
- L35 等 `server_default=sa.text('(CURRENT_TIMESTAMP)')`：PG 合法
- **无** AUTO_INCREMENT、TINYINT、ON UPDATE CURRENT_TIMESTAMP、ENUM(、create_type -- baseline 是跨库兼容 DDL，PG 下可直接 `alembic upgrade head` 建表。

## 2. 向量服务耦合

**结论：完全独立，迁移主库不影响向量服务**

- `vector_store_service.py:21-23` 用 `libsql_client`（独立客户端，非 SQLAlchemy）
- L52-82 初始化读 `settings.vector_db_url`（`config.py:143`），与主库 `settings.sqlalchemy_database_uri`（`config.py:243`）两套连接
- L89-122 建表 `rag_chunks`/`rag_summaries`，用 libsql 方言：`vector_distance_cosine()`、`BLOB` 存 embedding、`unixepoch()`、`ON CONFLICT(id) DO UPDATE`、`array('f').tobytes()` 编码
- 主库模型无任何表与 rag_chunks/rag_summaries 有 FK 或关联

### 换 pgvector 的利弊

**利**：统一数据库栈；可用 PG 事务保证主库与向量库一致性（当前双写无事务）；pgvector HNSW/IVFFlat 索引性能远优于 libsql 全表线性扫描；向量与业务数据可 JOIN。

**弊**：`vector_store_service.py` 几乎全改（SQL 方言 `vector_distance_cosine`->`<=>`、存储 `BLOB`->`vector(N)`、`_to_f32_blob`/`_from_f32_blob`（L408-422）整组废弃、`unixepoch()`->`EXTRACT(EPOCH FROM now())`、`ON CONFLICT DO UPDATE` 差异需验证）；需装 pgvector 扩展；现有 `rag_vectors.db` 数据需迁；pgvector `vector(N)` 要求**固定维度**，当前 BLOB 无此约束，若 `EMBEDDING_MODEL_VECTOR_SIZE`（`config.py:128`）切换模型会破坏 schema；已有 Python 侧相似度回退（L437-501）需重新测试。

**建议**：短期**不换**，保持 libsql 独立。长期若要统一栈再单独评估。

## 3. 测试栈

**现状：全部用 sqlite 内存库**

- `pytest.ini:1-4`：`testpaths = backend/tests`，`asyncio_mode = strict`，无 DB 配置
- 根 `conftest.py:1-7`：只把 `backend/` 加入 sys.path，无 DB fixture
- `backend/tests/conftest.py:1-15`：只旁路 SSRF，无 DB fixture
- 连 DB 的 8 个测试文件**都在文件内自建 sqlite 内存库**：
  - `test_chapter_delete_policy.py:26-37`、`test_chapter_outline_structured_fields.py:29`、`test_project_owner_authorization.py:14`、`test_finalize_service.py:33/101`、`test_chapter_generation_trace_service.py:35/83/123/177/238`、`test_background_task_service.py:14`、`test_inspiration_project_lifecycle.py:22/63/89`、`test_pipeline_langgraph_refactor_static.py:488/558/615`
  - 典型（`test_chapter_delete_policy.py:26-37`）：`create_async_engine("sqlite+aiosqlite:///:memory:")` + `StaticPool` + `Base.metadata.create_all`（**不走 alembic**）

### 迁移 PG 后测试策略

- **短期**：测试无需改动，继续用 sqlite 内存验证 ORM 逻辑
- **盲区**（sqlite 不覆盖的 PG 差异）：JSON vs JSONB 语义；PG 类型严格性（1.6 FK String(255) vs String(36)）；PG 字符串比较大小写敏感（sqlite 默认不敏感）；PG 事务隔离（sqlite SERIALIZABLE，PG READ COMMITTED）；PG 外键即时检查 vs sqlite DEFERRED
- **静态断言依赖 MySQL 方言 SQL**（迁移 PG 需同步维护）：
  - `test_tts_model_configuration.py:219-221` 读 `backend/db/schema.sql` 文本断言含 tts 列
  - `test_chapter_generation_trace_service.py:22-28` 读 `backend/db/migrations/add_chapter_generation_traces.sql` 文本断言
  - `test_prompt_database_migration_static.py`（静态迁移测试）
  - `test_dev_script_static.py`（dev 脚本静态测试）
  - 这些 `.sql` 全是 MySQL 方言（AUTO_INCREMENT/LONGTEXT/TIMESTAMP ON UPDATE CURRENT_TIMESTAMP），PG 迁移后需提供 PG 版或改读 alembic 迁移
- **中期建议**：新增 PG 集成测试 profile（环境变量切换 `DB_URL`），至少跑通 `alembic upgrade head` 在 PG 下建表，覆盖 FK 类型匹配等 PG 才暴露的问题

## 4. 部署配置

### 当前 DB 相关配置项清单

**后端 Settings（`backend/app/core/config.py`）**：
- L59-63 `database_url`（DATABASE_URL，覆盖下方配置）
- L64-68 `db_provider`（DB_PROVIDER，默认 mysql）
- L69-73 `mysql_host/port/user/password/database`
- L74-78 `sqlite_db_path`（SQLITE_DB_PATH）
- L219-225 `_normalize_db_provider` 限制 `{"mysql", "sqlite"}`
- L243-280 `sqlalchemy_database_uri`：sqlite 分支 + MySQL 分支
- L282-285 `is_sqlite_backend`

**驱动依赖（`backend/requirements.txt`）**：L4 `asyncmy==0.2.9`、L5 `aiosqlite==0.21.0`，**无 asyncpg/psycopg**

**会话工厂（`backend/app/db/session.py`）**：L10-21 按 `is_sqlite_backend` 分支

**初始化（`backend/app/db/init_db.py`）**：L88-127 `_ensure_database_exists`，L126 `CREATE DATABASE \`{database}\`` 反引号 -- PG 不兼容

**Docker Compose（`deploy/docker-compose.yml`）**：
- L16 `DB_PROVIDER: ${DB_PROVIDER:-sqlite}`
- L17 `SQLITE_DB_PATH`
- L19-23 `MYSQL_HOST/PORT/USER/PASSWORD/DATABASE`
- L80-105 MySQL service（profile: mysql, mysql:8.0, utf8mb4, 挂卷 mysql-data）

**环境变量示例**：`deploy/.env.example:51-86` DB_PROVIDER + SQLite + MySQL 配置段；`backend/env.example:12-13`（DB_PROVIDER）、L45-53（MYSQL_* + SQLITE_DB_PATH）

### 迁移 PG 需新增/修改清单

| 文件 | 行号 | 改动 |
|---|---|---|
| `backend/app/core/config.py` | L64-68 | db_provider 描述加 postgresql |
| `backend/app/core/config.py` | L219-225 | `_normalize_db_provider` 放行 `{"mysql","sqlite","postgresql"}` |
| `backend/app/core/config.py` | L243-280 | `sqlalchemy_database_uri` 新增 postgresql 分支：`postgresql+asyncpg://user:pass@host:port/db` |
| `backend/app/core/config.py` | L69-73 后 | 新增 `postgres_host/port/user/password/database` 字段 |
| `backend/app/core/config.py` | L282-285 | 可新增 `is_postgres_backend` 或保留现有 |
| `backend/requirements.txt` | L4 后 | 新增 `asyncpg` |
| `backend/app/db/init_db.py` | L126 | `CREATE DATABASE \`{db}\`` 改为 `CREATE DATABASE "{db}"`（双引号，PG 兼容；MySQL 双引号 ANSI 模式需确认） |
| `backend/app/db/session.py` | L10-21 | PG 走 else 分支复用 pool_pre_ping+pool_recycle，可选加 pool_size/max_overflow（非必须） |
| `deploy/docker-compose.yml` | L79 后 | 新增 postgres service（profile: postgres, postgres:16-alpine, 挂卷 pg-data, healthcheck pg_isready） |
| `deploy/docker-compose.yml` | L23 后 | app 环境变量新增 `POSTGRES_HOST/PORT/USER/PASSWORD/DATABASE` |
| `deploy/docker-compose.yml` | L122-126 | volumes 新增 `pg-data` |
| `deploy/.env.example` | L51 | DB_PROVIDER 注释加 postgresql 选项 |
| `deploy/.env.example` | L86 后 | 新增 PostgreSQL 配置段（POSTGRES_*） |
| `backend/env.example` | L13 | DB_PROVIDER 注释加 postgresql |
| `backend/env.example` | L53 后 | 新增 POSTGRES_* 配置项 |
| `backend/alembic/env.py` | - | **无需改动**（已用 settings.sqlalchemy_database_uri，L21） |
| `backend/alembic/versions/a53385d06521_baseline.py` | - | **无需改动**（跨库兼容，见 1.8） |

### 不需改动

- `backend/app/db/base.py`：纯 DeclarativeBase，无方言
- `a53385d06521_baseline.py`：autogenerate 产物，已用 with_variant 处理 mysql 方言，PG fallback 正常
- `vector_store_service.py`：与主库完全独立（见第 2 节）

## 关键风险排序

1. **高**：`memory_layer.py:43/97/134/170` FK 类型 `String(255)` vs 被引用 `NovelProject.id String(36)` 不匹配 -- PG 严格性会报错，MySQL 可能放行。需改模型 + 新 alembic 迁移。
2. **中**：`memory_layer.py:84/85/122/157/158/186/187` 共 7 处 `DateTime` 不带 `timezone=True`，与其他表 TIMESTAMPTZ 混用。需统一。
3. **中**：`init_db.py:126` `CREATE DATABASE` 反引号 PG 不兼容。
4. **低**：47 处 `JSON` 列在 PG 下非 JSONB，性能非最优（不改也能跑）。
5. **低**：`config.py:219-225` `_normalize_db_provider` 白名单不含 postgresql，需扩展。
6. **低**：`requirements.txt` 无 asyncpg，需新增。
7. **低**：4 个静态测试读 MySQL 方言 `.sql` 文件断言，需同步维护 PG 版本或改读 alembic。
