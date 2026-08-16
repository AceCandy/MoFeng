# 实施计划：章节生成节点唯一正式 V1

## Phase 1：收敛唯一版本合同

1. 将当前拆分 DAG 的 workflow/state/root payload 统一编号为 `1`。
2. 删除旧 Graph/state/payload/bindings/compiler/handler/runtime 分支，只保留无版本后缀正式实现。
3. 未知版本和 run/payload/checkpoint 身份漂移继续失败关闭。
4. 重新生成 OpenAPI 与 TypeScript artifacts。

验证：start、registry、payload parser、runtime 与前端 decoder 只接受唯一 V1；未知版本拒绝。

## Phase 2：真实产出节点

1. 拆分 `freeze_base_context` 与 `retrieve_context` 的持久活动。
2. 建立 plan、并行候选 1/2、review、refine、可选正文变换和超限压缩的独立节点/ref/hash。
3. 冻结 target/minimum/maximum 字数合同，注入候选与修订输入，并在持久化前确定性校验最终推荐正文。
4. 使用 `persist_drafts` 事务持久化候选，保留 selection checkpoint。
5. 使用 `finalize_revision` 原子写入 canonical revision、outbox 和 dispatcher identity。

验证：单/双候选、可选阶段开关、activity replay、ambiguous external、持久化回滚和 selection resume。

## Phase 3：Projection、trace 与前端

1. 保持 summary 后并行派发 memory/RAG/foreshadowing，RAG skip 可观察。
2. 使用 `wait_for_projections` 和 `reconcile_projections` 表达等待与汇合，但不给本地控制步骤提供节点重试。
3. 公开 trace 按真实 LLM/Embedding activity 输出 node kind、调用类型、引用和 bounded metadata。
4. 前端删除双状态机、旧节点 fallback 和版本猜测，始终展示真实 DAG，并仅在远程叶子节点显示重试。

验证：projection retry/stale/reconcile、trace rebuild、前端节点状态、跳过、等待和投影并行展示。

## Phase 4：质量门

1. 运行所有 `test_chapter_workflow*.py` 聚焦测试及相关 durable worker/projector 测试。
2. 运行 Python compileall、Ruff、Mypy；运行前端 Vitest、type-check、lint 和 API artifact check。
3. 全仓搜索版本化双实现符号、旧 Graph 节点键和 workflow root payload version 2 注册残留。
4. 独立复核版本身份、重试、fencing、敏感 trace 字段和前端映射。

## Phase 5：Fatal 章节恢复

1. 新增未定稿章节重置 API，复用 durable job fencing 与 terminal cleanup，并为 checkpoint 删除保留可重试 marker。
2. 重置后过滤已回到 `not_generated` 的 terminal run；无 durable run 时清理 Chapter 的未确认派生状态。
3. fatal 面板接通重新检查、重置和删除；删除按“重置→尾部删除”执行，所有恢复请求共享 pending 防重复提交。

验证：旧 lease 无法提交、未确认产物与私有 payload 被清除、checkpoint 删除失败可重试、current run 返回空、重置后章节可删除；前端动作、类型、lint 与 API artifact check 通过。

## 回滚点

- 代码与生成 artifacts 作为一个整体回滚。
- 系统尚未上线，不提供旧 workflow/checkpoint 运行时迁移；开发环境旧数据在启用当前版本前清理。
