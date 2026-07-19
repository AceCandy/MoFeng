# PG 迁移核心复核与技术栈优化点

> 本文件为主会话亲自调研 + 复核的结论（非子 agent 产出）。子 agent 全量调研见同目录 `dialect-scan.md` 与 `models-vector-test-deploy.md`。

## 一、核心文件复核（亲自 Read）

### 1. config.py 数据库配置段（L58-290）

- `database_url`（L59-63）：可选，填入后覆盖下方配置 -- **迁移 PG 的现成最小切入点**。
- `db_provider`（L64-68）：默认 mysql。
- `_normalize_db_provider`（L219-225）：白名单 `{"mysql","sqlite"}`，**显式拒绝其他** -> H1。
- `sqlalchemy_database_uri`（L243-280）：sqlite 分支（L260-270）+ mysql 分支（L272-280），**无 postgres 分支** -> H2。
- `is_sqlite_backend`（L282-285）：`get_backend_name() == "sqlite"`。
- `vector_db_url` / `vector_db_auth_token`（L143-152）：libsql 向量库，独立配置，与主库无关。

### 2. init_db.py（全文 Read）

- `_ensure_database_exists`（L88-127）：sqlite 分支（建父目录）vs 非 sqlite 分支。
- L121-124：`SELECT 1 FROM information_schema.schemata WHERE schema_name = :db` -- **PG 也有 information_schema，但查的是 schema 非 database** -> H4，需改查 `pg_database`。
- L126：`text(f"CREATE DATABASE \`{database}\`")` -- **反引号 MySQL 语法，PG 不兼容** -> H3。
- L117：`isolation_level="AUTOCOMMIT"` -- PG 也支持（CREATE DATABASE 需事务外）✓。
- `_run_alembic_upgrade`（L158-164）：alembic stamp/upgrade，dialect 无关。
- `_migrate_encrypt_provider_api_keys`（L183-198）：API key 加密迁移，dialect 无关。

### 3. alembic/env.py（全文 Read）

- L1 docstring："async 适配 aiosqlite/asyncmy" -> M6 文档更新。
- L21：`config.set_main_option("sqlalchemy.url", settings.sqlalchemy_database_uri)` -- **用应用配置的 uri，dialect 无关**。
- `async_engine_from_config`（L45）+ `NullPool` -- **按 drivername 自动选驱动**，只要 config 能生成 `postgresql+asyncpg://`，env.py 自动用 asyncpg。**env.py 主体无需改。**

### 4. baseline migration（`a53385d06521_baseline.py`）

- 只有 1 个版本文件（635 行，34 个 op.create_table，autogenerate 产物）。
- `from sqlalchemy.dialects import mysql`（L12）+ `sa.Text().with_variant(mysql.LONGTEXT(), 'mysql')`（13 处）-- PG fallback 到 `Text`（PG TEXT 无限长=LONGTEXT）✓。
- `sa.BigInteger().with_variant(sa.Integer(), 'sqlite')`（多处主键）-- PG 走 `BigInteger`（IDENTITY 自增）✓。
- `server_default=sa.text('(CURRENT_TIMESTAMP)')`（38 处）-- PG 合法（带括号支持）✓。
- `sa.JSON()`（约 30 处）-- PG 用 `JSON`（非 JSONB），可用 -> M5 可选优化。
- **结论：baseline 脚本天然兼容 PG，无需改。**

### 5. FK 类型不匹配（亲自复核）

- `memory_layer.py:43/97/134/170`：`project_id = Column(String(255), ForeignKey("novel_projects.id"...))`
- `novel.py:35`：`NovelProject.id = mapped_column(String(36), primary_key=True)`
- **String(255) vs String(36) 不匹配确认** -> H6。MySQL 放行，PG 外键严格性拒绝。既是迁移阻塞，也是既有技术债。

### 6. finalize_service dialect 分支

- `finalize_service.py:401`：`if self.db.get_bind().dialect.name == "sqlite":` -- SQLite 补 BigInteger 不自增的坑。PG 用 IDENTITY 自增，**不进该分支，安全** ✓。

### 7. 无全文搜索

- `rg "FULLTEXT|MATCH.*AGAINST|tsvector|to_tsquery"` 零匹配。迁移 PG 不涉及全文搜索迁移；PG tsvector 是未来收益点。

## 二、技术栈优化点（独立于 PG 迁移）

### A. 死/过时依赖

- `@types/marked ^5` + `marked ^16`（`frontend/package.json:27,30`）：marked 5+ 自带类型，`@types/marked` 过时冲突，应删（与已清理的 @headlessui 同类）。
- FastAPI 0.110（`requirements.txt:1`）偏旧，Pydantic 已 2.12，FastAPI 0.115+ 才完整对齐。
- redis-py 5.0.7 / asyncmy 0.2.9 偏旧，稳定可不动。

### B. 代码债

- Pydantic V1 `@validator` deprecated（`config.py:214/219/226/234` 等），应迁 `@field_validator`。
- model 与 migration default 不一致：model 用 `Column(DateTime, default=datetime.utcnow)`（Python 层），migration 用 `server_default=sa.text('(CURRENT_TIMESTAMP)')`（DB 层）-- autogenerate 噪音根源。
- FK 类型不匹配（H6）。
- DateTime 时区混用（M1）。
- `backend/db/schema.sql` + `backend/db/migrations/*.sql` 是 alembic 之前的旧迁移系统（MySQL 方言），被 4 个静态测试读取 -- 两套迁移系统并存，应择一保留。
- 静态测试 dialect 耦合（`test_tts_model_configuration.py:219`、`test_chapter_generation_trace_service.py:22` 等）。

### C. 架构

- 向量服务 libsql 独立于主库（双写无事务）。
- Celery 已清理 ✓。
- 前端 bundle budget 自检 ✓（好实践）。
- 无全文搜索（PG tsvector 是迁 PG 的潜在收益）。

## 三、验证了什么 / 没验证什么

**亲自核实**：config.py 数据库配置段、init_db.py 全文、alembic/env.py、baseline 脚本 dialect 用法、`memory_layer.py:43` 与 `novel.py:35` FK 类型不匹配、`backend/db/` 存在旧 sql、finalize_service dialect 分支、零全文搜索、前端 marked 类型包冲突。

**子调研覆盖**（基于真实代码，给出行号可查）：dialect 全量扫描见 `dialect-scan.md`、models 类型/向量服务/测试栈/部署配置见 `models-vector-test-deploy.md`。

**没验证**：未实际搭 PG 跑 `alembic upgrade head`（静态分析结论）；pgloader 数据迁移未实测；FastAPI 升级兼容性未测。
