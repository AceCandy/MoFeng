# 废弃 _ensure_schema_updates 过渡态（alembic 覆盖全部列）

## Goal

L25 gap：alembic baseline a53385d06521 已建(34表)，但 init_db.py:124 _ensure_schema_updates 过渡态未废弃（手动ALTER补goals/highlights/character_states等列）。需确认 alembic upgrade head 能从空库建到当前schema含全部列 + 旧库已迁移，然后删 _ensure_schema_updates 调用(init_db.py:33)+定义(L124-233)+create_all(L31)。有数据风险，需在场验证。

## Requirements

- init_db 用 alembic upgrade head 替代 create_all + _ensure_schema_updates 过渡态；baseline migration 修复循环 FK + 建表顺序。

## Acceptance Criteria

- [x] init_db 删 create_all + _ensure_schema_updates，改 _run_alembic_upgrade（alembic upgrade head + 旧库 stamp 检测）
- [x] baseline 循环 FK 修复（chapter_versions<->chapters 用 use_alter 分离 + 34 表拓扑序重排 + models use_alter）
- [x] 三场景验证：新库 upgrade head 建全表 + 已管理库 no-op + 旧库 stamp head
- [x] schema 测试改测 alembic baseline（test_chapter_outline_structured_fields + test_tts_model_configuration）

## Notes

- Keep `prd.md` focused on requirements, constraints, and acceptance criteria.
- Lightweight tasks can remain PRD-only.
- For complex tasks, add `design.md` for technical design and `implement.md` for execution planning before `task.py start`.
