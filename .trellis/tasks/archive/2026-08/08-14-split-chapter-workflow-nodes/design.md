# 技术设计：章节生成节点唯一正式 V1

## 1. 目标与非目标

唯一正式 V1 的事实源是可恢复的真实执行 DAG。每次 LLM、Embedding 或其他远程调用拥有独立 activity/result 引用和重试边界；本地持久化、人工等待、投影等待、汇合校验和终态只保留状态展示，不提供节点级重试。

本次不重写 LLM prompt、章节内容算法、Projection 锁顺序或 durable worker 基础设施，也不把一个模型活动拆成 HTTP/解析等微节点。

## 2. 版本合同

- 当前拆分后的 DAG 直接定义为 `workflow_version=1`。
- checkpoint 使用唯一 `state_schema_version=1`，root job 使用唯一 `payload_version=1`。
- schema、payload、bindings、compiler、handler 和 runtime 均只有一个无版本后缀的正式实现。
- registry 和 payload parser 按版本精确匹配；未知版本或 payload/run/checkpoint 身份不一致时失败关闭。
- 系统尚未上线，不保留旧 Graph、旧节点键或旧 checkpoint 的恢复兼容。开发环境旧 workflow/checkpoint 数据在使用新版本前清理。
- writer 旧请求形状仅可作为当前 durable run 的命令适配器，不能成为 checkpoint 输入，也不能回退到另一套生成流程。

## 3. 节点与产物

### 3.1 生成链

| Node key | 类型 | 产物/依赖 |
|---|---|---|
| `freeze_base_context` | execution | 冻结基础上下文 hash/ref |
| `retrieve_context` | execution | retrieval snapshot/hash |
| `plan_chapter` | execution | `ChapterWorkflowPlanOutput` |
| `generate_candidate_1` | execution | ordinal=1 候选正文 |
| `generate_candidate_2` | conditional execution | ordinal=2 候选；单候选时明确跳过 |
| `review_candidates` | execution | 跨候选评审和推荐 ordinal |
| `refine_candidate` | execution | 必选评审引导润色正文 |
| `enhance_content` | optional execution | 增强后的正文版本 |
| `repair_consistency` | optional execution | 一致性修复正文版本 |
| `optimize_style` | optional execution | 风格优化正文版本 |
| `enrich_content` | optional execution | 扩写后的正文版本 |
| `compress_candidate` | conditional execution | 推荐正文超出冻结上限时的压缩版本；未超限明确跳过 |
| `persist_drafts` | transactional execution | 草稿版本、评审元数据和推荐版本 |
| `finalize_revision` | transactional execution | canonical revision、outbox、dispatcher identity |

候选 1/2 从 `plan_chapter` 静态并行 fan-out，在 `review_candidates` 前使用 barrier 汇合；每个候选使用独立 activity key。并发分支只合并引用型 map，不并发写 `node_key`。正文变换节点保留父结果引用并生成新 content hash，不覆盖父版本。

启动时从统一章节字数配置冻结 target/minimum/maximum。候选 Prompt 必须携带该合同；推荐正文完成全部修订后若超过 maximum，进入独立 `compress_candidate` activity，压缩结果再次按同一口径校验后才允许持久化。

### 3.2 控制链

- `wait_for_selection`：人工选择 checkpoint，不调用模型。
- `wait_for_projections`：等待 projection children 或接受 retry command，不产生章节业务产物。
- `reconcile_projections`：验证 required projections 的 source hash、generation、status 和 stream identity。
- `successful`：终态，不计入执行节点。

`freeze_base_context`、`persist_drafts` 与 `finalize_revision` 同样属于本地事务步骤：可展示真实状态，但不是远程调用重试节点。

### 3.3 定稿投影

Projection Job 保持独立：`generate_summary` 完成后并行派发 `project_memory`、`project_rag`（可跳过）和 `project_foreshadowing`，最后由 `reconcile_projections` 汇合。UI 展示真实分支，不绘制成固定串行步骤。

## 4. 后端边界

- `freeze_base_context` 只验证并持久引用 start 事务冻结的基础上下文；`retrieve_context` 单独执行检索 activity。
- 模型 activity 的 `node_key`、`stage` 和 ref 与真实节点一一对应，继续保留 provider request key、ambiguous external 处理、结果解析和 telemetry。
- runtime 只解析唯一正式 state/payload；resume 校验按当前节点键分发，禁止修改 workflow identity。
- `persist_drafts` 保持候选持久化 outcome writer 原子性；`finalize_revision` 保持 revision/outbox/dispatcher 单事务。
- 公开 trace 只输出 allowlist 中的 node kind、stage、uses_llm、引用、skip reason、duration 和输出摘要，不输出 prompt、完整正文、provider response 或密钥。

## 5. 前端边界

- `ChapterGenerating` 始终展示唯一真实 DAG，不通过节点名猜测工作流版本。
- 候选使用 UI 分组包裹真实子节点；可选节点按真实 node key 匹配 trace 并展示 skip reason。
- `useGenerationPipeline` 只维护一个状态机；节点显式声明远程重试类型，本地执行与等待节点不能从状态文案推断出重试能力。
- summary、memory、RAG、foreshadowing 按各自持久化远程 activity 展示；投影 Job 与汇合只作为分组和状态，不作为可重试叶子节点。
- summary、memory、RAG、foreshadowing 各分支只消费本分支 trace；缺少 trace 一律等待，其他分支或 `wait_for_projections` 不得被当作本分支已执行或已跳过的证据。伏笔无可处理对象时由本分支提交成功表示检查完成，不显示为跳过。
- `generationTrace` 只映射当前真实节点和独立 projection 节点，不保留旧 Graph alias。
- 运行时 decoder 仅接受版本 `1`，未知版本进入 fatal contract boundary。

