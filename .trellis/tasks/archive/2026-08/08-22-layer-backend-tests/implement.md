# 后端测试分层与 Docker 隔离：实施计划

## Success Criteria

快速测试无需 Docker/Testcontainers，PostgreSQL 测试可被单独选择，并继续支持外部 PostgreSQL 与容器回退。

## Steps

1. 在最小聚焦测试中固定 marker 分类契约。
   - 数据库 fixture 闭包会获得 `postgres` marker。
   - 普通测试项不会被误标。
   - verify: 聚焦测试先失败，证明覆盖当前缺口。
2. 在 `backend/pytest.ini` 注册 `postgres` marker，在 `backend/tests/conftest.py` 增加 collection 分类 hook。
   - verify: 两个 profile 在 `--strict-markers` 下均可收集，且数据库测试只出现在 PostgreSQL profile。
3. 将 Testcontainers community 导入移动到 `_pg_engine` 的容器回退分支。
   - verify: 单独导入 conftest 后，`testcontainers` 未进入 `sys.modules`；旧路径弃用告警消失。
4. 运行快速 profile 与 PostgreSQL profile。
   - verify: 快速 profile 不访问 Docker；设置 `TEST_POSTGRES_URL` 后 PostgreSQL 隔离测试通过。
   - verify: Docker 可用时再运行未设置 `TEST_POSTGRES_URL` 的容器回退；不可用则明确记录为未验证。
5. 独立复核 diff 与完整影响面。
   - verify: 没有生产代码、CI、Docker 配置或测试目录迁移；相关后端规范检查通过。

## Validation Commands

```bash
cd backend
.venv/bin/python -m pytest -q tests/test_pytest_profiles.py --strict-markers
.venv/bin/python -m pytest --collect-only -q -m "not postgres" --strict-markers
.venv/bin/python -m pytest --collect-only -q -m postgres --strict-markers
.venv/bin/python -m pytest -q -m "not postgres" --strict-markers
TEST_POSTGRES_URL="<service-url>" .venv/bin/python -m pytest -q tests/test_postgres_isolation.py -m postgres --strict-markers
env -u TEST_POSTGRES_URL .venv/bin/python -m pytest -q tests/test_postgres_isolation.py -m postgres --strict-markers
```

最后一条仅在 Docker 可用时执行。实际实施时不得把 URL、凭据或本地环境值写入任务材料、日志摘要或提交信息。

## Risk and Rollback Points

- collection hook 必须在 marker 筛选前运行；若收集数量异常，先回滚 hook 并检查 fixture 闭包，不扩大为目录迁移。
- 快速 profile 若仍加载 Testcontainers，回到顶层 import 调用链定位，不用环境变量掩盖。
- PostgreSQL profile 若隔离测试失败，不修改既有数据库生命周期契约来迁就 marker；回滚本任务并单独诊断。

## Review Gate

- PRD、design、implement、research 与 JSONL 上下文均已复核。
- 只有用户在看到最新规划摘要后再次明确批准，才运行 `task.py start` 并修改测试代码。
