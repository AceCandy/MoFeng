# 迁移 Pydantic v2 配置写法

## Goal

将生产代码中已确认的 10 处 Pydantic v1 弃用写法迁移到项目锁定版本的 v2 原生 API，消除运行时告警，同时保持配置校验、ORM 属性读取、序列化和 OpenAPI 契约不变。

## Background

- 项目锁定 `pydantic==2.12.2`、`pydantic-settings==2.11.0`。
- 告警基线确认 `backend/app/core/config.py` 有 3 个 v1 `@validator`，六个 schema 文件有 7 个 class-based `Config`；导入目标模块恰好产生 10 条 `PydanticDeprecatedSince20`。
- 生产代码未发现 `root_validator`、`orm_mode`、`allow_population_by_field_name`、`validate_all`、`schema_extra` 等其他明确 v1 命中点。
- 前置子任务 `08-22-converge-auth-http-client` 已完成并归档；本任务是父任务中的第 3 项。

## Requirements

- R1. 将 `Settings` 的 3 个 `@validator` 机械迁移为 `field_validator`，保留 before/after 时机、字段顺序、默认值行为和原错误文案。
- R2. 将 7 个仅含 `from_attributes=True` 的 `class Config` 迁移为 `model_config = ConfigDict(from_attributes=True)`。
- R3. 保持 `database_url` 空白处理、`logging_level` 大小写/合法值处理、job load/peak 两倍约束及错误信息不变。
- R4. 保持七个 Read schema 的字段、默认值、`model_validate(orm_obj)`、`model_dump()` 和 JSON schema 结果兼容；保留 `PromptRead.model_validate` 的标签转换逻辑。
- R5. 不迁移未弃用的 `SettingsConfigDict(populate_by_name=True)` 或现有字典形式 `model_config`，不修改业务字段、可变默认值或相邻 schema 债务。
- R6. 使用现有 Pydantic v2 API，不新增依赖、兼容层、基类或批量抽象。

## Acceptance Criteria

- [x] `backend/app` 中不再存在 `@validator`、`@root_validator` 或 `class Config:` 的已确认生产命中。
- [x] 目标模块在 `PydanticDeprecatedSince20` 设为 error 时可无告警导入。
- [x] 配置测试覆盖 database URL、logging level、load/peak 默认值和非法两倍约束，行为及错误文案兼容。
- [x] 七个 Read schema 均证明 `from_attributes` 生效，并保持字段 dump / JSON schema 契约。
- [x] 聚焦 pytest、相关 OpenAPI 测试和 scoped Ruff 通过；快速非 PostgreSQL profile 的结果被记录。
- [x] 独立复核确认 diff 只包含机械迁移、最小契约测试和必要规范同步。

## Out of Scope

- 升级 Pydantic、pydantic-settings 或 FastAPI。
- 修改 API 字段、默认值、别名、OpenAPI 产物或前端生成类型。
- 处理 `populate_by_name` 的未来迁移、可变默认值、Prompt 自定义转换设计或其他 schema 重构。
- 修复快速 profile 中与本任务无关的既有 OpenAPI 路径计数失败。
