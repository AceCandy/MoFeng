# 后端 pytest 分层现状

## Confirmed Evidence

- `backend/tests/conftest.py:23` 顶层导入 `testcontainers.postgres.PostgresContainer`，所以任何 pytest 收集都会加载 Testcontainers。
- `_pg_engine` 位于 `backend/tests/conftest.py:226-244`：优先读取 `TEST_POSTGRES_URL`；只有未配置时才启动 `pgvector/pgvector:pg16` 容器。
- `_temporary_postgres_engine` 位于 `backend/tests/conftest.py:61-103`：创建 `mofeng_pytest_<uuid>` 临时数据库、安装 vector、建表并在结束时终止连接和删除数据库。
- `db_session_factory` 与 `isolated_pg` 分别位于 `backend/tests/conftest.py:252-276`，都依赖 `_pg_engine`。
- `backend/pytest.ini` 只有 session loop 配置，没有 PostgreSQL marker。
- 磁盘检索显示约 36 个测试文件请求 `_pg_engine`、`db_session_factory` 或 `isolated_pg`；逐文件迁移或装饰会产生无必要的大 diff。
- `backend/requirements-dev.txt` 锁定 `testcontainers==4.15.0`。该版本本地源码中的 `testcontainers/postgres.py` 仅转发到 `testcontainers.community.postgres` 并发出弃用告警；community 模块直接定义 `PostgresContainer`。

## Applicable Project Contracts

- `.trellis/spec/backend/quality-guidelines.md` 要求 PostgreSQL 锁、迁移、lease/fencing、事件顺序与异步驱动行为使用 PostgreSQL 集成测试，不能用 SQLite 替代。
- `.trellis/spec/backend/database-guidelines.md` 规定 `TEST_POSTGRES_URL` 只定位服务，测试必须创建随机临时数据库并完整清理。
- `.trellis/spec/backend/index.md` 要求数据库生命周期变更运行聚焦测试并使用隔离 PostgreSQL 验证。

## Decision

采用一个已注册的 `postgres` marker，并在 collection 阶段按 fixture 闭包自动分类。Testcontainers 导入移动到 `_pg_engine` 的容器回退分支并改用 community 路径。保留现有数据库隔离实现，不移动测试文件、不新增依赖。

## Verification Focus

- marker 分类发生在 `-m` 筛选前。
- 快速 profile 的 collection 与执行都不加载 Testcontainers。
- 外部 URL 与容器回退仍进入同一个临时数据库生命周期。
- 新增独立 PostgreSQL fixture 时必须依赖 `_pg_engine` 或显式标记。
