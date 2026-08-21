# 后端测试分层与 Docker 隔离

## Goal

让不依赖 PostgreSQL 的后端测试可在没有 Docker/Testcontainers 的环境中收集和运行，同时保留 PostgreSQL 集成测试的外部服务与容器回退能力。

## Background

- `backend/tests/conftest.py:23` 在 pytest 收集阶段顶层导入 Testcontainers；容器实际只在 `_pg_engine` 被请求且未配置 `TEST_POSTGRES_URL` 时启动。
- `backend/pytest.ini` 尚未注册 PostgreSQL 集成测试 marker，因此无法稳定选择快速测试或数据库测试。
- `backend/requirements-dev.txt` 锁定 Testcontainers 4.15.0；旧导入路径会产生弃用告警，community 路径是当前兼容入口。

## Requirements

- R1. 注册明确的 `postgres` pytest marker，并让依赖 `_pg_engine`、`db_session_factory` 或 `isolated_pg` fixture 的测试在收集阶段自动获得该 marker。
- R2. `-m "not postgres"` profile 不得导入或启动 Testcontainers，也不得要求 Docker 可用。
- R3. Testcontainers 仅在 `_pg_engine` 的容器回退分支内延迟导入，并使用 Testcontainers 4.15 的非弃用 community 路径。
- R4. 保持现有 `TEST_POSTGRES_URL` 优先、`pgvector/pgvector:pg16` 容器回退的选择顺序和连接行为。
- R5. 保持临时数据库、随机 schema、pgvector 初始化和失败清理契约不变。
- R6. 采用 marker 分层，不批量移动测试目录，不修改生产数据库代码、CI 或 Docker 部署配置。

## Acceptance Criteria

- [x] `postgres` marker 已注册，`--strict-markers` 下快速与 PostgreSQL profile 均可完成收集。
- [x] 所有通过三类 PostgreSQL fixture 间接或直接依赖 `_pg_engine` 的测试都会被 PostgreSQL profile 选中，并被快速 profile 排除。
- [x] 快速 profile 可在未配置 `TEST_POSTGRES_URL` 且不访问 Docker 的环境中运行，pytest 收集阶段不加载 Testcontainers。
- [x] 配置 `TEST_POSTGRES_URL` 时，PostgreSQL profile 仍使用外部服务创建并清理随机临时数据库。
- [x] 未配置 `TEST_POSTGRES_URL` 时，容器回退仍使用 `pgvector/pgvector:pg16`；若当前环境无 Docker，必须记录该运行时验证未执行。
- [x] 旧 `testcontainers.postgres` 弃用告警不再出现，既有 PostgreSQL 隔离测试仍通过。
- [x] 修改仅限 pytest 配置、测试 fixture 与覆盖该分层契约的聚焦测试。

## Out of Scope

- 重排或搬迁约 36 个 PostgreSQL 测试文件。
- 把 PostgreSQL 集成测试改写为 SQLite 或 mock 数据库测试。
- 修改生产数据库连接、Alembic、容器编排或 CI 工作流。
- 为其他外部服务建立新的通用测试分类框架。

## Notes

- 本任务是父任务 `08-22-technical-debt-program` 的第 1 项；完成并归档后再推进认证 HTTP 客户端任务。
- 当前无阻塞性开放问题。
