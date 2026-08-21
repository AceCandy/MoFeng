# 后端测试分层与 Docker 隔离：技术设计

## Boundaries

本任务只调整 pytest 测试基础设施：`backend/pytest.ini`、`backend/tests/conftest.py`，以及覆盖 marker 契约的最小测试。生产数据库代码、测试目录结构、CI 与 Docker 配置保持不变。

## Marker Contract

- 注册 `postgres` marker，含义是测试需要真实 PostgreSQL 服务。
- 在 `pytest_collection_modifyitems` 中检查测试项的 fixture 闭包；命中 `_pg_engine`、`db_session_factory` 或 `isolated_pg` 时添加 `pytest.mark.postgres`。
- collection hook 使用 `tryfirst=True`，保证 marker 表达式筛选前完成分类。
- 新测试若直接管理 PostgreSQL 且不依赖上述 fixture，必须显式添加 `postgres` marker；本任务不建立更通用的外部服务分类框架。

## Runtime Flow

```text
pytest collection
  -> fixture closure classification
  -> postgres / not postgres marker selection
  -> only selected tests enter fixture setup

_pg_engine setup
  -> TEST_POSTGRES_URL present
       -> existing disposable database flow
  -> TEST_POSTGRES_URL absent
       -> import testcontainers.community.postgres
       -> start pgvector/pgvector:pg16
       -> existing disposable database flow
```

快速 profile 在 collection 和执行阶段都不会进入 `_pg_engine`，因此不会导入 Testcontainers 或访问 Docker。PostgreSQL profile 继续复用既有 `_temporary_postgres_engine` 与 `_isolated_postgres_scope`，数据库命名、pgvector 初始化、search path 和清理顺序不变。

## Compatibility

- 保留 `TEST_POSTGRES_URL` 的服务定位语义，不直接修改该 URL 指向的业务数据库。
- 保留 `pgvector/pgvector:pg16`、`driver="asyncpg"` 与 session event-loop 契约。
- 将弃用的 `testcontainers.postgres` 改为 Testcontainers 4.15 已提供的 `testcontainers.community.postgres`，类与连接 URL 行为不变。
- 不给现有约 36 个数据库测试文件逐个添加装饰器，也不移动目录。

## Trade-offs

中央 fixture 分类比逐文件 marker 的 diff 更小，也能覆盖通过 `db_session_factory` 或 `isolated_pg` 间接依赖 PostgreSQL 的测试。代价是新建的独立 PostgreSQL fixture 必须依赖 `_pg_engine` 或显式标记；该约束在 marker 描述和聚焦测试中固定。

## Rollback

本任务无数据迁移。若 marker 选择产生遗漏，可单独回滚 collection hook、marker 注册和延迟导入，恢复原测试入口；生产行为和数据库 schema 不受影响。
