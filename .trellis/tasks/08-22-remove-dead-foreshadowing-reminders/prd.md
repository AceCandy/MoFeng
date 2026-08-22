# 删除无调用伏笔提醒链

## Goal

删除 `ForeshadowingService` 中已确认不可达的旧提醒闭环和仅为该闭环存在的测试，减少误导性维护面，同时完整保留当前伏笔列表、自动跟踪、章节投影和数据模型能力。

## Background

- CodeGraph 与全仓精确搜索确认 `check_and_create_reminders` 没有生产调用者或动态注册。
- `create_reminder` 仅被 `check_and_create_reminders` 调用；`get_unresolved_foreshadowings` 仅被该死链和 `test_foreshadowing_service.py` 的唯一测试调用。
- 活跃自动伏笔流程使用独立的 `ForeshadowingTrackerService`，由 `EnhancedWritingFlow` 调用，不依赖待删方法。
- 现行伏笔列表 API 只调用 `ForeshadowingService.get_foreshadowings`；`abandon_foreshadowing` 是独立 CRUD，即使当前无 caller 也不属于本提醒链任务。

## Requirements

- R1. 从 `backend/app/services/foreshadowing_service.py` 删除 `get_unresolved_foreshadowings`、`create_reminder`、`check_and_create_reminders`。
- R2. 删除仅服务于上述方法的 `ACTIVE_FORESHADOWING_STATUSES`、`Dict`、`and_`、`ForeshadowingReminder` import。
- R3. 删除只覆盖 `get_unresolved_foreshadowings` 的 `backend/tests/test_foreshadowing_service.py`；不为已删除行为保留测试壳。
- R4. 保留 `get_foreshadowings`、`abandon_foreshadowing`、`ForeshadowingTrackerService`、现行 router、`ForeshadowingReminder` 模型/关系、迁移和数据库表。
- R5. 删除后精确搜索不得存在三个目标方法或专属常量引用，并运行现行伏笔 API/跟踪相关回归。

## Acceptance Criteria

- [x] 三个目标方法、专属常量、孤立 import 和专属测试文件已删除。
- [x] 全仓生产代码与测试不再引用三个目标方法或 `ACTIVE_FORESHADOWING_STATUSES`。
- [x] `ForeshadowingService.get_foreshadowings` 与 router 测试通过。
- [x] 活跃 `ForeshadowingTrackerService`、章节投影、伏笔模型与迁移未修改。
- [x] 后端静态检查、目标测试和相关伏笔回归通过；独立复核无阻塞发现。

## Out of Scope

- 删除或重构 `abandon_foreshadowing` 及其他独立 CRUD。
- 重设计提醒策略或 `ForeshadowingTrackerService`。
- 删除 `ForeshadowingReminder` 模型、表、关系、迁移或历史数据。
- 修改前端伏笔展示、API schema 或历史审计文档。
