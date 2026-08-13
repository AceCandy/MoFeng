# 修复主工作流优选版本投影

## Goal

修复 durable Chapter workflow 在 AI 已评审并润色优选版本后，人工确认仍显示全部候选的问题；用主运行链路的集成证据替代旧流水线假数据测试。

## Background

- durable 评审通过 `ChapterWorkflowReviewOutput.best_ordinal` 选出唯一版本，post-review 只润色该 ordinal。
- `ChapterWorkflowCandidatePersistenceService` 将 AI evaluation 绑定到优选版本，但当前写入 `ChapterVersion.metadata` 时只保存 `_chapter_workflow.run_id/ordinal`，没有持久化结构化优选身份。
- `NovelService` 的待确认投影只识别 `metadata.ai_review.is_best=true`，因此 durable 数据无法命中并回退为全部候选。
- 上一修复只用兼容 `PipelineOrchestrator` 元数据构造读侧测试，未覆盖 durable review → post-review → persist → chapter read 主链，产生假阳性。

## Requirements

- durable 候选持久化必须从已验证的 `review.best_ordinal` 派生每个版本的严格布尔优选标记。
- 优选标记与候选版本、evaluation、post-review 内容必须在同一事务中持久化，刷新后仍可稳定投影。
- `NovelService` 待确认投影只显示唯一优选版本；未入选版本仍保留在完整版本集合中。
- 无 review、旧数据缺少标记或标记冲突时继续保守回退，不猜测优选版本。
- 回归测试必须经过 durable activity/persistence 主链并调用章节公开投影，不得手工构造旧流水线专属元数据作为主要验收证据。
- 更新工作流规范和跨层检查规则，明确兼容链路测试不能替代当前生产主链测试。

## Out of Scope

- 本次不删除 `PipelineOrchestrator`。它仍是 `chapter_generation` worker 的生产处理器，并承担配置关闭时的 legacy drain、旧节点重试和历史 trace 恢复。
- 不改变 AI 评审、润色提示词、候选数量或前端确认接口。
- 不迁移已经处于 `waiting_for_confirm` 且缺少优选标记的旧候选；这些数据继续走兼容多候选回退。

## Acceptance Criteria

- [x] durable 评审选择 ordinal 2、post-review 润色 ordinal 2 后，持久化的 v2 标记为唯一优选，v1 明确不是优选。
- [x] 同一测试读取章节公开投影时，`versions` 保留 v1/v2，`version_selections` 仅包含润色后的 v2 及其真实版本 ID。
- [x] AI evaluation 仍绑定 v2，activity replay、事务回滚和隐私约束不回归。
- [x] 前端单候选确认测试、类型检查和静态检查继续通过。
- [x] 独立复核确认主链数据流与规范一致，无高、中严重问题。
