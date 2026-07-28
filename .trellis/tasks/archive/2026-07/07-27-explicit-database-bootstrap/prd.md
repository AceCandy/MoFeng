# 拆分数据库 Migration、Bootstrap 与 Runtime

## Goal

把数据库创建、Alembic schema migration、一次性数据 bootstrap、readiness 和 API/worker runtime 拆成显式且可独立执行的职责，消除多进程启动时隐式写库和迁移竞争。

## Background

- FastAPI lifespan 每次启动都调用 `init_db()`，随后预热 Prompt：`backend/app/main.py:56-62`。
- `init_db.py` 当前依次处理建库、Alembic、默认管理员、旧配置清理、系统配置、Prompt seed 和历史 API key 加密：`backend/app/db/init_db.py:39-204`。
- Alembic 已经是 schema source of truth；问题不再是缺少 migration，而是 runtime 仍负责 migration/data mutation。
- durable job child 将引入独立 worker；若沿用当前入口，API 与 worker 可能并发执行初始化。

## Requirements

- DBB-1：提供显式 `db-create`（仅安装场景）、`db-migrate`、`db-bootstrap`、`db-check` 命令，职责互不重叠。
- DBB-2：API 和 worker runtime 不得执行 schema migration、创建管理员、seed 或历史数据迁移。
- DBB-3：data bootstrap 必须有 version ledger、事务、幂等和并发互斥；每个 version 只执行一次。
- DBB-4：默认配置、Prompt seed、管理员初始化必须定义 merge/overwrite 规则，不得在重启时覆盖用户修改。
- DBB-5：历史 API key 加密迁移进入受版本控制的数据迁移；日志不得包含 key 内容。
- DBB-6：部署顺序必须是 migrate → bootstrap → API/worker；migration 失败时 runtime 不得 ready。
- DBB-7：区分 liveness 与 readiness；readiness 至少验证 DB 可达、Alembic head、bootstrap minimum 和 binary rollback floor 一致。
- DBB-8：支持空库、当前版本库和旧库无 `alembic_version` 的既有兼容路径；legacy schema 必须先只读分类并匹配已知 baseline fingerprint，未知/不完整结构 fail closed，禁止自动 stamp。

## Dependencies

- 无技术前置；在 durable job 之前完成，确保新增 worker 使用干净启动边界。

## Acceptance Criteria

- [ ] 导入/启动 API 或 worker 不会执行 `CREATE DATABASE`、Alembic、seed、管理员创建或数据迁移。
- [ ] 空库通过显式命令可完成建库、migration 和 bootstrap；第二次运行无额外 mutation。
- [ ] 两个并发 bootstrap 进程只有一个执行每个 version，另一个安全退出或等待。
- [ ] legacy adoption 只接受登记的 schema fingerprint，并记录 operator、fingerprint、备份确认和 stamp 结果；未知结构不会改变数据库。
- [ ] schema 落后时 liveness 可存活但 readiness 失败，且给出不含密钥的诊断。
- [ ] 用户修改过的 Prompt/配置不会被后续 bootstrap 覆盖。
- [ ] deploy compose/script 明确包含 one-shot migrate/bootstrap，并让 API/worker 等待成功。
- [ ] `init_db.py` 不再是混合职责入口；对应直接测试覆盖每个命令。
- [ ] 执行新 bootstrap version 后只允许回滚到理解 ledger/readiness floor 的兼容版本；更旧 binary 拒绝部署或 readiness 失败。

## Out Of Scope

- 重做 Alembic baseline 或改换数据库引擎。
- 把生产数据库创建权限授予 API/worker。
- 自动轮换管理员凭据或业务密钥。
