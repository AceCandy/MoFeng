# 校准 durable job 歧义事件测试

## Goal

让 durable job 歧义结果测试覆盖当前正式审计事件链，恢复 PostgreSQL pytest profile 的可信门禁。

## Background

- `JobService.mark_activity_ambiguous` 自提交 `b8ea221` 起先写入 `activity.ambiguous`，再写入投影后的 `workflow.needs_attention`。
- `test_workflow_transition_adapter_maps_ambiguity_cancel_and_failure` 仍期望旧序列，漏掉中间审计事件，因此 PostgreSQL profile 出现 1 个失败。
- durable job spec 已把 `activity.ambiguous` 纳入 activity 事件契约；运行时行为不是本任务要修的缺陷。
- 该测试的 activity 没有公开 `node_key`，所以 `activity.ambiguous` 不推进 workflow revision；现有 `row_revision == 2` 断言必须保留。

## Requirements

- R1. 更新聚焦测试，使其断言完整顺序：queued、phase changed、activity started、activity ambiguous、workflow needs attention。
- R2. 保留对终态、row revision、activity attempt/fencing token 和最终 workflow event 的全部现有断言。
- R3. 验证 `activity.ambiguous` 只公开 task snapshot，且不包含私有 payload、result 或 provider request key；不因测试修复放宽安全断言。
- R4. 不修改 `JobService`、transition adapter、事件 schema 或业务状态机。

## Acceptance Criteria

- [x] 歧义、取消、失败映射聚焦测试通过，并精确覆盖 `activity.ambiguous` 的位置及公开 payload 边界。
- [x] durable job 相关 PostgreSQL 测试通过，完整 PostgreSQL profile 不再出现该失败。
- [x] 产品代码无 diff，事件数量与顺序变化有既有提交和 spec 支撑。
- [x] 独立复核确认不是通过弱化或删除序列断言获得绿灯。

## Out of Scope

- 改变歧义活动重试、人工介入、取消或失败语义。
- 重构 durable job 测试结构或修复其他 PostgreSQL 测试。

## Notes

- 这是单测试契约校准任务，预计为 PRD-only 轻量变更。
