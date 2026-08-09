# 当前生成链路核验摘要

## 前端

- `ChapterWorkflowPanel.vue:11-80` 在生成中展示独立状态行与取消按钮；`WDWorkspace.vue:94-98` 下方同时展示 `ChapterGenerating` 进度。
- `WDWorkspace.vue:431-437` 已按当前 `workflowRunId` 过滤 trace；`WDWorkspace.vue:464-480` 的草稿正文仍直接取 `selectedChapterResolvedContent`，因此会读取旧章节缓存。
- actor 在取消终态只触发 Vue Query invalidate；invalidate 是后台刷新，不会立即移除旧缓存。
- 最近提交 `97a51c6` 已修复首次候选描红重复展示，必须保留 finalized-content gate、空正文壳和 run_id trace 过滤。

## 取消

- `JobService._apply_standard_cancel_command`、`_apply_ambiguous_cancel_command` 和 `mark_cancelled` 只转换 job/run 状态，没有删除 ChapterVersion、ChapterEvaluation 或 ChapterGenerationTrace。
- durable job 约束要求 running cancel 只有在持有有效 lease/fence 的终态才能清理，不能在 cancel_requested 中间态提前删除。
- workflow candidate metadata 已记录 `_chapter_workflow.run_id`；正式版本同时可能被 Chapter 或 ChapterRevision 引用，删除必须按 run provenance 和引用保护共同筛选。
- generation trace 是 JobEvent 派生的可删除兼容投影；可以删当前 run trace，但不能删 JobEvent 或移动 projector cursor。

## 多版本

- 管理设置写入 `writer.chapter_versions`。
- 旧 `PipelineOrchestrator._resolve_version_count` 读取显式值、系统配置和兼容默认；新 `ChapterWorkflowStartService.start` 只执行 `FlowConfig.model_validate(flow_config or {})`。
- `ChapterWorkflowHandler.generate_candidates` 使用 `flow_config.versions or 1`，所以新 workflow 在未显式传值时固定生成一个版本。
- 候选生成循环、持久化和前端 `workflow_run_id` 过滤均支持两个版本，根因位于 start 配置冻结。

## 当前工作树保护

- 相关 workflow/trace/actor/content-cleaning 文件已有用户未提交改动。
- 实施必须增量编辑，禁止回滚 stale snapshot 防护、row_revision invalidate、activity trace、候选内容递归解包等现有改动。
