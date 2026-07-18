# Design: 修复 model FK 类型与 DateTime 时区

> child of `07-19-migrate-to-postgres`。H6（FK 类型不匹配）+ M1（DateTime 时区混用）。

## 1. 背景与范围

`memory_layer.py` 的 4 处 FK `String(255)` 与 `novel_projects.id String(36)` 类型不匹配（H6），7 处 `DateTime` 缺 `timezone=True`（M1）。**无论是否迁移 PG 都该修**：

- H6 是数据完整性隐患——`String(255)` 允许超长 project_id 写入，虽 UUID 实际 36 字符，但类型契约错误；MySQL 不强制 FK 类型匹配故放行，PG 严格校验会拒绝建 FK。
- M1 在 MySQL 下无实质效果（DATETIME 不存时区），但为 PG `TIMESTAMPTZ` 做准备，且对齐全项目 `DateTime(timezone=True)` 规范（`novel.py` 已遵守）。

## 2. 现状（磁盘确认）

### 2.1 H6：FK String(255) 残留（4 处）

`memory_layer.py` 4 表 `project_id` 用旧式 `Column(String(255), ForeignKey("novel_projects.id"))`：

| 行 | 表 |
|---|---|
| L43 | character_states |
| L97 | timeline_events |
| L134 | causal_chains |
| L170 | story_time_trackers |

对比 `novel_projects.id = mapped_column(String(36))`（`novel.py` L35）。

**范围精确性佐证**：baseline 里 `chapter_generation_traces.project_id`（L423）和 `foreshadowings.project_id`（L477）已是 `String(length=36)`。项目其他表已对齐，仅 memory_layer 4 表残留。修复无遗漏。

### 2.2 M1：DateTime 无时区（7 处）

`memory_layer.py` 7 处 `Column(DateTime, default=datetime.utcnow)`：

| 行 | 表 | 列 |
|---|---|---|
| L84/85 | character_states | created_at / updated_at |
| L122 | timeline_events | created_at |
| L157/158 | causal_chains | created_at / updated_at |
| L186/187 | story_time_trackers | created_at / updated_at |

对比 `novel.py` 规范：`DateTime(timezone=True) + server_default=func.now()`。

## 3. 方案

### 3.1 model 改动（最小 diff，保持旧式 Column API）

memory_layer.py 仍用旧式 `Column` API（迁移到 `mapped_column` 是独立重构，不在本任务范围）。只改：

- 4 处 `String(255)` → `String(36)`（仅 project_id FK 列；L45 character_name 等业务字段 String(255) 不动）
- 7 处 `DateTime` → `DateTime(timezone=True)`

### 3.2 alembic migration（跨方言 alter）

新建 `backend/alembic/versions/<rev>_fix_memory_layer_fk_datetime.py`，`down_revision='a53385d06521'`。用 `op.batch_alter_table` 包裹——sqlite 不支持 alter column type，batch 重建表；mysql/pg 直接 alter。

```python
from alembic import op
import sqlalchemy as sa

revision = '<rev>'
down_revision = 'a53385d06521'
branch_labels = None
depends_on = None

TABLES = ['character_states', 'timeline_events', 'causal_chains', 'story_time_trackers']
DATETIME_COLS = {
    'character_states': ['created_at', 'updated_at'],
    'timeline_events': ['created_at'],
    'causal_chains': ['created_at', 'updated_at'],
    'story_time_trackers': ['created_at', 'updated_at'],
}

def upgrade():
    for table in TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            # H6: String(255) -> String(36)
            batch_op.alter_column(
                'project_id',
                existing_type=sa.String(length=255),
                type_=sa.String(length=36),
                existing_nullable=False,
                postgresql_using='project_id::varchar(36)',
            )
            # M1: DateTime -> DateTime(timezone=True)
            for col in DATETIME_COLS[table]:
                batch_op.alter_column(
                    col,
                    existing_type=sa.DateTime(),
                    type_=sa.DateTime(timezone=True),
                    existing_nullable=True,
                    postgresql_using=f"{col} AT TIME ZONE 'UTC'",
                )

def downgrade():
    for table in TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            for col in DATETIME_COLS[table]:
                batch_op.alter_column(
                    col,
                    existing_type=sa.DateTime(timezone=True),
                    type_=sa.DateTime(),
                    existing_nullable=True,
                )
            batch_op.alter_column(
                'project_id',
                existing_type=sa.String(length=36),
                type_=sa.String(length=255),
                existing_nullable=False,
            )
```

### 3.3 实现修正（implement 阶段发现，trellis-check 确认）

