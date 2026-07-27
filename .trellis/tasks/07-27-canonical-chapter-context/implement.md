# Canonical Chapter Context Implementation Plan

## Steps

- [x] 用 CodeGraph 定位 generation/review/consistency 的所有 context caller 和现有测试；记录允许差异。
- [x] 新增 contract、section enums 和稳定 serialization/hash tests。
- [x] 新增 resolver，复用现有 repository、writer visibility 和 RAG adapter，不复制查询。
- [x] 新增三个 pure adapters 与首章/RAG/fallback/budget/visibility fixtures。
- [x] shadow 接入 pipeline 与 writer，结构化比较但不记录完整 prompt。
- [x] 逐入口 cutover，删除本任务造成的旧 helper/import orphan。
- [x] 运行独立复核，确认 caller 中没有第二套 context 查询/组装。

## Validation

```bash
cd backend
pytest tests/test_chapter_context_contract.py tests/test_chapter_context_resolver.py tests/test_canonical_review_context.py tests/test_pipeline_context_restore.py tests/test_ai_review_service.py
pytest tests/test_canonical_context_wiring_static.py
pytest tests/test_pipeline_langgraph_refactor_static.py -k "not pipeline_director_mission_failure_terminates_generation and not collect_history_context_loads_selected_version_with_async_session and not mark_generation_failed_records_full_runtime_error_trace and not replace_chapter_versions_stores_review_feedback_while_waiting_for_confirm"

# 需要 Docker/Testcontainers 的完整 pipeline 门禁
pytest tests/test_pipeline_langgraph_refactor_static.py
```

新增测试应单独可运行。若既有静态 pipeline 测试存在与本任务无关的失败，记录基线并只修复由本 diff 引入的断言。

## Completion

- canonical contract/resolver/adapter/recovery/AI review suite：`50 passed`。
- pipeline 非数据库套件：`25 passed, 4 deselected`。
- `python -m compileall -q app`：通过。
- `git -c core.whitespace=cr-at-eol diff --check`：通过。
- 最终独立只读复核：无阻断项。
- 未执行：pipeline 的 4 个数据库测试与 consistency 的 2 个数据库测试；`tests/conftest.py` 强制启动 testcontainers，当前环境无 Docker socket 权限。

## Rollback

- 本变更不修改数据库 schema 或持久数据；review 请求新增向后兼容的可选 `chapter_number` 字段。若上线验证失败，整体 git revert 本次发布变更，恢复旧 builder、caller 与请求 schema。
- 不通过运行时 feature flag 长期保留两套 DB 读取路径；独立纯映射的 shadow oracle 和 contract tests 可继续用于定位差异。
- 只有 pipeline/writer 通过代表性 shadow 对比，且 consistency/generation 通过共享 contract/wiring tests 后，才允许提交删除旧 builder 的变更。
