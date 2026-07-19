# 剔除 MySQL/SQLite 主库并迁移向量层至 pgvector

## Goal

将 MoFeng 从「三后端并存（mysql/sqlite/postgresql）」收敛为**只支持 PostgreSQL**：
1. 主业务库剔除 mysql/sqlite 全部分支与依赖，只留 postgresql。
2. 向量层从 libsql（sqlite 衍生）迁移到 pgvector，与主库统一在 PG。

是**替换/下线**，不是新增选项。推翻 `07-19-migrate-to-postgres` 的两个非目标（并存保留、libsql 不动）。

## Background

- 来源：2026-07-19 用户决策。前置任务 `07-19-migrate-to-postgres`（三后端并存）+ `07-19-pg-data-migration-verify`（34 表数据已迁 PG，行数+hash 双校验绿）已完成数据层迁移。
- 远程 PG `192.168.1.249:15432/mofeng`：41 表，alembic head `6e85c84f9541`，root superuser，pgvector 扩展可用（vector 0.8.5，未装）。
- 现状：`backend/.env` 仍 `DB_PROVIDER=mysql` 连 MySQL；PG 库已就绪但 backend 未切。
- 向量层 `vector_store_service.py`（546 行）深度依赖 libsql 原生 SQL，被 7 处调用（finalize/knowledge_retrieval/review_context/chapter_context/chapter_ingest/pipeline_orchestrator/writer.py）；`rag_chunks`/`rag_summaries` 不在 ORM，仅 libsql 原生 SQL 建表；`backend/storage/rag_vectors.db` 有现存向量数据。

## 用户决策（2026-07-19）

| 决策点 | 选择 |
|---|---|
| 8 个 sqlite in-memory 测试 | 改纯单元测试（mock DB 层） |
| libsql 向量库 | 一并剔除换 pgvector |
| 3 个 mysql CLI 脚本 + schema.sql | 删掉（alembic 已接管） |
| config 的 db_provider 字段 | 删字段（.env 不再有 DB_PROVIDER） |

## 阶段 1：主库 dialect 清理

### Requirements

- `config.py`：删 `db_provider`/`mysql_*`/`sqlite_db_path` 字段、`_normalize_db_provider` validator、`is_sqlite_backend` 属性；`sqlalchemy_database_uri` 删 sqlite/mysql 分支只留 postgresql（保留 `database_url` 覆盖入口）。
- `session.py`：删 `is_sqlite_backend` 分支，只留 `pool_pre_ping=True, pool_recycle=3600`。
- `init_db.py`：`_ensure_database_exists` 删 sqlite/mysql 分支，只留 `pg_database` 查询。
- `alembic/env.py`：注释改 asyncpg。
- 7 个 model：删 `BigInteger().with_variant(Integer,"sqlite")`->`BigInteger`；删 `Text().with_variant(LONGTEXT,"mysql")`->`Text`；删 `from sqlalchemy.dialects.mysql import LONGTEXT`。
- `finalize_service.py` L401、`llm_config_service.py` L255：删 sqlite 分支/注释（HttpUrl->str 转换保留，PG 下也安全）。
- `requirements.txt`：删 `asyncmy`、`aiosqlite`（`libsql-client` 暂留待阶段2）。
- 8 个 sqlite 测试：改 mock（mock repo/session 接口层，保留 service 编排验证意图；纯 SQL 级联验证类测试标注覆盖度风险）。
- 删 `deploy/scripts/verify_migration.sh`、`run_migrations.sh`、`rollback.sh`、`backend/db/schema.sql`。
- `backend/.env`：删 `DB_PROVIDER` + SQLITE/MYSQL 段，加 `POSTGRES_*`（指向 192.168.1.249:15432/mofeng, root）。
- `backend/env.example`、`deploy/.env.example`：同步只留 PG 配置。
- `deploy/docker-compose.yml`：删 db(mysql) 服务 + mysql-data/sqlite-data 卷 + MYSQL_*/SQLITE_* 环境变量；pg 服务保留（镜像阶段2换 pgvector）。
- `deploy/Dockerfile`：删 `default-libmysqlclient-dev` + SQLite 清理注释。
- `README.md`、`README-en.md`、`docs/DEPLOYMENT.md`：删 SQLite/MySQL 描述，改 PostgreSQL。

### 验证

- `alembic upgrade head` 在 PG 幂等（已 head，应 no-op）。
- backend 连 PG 启动，健康检查通过。
- 现有测试套件（mock 改造后）绿。

## 阶段 2：libsql -> pgvector

### Requirements

- `models`：新增 `RagChunk`/`RagSummary` ORM（含 `Vector(N)` 列，N=EMBEDDING_MODEL_VECTOR_SIZE）。
- alembic migration：`CREATE EXTENSION IF NOT EXISTS vector` + 建 rag_chunks/rag_summaries + HNSW/IVFFlat 索引。
- 重写 `vector_store_service.py`：libsql 原生 SQL -> SQLAlchemy Core/ORM + pgvector 操作符（`<=>`/`<->`）；保留 7 调用方公开接口（search/query_chunks/add_chapter_to_store 等）签名不变。
- 向量数据迁移：`rag_vectors.db` 现有数据 -> pgvector（float32 二进制 -> vector 文本格式）。
- `requirements.txt`：删 `libsql-client`，加 `pgvector`。
- `config.py`：删 `vector_db_url`/`vector_db_auth_token`（libsql 专用），向量配置复用主库 PG 连接。
- `deploy/docker-compose.yml`：pg 镜像 `postgres:16-alpine` -> `pgvector/pgvector:pg16`。

### 验证

- pgvector 扩展已装，rag 两表 + 索引建好。
- 向量数据迁移行数+抽样校验。
- RAG 检索端到端跑通（章节生成走知识检索）。

## 非目标

- 不动前端。
- 不动 Redis（缓存与 SSE）。
- 不改业务逻辑（仅换存储后端）。
- 不回填 MySQL（MySQL 原库保留观察期，仅读不写）。

## 风险

- **测试 mock 覆盖度**：8 测试中验证 ORM 级联/SQL 行为的（如 chapter_delete_policy）mock 后覆盖度下降，需 case-by-case 标注。
- **向量数据迁移**：libsql float32 二进制编码与 pgvector vector 文本格式转换，需校验维度一致。
- **pgvector 索引性能**：HNSW vs IVFFlat 取舍，建索引期间对写入有影响。
- **不可逆**：删 mysql/sqlite 代码后回滚需 git revert + MySQL 数据仍在（观察期内可恢复并存）。

## Acceptance Criteria

- [ ] 阶段1：backend 连 PG 启动健康，测试套件绿，`rg -i 'mysql|sqlite|aiosqlite|asyncmy' backend/app/ requirements.txt` 仅剩 libsql（阶段2处理）。
- [ ] 阶段2：pgvector 扩展装好，rag 两表+索引建好，向量数据迁移校验绿，RAG 端到端跑通。
- [ ] 全程 MySQL 原库不动（仅读），数据无损。