实际 mysql 下 `batch_alter_table` 的 `recreate='auto'`（默认）对 FK 列 alter **不自动 drop FK**--MySQL ERROR 1832 禁止 alter 被 FK 引用的列类型（`Cannot change column 'project_id': used in a foreign key constraint`）。修正：用 `sa.inspect` reflect 各表 project_id FK 名称（`_get_project_id_fk_name`），mysql/pg 显式 `drop_constraint` + `alter_column` + `create_foreign_key`（保留 `ondelete='CASCADE'` 与原名称）；sqlite reflect 不到名称（None）则跳过，靠 batch 重建表自动处理 FK。见 `03bb4c218e9e666ec466d0a3_fix_memory_layer_fk_datetime.py` 实际实现。§3.2 原模板的 batch 自动 drop/recreate 假设不成立。

## 4. 三后端行为分析

| 后端 | H6 alter (String 255→36) | M1 alter (DateTime→tz) | 验证 |
|---|---|---|---|
| mysql | `MODIFY COLUMN VARCHAR(36)`；数据均 UUID(36) 无截断 | `DATETIME→DATETIME`（timezone=True 在 mysql 被忽略，noop） | 本任务实测 |
| sqlite | batch 重建表（sqlite 不支持 alter type） | batch 重建表；存储格式不变（TEXT ISO8601） | 本任务实测 |
| pg | `ALTER COLUMN TYPE VARCHAR(36) USING project_id::varchar(36)` | `TIMESTAMP→TIMESTAMPTZ USING col AT TIME ZONE 'UTC'` | **依赖 child 01**，本任务仅代码就绪 |

## 5. 边界与风险

### 5.1 M1 + default naive（prd 明确排除，仅标注）

model 的 `default=datetime.utcnow` 返回 naive datetime。加 `timezone=True` 后：

- mysql/sqlite：naive 写入 OK（mysql DATETIME 不存 tz；sqlite 存 TEXT）
- pg：naive datetime 写入 `TIMESTAMPTZ`，asyncpg 当 UTC 处理（不报错），功能正确但非最佳

prd 明确排除 default 统一（Python `default` vs `server_default` 是独立技术债）。本任务遵守，不扩大范围。后续 default 统一任务应改 `datetime.now(timezone.utc)` 或 `server_default=func.now()`。

### 5.2 pg 验证依赖 child 01

prd AC 写"三后端 `alembic upgrade head` 通过"，但 pg 接入在 child 01（pg-code-connect）。本任务实测 mysql + sqlite；pg 路径代码就绪（`postgresql_using` 已写），实际 pg upgrade 验证留到 01 完成后或 parent 集成阶段。

**建议**：本任务 AC 的"pg 通过"调整为"pg migration 代码就绪 + 语法审查"，实测在 01 后补。需用户确认是否接受此 AC 调整。

### 5.3 batch_alter_table 对 mysql 的开销

batch 对 mysql 改列类型通常 in-place（MODIFY COLUMN），不重建表。开发库表小，无性能风险。FK 约束由 alembic batch 自动 drop/recreate。

### 5.4 H6 数据完整性验证

升级前确认 `SELECT MAX(LENGTH(project_id))` 均 ≤ 36。project_id 源自 `NovelProject.id`（String(36) UUID），不会有超长数据。AC 含此项。

## 6. 验证策略

1. model 改动后 `alembic revision --autogenerate` 应产出空 diff（model 与新 migration 一致）——本任务手写 migration，autogenerate 仅作交叉验证
2. mysql/sqlite：`alembic upgrade head` + `alembic downgrade -1` + `alembic upgrade head` 往返通过
3. 既有 pytest 全绿（测试用 `Base.metadata.create_all` 从 model 建库，验证 model 层正确；**不验证 migration 脚本本身**，故 migration 需单独实跑）
4. H6 数据完整性：dev 库查 `MAX(LENGTH(project_id))`
5. pg：migration 代码 review（`postgresql_using` 语法），实测留 01

## 7. 回滚

- migration downgrade：batch 反向 alter（String(36)→String(255)，DateTime(tz)→DateTime）
- model revert：git revert 该 commit
- 生产回滚：`alembic downgrade -1` 后 redeploy 旧代码

## 8. spec 更新（Phase 3.3）

`database-guidelines.md` L118-131 过时：描述的 `Base.metadata.create_all` + `_ensure_schema_updates` fallback 在生产 `init_db.py` 已不存在（纯 alembic `_run_alembic_upgrade`：新库 upgrade head，旧库 stamp head 再 upgrade）。`create_all` 仅测试用。本任务 spec update 阶段修正该段，避免误导后续迁移任务。

## 9. 不做（明确排除）

- 不把 memory_layer.py 迁移到 `mapped_column` 新式 API（独立重构）
- 不统一 `default=datetime.utcnow` → `server_default=func.now()`（独立技术债，prd 排除）
- 不改 memory_layer 的 `character_id`/`caused_by_event_id` 等 BigInteger FK（它们与 BIGINT_PK_TYPE 在三后端下均兼容，非 H6 范围）
- 不实测 pg（依赖 child 01）