## 6. 风险、回滚与验证

- 风险：版本字段、OpenAPI、生成 TypeScript、运行时 decoder 必须作为同一发布单元同步。
- 风险：开发库若残留旧 workflow/checkpoint 数据将无法恢复，这是已确认的上线前清理项，不在运行时增加兼容代码。
- 回滚：代码整体回滚到本任务前；不支持把新 checkpoint 降级解释为旧 Graph。
- 验证：Graph/activity、进程恢复、selection/projection resume、projection reconcile、未知版本拒绝、OpenAPI artifact、前端类型和真实 DAG 展示测试。

## 7. Fatal 恢复边界

- `再次检查` 只串行重取 current snapshot，不修改服务端状态；同一不兼容运行仍会保持 fatal。
- `POST /api/writer/novels/{project_id}/chapters/{chapter_number}/reset` 只重置未定稿章节。事务内锁定 root job、run、Chapter，递增 fencing token，终止 job/run，清理未确认版本、评审、trace 和 command/activity 私有 payload，并把 Chapter 恢复为 `not_generated`。
- checkpoint 删除采用两阶段协议：先提交专用 `__chapter_reset_pending__` marker，再调用 saver 删除 thread，最后重新锁定并清 marker；外部删除失败时保留 marker，重复调用重置接口继续幂等删除。该 marker 不与定期 retention 的 `__retention_pending__` 混用，避免补做 retention 清理被误判为章节已重置。
- current-run 查询只在 Chapter 仍非 `not_generated` 时暴露无 successor 的 terminal run，避免重置后重新读取旧失败事实。
- fatal 删除复用“重置→既有尾部删除”两个请求。第二个请求失败不会恢复旧运行，只留下已重置且可再次删除的章节大纲。

## 8. 未成功工作流的彻底重置

### 8.1 可用边界

`successful` 是唯一禁止重置的工作流终态。`queued`、`running`、`waiting_for_selection`、`finalizing`、`projection_pending`、`needs_attention`、`failed`、`cancelled` 和 fatal contract boundary 均可重置。前端不根据正文是否存在猜测权限，只根据当前 workflow snapshot 是否尚未 `successful` 展示“重置本章”；后端重新锁定并验证同一条件。

### 8.2 补偿事务

重置继续复用 `POST /api/writer/novels/{project_id}/chapters/{chapter_number}/reset`，不新增平行 API。事务内按现有锁序锁定 root job、run、Chapter，并执行：

1. 递增 root fencing token，终止当前 root job/run，同时取消或失活同一 workflow stream 下的 dispatcher、finalize 和 projection jobs/activities，阻止迟到 worker 提交。
2. 若 Chapter 已存在 active canonical revision/projection generation，复用 `ChapterProjectionService.create_tombstone_job` 写入 `ChapterRevisionSuperseded` 补偿事实；tombstone 与 active visibility cut 同事务，使当前 revision 的 projection runs 变 stale，RAG、memory、summary 和非人工 foreshadowing 立即退出活跃读取。
3. 清除该章全部 `ChapterVersion`、`ChapterEvaluation` 和 generation trace；历史 `ChapterRevision.selected_version_id` 依赖外键置空，revision 的 `source_content` 保留审计正文。
4. 清空 Chapter 的 `selected_version_id`、summary、word count、source hash、projection generation/snapshot 和生成字段，状态恢复为 `not_generated`。`current_revision` 保持 tombstone revision，不归零；下一 run 以该 revision 为 `base_revision`，后续 finalize 继续单调递增。
5. 清理 command/activity 私有 payload，并沿用独立 `__chapter_reset_pending__` marker 完成 checkpoint 两阶段删除。

该事务保留 canonical revision、outbox、projection run、JobEvent、command/activity 身份及审计字段，不物理删除 durable 历史。若重复请求发现同一 run 已终止且 Chapter 已是无正文的 `not_generated`，只继续未完成的 checkpoint/tombstone 派发清理。

### 8.3 前端与缓存

- `ChapterWorkflowPanel` 在除 `successful` 外的已建立 workflow phase 展示“重置本章”；按钮复用现有二次确认和 pending 防重复提交。
- 重置响应同时更新 Project cache、用响应中的重置章节替换当前 Chapter query（缺失时移除旧 query），再刷新项目列表并让 workflow actor resync；不得只 invalidate 后保留旧 `data`。正文、候选、描红/落墨临时快照和旧 terminal run 必须在同一恢复动作后退出展示。
- “取消本轮”仍只撤销当前 run 的未确认派生结果；“重置本章”明确清空整个章节的用户可见内容，两者文案和行为不合并。

### 8.4 失败与回滚

- checkpoint 外部删除失败时，数据库中的清空事实保持提交，marker 保留并可重试；不得恢复旧正文或旧 worker。
- tombstone dispatcher 暂时失败时，active visibility 已在事务内切断；后台任务可按 durable 机制重试。
- 代码回滚只撤回新入口与补偿编排，不尝试恢复用户已明确清空的正文。
