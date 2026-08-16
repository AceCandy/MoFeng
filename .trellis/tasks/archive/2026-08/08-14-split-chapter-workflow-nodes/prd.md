# 重构章节生成节点边界

## Goal

让章节生成页面、durable workflow 和下游 projection 对“节点”的定义一致：只有一次独立的 LLM、Embedding 或其他远程调用才是可重试执行节点；本地持久化、等待、人工交互、汇合校验和终态可以展示，但不能伪装成可重试节点。

## Background / Confirmed Facts

- 当前前端生成阶段把 `context_prep`、`rag_retrieval`、`director_mission`、`draft_generation`、`quality_review`、`review_refinement` 展示为六步，但 `rag_retrieval` 与 `context_prep` 都映射到 `freeze_context`。
- 当前 `review_candidates` 同时完成候选评审和 post-review 阶段；`persist_candidates`、人工选择等待、正式定稿和 projection 等真实边界没有完整呈现在前端。
- 当前主 Graph 还包含 `waiting_for_selection`、`projection_pending`、`observe_projection`、`successful` 等非内容生产节点。
- 定稿后的 summary、memory、RAG、foreshadowing 已由独立 Projection Job 执行，其中 RAG 受向量配置和跳过选项控制；下游投影在摘要完成后按依赖创建，不应被伪造成固定串行步骤。
- durable job/activity 的租约 fencing、幂等键、结果 hash、外部副作用分类和事务 outcome writer 是现有契约，必须保留。
- canonical finalize 的 revision/outbox/dispatcher 写入必须保持原子事务；单个 Projection 的 activity 计算与结果提交边界也不能拆散。

## Requirements

### R1. 产出节点边界

将自动生成主流程表达为以下业务产出节点：

1. `freeze_base_context`：基础上下文快照。
2. `retrieve_context`：检索增强上下文。
3. `plan_chapter`：章节任务方案。
4. `generate_candidate:{ordinal}`：每个候选正文独立产出，按配置启用并独立重试；多候选必须从同一规划结果并行 fan-out，并在评审前汇合。
5. `review_candidates`：跨候选评审报告和推荐版本。
6. `refine_candidate`：推荐版本的润色正文。
7. 可选正文变换节点：增强、一致性修复、优化、扩写；每个节点产生新的正文版本并保留父版本引用。
8. `compress_candidate`：推荐正文超过冻结字数上限时生成压缩版本；未超限时明确跳过。
9. `persist_drafts`：候选版本、评审元数据和推荐版本的事务持久化。
10. `finalize_revision`：canonical ChapterRevision、outbox 和派发身份。

定稿投影表达为独立产出节点：`generate_summary`、`project_memory`、`project_rag`（可跳过）、`project_foreshadowing`。

### R2. 控制节点分层

`wait_for_selection`、`wait_for_projections`、`reconcile_projections`、`successful` 必须保留必要的状态机语义，但在后端类型、trace 元数据和前端视觉上标记为控制/汇合/终态，不计入内容生产节点数量。

### R3. 状态与产物可追踪

每个产出节点必须拥有稳定的 node key、输入引用、activity/result 引用、结果 hash、状态、耗时、模型调用信息（若有）和可定位的输出摘要；禁止前端通过文案猜测后端节点或 LLM 使用情况。

### R4. 重试与版本

节点级重试必须对应真实远程 activity 边界，复用上游已成功结果，只重新执行当前失败的 LLM/Embedding 调用；本地持久化、等待、汇合与终态不得提供节点级重试。系统尚未上线，拆分后的 DAG 直接定义为唯一正式 `workflow_version=1`、`state_schema_version=1` 和 root `payload_version=1`；不保留旧 Graph/checkpoint 兼容层，未知或不匹配版本必须失败关闭。

### R5. 前端展示

前端应展示真实产出节点、人工等待、投影并行分支和汇合校验；候选版本可用一个 UI 分组包裹多个 `generate_candidate:{ordinal}` 子节点，但分组不伪装成执行节点。条件跳过必须显示跳过原因。

### R6. 验证

为后端 Graph/handler、activity/result 链、投影并行与汇合、当前 checkpoint 恢复、未知版本拒绝、前端节点归一化和 trace 展示补充或调整聚焦测试；至少覆盖单候选、双候选、可选后处理关闭、RAG 跳过、人工选择恢复、投影失败重试和最终成功汇合。

### R7. 不可读运行恢复

