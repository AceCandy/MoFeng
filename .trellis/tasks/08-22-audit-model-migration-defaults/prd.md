# 核对并收敛模型迁移默认值

## Goal

用实际 schema 与迁移历史核对 SQLAlchemy 模型默认值，只修复会造成可观察行为或迁移漂移的已证实不一致。

## Background

- 已观察到 `memory_layer.py` 的 Python `created_at` default 与 Alembic server default 可能存在漂移，但尚未证明需要 schema 变更。
- 既有 memory-layer `project_id` 长度已统一为 `String(36)`，不属于本任务。

## Requirements

- R1. 对目标模型、Alembic 历史和实际 PostgreSQL schema 建立默认值对照表。
- R2. 区分 Python-side default、server default 与 `onupdate` 的生效边界，先确认用户可见或迁移影响再修改。
- R3. 仅修复证据充分的不一致；若现状正确，输出审计结论而不生成空迁移。
- R4. 若需要迁移，迁移必须可升级、可回滚，并与模型定义一致。

## Acceptance Criteria

- [ ] 目标字段均有模型、迁移历史与实际 schema 三方对照结论。
- [ ] 每项修改均关联明确的不一致证据和可观察影响；无证据项保持不变。
- [ ] 如生成迁移，空 PostgreSQL 数据库 upgrade/downgrade/upgrade 与相关模型测试通过。
- [ ] 如无需修改，PRD/研究材料记录“无需迁移”的可复核证据。
- [ ] 不重新处理已解决的 `project_id` 长度问题。

## Out of Scope

- 推测性统一所有时间字段或重写迁移历史。
- 与默认值无关的索引、外键、字段类型或业务逻辑调整。

## Notes

- 本任务按父任务顺序在遗留编辑器契约任务完成后启动；这是“先审计、后决定是否改代码”的任务。
