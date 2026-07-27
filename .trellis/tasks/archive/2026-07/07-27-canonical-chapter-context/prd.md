# 统一 Canonical Chapter Context

## Goal

让章节生成、评审和一致性检查从同一个版本化、可序列化、可解释的上下文事实中派生输入，消除 caller 自行查询和拼接造成的行为漂移，并为 durable workflow 提供可冻结的输入快照。

## Background

- pipeline 的评审上下文只包含 blueprint、outline、mission 和历史章节：`backend/app/services/pipeline_orchestrator.py:2066-2090`。
- writer 的评审路径额外查询 memory、constitution、persona、foreshadows、related chapters 和 plot threads：`backend/app/api/routers/writer.py:210-332`。
- `ReviewContextBuilder` 只覆盖 RAG/上下文的一部分，删除它后 caller 仍保留大量手工组装，说明当前 seam 没有集中复杂度：`backend/app/services/review_context_builder.py:41-94`。
- `ChapterContextService` 在向量不可用时返回空结果，当前 caller 各自决定如何降级：`backend/app/services/chapter_context_service.py:61-99`。

## Requirements

- CCTX-1：定义 Pydantic `ChapterContext` contract，包含 schema version、project/chapter、source revision、blueprint、outline/mission、历史章节、memory、constitution、persona、foreshadows、plot threads 与 RAG 结果。
- CCTX-2：每个 section 必须携带 provenance、是否截断和 fallback 原因；不得用缺字段与空字符串混合表达不同状态。
- CCTX-3：唯一 resolver 负责 DB/RAG 读取、可见性裁剪、排序、预算和降级；router、pipeline、review、consistency caller 不得再直接拼接同类字段。
- CCTX-4：generation/review/consistency 通过薄 adapter 从同一 context 派生所需视图；adapter 不执行 DB 或网络 I/O。
- CCTX-5：同一 canonical source revision、同一检索快照和同一 policy version 必须得到稳定序列化结果；durable run 可存储 snapshot/hash 并在恢复时复用。可变 projection checkpoint 不参与顶层 source revision。
- CCTX-6：RAG 关闭、embedding 失败、无前一章、无 memory/foreshadowing 时必须有一致且可测试的降级输出。
- CCTX-7：blueprint writer visibility 规则继续生效，不能因统一 contract 泄露当前角色不应看到的信息。
- CCTX-8：切换前用独立纯映射保留 pipeline/writer 旧视图作为 shadow oracle；对比只记录结构化 diff，不记录完整 prompt 或敏感配置。旧 builder 覆盖的入口通过代表性对比、其他入口通过共享 contract/wiring tests 后，私有旧 DB builder 与新 resolver 原子替换，不长期保留双读取路径。

## Dependencies

- 无前置 child；这是实际实现的第一个子任务。
- 输出的 serializable contract 与 snapshot/hash 被 durable workflow 和 projection invalidation 使用。

## Acceptance Criteria

- [x] 同一 fixture 通过 pipeline、writer 和 consistency adapter 后，共享 section 的结构与值一致。
- [x] contract/golden tests 覆盖首章、普通章节、RAG 关闭、embedding 失败、裁剪超预算、缺少可选数据和 writer visibility。
- [x] `pipeline_orchestrator.py` 与 `writer.py` 不再拥有独立 `_build_review_context` 业务组装逻辑。
- [x] resolver 的所有 section 都能说明来源、revision、truncation 和 fallback；缺少 projection 来源使用显式 sentinel，序列化不含 ORM/session 对象。
- [x] 旧新 builder shadow compare 在代表性 fixture 上无未解释差异后才 cutover。
- [x] 现有 `test_review_context_builder.py` 的检索语义得到保留或由新 contract test 明确替代。

## Out Of Scope

- 本子任务不引入 worker、checkpoint、outbox 或前端 statechart。
- 不重新设计 prompt 文案、模型参数或 RAG 排名算法。
- 不顺手修复与 context contract 无关的 pipeline 静态测试失败。
