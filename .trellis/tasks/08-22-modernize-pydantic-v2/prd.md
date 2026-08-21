# 迁移 Pydantic v2 配置写法

## Goal

消除项目内已确认的 Pydantic v1 弃用写法，保持配置校验、schema 序列化和 API 契约不变。

## Background

- `backend/app/core/config.py` 仍有 3 处 `@validator`。
- 多个 schema 仍使用内嵌 `class Config`；项目运行于 Pydantic v2，应迁移到对应 v2 写法。

## Requirements

- R1. 仅迁移仍在生产路径使用的 `@validator` 与 `class Config` 弃用写法。
- R2. 保持字段默认值、别名、ORM 属性读取、校验顺序、错误信息语义和序列化结果兼容。
- R3. 使用项目已安装的 Pydantic v2 原生 API，不新增兼容层或依赖。
- R4. 对迁移触及的配置与 schema 增加或调整最小聚焦测试。

## Acceptance Criteria

- [ ] 项目源代码中已确认的 Pydantic v1 `@validator` 与内嵌 `class Config` 均已替换。
- [ ] 配置加载、非法配置拒绝、ORM schema 与 JSON/OpenAPI 相关聚焦测试通过。
- [ ] 目标测试运行时不再产生这些 Pydantic 弃用告警。
- [ ] 未改变 API 字段名、默认值或业务校验行为。

## Out of Scope

- 升级 Pydantic/FastAPI 版本。
- 重命名 API 字段、调整业务校验或批量重写未弃用 schema。

## Notes

- 本任务按父任务顺序在认证 HTTP 客户端任务完成后启动；启动前需核对所有具体命中点与调用契约。
