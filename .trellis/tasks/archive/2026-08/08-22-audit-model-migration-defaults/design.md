# 技术设计

## 审计边界

本任务是证据型审计，不预设必须产生代码。只检查 `backend/app/models/memory_layer.py` 的四个模型、对应 Alembic revision、实际 PostgreSQL catalog 和生产创建路径。

## 三方结论

| 表/字段组 | 模型 | 迁移与实际 schema | 结论 |
| --- | --- | --- | --- |
| `character_states.chapter_revision/artifact_generation/is_active` | Python default + server default | 后续 projection migration 与实际 default 分别为 `0`、`legacy`、`true`，均 NOT NULL | 一致 |
| 四表 `created_at`、三表 `updated_at` | Python UTC default；`updated_at` 另有 Python onupdate | baseline 无 server default；实际为可空 TIMESTAMPTZ、无 column default | 职责差异，不是 schema 漂移 |
| `timeline_events.importance/is_turning_point` | Python default `5/False` | baseline 与实际均无 server default、列可空 | ORM 路径一致，无直接 SQL 依赖 |
| `causal_chains.status/importance` | Python default `pending/5` | baseline 与实际均无 server default、列可空 | ORM 路径一致，无直接 SQL 依赖 |
| `story_time_trackers.time_system/default_chapter_duration` | Python default `modern/1 day` | baseline 与实际均无 server default、列可空 | ORM 路径一致，无直接 SQL 依赖 |

## 生效契约

- Python `default` 在 SQLAlchemy 生成且未显式提供该列的 INSERT 中生效。
- `server_default` 属于数据库 DDL，在绕过 ORM 或显式省略列时生效。
- Python `onupdate` 不是数据库触发器，只在 SQLAlchemy 发出符合条件的 UPDATE 时生效。
- 当前生产创建点为 `MemoryLayerService`、chapter projection/finalize 服务中的 ORM 实例化；未发现对四表的直接 INSERT。

## 决策

不新增迁移、不改模型。形式上补齐 server default 会扩大数据库直写契约，并可能改变非 ORM 写入的 NULL 行为；当前没有调用方或故障证据要求该行为。最小且风险最低的交付是保留审计材料，并用现有迁移生命周期和 ORM 测试验证结论。

## 验证与回滚

- 对配置 PostgreSQL 仅执行 catalog/readiness 只读查询。
- PostgreSQL pytest 通过 `TEST_POSTGRES_URL` 创建并销毁随机临时数据库；不写配置业务库。
- 因无产品代码和迁移改动，无 schema 回滚动作；若验证推翻结论，停止并返回 Phase 1 重新设计迁移。
