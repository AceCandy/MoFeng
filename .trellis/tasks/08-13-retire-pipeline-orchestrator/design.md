# 退役 PipelineOrchestrator：技术设计

## Target Architecture

生成请求只有一条路径：writer HTTP endpoint → `ChapterWorkflowCompatibilityService` → `ChapterWorkflowStartService` / workflow retry command → `chapter_workflow` handler → durable runtime。

兼容服务保留的只是旧 HTTP 请求形状到 durable 命令的适配，不再承担新旧执行器分流。`adapt_generation` 因此总是返回 `BackgroundTaskResponse`，不再接收 start gate，也不再以 `None` 表示 legacy drain。

## Retry Contract

`from_node_key` 是现有客户端合同，继续通过 `LEGACY_RETRY_NODE_MAP` 映射 durable node。它要求当前 revision 存在 active 或 latest retryable workflow run；找不到时抛出 `ChapterWorkflowCompatibilityConflictError("workflow_retry_run_not_found")`。这比无声开启全新生成更忠实于“从节点恢复”的语义。

## Deletion Boundary

删除：

- `pipeline_orchestrator.py` 与 `chapter_generation_task_runner.py`；
- `chapter_generation` handler 注册和 writer fallback；
- workflow start feature flag 的应用、部署和发布契约；
- 只覆盖旧 orchestrator/runner/context replay 的测试；
- 当前文档中的旧双轨说明。

保留：

- writer 普通/高级生成端点与前端调用；
- `ChapterWorkflowCompatibilityService` 的生成/retry/select 适配；
- `chapter_finalize` job 与 finalize fallback；
- generation trace 模型、投影器、公开 schema 和 UI。durable job event projection 仍以这些结构提供进度与诊断；表名是领域历史命名，不等于旧执行器所有权。
- 既有 Alembic revisions。已执行迁移必须保持不可变，且相关表仍在使用。

## Compatibility Decision

项目未上线，因此不 drain 已排队的 `chapter_generation` job，不恢复旧 LangGraph snapshot，也不添加 tombstone handler。部署新代码后遇到这类不存在于真实生产的数据可直接视为不受支持。

## Rollback

这是删除型变更，无数据库迁移。回滚到变更前提交即可恢复旧 runner、开关和实现；保留 trace schema/表使代码回滚不受数据库结构阻碍。

