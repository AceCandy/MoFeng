# Design: ProjectMemory 乐观锁

## 机制

乐观锁 = `UPDATE ... SET version=version+1, <fields> WHERE id=? AND version=expected_version`。
`rowcount=0` 表示冲突（version 不匹配，期间被其他事务改过）。

用 SQLAlchemy `update()` 语句（非 ORM setattr），避免 expire_on_commit 干扰，且能拿到 rowcount。

## 写点改造

### 1. put_project_memory（projects.py:165-190）

`ProjectMemoryPayload` 加 `expected_version: Optional[int]`。

- memory 存在：`expected_version` 必填，`update()` 守卫，rowcount=0 返回 409。
- memory 不存在：新建（version default=1），无需守卫。
- 返回值带 `version`（前端下次编辑用）。

```python
data = payload.model_dump(exclude_unset=True)
data.pop("expected_version", None)
update_values = {k: v for k, v in data.items() if hasattr(ProjectMemory, k)}

if memory:
    if payload.expected_version is None:
        raise HTTPException(400, "缺少 expected_version")
    stmt = (
        update(ProjectMemory)
        .where(ProjectMemory.id == memory.id, ProjectMemory.version == payload.expected_version)
        .values(**update_values, version=ProjectMemory.version + 1)
    )
    result = await session.execute(stmt)
    if result.rowcount == 0:
        raise HTTPException(409, "记忆已被修改，请刷新后重试")
    await session.refresh(memory)
else:
    memory = ProjectMemory(project_id=project_id, **update_values)
    session.add(memory)
    await session.commit()
    await session.refresh(memory)
```

### 2. finalize_chapter（finalize_service.py:189-279）

难点：跨事务（读 commit → LLM → 写回）。

- line 192 读 memory 后，**commit 前**记 `memory_id = project_memory.id` + `old_version = project_memory.version`（commit 后对象 expire，需提前记）。
- 写回（line 250-279）改用 `update()` 语句守卫 `old_version`：

```python
update_values = {"last_updated_chapter": chapter_number, "version": ProjectMemory.version + 1}
if new_summary:
    update_values["global_summary"] = new_summary
if new_plot_arcs:
    update_values["plot_arcs"] = new_plot_arcs
stmt = (
    update(ProjectMemory)
    .where(ProjectMemory.id == memory_id, ProjectMemory.version == old_version)
    .values(**update_values)
)
update_result = await self.db.execute(stmt)
if update_result.rowcount == 0:
    result["conflict"] = True  # memory 被并发改，保留对方，LLM 结果在 snapshot
```

- snapshot 创建（line 266）用 `new_summary`/`new_plot_arcs` 变量，不依赖 memory 属性，冲突时仍有 LLM 结果。
- 删除 `project_memory.version += 1`（line 277）和字段 setattr（line 251/254/276），改由 update 语句承担。

### 3. 删章回滚（novel_service.py:892-901）

加 `version+1`（bug fix），不加守卫（强制覆盖）。同事务内，保持 ORM setattr + 显式自增即可：

```python
if previous_snapshot:
    memory.last_updated_chapter = previous_snapshot.chapter_number
    memory.global_summary = previous_snapshot.global_summary_snapshot
    if previous_snapshot.plot_arcs_snapshot is not None:
        memory.plot_arcs = previous_snapshot.plot_arcs_snapshot
    memory.version += 1  # 新增
    return
memory.last_updated_chapter = 0
memory.global_summary = ""
memory.plot_arcs = {}
memory.version += 1  # 新增
```

## 前端

- 确认 GET memory 返回带 `version`（`_model_to_dict` 应已包含）。
- PUT `/memory` payload 加 `expected_version` = 当前 memory.version。
- 409 处理：`globalAlert` 提示"记忆已被修改，请刷新"，invalidate memory query。

## 测试

- `test_put_project_memory_conflict`：expected_version 不匹配 → 409；匹配 → 更新成功 + version+1。
- `test_finalize_conflict_no_overwrite`：finalize 写回前改 DB version → 不覆盖 memory + result.conflict=True + snapshot 有 LLM 结果。
- `test_restore_memory_version_increment`：删章回滚后 version 增加。
