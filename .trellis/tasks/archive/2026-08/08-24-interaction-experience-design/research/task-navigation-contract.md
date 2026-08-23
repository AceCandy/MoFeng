# 任务结果导航合同摘录

## 规范约束

来源：`.trellis/spec/backend/durable-job-guidelines.md:248-270`。

- task list、snapshot 与 SSE 必须使用同一白名单公开投影，且不得填充私有 `payload` 或 `result`。
- task detail 可向所属用户返回 result，但仍不得返回输入 payload。
- HTTP/SSE snapshot 与 task event 必须经过同一前端运行时 decoder；格式错误、scope 漂移或未知版本不能进入任务状态。
- PostgreSQL event 是事实来源，Redis 只负责唤醒；新增可空字段不能破坏旧事件回放与 polling fallback。

## 当前实现证据

- 白名单投影集中在 `backend/app/services/job_public_projection.py:62-83` 的 `public_job_snapshot()`。
- API list、snapshot 与 SSE 分别通过 `backend/app/api/routers/tasks.py:101-134` 的 `_public_task_response()`、`_serialize_snapshot()` 和 `_serialize_event()`。
- 前端统一运行时校验位于 `frontend/src/api/tasks.ts:45-178`，SSE reducer 与 polling fallback 位于 `frontend/src/queries/tasks.ts:35-188`。
- 当前公开任务已有 `project_id/task_type/stream_type/stream_id`，没有 `chapter_number`（`backend/app/schemas/task.py:16-45`）。

## 本任务实施边界

- `chapter_number` 必须是可空新增字段，只能由 `chapter_workflow`、`chapter_finalize`、`chapter_edit_postprocess` 和正整数 payload 字段白名单生成；不能返回 payload、解析标题或解析日志。
- list、snapshot、SSE 和 detail 使用同一字段语义；旧事件缺字段时前端按项目级导航降级。
- 失败 workflow 只导航回写作台；允许的 retry/cancel/reset 继续由 workflow snapshot 的 `allowed_commands` 决定。
- `chapter_outline` 与四种普通 projection 只导航项目档案；outbox、reconcile、tombstone 不提供导航动作。
