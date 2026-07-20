# ProjectMemory 乐观锁补全

## Goal

P3 #6 收尾：`ProjectMemory.version` 字段已存在（`project_memory.py:61`，注释"用于乐观锁"），但三个写点均无 `WHERE version=?` 守卫，并发更新会丢失（lost update）。补全乐观锁，冲突时安全处理。

## Background

写点梳理（rg 全 `backend/app/`，排除读点 consistency_service / knowledge_retrieval_service）：

1. **finalize_service.finalize_chapter:250-279** - 定稿跨事务写回（读 → commit 释放连接 → LLM 几十秒 → 写回）。写回基于旧 ORM 对象 `setattr`，期间用户编辑 memory 会被覆盖。`version += 1` 是对象自增，不守卫。
2. **novel_service._restore_project_memory_after_completed_delete:892-901** - 删章回滚恢复 memory，改字段但**未自增 version**（bug，version 不单调）。
3. **projects.put_project_memory:183-186** - 用户编辑，`setattr` 循环无守卫无自增。

## Requirements

- **put_project_memory**：payload 加可选 `expected_version`。memory 存在且传了 expected_version 时用 `UPDATE ... WHERE id=? AND version=expected_version` 守卫，rowcount=0 返回 409；不传则跳过守卫（向后兼容，该接口当前无调用方）。version 自增。返回值带 version。
- **finalize_chapter**：读时记 `old_version`（commit 前），写回用 `UPDATE ... WHERE version=old_version` 守卫。冲突时**不覆盖 memory**（保留并发修改），LLM 结果仍写入 `ChapterSnapshot`，`result["conflict"]=True`。不重试（LLM 太贵）。
- **删章回滚**：加 `version+1`（bug fix）。**不加守卫**——删章是用户主动重操作，语义为"强制恢复到删章前"，应优先于并发编辑。
- **前端**：确认前端无 PUT `/memory` 调用（孤儿接口），本轮不改前端。
- **测试**：覆盖 put 冲突 409、finalize 冲突不覆盖、回滚 version 自增。

## Acceptance Criteria

- [ ] put_project_memory 并发冲突（expected_version 不匹配）返回 409
- [ ] finalize_chapter 冲突时不覆盖 memory，result.conflict=True，snapshot 仍有 LLM 结果
- [ ] 删章回滚后 memory.version 单调增
- [ ] put_project_memory expected_version 可选：传了不匹配返回 409，不传跳过守卫；更新成功 version+1
- [ ] 全量后端 pytest 绿 + 前端四件套绿
- [ ] 独立复核通过

## Notes

- finalize 跨事务乐观锁是难点：LLM 结果已生成，冲突时不重试，改为不覆盖 memory + 存 snapshot 供用户参考。
- 回滚不加守卫的决策：删章优先于并发编辑，强制覆盖符合用户预期（用户删章期望 memory 回滚）。
- 回滚 version 自增是顺带修的 bug，非乐观锁核心，但保证 version 单调。
