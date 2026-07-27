# Replayable Chapter Projections Implementation Plan

## Steps

- [ ] 固定现有 finalize/delete/regenerate characterization tests 和派生数据 ownership map。
- [ ] Alembic 增加 Chapter revision、outbox、projection execution/checkpoint/status schema。
- [ ] 实现 canonical command transaction 与 outbox repository（flush only）。
- [ ] 先实现 summary projection/result cache，再迁 memory、RAG、foreshadowing 和 trace。
- [ ] 将 vector 写入改为 staging + active revision，并移除 adapter 内 commit/session ownership。
- [ ] 实现 required projection reconciler、Chapter successful transition、retry/replay/dry-run CLI。
- [ ] 迁移 delete/regenerate 为 tombstone/superseded events。
- [ ] shadow 对比旧新结果，按 aggregate marker cutover 后删除旧同步副作用路径。

## Validation

```bash
cd backend
pytest tests/test_finalize_service.py tests/test_chapter_delete_policy.py
pytest tests/test_chapter_projection_outbox.py tests/test_chapter_projection_replay.py
```

PostgreSQL integration tests必须覆盖 transaction rollback、双 worker、迟到旧 revision、crash/retry、vector active generation 切换和 replay。现有 router 静态测试只在行为 owner 改变时更新，不为通过测试保留错误边界。

## Rollback

- 暂停 consumer，outbox 保留等待恢复。
- migration marker 决定某个 Chapter revision 由旧同步 path 或新 projections 处理，禁止同时启用。
- canonical revision/outbox 不做破坏性 downgrade；回滚版本可忽略新 event type。
