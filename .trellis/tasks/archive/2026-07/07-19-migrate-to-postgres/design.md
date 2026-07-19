# 迁移 PostgreSQL 技术设计

基于 `research/` 三份调研。dialect 耦合度"中"，业务层零改动，改造集中在入口层 + model 修复。

## 整体架构

`DB_PROVIDER` 三选项并存：

| provider | 驱动 | 用途 |
|---|---|---|
| sqlite | aiosqlite | 本地开发/测试 |
| mysql | asyncmy | 现有生产 |
| postgresql | asyncpg | 新增选项 |

`config.py` 的 `sqlalchemy_database_uri` 按 db_provider 生成对应连接串；`session.py` / `alembic/env.py` 按 drivername 自动选驱动，**无需 dialect 分支**（`async_engine_from_config` 内部按 drivername 解析）。

## 改动清单（分级）

### 必须改（连通性阻塞，不改连不上 PG）

| # | 位置 | 问题 | 改动 |
|---|---|---|---|
| H1 | `config.py:223` | db_provider 白名单 `{"mysql","sqlite"}` | 加 `"postgresql"` |
| H2 | `config.py:260-280` | uri 无 PG 分支 | 新增 `postgresql+asyncpg://` 分支 + `postgres_*` 字段；或最小改动复用现成 `database_url` 字段（`config.py:59`，已支持透传 `DATABASE_URL`） |
| H3 | `init_db.py:126` | `CREATE DATABASE \`{db}\`` 反引号 MySQL 语法 | dialect 分支：PG 用 `"{db}"` 双引号；MySQL 保留反引号 |
| H4 | `init_db.py:121-124` | `information_schema.schemata` 在 PG 查的是 schema 非 database | PG 改查 `pg_database WHERE datname=:db`，或 try/except duplicate 错误 |
| H5 | `requirements.txt` | 无 PG 异步驱动 | 加 `asyncpg`（SQLAlchemy async PG 事实标准） |
| H6 | `memory_layer.py:43/97/134/170` | FK `String(255)` 引用 `novel_projects.id String(36)`，PG 严格性拒绝 | 改 model 为 `String(36)` + 新 alembic 迁移 alter column（**已亲自复核**） |

### 建议改/验证（可连但有行为差异）

| # | 位置 | 问题 | 处理 |
|---|---|---|---|
| M1 | `memory_layer.py:84/85/122/157/158/186/187` | 7 处 `DateTime` 不带 `timezone=True`，与全表 `TIMESTAMPTZ` 混用 | 统一 `timezone=True` + 迁移 |
| M2 | `finalize_service.py:401` | `dialect.name == "sqlite"` 分支手动分配 id | PG 不进该分支（BigInteger+IDENTITY 自增），安全 ✓，仅验证 |
| M3 | `novel_service.py:965` | `_to_utc_if_possible` 假设 SQLite naive 即 UTC | PG 返回 aware，走 `astimezone` 分支，行为更正确 ✓，仅验证 |
| M4 | baseline 38 处 `server_default=sa.text('(CURRENT_TIMESTAMP)')` | PG 合法（带括号支持） | 验证时区语义一致性，无需改 |
| M5 | 47 处 `sa.JSON()` | PG 生成 `JSON` 非 `JSONB`，失去 GIN 索引/`@>` 查询/性能 | 可选：`JSON().with_variant(JSONB, "postgresql")` 保持跨库；不改也能跑 |
| M6 | `alembic/env.py:1` docstring | 注释只提 aiosqlite/asyncmy | 文档更新（代码无需改） |
| M7 | `llm_config_service.py:254` | 注释声称"sqlite 无法写 HttpUrl"，实际是 HttpUrl->Text 适配（dialect 无关） | 改注释，代码不动 |

### 无需改（自动兼容，已确认）

