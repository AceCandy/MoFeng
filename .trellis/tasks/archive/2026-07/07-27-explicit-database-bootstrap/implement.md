# Explicit Database Bootstrap Implementation Plan

## Steps

- [x] 提取现有 `init_db.py` 每项职责和数据覆盖规则，补 characterization tests。
- [x] 增加 CLI/entrypoints 与只读 schema/bootstrap check。
- [x] 定义已知 legacy baseline fingerprints、只读 classification、显式 adopt/stamp 与审计记录；未知结构 fail closed。
- [x] 增加 bootstrap ledger Alembic migration、互斥执行器和版本化步骤。
- [x] 将历史 key 加密、Prompt/config/admin seed 迁入显式 version。
- [x] 从 FastAPI lifespan 移除 mutation，只保留 security check、readiness 和 read-only preload。
- [x] 建立 ledger-aware rollback floor，并更新 Compose/scripts，使 migrate/bootstrap 在 API/worker 前执行；部署规范要求先落兼容 binary，再执行新的 bootstrap version。
- [x] 删除本任务产生的兼容 dead code，并独立复核启动导入链；仅保留设计要求的一个发布窗口兼容 wrapper。

## Validation

```bash
cd backend
pytest tests/test_database_bootstrap.py tests/test_database_readiness.py
alembic current
alembic upgrade head
```

必须增加 PostgreSQL integration cases：empty/current/legacy database、重复执行、双进程竞争和 migration failure。不要只用 SQLite 证明此契约。

## Validation Record

- Final integration rerun (2026-07-31): the isolated PostgreSQL backend suite passed `603` tests, including empty/current/legacy migration, rollback, repeated bootstrap and concurrent bootstrap coverage.
- Alembic reported a single head; bundled and external PostgreSQL Compose configurations parsed successfully.
- Bash syntax checks and `git diff --check` passed.
- PowerShell runtime validation was not executed because `pwsh` is unavailable; static deployment contract tests passed.

## Rollback

- 保留一个发布窗口的兼容 CLI wrapper，但 API/worker 不恢复隐式 migration。
- deploy 只可回退到理解当前 ledger/readiness floor 的兼容 binary，不允许调用更旧的隐式初始化函数。
- data bootstrap 使用补偿 version，不删除 ledger 历史。
