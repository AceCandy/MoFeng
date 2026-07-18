# 修复 model FK 类型与 DateTime 时区

## Goal

修复 `memory_layer.py` 的 FK 类型不匹配（H6）与 DateTime 时区混用（M1）。**无论是否迁移 PG 都该修**（既是迁移阻塞，也是既有技术债 + 数据完整性隐患）。parent: `07-19-migrate-to-postgres`。

## Requirements

- `memory_layer.py:43/97/134/170` FK `String(255)` -> `String(36)`（与 `novel_projects.id String(36)` 一致）（H6）
- `memory_layer.py:84/85/122/157/158/186/187` 共 7 处 `DateTime` 加 `timezone=True`（M1）
- 新 alembic 迁移脚本：alter column type（String(255)->String(36)）+ DateTime 加时区
- model 与 migration default 不一致（Python default vs server_default）不在本任务范围（独立技术债）

## Acceptance Criteria

- [ ] `memory_layer.py` FK 类型与 `novel_projects.id` 一致（String(36)）
- [ ] `memory_layer.py` DateTime 全 `timezone=True`
- [ ] mysql `alembic upgrade head` 往返通过（upgrade + downgrade -1 + upgrade，实测）
- [ ] sqlite 新 migration 往返通过（create_all + stamp baseline + downgrade + upgrade 实测）；注：baseline `a53385d06521` 在 sqlite 从零 `upgrade head` 因 `use_alter=True` FK 预存问题不可达，独立 follow-up
- [ ] pg migration 代码就绪 + 语法审查（`postgresql_using` 正确；实测 `alembic upgrade head` 依赖 child 01 完成后补，本任务不实测）
- [ ] 既有 pytest 全绿（含 test_finalize_service / test_chapter_delete_policy 等连库测试）
- [ ] H6 数据完整性验证（现有数据均在 String(36) 长度内，迁移无数据丢失）

## Notes

- 技术细节见 parent `design.md`（H6、M1）与 `research/models-vector-test-deploy.md` 第 1.6/1.4 节。
- 依赖：无。**建议最先做**（独立于 PG 迁移，纯技术债修复）。
- `task.py start` 前补 `design.md` + `implement.md`。