- **baseline migration**（`a53385d06521_baseline.py`）：`with_variant(mysql.LONGTEXT, 'mysql')` PG fallback 到 `Text`（PG TEXT 无限长=LONGTEXT）；`with_variant(Integer, 'sqlite')` PG 走 `BigInteger`（IDENTITY 自增）。**迁移文件零改动。**
- **session.py**：PG 走 `else` 分支（`pool_pre_ping`+`pool_recycle=3600`），`check_same_thread` 不会加到 PG。
- **alembic/env.py 主体**：dialect 无关。
- **Enum**：列全用 `String(32)`，无 `Enum()` 列，PG 无需 `CREATE TYPE`。
- **向量服务**：libsql 独立于主库，迁移主库零影响。

## 数据迁移方案（MySQL -> PG）

推荐 **pgloader**（声明式工具，自动类型映射：`AUTO_INCREMENT`->`SERIAL`、`LONGTEXT`->`TEXT`、`TINYINT(1)`->`BOOLEAN`、`utf8mb4`->`UTF8`）。

关键注意：
- 自增列迁移后 `setval` 同步序列当前值。
- `NovelProject.id` 是 `String(36)` UUID，非自增，直接搬。
- **H6 必须在数据迁移前先修**，否则 PG 建表就失败。
- 时区：MySQL `CURRENT_TIMESTAMP` 受会话 `time_zone` 影响，PG `TIMESTAMPTZ` 存绝对时间，迁移时统一转 UTC。

备选：mysqldump + 手工转换（繁琐）；自写 ETL（最可控最慢）。

## 验证策略

1. PG 建库跑 `alembic upgrade head`（验证 baseline 兼容 + H6 修复）。
2. 现有 sqlite 测试继续跑（验证 ORM 逻辑不破）。
3. 新增 PG 集成测试 profile（环境变量切 `DATABASE_URL` 指向 PG，覆盖 sqlite 盲区：类型严格性 / JSON vs JSONB / 大小写敏感 / 事务隔离 / 外键即时检查）。
4. 4 个静态测试处理 MySQL 方言 `.sql`（`test_tts_model_configuration`、`test_chapter_generation_trace_service` 等，改读 alembic 或提供 PG 版）。
5. 真机端到端：章节生成 7 步流水线、评审、伏笔追踪、RAG 检索。

## 回滚方案

- 保留 mysql 分支：`DB_PROVIDER` 仍支持 mysql，配置层不删除，随时切回。
- 灰度：PG 先作只读副本验证 -> 数据校对一致 -> 切写 -> 观察。
- 数据迁移期保留 MySQL 原库 7-30 天作为回滚数据源，不立即下线。

## 风险分级

| 等级 | 项 | 影响 |
|---|---|---|
| 🔴 高 | H6 FK 类型不匹配 | PG 建表直接失败，必须先修 |
| 🔴 高 | H3 CREATE DATABASE 反引号 | PG 首次启动建库失败 |
| 🟠 中 | H1/H2/H4/H5 连通性 | 不改连不上 PG，改动明确低风险 |
| 🟠 中 | M1 DateTime 时区混用 | 跨表时间比较异常 |
| 🟡 低 | M5 JSON 非 JSONB | 性能非最优，不改能跑 |
| 🟡 低 | 静态测试 dialect 耦合 | 测试维护成本 |
| ⚪ 无 | baseline / session / 向量服务 | 自动兼容 |

## 向量服务（不迁，说明）

libsql 独立于主库（`vector_store_service.py` 走 `libsql_client`，非 SQLAlchemy）。迁移主库零影响。换 pgvector 短期不建议：工作量大、`vector(N)` 固定维度约束与 `EMBEDDING_MODEL_VECTOR_SIZE` 可变冲突、需 `CREATE EXTENSION vector`、现有 `rag_vectors.db` 数据需迁。长期若要统一栈再单独评估。

## 工作量评估

代码改动约 80-120 行：
- config.py（白名单 + uri 分支 + postgres_* 字段）：~30 行
- init_db.py（CREATE DATABASE dialect + pg_database）：~15 行
- requirements.txt：+1 行
- memory_layer.py（FK × 4 + DateTime × 7）+ 新 alembic 迁移：~40 行
- 部署 compose + env：~25 行
