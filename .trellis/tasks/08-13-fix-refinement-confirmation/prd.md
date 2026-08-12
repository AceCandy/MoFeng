# 修复润色后重复选版

## Goal

AI 评审已经选出唯一优选版本并完成修复润色后，人工确认阶段只向用户展示该润色结果，避免用户再次在优选版本和已淘汰原稿之间选版。

## Background

- `pipeline_orchestrator.py:1528-1554` 已按 `best_version_index` 只对优选版本执行修复润色。
- `pipeline_orchestrator.py:1614-1698` 为保留生成历史，仍会保存本轮全部版本及其 `metadata.ai_review.is_best` 标记。
- `novel_service.py:1253-1267` 当前把全部已保存版本投影为 `version_selections`。
- `ChapterWorkflowPanel.vue:84-109` 会遍历全部 `version_selections`，因此人工确认阶段重新出现两个版本。

## Requirements

- 数据库继续保留本轮全部原始候选，不删除未入选版本。
- 当章节处于 `waiting_for_confirm` 且本轮版本含唯一 `metadata.ai_review.is_best=true` 时，公开的待确认候选只包含该优选版本。
- 优选版本的内容必须是完成修复润色后写回并持久化的内容。
- 对没有 `ai_review.is_best` 标记的旧数据或非 AI 评审流程保持兼容：不得把候选错误过滤为空，沿用现有候选集合。
- 人工确认仍使用现有真实版本 ID 提交，不改变确认接口和状态机命令。
- 单一候选的界面语义应是确认润色结果，不再暗示用户需要进行多版本优选。

## Out of Scope

- 不删除或迁移历史 `chapter_versions` 数据。
- 不改变 AI 评审算法、提示词、评分规则或修复润色逻辑。
- 不改变历史版本面板展示全部版本的能力。
- 不新增数据库字段、迁移或新的确认接口。

## Acceptance Criteria

- [x] 两个生成版本完成 AI 评审和修复润色后，人工确认阶段只展示一个候选。
- [x] 展示并提交的候选 ID 对应 `metadata.ai_review.is_best=true` 的版本，其正文为修复润色后的正文。
- [x] 未入选版本仍保存在历史版本数据中。
- [x] 缺少优选标记的旧 `waiting_for_confirm` 数据仍返回原候选，用户可以继续完成流程。
- [x] 现有多候选键盘选择与真实版本 ID 提交能力保持可用，兼容回退不回归。
- [x] 后端针对性测试和前端组件测试通过；按 Java 之外的项目规范运行相关类型/静态检查。
