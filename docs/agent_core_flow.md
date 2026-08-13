# Agent 核心流程

本文描述当前生产章节生成链路。章节生成只有 durable Chapter workflow 一套执行模型，不存在旧编排器或配置切流。

## HTTP 入口

现有客户端入口保持不变：

- `POST /api/writer/novels/{project_id}/chapters/generate`
- `POST /api/writer/advanced/generate`
- `POST /api/writer/chapter-workflows`

普通和高级 writer 入口通过 `ChapterWorkflowCompatibilityService` 适配为 workflow start。无 `from_node_key` 时创建或复用当前 revision 的 root job；有 `from_node_key` 时只允许映射到现存 durable run 的 retry command。找不到 run、节点不支持或节点不匹配时返回 409，不会回退到另一套生成实现。

## Durable 工作流

生产 worker 只注册 `chapter_workflow` v1 handler。固定节点顺序为：

1. `freeze_context`：冻结项目、章节、写作输入和 canonical `ChapterContext`。
2. `plan_and_direct`：生成章节任务与导演约束。
3. `generate_candidates`：按冻结输入生成候选版本。
4. `review_candidates`：评审候选，选出唯一 `best_ordinal`，并只对优选版本执行启用的 post-review stages。
5. `persist_candidates`：在 root lease fence 内原子持久化候选、evaluation、优选标记和等待状态。
6. `waiting_for_selection`：释放 worker lease，等待用户选择；公开状态通过 workflow snapshot 与 event stream 提供。
7. `finalize_revision`：校验候选身份与 chapter revision，原子创建 canonical revision、outbox 和 projection dispatcher job。
8. `projection_pending` / `observe_projection`：等待并验证派生投影结果，最终进入 `successful`。

节点状态、checkpoint、activity 引用和 result hash 都属于 durable contract。worker 进程终止后由 PostgreSQL lease/fencing 恢复，不依赖应用进程内状态或 LangGraph trace snapshot。

## 模型调用

`ChapterWorkflowLLMProvidersV1` 是 workflow 的模型提供者边界：

- `candidate` 生成正文候选；
- `review` 返回结构化评审和唯一优选 ordinal；
- `post_review` 对已选版本执行一致性、优化等启用阶段。

底层调用继续复用 `LLMService`、模型路由、prompt 服务和统一 telemetry。私有 prompt、原始响应和完整正文只保存在受限 activity payload 或领域表中，公开 job/result 只暴露定位、状态和安全摘要。

## 上下文与 RAG

`ChapterContextResolver` 构造版本化 canonical snapshot，统一服务于规划、生成、评审与重试。RAG 是否启用、查询、模式和 POV 输入在 start 时规范化并冻结；后续 activity 通过引用读取，不在每个节点各自拼装一份漂移的上下文。

## 候选、评审与人工确认

候选 activity、review activity 和 post-review activity 先产生私有、可重放结果。`ChapterWorkflowCandidatePersistenceService` 校验它们属于同一 run 和候选集合后，在一个 fenced transaction 中写入：

- `ChapterVersion` 正文及 `_chapter_workflow` 身份；
- 从 `review.best_ordinal` 派生的 `metadata.ai_review.is_best`；
- 绑定优选版本的 AI evaluation；
- `waiting_for_confirm` 章节状态和 workflow checkpoint。

公开章节读取保留完整 `versions`，但 `version_selections` 只暴露唯一优选且已润色的候选。缺少或冲突的优选标记才保守回退为全部候选。

## 选择与定稿

旧 writer select/finalize 路径仍是公开兼容入口，但 active workflow 下会转换为 `select` command。workflow resume 后由 `ChapterWorkflowFinalizeService` 验证：

- run、root job、chapter、candidate 和 revision 身份一致；
- 选中版本属于当前 run；
- 正文 hash 未漂移；
- 当前状态允许定稿。

随后复用 canonical finalize/projection 服务创建 revision、outbox 和派生任务。没有 active workflow 的既有手工定稿仍走独立 durable `chapter_finalize` / projection 链路，它不属于章节生成双轨。

## Trace 与进度

`chapter_generation_traces` 是公开生成诊断投影的历史表名，不代表旧执行器。durable job events 通过 `chapter_generation_trace_projector` 投影为前端现有 trace DTO，供生成进度、失败定位和耗时展示使用，因此模型、投影器、公开 schema 和 UI 继续保留。

## 修改边界

修改章节生成流程时优先定位：

- 图与状态：`chapter_workflow_graph.py`、`chapter_workflow_runtime.py`、`schemas/chapter_workflow.py`
- provider/activity：`chapter_workflow_handler.py`、`chapter_workflow_activities.py`
- 上下文：`chapter_workflow_start.py`、`chapter_workflow_context.py`、`chapter_context_resolver.py`
- 候选持久化：`chapter_workflow_persistence.py`
- 人工命令与定稿：`chapter_workflow_compatibility.py`、`chapter_workflow_finalize.py`
- worker 注册：`job_handlers.py`

跨层改动至少保留一条从当前生产入口经过 persistence 到公开 projection 的集成测试；兼容请求 fixture 不能替代 durable producer 主链证据。
