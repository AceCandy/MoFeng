"""fix memory layer fk datetime

修复 memory_layer 4 表 project_id FK 类型不匹配（H6：String(255)->String(36)，
与 novel_projects.id String(36) 一致）+ 7 处 DateTime 加 timezone=True（M1）。

跨方言处理：
- mysql：严格限制 FK 列 alter type，必须先 drop FK 再 alter 再 recreate（reflect FK 名称）
- postgresql：允许兼容类型 alter，但 drop+recreate 也安全且保留 postgresql_using 显式转换
- sqlite：走 batch_alter_table 重建表路径，reflect 不到 FK 名称（None），跳过显式 drop/recreate

pg 路径代码就绪，实测留 child 01 (pg-code-connect) 完成后补。

Revision ID: 03bb4c218e9e666ec466d0a3
Revises: a53385d06521
Create Date: 2026-07-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '03bb4c218e9e666ec466d0a3'
down_revision: Union[str, None] = 'a53385d06521'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# 4 表 project_id FK：String(255) -> String(36)，与 novel_projects.id 对齐
TABLES = ['character_states', 'timeline_events', 'causal_chains', 'story_time_trackers']

# 7 处 DateTime -> DateTime(timezone=True)，与全表 TIMESTAMPTZ 规范对齐
DATETIME_COLS = {
    'character_states': ['created_at', 'updated_at'],
    'timeline_events': ['created_at'],
    'causal_chains': ['created_at', 'updated_at'],
    'story_time_trackers': ['created_at', 'updated_at'],
}


def _get_project_id_fk_name(bind, table):
    """reflect 表的 project_id FK 约束名称。

    不同 dialect 命名规则不同：mysql 默认 <table>_ibfk_<n>，pg 默认 <table>_<column>_fkey，
    sqlite 通常无名称。reflect 不到名称时返回 None（sqlite batch 重建表自动处理 FK）。
    """
    inspector = sa.inspect(bind)
    for fk in inspector.get_foreign_keys(table):
        if 'project_id' in (fk.get('constrained_columns') or []):
            return fk.get('name')
    return None


def upgrade() -> None:
    bind = op.get_bind()
    # 反映各表 project_id FK 名称；None 表示该 dialect 无命名 FK（sqlite），由 batch 自动处理
    fk_names = {t: _get_project_id_fk_name(bind, t) for t in TABLES}

    for table in TABLES:
        fk_name = fk_names[table]
        with op.batch_alter_table(table, schema=None) as batch_op:
            if fk_name:
                # mysql/pg: 显式 drop FK 约束（mysql 修改 FK 列类型前必须 drop）
                batch_op.drop_constraint(fk_name, type_='foreignkey')
            # H6: project_id FK String(255) -> String(36)
            batch_op.alter_column(
                'project_id',
                existing_type=sa.String(length=255),
                type_=sa.String(length=36),
                existing_nullable=False,
                postgresql_using='project_id::varchar(36)',
            )
            if fk_name:
                # mysql/pg: recreate FK 约束（保留 ondelete='CASCADE' 与原名称）
                batch_op.create_foreign_key(
                    fk_name, 'novel_projects', ['project_id'], ['id'], ondelete='CASCADE'
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


def downgrade() -> None:
    bind = op.get_bind()
    fk_names = {t: _get_project_id_fk_name(bind, t) for t in TABLES}

    for table in TABLES:
        fk_name = fk_names[table]
        with op.batch_alter_table(table, schema=None) as batch_op:
            if fk_name:
                batch_op.drop_constraint(fk_name, type_='foreignkey')
            # M1 反向：DateTime(timezone=True) -> DateTime
            for col in DATETIME_COLS[table]:
                batch_op.alter_column(
                    col,
                    existing_type=sa.DateTime(timezone=True),
                    type_=sa.DateTime(),
                    existing_nullable=True,
                )
            # H6 反向：project_id String(36) -> String(255)
            batch_op.alter_column(
                'project_id',
                existing_type=sa.String(length=36),
                type_=sa.String(length=255),
                existing_nullable=False,
            )
            if fk_name:
                batch_op.create_foreign_key(
                    fk_name, 'novel_projects', ['project_id'], ['id'], ondelete='CASCADE'
                )
