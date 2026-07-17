# 废弃 _ensure_schema_updates 过渡态（alembic 覆盖全部列）

## Goal

L25 gap：alembic baseline a53385d06521 已建(34表)，但 init_db.py:124 _ensure_schema_updates 过渡态未废弃（手动ALTER补goals/highlights/character_states等列）。需确认 alembic upgrade head 能从空库建到当前schema含全部列 + 旧库已迁移，然后删 _ensure_schema_updates 调用(init_db.py:33)+定义(L124-233)+create_all(L31)。有数据风险，需在场验证。

## Requirements

- TBD

## Acceptance Criteria

- [ ] TBD

## Notes

- Keep `prd.md` focused on requirements, constraints, and acceptance criteria.
- Lightweight tasks can remain PRD-only.
- For complex tasks, add `design.md` for technical design and `implement.md` for execution planning before `task.py start`.
