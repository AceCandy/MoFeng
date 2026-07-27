# 构建 Durable Chapter Workflow

## Goal

把章节生成、评审、人工选版、定稿、projection 等待、节点重试和恢复收敛到一个 PostgreSQL 持久化的 LangGraph workflow run，消除 HTTP 长请求、手工 trace 恢复和 router 编排。

## Background

- 当前 pipeline 虽使用 LangGraph，但没有 checkpointer，失败恢复由应用删除后续 trace 并重建 state/recovery graph：`backend/app/services/pipeline_orchestrator.py:340-423`。
- 高级生成 endpoint 直接 await 最长 600 秒级 LLM 流程：`backend/app/api/routers/writer.py:876-895`。
- 定稿 router 负责的步骤多于 `FinalizeService`，没有统一 workflow owner：`backend/app/api/routers/writer.py:898-1206`、`backend/app/services/finalize_service.py:158-309`。

## Requirements

- WF-1：每个 run 使用稳定 `run_id/thread_id`，绑定 project、chapter、base revision、JobRun 和 frozen context snapshot。
- WF-2：graph 明确覆盖 context、plan、generate、review、wait-for-selection、finalize、wait-for-projections、successful/failed/cancelled。
- WF-3：使用与当前 LangGraph 版本兼容的 PostgreSQL checkpointer；worker/process 重启后从 checkpoint 恢复。
- WF-4：每个有副作用 step 有稳定 step id、input hash、activity intent/result 和幂等提交；已有持久化成功 result 的 step 不重复。provider response 未能持久化的模糊窗口遵循 activity ambiguity contract，不自动重放。
- WF-5：人工 select/retry/cancel 通过持久 command inbox 进入，带 command id、expected run/revision 和幂等键。
- WF-6：同一 project/chapter/revision 最多一个 active run；run 与 root JobRun 在同一事务进入/离开 active set。自动 retry 沿用 run；terminal 后的用户 retry 只有在没有 successor 时才能原子 re-activate，否则返回当前 run。
- WF-7：trace 从 workflow/job events 投影，仅用于展示；不得再决定 recovery node/state。
- WF-8：HTTP start 返回 202 + run snapshot/link；status/commands 与旧 endpoint 在兼容窗口有 adapter。
- WF-9：workflow 等待 projection reconciler 将 Chapter current revision 标记为 `successful` 后结束 run；workflow 自身不得写该 Chapter transition。projection failed 可从该阶段恢复，无需重跑生成。
- WF-10：错误按 node、retryability 和 public category 表达；取消、超时和 stale command 有确定状态。

## Dependencies

- 依赖 canonical context、explicit bootstrap、durable job/event log 和 replayable projections 全部完成。
- 完成后固定 OpenAPI，供 generated contracts 与 WritingDesk statechart 使用。

## Acceptance Criteria

- [ ] 在生成完成、等待选版和 projection 处理中分别终止 worker，重启后从对应 checkpoint 继续。
- [ ] 重复 start/select/retry/cancel 不重复已有成功 result、canonical version、outbox 或 projection；模糊外部结果进入 reconcile，不触发盲目 LLM 重放。
- [ ] stale revision command 被拒绝并返回当前 run snapshot，不覆盖新 run。
- [ ] 同章并发 start 只有一个 active run；另一请求返回同一 durable id。
- [ ] cancel/failed/retry/superseded 与 JobRun terminal transition 在同一事务释放/重取 active；stale-run reconciler 能修复人为制造的不一致。
- [ ] API 请求无需等待章节生成完成，Web 进程重启不影响 run 最终进度。
- [ ] trace 表清空或 trace projection 暂停不会破坏 workflow recovery。
- [ ] 旧 endpoint adapter 与新 async API 在兼容窗口对同一 run 返回一致 Chapter lifecycle。

## Out Of Scope

- 不在本子任务引入 Temporal 或跨服务 workflow。
- 不重写 LLM prompt、review 算法或候选版本评分策略。
- 不让 workflow history 成为 Chapter canonical data 的替代品。
