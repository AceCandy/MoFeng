# 技术设计

## 调用边界

旧链为一个无外部入口的内部闭环：

```text
check_and_create_reminders
├── get_unresolved_foreshadowings
└── create_reminder
```

全仓无 API、任务、服务、动态字符串或注册表调用 `check_and_create_reminders`。唯一外部引用是专属测试直接调用 `get_unresolved_foreshadowings`。

## 删除清单

- `ForeshadowingService` 的 3 个旧提醒方法。
- 只被旧查询使用的 `ACTIVE_FORESHADOWING_STATUSES`。
- 删除后孤立的 `Dict`、`and_`、`ForeshadowingReminder` import。
- 只包含 1 条死链测试的 `backend/tests/test_foreshadowing_service.py`。

## 保留边界

- `ForeshadowingService.get_foreshadowings` 与列表 router。
- `ForeshadowingService.abandon_foreshadowing`，避免把独立 CRUD 债务混入本任务。
- 活跃的 `ForeshadowingTrackerService` 和 `EnhancedWritingFlow`。
- `ForeshadowingReminder` ORM 模型、与 `Foreshadowing` 的 relationship、Alembic 历史及数据库数据。

## 兼容与回滚

目标方法没有生产调用者，因此没有运行时 API 兼容面。删除是单文件代码收缩加单测试文件删除，可通过单提交回滚；不涉及 schema 或数据回滚。

