# AIMETA P=LangGraph_checkpoint_schema契约|R=外部表名_pinned版本|NR=不连接数据库或执行DDL|E=CHECKPOINT_TABLES|X=internal|A=contract|D=none|S=none|RD=./README.ai
"""Pinned LangGraph PostgreSQL checkpoint schema identifiers."""

CHECKPOINT_TABLES = frozenset(
    {"checkpoint_migrations", "checkpoints", "checkpoint_blobs", "checkpoint_writes"}
)
CHECKPOINT_MIGRATION_VERSIONS = tuple(range(10))