当当前章节运行因未知版本、checkpoint 漂移或契约错误进入 fatal 边界时，重新检查只能重新读取事实；页面必须同时提供“重置本章”和“删除章节”。重置遵守 R8 的彻底清空语义，必须先递增 root job fencing token 并终止旧 job/run，再清理当前章节与旧运行。checkpoint 使用独立于 retention 的可重试两阶段删除 marker；重置完成后，历史 terminal run 不再作为该 `not_generated` 章节的 current run。删除异常章节复用“先重置、再按既有尾部章节规则删除”的链路。

### R8. 未成功工作流的彻底重置

只要章节工作流尚未进入 `successful`，页面都必须提供“重置本章”，包括正文已经写入 canonical revision、但摘要、记忆、RAG 或伏笔投影仍在执行或失败的阶段。重置必须 fence 当前 run 及其 dispatcher/projection worker，清除本 run 的未确认候选、评审、trace、私有 payload 和 checkpoint，并通过精确 tombstone 撤销本 run 已产生的投影产物；canonical `ChapterRevision`、outbox、projection run 和 durable 审计只允许失活或 supersede，不得物理删除。重置后保留章节大纲，旧 terminal run 不再作为 current run，章节可以重新生成。

若当前 run 启动前已有正式正文，重置也不恢复旧正文：章节的用户可见正文、版本、评审、摘要和所有自动投影均清空，只保留章节大纲。历史 canonical revision 仍作为不可变审计保留，但不得继续成为章节读取入口；重置以新的 tombstone revision 作为后续生成的 revision 基线，不能把 revision 号归零或复用。

## Out of Scope

- 不拆分单次模型活动内部的 prompt 组装、HTTP 调用、响应解析等微步骤。
- 不拆分 canonical finalize 的 prepare/apply/事务写入内部步骤。
- 不改变章节正文、记忆、伏笔或索引的业务算法，只调整其执行边界、状态和展示契约。
- 不引入新的队列、缓存或工作流框架。
- 不物理删除 canonical revision、outbox、projection run、JobEvent 或 command/activity 审计；“清空整章”是用户可见状态和活跃派生产物的清空，不是抹除审计历史。

## Acceptance Criteria

- [ ] 后端运行图或版本化运行图能区分所有产出节点与控制节点，节点拓扑与持久化/Projection 实际执行一致。
- [ ] `rag_retrieval` 不再与基础上下文节点重复；评审、润色、持久化、人工选择、正式定稿均有清晰边界。
- [ ] 候选生成和可选后处理能按真实 activity/Job 独立记录、重试和恢复，且不重复已完成的外部调用。
- [ ] 双候选实际并行执行并在评审前汇合；目标、最小和最大字数冻结进 workflow 输入，最终推荐正文不得超过上限。
- [ ] 定稿投影按真实依赖并行派发；RAG 跳过可解释；汇合节点仅在 required projections 全部成功后进入成功态。
- [ ] 前端节点列表、状态、trace 详情、重试入口与后端 activity 一致；只有真实 LLM/Embedding 远程调用节点可重试，本地执行与控制节点只展示状态。
- [ ] fatal 章节可重新检查、保留大纲重置或删除；重置会 fence 旧 worker，checkpoint 删除失败可重试，且旧 terminal run 不会再次触发 fatal。
- [ ] 任意尚未 `successful` 的工作流都可从页面重置；即使 canonical revision 已写入，也会停止迟到 worker、撤销本 run 的投影可见结果，清空旧正式正文且只保留章节大纲，并恢复为可重新生成状态。
- [ ] 现有 durable job、当前 checkpoint、outbox、projection、SSE 和生成失败语义没有未覆盖的回归。
- [ ] 聚焦 backend/frontend 测试、类型检查和静态检查通过；未改变的全量环境限制在验证记录中明确说明。

## Key Decisions / Risks

- 以真实执行 DAG 为事实源，前端只做分组和呈现；候选使用可合并的引用型状态并行执行，评审仅在所有候选分支完成后运行。
- 系统尚未上线，不存在生产旧运行；当前拆分 DAG 直接成为唯一正式 V1。开发环境旧 workflow/checkpoint 数据需清理，不允许被新 schema 猜测解析。
- “删除异常章节”由重置与既有删除两个请求组成；若第二个请求失败，章节停留在已安全重置、保留大纲的可恢复状态，可再次删除。
- 每个新增节点都会增加 checkpoint、activity 和测试面；因此只按独立产物拆分，不按内部函数或日志事件拆分。
- 未成功 run 已写入 canonical revision 时，重置使用补偿式 tombstone，而不是回滚或物理删除不可变事实；迟到 worker 必须同时受 job fencing 与 revision/generation 身份校验阻止。
- 清空后以 tombstone revision 继续单调递增，避免新生成与历史 revision 唯一键冲突。
