# 验证记录

## Targeted Checks

- `pytest -q tests/test_pytest_profiles.py --strict-markers`: 1 passed；旧 Testcontainers 弃用告警不再出现。
- `ruff check tests/conftest.py tests/test_pytest_profiles.py`: passed。
- `pytest --collect-only -q -m "not postgres" --strict-markers`: 460 selected，237 deselected。
- `pytest --collect-only -q -m postgres --strict-markers`: 237 selected，460 deselected。
- 单独导入 `conftest` 后检查 `sys.modules`: 未加载 `testcontainers`。

## PostgreSQL Paths

- 未设置 `TEST_POSTGRES_URL`，通过 Testcontainers 容器回退运行 `test_postgres_isolation.py`: 7 passed。
- 使用临时 pgvector 服务设置 `TEST_POSTGRES_URL` 运行同一文件: 7 passed；验证容器已删除。
- 完整 PostgreSQL profile: 236 passed，1 unrelated failure，460 deselected。

## Full Fast Profile

- 完整快速 profile: 459 passed，1 unrelated failure，237 deselected。

## Unrelated Existing Failures

- `test_openapi_inventory_and_operation_ids_preserve_the_baseline`: 当前 OpenAPI paths 为 88，测试基线为 87；本任务未修改路由或 schema。
- `test_workflow_transition_adapter_maps_ambiguity_cancel_and_failure`: 实际事件含 `activity.ambiguous`，测试期望列表缺少该事件；本任务未修改 durable-job 生产代码或该测试。

上述失败不在本子任务范围内，未进行顺带修复。
