# 核对并收敛模型迁移默认值

## Goal

用模型定义、Alembic 历史和实际 PostgreSQL schema 三方证据判定 memory-layer 四表的默认值是否真实漂移；只修复会造成现有可观察行为或迁移不一致的已证实问题，不为形式统一制造迁移。

## Background

- 目标表为 `character_states`、`timeline_events`、`causal_chains`、`story_time_trackers`。
- 当前模型同时存在 Python-side `default`、`onupdate` 和少量 `server_default`；三者生效边界不同，不能仅因文本不一致判定缺陷。
- 配置 PostgreSQL 当前位于 Alembic head `c8e5f2a1d4b6`。只读 catalog 查询确认实际 schema 与迁移历史一致。
- CodeGraph 确认生产创建路径均通过 SQLAlchemy ORM，没有对四表的直接 SQL INSERT；现有路径会触发 Python-side default。
- 历史 `project_id` 长度问题已由 `03bb4c218e9e666ec466d0a3` 修复为 `String(36)`，不属于本任务。

## Requirements

- R1. 对目标字段记录模型、迁移历史、实际 PostgreSQL `column_default`/nullability/type 和生效边界。
- R2. `default` 仅覆盖 ORM 生成 INSERT，`server_default` 覆盖数据库省略列的 INSERT，`onupdate` 仅在 ORM 更新满足触发条件时生效；审计不得混淆三者。
- R3. 只有现有生产路径、迁移生命周期或真实 schema 出现可观察不一致时才修改模型或新增迁移。
- R4. 当前证据结论为无需模型或迁移修改：实际 schema 与迁移链一致，生产写入均走 ORM，未发现依赖缺失 server default 的路径。
- R5. 用现有 PostgreSQL 测试设施验证空库升级至 head 和 memory-layer ORM 写入；测试只能使用随机临时数据库，不得对配置业务库执行写操作。

## Acceptance Criteria

- [x] 四张目标表的默认值三方对照表完整，包含 Python default、server default、onupdate、实际类型和 nullability。
- [x] 实际 PostgreSQL revision 与 catalog 结果有可复核的只读查询记录。
- [x] 所有生产创建路径已核对；没有直接 SQL INSERT 或其他绕过 ORM default 的已知路径。
- [x] 空临时 PostgreSQL 数据库能够升级到 head 并通过 readiness；相关 memory-layer ORM 测试通过。
- [x] 不新增空迁移，不改写历史迁移，不重新处理已解决的 `project_id` 长度问题。
- [x] 执行期未出现与当前证据冲突的失败，无需返回规划或创建迁移。

## Out of Scope

- 推测性统一全仓时间戳或把所有 Python default 改成 server default。
- 与默认值无关的索引、外键、字段类型、nullability 或业务逻辑调整。
- 重写 `a53385d06521` baseline 或 `03bb4c218e9e666ec466d0a3` 历史迁移。
- 将配置业务库作为测试写入目标。
