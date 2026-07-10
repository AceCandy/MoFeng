# 修复 pipeline 静态测试 node_key 断言失效

## Goal

修复 `test_pipeline_langgraph_refactor_static.py` 中两个持续失败的静态源码断言测试，使其与 `pipeline_orchestrator.py` 当前实现一致，且不掩盖真实的持久化行为回归。

## Background

- main 分支上的预存失败，与 TTS 任务（chapter-tts-reading）无关，在提交 TTS 前跑后端全套时发现。
- 两个失败用例：
  - `test_pipeline_auto_reviews_and_refines_without_manual_choice`
  - `test_pipeline_persists_generated_versions_as_draft_not_successful`
- 测试读取 `backend/app/services/pipeline_orchestrator.py` 源码文本，断言 `_graph_persist_versions` 块包含 `node_key="save_draft"`、`node_label="保存草稿"`、`"保存草稿节点不调用模型"` 等字符串；当前源码已不含这些串，断言失败。
- 推测某次 pipeline 重构改动了节点命名/结构，但未同步更新静态测试。

## Requirements

- 先确认 `_graph_persist_versions` 当前实现：`save_draft` 节点是已被合理重构（改名/移除），还是被误删导致行为回归。
- 若源码已合理重构：更新静态测试断言对齐新节点命名/结构。
- 若源码回归：恢复 `save_draft` 节点及相关持久化草稿逻辑。
- 不能仅删除断言糊弄；必须确认 pipeline 实际把生成的版本作为草稿持久化（动态行为正确），而非仅静态字符串对齐。

## Acceptance Criteria

- [ ] `test_pipeline_auto_reviews_and_refines_without_manual_choice` 通过
- [ ] `test_pipeline_persists_generated_versions_as_draft_not_successful` 通过
- [ ] 后端全套 `backend/.venv/bin/python -m pytest -q backend/tests` 无新增失败
- [ ] 已确认 pipeline 持久化草稿的动态行为未回归（不仅是静态字符串对齐）

## Out Of Scope

- pipeline 的功能重构或节点大改，仅修复测试与源码的一致性并确认行为。

## 复现

```bash
backend/.venv/bin/python -m pytest -q \
  backend/tests/test_pipeline_langgraph_refactor_static.py::test_pipeline_auto_reviews_and_refines_without_manual_choice \
  backend/tests/test_pipeline_langgraph_refactor_static.py::test_pipeline_persists_generated_versions_as_draft_not_successful
```
