# 修复章节重生成与多版本生成 - 技术设计

## 1. 边界与原则

本次沿用现有 Vue 工作台、Chapter Workflow actor、durable JobService 和候选持久化结构，不新增 API 字段、数据库表或前端全局状态。

“彻底取消”的数据边界是当前 run 的未确认派生结果，而不是删除 durable 身份或正式章节事实：

```text
取消命令
  -> root job/run 进入 fenced cancelled 终态
  -> 清当前 run 未保护候选 + 评估 + 可删除 trace
  -> 无正式正文时重置章节草稿状态
  -> 保留 JobEvent/command/activity/checkpoint 审计与正式 revision/projection
  -> 前端失效 chapter/project query
```

## 2. 前端设计

### 2.1 状态行与取消入口

- `ChapterWorkflowPanel` 继续负责待开始、待选版、失败恢复、取消后重启等决策型内容。
- 生成进度可见的纯状态阶段不再渲染其大标题区。
- `ChapterGenerating`/进度头接收 `canCancel`、`pending` 并向 `WDWorkspace` 发出 `cancel`；是否可取消仍只取 `workflowAllowedCommands`，不在 UI 推断。
- `WDWorkspace` 使用一个本地 handler 同时清空候选描红与落墨快照，再向上发出 `workflowCancel`，避免两个入口出现不同清理行为。

### 2.2 当前 run 预览隔离

`traceReplayProps.chapterContentPreview` 在存在当前 workflow 时不再回退到 `selectedChapterResolvedContent`。它只读取已经由 `WritingDesk` 按 `workflow_run_id` 过滤的 `workflowCandidates`；没有当前 run 候选时传空字符串。

这同时解决两类竞态：取消响应后的 Vue Query 后台刷新尚未结束，以及新 run snapshot 已接受但旧章节缓存仍在。非 workflow 历史回看仍保留原有版本解析兜底。

## 3. 后端取消设计

### 3.1 统一终态清理

在 JobService 已持有 `BackgroundTask -> ChapterWorkflowRun -> Chapter` 锁和有效 fencing 的取消完成路径调用一个最小清理 helper。标准 waiting cancel、ambiguous cancel 和 worker `mark_cancelled` 都复用该 helper；只记录 cancel_requested 的中间态不清数据。

helper 行为：

1. 锁定该章版本并按 id 排序。
2. 仅选择 metadata 中 `_chapter_workflow.run_id == 当前 run.id` 的候选。
3. 排除 `Chapter.selected_version_id` 和任意 `ChapterRevision.selected_version_id` 引用的版本。
4. 先删候选评估，再删剩余未保护版本。
5. 删除 `source_run_id == 当前 run.id` 的 generation trace 兼容投影；保留 JobEvent 和 projector checkpoint。
6. 仅当章节没有正式选中版本/正式正文，且当前草稿状态由本 run 候选产生时，将 generation status/progress/step 等恢复为现有生成前默认值。

重复调用时没有匹配版本/trace 即为空操作。任何删除、章节重置、run/job cancelled 转换和事件追加必须随所属 service transaction 一起提交或回滚。

### 3.2 正式内容保护

不复用 Chapter tombstone/finalize 逻辑。tombstone 面向正式 revision supersede，会制造新的投影事实，不符合“丢弃未确认草稿”的语义。

如果当前 run 正在重生成一个已有正式章节，只删除本 run 新建且未被引用的候选；原 `content`、selected version、revision、outbox 与 projection 均保持。

## 4. 版本数解析设计

把旧 pipeline 已有的版本数解析契约提取为可复用的后端函数/服务：

```text
显式 flow_config.versions
  > system_configs writer.chapter_versions / legacy key
  > 现有兼容环境/Settings 默认值
  > clamp 到 1..2
```

`ChapterWorkflowStartService` 在 idempotency/active-run 判断所使用的请求规范化之前解析一次，并把同一 `FlowConfig` 对象用于幂等比较、runtime input hash 和 job payload。这样省略 versions 的相同幂等请求不会因“未解析 None”和“已冻结 2”产生冲突。

已有 active run 直接返回其原始 payload，不重新解析系统配置。

## 5. 兼容性与回滚

- 无 schema、OpenAPI 或数据库迁移。
- API 请求仍允许省略 `flow_config`，行为从错误的固定 1 修正为系统配置。
- 回滚可按前端 UI/预览、取消清理、版本解析三组提交块逐组撤回；持久化清理本身不可恢复被取消的未确认候选，因此测试必须先证明正式引用保护。
- 当前未提交的 actor/trace/content-cleaning 改动均作为前置事实保留，不做无关格式化或重构。
