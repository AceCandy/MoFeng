# Memory-layer 默认值审计

## 证据来源

- 模型：`backend/app/models/memory_layer.py`
- baseline：`backend/alembic/versions/a53385d06521_baseline.py`
- memory-layer 类型修复：`backend/alembic/versions/03bb4c218e9e666ec466d0a3_fix_memory_layer_fk_datetime.py`
- projection 字段迁移：`backend/alembic/versions/e7c9a1b2d3f4_expand_replayable_chapter_projections.py`
- 实际 PostgreSQL：Alembic head `c8e5f2a1d4b6`，通过 `information_schema.columns` 只读查询。

## 字段矩阵

| 表 | 字段 | 模型行为 | 迁移历史 | 实际 PostgreSQL |
| --- | --- | --- | --- | --- |
| character_states | chapter_revision | Python `0` + server `0` | projection revision 新增 server default | bigint，NOT NULL，default `0` |
| character_states | artifact_generation | Python `legacy` + server `legacy` | projection revision 新增 server default | varchar，NOT NULL，default `legacy` |
| character_states | is_active | Python `True` + server `true` | projection revision 新增 server default | boolean，NOT NULL，default `true` |
| character_states | created_at | Python UTC default | baseline 无 server default；后续只改 timezone | TIMESTAMPTZ，可空，无 default |
| character_states | updated_at | Python UTC default + onupdate | baseline 无 server default；后续只改 timezone | TIMESTAMPTZ，可空，无 default |
| timeline_events | importance | Python `5` | baseline 无 server default | integer，可空，无 default |
| timeline_events | is_turning_point | Python `False` | baseline 无 server default | boolean，可空，无 default |
| timeline_events | created_at | Python UTC default | baseline 无 server default；后续只改 timezone | TIMESTAMPTZ，可空，无 default |
| causal_chains | status | Python `pending` | baseline 无 server default | varchar，可空，无 default |
| causal_chains | importance | Python `5` | baseline 无 server default | integer，可空，无 default |
| causal_chains | created_at | Python UTC default | baseline 无 server default；后续只改 timezone | TIMESTAMPTZ，可空，无 default |
| causal_chains | updated_at | Python UTC default + onupdate | baseline 无 server default；后续只改 timezone | TIMESTAMPTZ，可空，无 default |
| story_time_trackers | time_system | Python `modern` | baseline 无 server default | varchar，可空，无 default |
| story_time_trackers | default_chapter_duration | Python `1 day` | baseline 无 server default | varchar，可空，无 default |
| story_time_trackers | created_at | Python UTC default | baseline 无 server default；后续只改 timezone | TIMESTAMPTZ，可空，无 default |
| story_time_trackers | updated_at | Python UTC default + onupdate | baseline 无 server default；后续只改 timezone | TIMESTAMPTZ，可空，无 default |

## 创建路径

CodeGraph 定位到的生产实例化点：

- `MemoryLayerService.update_character_state` 创建 `CharacterState`。
- chapter projection/finalize 路径创建 `CharacterState`。
- `MemoryLayerService.add_timeline_event` 创建 `TimelineEvent`。
- `MemoryLayerService.add_causal_chain` 创建 `CausalChain`。
- `MemoryLayerService.get_or_create_time_tracker` 创建 `StoryTimeTracker`。

未发现生产代码对四表执行直接 SQL INSERT。上述 ORM 路径均未显式传入的字段由 SQLAlchemy Python default 填充。

## 只读查询形状

```sql
SELECT version_num FROM alembic_version;

SELECT table_name, column_name, column_default, is_nullable, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name IN (
    'character_states',
    'timeline_events',
    'causal_chains',
    'story_time_trackers'
  )
ORDER BY table_name, column_name;
```

查询记录不保存连接地址、用户名或密码。

## 结论

模型、迁移历史和实际 schema 没有互相矛盾。缺少 server default 的字段均从 baseline 起保持该 DDL，当前生产写入依赖 ORM Python default，未发现绕过路径。因此当前无需新增迁移；若未来引入数据库直写、批量 COPY 或要求数据库层强制默认值，应以新的可观察契约单独规划。

## 验证记录

2026-08-22 使用项目 `backend/.venv` 和配置 PostgreSQL 服务执行；测试 fixture 只创建并清理随机临时数据库。

```bash
PYTHONPATH=. TEST_POSTGRES_URL='<configured asyncpg URL>' \
  .venv/bin/python -m pytest -q \
  tests/test_database_readiness.py::test_postgres_empty_and_current_database_lifecycle

PYTHONPATH=. TEST_POSTGRES_URL='<configured asyncpg URL>' \
  .venv/bin/python -m pytest -q \
  tests/test_project_memory_lock.py \
  tests/test_finalize_service.py \
  tests/test_chapter_delete_policy.py
```

- 数据库生命周期：`1 passed`，空库升级、重复迁移、bootstrap 与 readiness 通过。
- memory-layer ORM 路径：`14 passed`。
- 两次测试各有 1 条第三方 `passlib` 使用 Python `crypt` 的弃用警告，与本任务无关。
- 未启动项目服务或 PostgreSQL 容器；未对配置业务库执行写入。
