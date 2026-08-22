# 伏笔提醒死链清单

## 目标符号

| 符号 | 当前引用 | 结论 |
| --- | --- | --- |
| `check_and_create_reminders` | 仅定义 | 无生产入口，删除 |
| `create_reminder` | 仅被上一方法调用 | 内部死链，删除 |
| `get_unresolved_foreshadowings` | 被上一方法和唯一专属测试调用 | 测试不能证明生产可达，删除 |
| `ACTIVE_FORESHADOWING_STATUSES` | 仅被旧未回收查询使用 | 删除 |

## 删除后孤立依赖

- `typing.Dict`
- `sqlalchemy.and_`
- service 层的 `ForeshadowingReminder` import
- `backend/tests/test_foreshadowing_service.py` 全文件

`List`、`Optional`、`func`、`select`、`Foreshadowing` 和日志仍由保留方法使用。

## 保留证据

- `backend/app/api/routers/foreshadowing.py` 只调用 `get_foreshadowings`。
- `backend/app/services/enhanced_writing_flow.py` 使用 `ForeshadowingTrackerService`，不是本次旧服务方法。
- `ForeshadowingReminder` 仍是 ORM 模型并挂在 `Foreshadowing.reminders` relationship；本任务不删除 schema 或数据。
- `abandon_foreshadowing` 不属于旧提醒闭环，保持不变。

## 搜索范围

已对 `backend/app`、`backend/tests`、前端、任务/配置注册和非生成文档执行精确符号搜索；未发现 `getattr` 字符串、任务名或 API 注册引用。

## 验证记录

- 删除前：`test_foreshadowing_service.py` 与 `test_foreshadowing_router.py` 共 `3 passed`。
- 删除后：Ruff 与 `compileall` 通过，目标符号在 `backend/app`、`backend/tests` 零命中。
- 删除后：`test_foreshadowing_router.py`、`test_chapter_edit_postprocess.py`、`test_chapter_projection_retention.py` 共 `12 passed`。
- `test_chapter_long_task_jobs.py::test_finalize_prepare_apply_reuses_workflow_stream_without_early_commit` 两次在 `isolated_pg` fixture 建表阶段因 `admin_settings` 重复而 setup 失败，测试体未执行；该文件不引用本次删除符号，测试设施修复不纳入本任务。
- 未启动应用服务或 PostgreSQL 容器；PostgreSQL 测试使用随机临时数据库并完成清理。
