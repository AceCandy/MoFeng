# Explicit Database Bootstrap Design

## Process Roles

```text
db-create     -> 可选安装命令，只负责目标 database 存在
db-migrate    -> Alembic upgrade head
db-bootstrap  -> versioned data migrations / seeds
db-check      -> 只读检查 connection + alembic head + bootstrap minimum
api runtime   -> security validation + db-check + read-only prompt preload
worker        -> db-check + consume jobs
```

生产部署不默认授予 `CREATE DATABASE` 权限；`db-create` 只用于本地或明确的首次安装流程。

## Bootstrap Ledger

新增 bootstrap version ledger，记录 version、name、checksum、started/completed/failed time。执行器使用 PostgreSQL advisory lock 或等价互斥，单个 version 在事务内完成业务写入与 completed 标记。

步骤按不可变 version 注册，例如：

- 初始 system config defaults：只 insert missing，不覆盖 existing value。
- Prompt seed：按稳定 name insert missing；内容升级必须是新的显式 version，不随文件变化自动覆盖。
- default admin：只在显式配置且不存在时创建，凭据不写日志。
- historical key encryption：扫描/更新作为一次性 version，完成后不在 runtime 重跑。

## Readiness

- `/health` 保持轻量 liveness。
- `/ready` 或内部 readiness command 检查 `SELECT 1`、Alembic current=head、minimum bootstrap version。
- 依赖失败返回不可 ready，不触发修复动作。

## Deployment

Compose 使用同一应用镜像的 one-shot migrate/bootstrap service 或部署脚本显式串行执行。API 与 worker 只依赖成功结果，不通过导入 FastAPI app 获取初始化副作用。

## Compatibility

旧库无 Alembic version 时先生成只读 schema fingerprint（关键表、列、类型、约束和 index），只与代码登记的已知 baseline fingerprint 比较。完全匹配后，operator 通过显式 adopt 命令并确认备份才可 stamp；不匹配、部分匹配或未知结构一律 fail closed，不执行 stamp/upgrade。adoption 的 fingerprint、operator、时间和结果写入审计 ledger。

迁移采用两阶段发布：兼容 release 先让旧 runtime 理解 bootstrap ledger/readiness floor 并停止隐式 mutation；下一 release 才执行新的 bootstrap versions。执行后，rollback floor 是该兼容 release，任何不读取 ledger 的更旧 binary 都不是合法回滚目标。

旧 `init_db()` 在一个发布窗口内只能作为显式 CLI compatibility wrapper，且必须读取 ledger/fingerprint；runtime 不再调用它，contract 阶段删除 wrapper。

## Rollback

schema rollback 遵循 Alembic revision 策略；data bootstrap 默认 forward-only，需通过新 compensating version 修正。部署只能回滚到理解当前 ledger minimum 和 readiness floor 的 binary；不得通过脚本重新调用不识别 ledger 的旧函数。
