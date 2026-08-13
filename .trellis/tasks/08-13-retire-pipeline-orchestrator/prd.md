# 退役 PipelineOrchestrator

## Goal

在产品尚未上线、无需承接旧生成任务或旧 trace 恢复的前提下，彻底删除章节生成双轨：所有现有 HTTP 生成入口统一进入 durable Chapter workflow，生产代码不再包含或注册 `PipelineOrchestrator`。

## Background

- 当前普通/高级生成端点先尝试 durable workflow，但受 `chapter_workflow_start_enabled` 控制；关闭时或旧式节点重试找不到 workflow run 时，会入队 `chapter_generation`。
- `chapter_generation` worker runner 是生产代码中唯一实例化 `PipelineOrchestrator` 的路径。
- durable workflow 已覆盖上下文冻结、规划、候选生成、AI 评审、优选润色、候选持久化、人工确认、定稿、retry/resume、lease recovery 与公开进度投影。
- 项目尚未上线，用户明确不要求保留旧 `chapter_generation` job、旧 LangGraph trace snapshot 或旧节点恢复的数据兼容。

## Requirements

- 普通生成、高级生成和 `/chapter-workflows` 入口无条件创建或复用 `chapter_workflow` root job，保持现有 HTTP 路径、202 响应和公开响应结构。
- 旧式 `from_node_key` 仅在能映射到当前 durable run 的失败节点时提交 workflow retry；找不到 run、节点不支持或节点不匹配时返回明确 409，禁止回退旧生成。
- 删除 `chapter_workflow_start_enabled` 应用配置及部署/示例/发布契约中的对应环境变量。
- 删除 `chapter_generation` job 注册、runner、`PipelineOrchestrator` 实现及仅验证它们的测试。
- 更新仍描述旧编排器或双轨发布方式的当前文档。
- 保留 durable workflow 仍使用的公共 HTTP 路径、`chapter_finalize` durable 链路、job/event trace 投影、trace 数据模型和既有 Alembic 迁移。
- 不迁移或兼容任何未上线的旧 `chapter_generation` job 与旧 trace snapshot。

## Out Of Scope

- 不重命名现有 writer HTTP 路径或前端 API 方法。
- 不删除 `chapter_generation_traces` 表、公开 trace schema/UI 或 trace projector。
- 不重构 durable workflow 内部节点、提示词或生成算法。
- 不删除非 `PipelineOrchestrator` 专属的上下文、评审、润色、定稿和 projection 服务。

## Acceptance Criteria

- [x] 普通和高级生成端点只产生 `chapter_workflow` job，不存在配置关闭或 fallback 到 `chapter_generation` 的分支。
- [x] `/chapter-workflows` 入口常开；代码库与发布配置中不存在 `chapter_workflow_start_enabled` / `CHAPTER_WORKFLOW_START_ENABLED`。
- [x] 旧式 retry 有合法 durable run 时仍可映射并重试；无 run 时返回 409，且不创建任何 job。
- [x] 生产代码中不存在 `PipelineOrchestrator`、`chapter_generation_task_runner` 或 `chapter_generation` handler 注册。
- [x] durable workflow 的生成、评审、润色、持久化、人工确认、失败重试与 finalize 目标测试通过。
- [x] 静态检查证明 writer 不再入队 `chapter_generation`，worker registry 不再支持该 job type。
- [x] Ruff、相关后端测试、前端类型检查与 lint 通过，独立复核无高/中严重问题。
