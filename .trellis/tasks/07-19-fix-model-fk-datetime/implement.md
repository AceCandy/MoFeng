# Implement: 修复 model FK 类型与 DateTime 时区

> child of `07-19-migrate-to-postgres`。执行计划，配合 `design.md`。

## 前置确认（review gate 0）

- [ ] H6 数据完整性：dev mysql 库执行（4 表）
  ```sql
  SELECT MAX(LENGTH(project_id)) FROM character_states;
  SELECT MAX(LENGTH(project_id)) FROM timeline_events;
  SELECT MAX(LENGTH(project_id)) FROM causal_chains;
  SELECT MAX(LENGTH(project_id)) FROM story_time_trackers;
  ```
  确认均 ≤ 36。若有 >36 数据：停止，先排查（不应存在，project_id 源自 UUID String(36)）。

## 阶段 1：model 改动

- [ ] `backend/app/models/memory_layer.py` L43/97/134/170：`String(255)` → `String(36)`（4 处 project_id FK）
- [ ] `backend/app/models/memory_layer.py` L84/85/122/157/158/186/187：`DateTime` → `DateTime(timezone=True)`（7 处）
- 验证：`rg -n 'project_id = Column\(String\(255\)' backend/app/models/memory_layer.py` 应无结果；`rg -n 'DateTime\)' backend/app/models/memory_layer.py` 确认 7 处均带 `timezone=True`
- **注意**：L45 `character_name` 等业务字段 `String(255)` 不改，只改 project_id FK 列

## 阶段 2：alembic migration

- [ ] 新建 `backend/alembic/versions/<rev>_fix_memory_layer_fk_datetime.py`
  - `revision` 用 `cd backend && .venv/bin/python -c "import secrets; print(secrets.token_hex(12))"` 生成 12 字节 hex
  - `down_revision = 'a53385d06521'`
  - 按 `design.md` §3.2 模板写 upgrade/downgrade（batch_alter_table + postgresql_using）
- [ ] `cd backend && .venv/bin/alembic history` 确认新 rev 在 head

## 阶段 3：验证（review gate 1）

### 3.1 mysql 实测（dev 库）
- [ ] `cd backend && .venv/bin/alembic upgrade head`
- [ ] `cd backend && .venv/bin/alembic downgrade -1`
- [ ] `cd backend && .venv/bin/alembic upgrade head`（往返）

### 3.2 sqlite 实测
- [ ] 临时指向 sqlite 文件库（`DB_PROVIDER=sqlite` + 临时 DATABASE_URL），`alembic upgrade head` + `downgrade -1` + `upgrade head` 往返通过
  - 注意：sqlite 需 batch_alter_table 重建表，验证无报错

### 3.3 pytest
- [ ] `cd backend && .venv/bin/python -m pytest tests/ -x`（重点 test_finalize_service / test_chapter_delete_policy / test_chapter_generation_trace_service / test_chapter_outline_structured_fields 等连库测试）

### 3.4 H6 数据完整性
- [ ] dev 库 `MAX(LENGTH(project_id))` 查询（gate 0 已做，upgrade 后复查）

### 3.5 pg（代码就绪，不实测）
- [ ] migration 代码 review：`postgresql_using='project_id::varchar(36)'` 与 `postgresql_using=f"{col} AT TIME ZONE 'UTC'"` 语法正确
- [ ] 实测留 child 01 完成后

## review gate（trellis-check 复核）

- model diff 仅 11 处（4 FK + 7 DateTime），无扩大
- migration 跨方言（batch_alter_table + postgresql_using）
- mysql/sqlite 往返通过
- pytest 全绿
- pg 路径代码就绪（语法审查通过）
- `database-guidelines.md` L118-131 过时段落已标注（Phase 3.3 修）

## 回滚点

- model 改动后 migration 没跑：`git checkout backend/app/models/memory_layer.py` + 删 migration 文件
- migration 跑了但出错：`cd backend && .venv/bin/alembic downgrade -1` + git revert
- 已 commit：`git revert <commit>`

## 完成后

- [ ] Phase 3.3：spec update——修正 `database-guidelines.md` L118-131 过时段落（create_all/_ensure_schema_updates 已非生产路径）
- [ ] Phase 3.4：commit（model + migration + spec 修正，按 commit 风格）
- [ ] 提示用户 `/trellis:finish-work`
