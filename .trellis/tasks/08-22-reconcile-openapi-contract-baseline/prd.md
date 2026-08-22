# 校准 OpenAPI 契约基线

## Goal

让 OpenAPI 库存测试与当前已提交且可重复生成的公开契约一致，恢复快速 pytest profile 的有效门禁信号。

## Background

- `backend/openapi.json` 与运行时 exporter 均为 88 个 paths、112 个 operations。
- `backend/tests/test_openapi_contract.py` 仍使用 87、111 和旧 operation-id hash。
- 相比最后一次基线提交，新增路径仅为 `/api/writer/novels/{project_id}/chapters/{chapter_number}/reset`；artifact 更新来自既有章节工作流任务，本任务不重新设计该 API。

## Requirements

- R1. 先验证 runtime schema 与已提交 `backend/openapi.json` 字节/语义一致，再校准库存常量和 operation-id hash。
- R2. 只修改测试基线及必要验证记录；不得新增、删除、重命名路由或手工修改生成 artifact。
- R3. 保留 operation id 唯一性、schema 下限、显式响应 schema 和 exporter 确定性等其他断言。
- R4. 若 exporter 与 artifact 存在除已知库存常量外的漂移，停止并返回规划，不直接刷新基线。

## Acceptance Criteria

- [x] OpenAPI inventory 测试以 88 paths、112 operations 和当前确定性 hash 通过。
- [x] 完整 `test_openapi_contract.py`、exporter check 与前端 API contract gate 通过。
- [x] runtime 与 committed artifact 一致，任务 diff 不包含路由、schema 或生成 artifact 改动。
- [x] 后端快速 profile 不再因 OpenAPI inventory 失败。
- [x] 独立复核确认没有把未解释的契约漂移吸收到新基线。

## Out of Scope

- 修改 reset API 的业务行为、鉴权、请求/响应 schema 或 operation id。
- 顺带修复其他 OpenAPI、后端测试或生成类型问题。

## Notes

- 这是测试基线校准任务，预计为 PRD-only 轻量变更。
