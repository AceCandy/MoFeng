# Journal - AceCandy (Part 1)

> AI development session journal
> Started: 2026-07-05

---



## Session 1: 章节朗读与 TTS 模型接入及供应商能力隔离

**Date**: 2026-07-10
**Task**: 章节朗读与 TTS 模型接入及供应商能力隔离
**Branch**: `main`

### Summary

接入章节朗读与 TTS（MiMo Chat Audio + OpenAI Speech 两协议）；乾坤万象中枢新增语音朗读 Tab，并将供应商按 tts 能力隔离，修复 TTS Tab 获取全部供应商的问题；trellis-check 全量复核 15/15 验收项通过，自修回退通知补失败原因摘要与取消模型预取；新建 pipeline 静态测试修复跟踪任务。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `c37ee24` | (see git log) |
| `07b6442` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 2: 修复 pipeline 静态测试 node_key 断言

**Date**: 2026-07-10
**Task**: 修复 pipeline 静态测试 node_key 断言
**Branch**: `main`

### Summary

修复 test_pipeline_langgraph_refactor_static 两个预存失败：_graph_persist_versions 的 trace node_key 已从 save_draft 重构为 persist_versions（旧 key 经 TRACE_KEY_TO_GRAPH_NODE 映射保留兼容），更新静态断言对齐现状；动态行为不变，仍持久化为草稿（WAITING_FOR_CONFIRM）。后端全套 184 passed。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `b3924ce` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete
