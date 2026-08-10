# 注册配置与 bootstrap 契约

## Goal

确保公开环境变量 `ALLOW_USER_REGISTRATION` 在 Pydantic Settings v2 中被正确解析，
首次 bootstrap 使用该值补齐系统配置，同时保留数据库配置优先和现有默认策略。

## Requirements

- `ALLOW_USER_REGISTRATION` 是 canonical 名称，`ALLOW_REGISTRATION` 是兼容名称；两者
  冲突时 canonical 名称优先。
- 未设置环境变量时 `allow_registration` 默认值仍为 `True`。
- bootstrap 只在 `auth.allow_registration` 缺失时写入，不覆盖数据库已有值。
- 运行时继续由 `SystemConfig` 优先，`Settings` 只作为 fallback。
- 清理 `backend/app/core/config.py` 中其余无效 `Field(env=...)` 元数据：标准字段名直接
  依赖 BaseSettings 解析，非标准/兼容名称使用 Pydantic v2 validation alias。
- 保持当前直接构造 `Settings(...)` 的兼容性，不修改默认值、类型、系统配置 key 或
  bootstrap 版本。

## Out Of Scope

- 不改变是否默认开放注册的产品决策。
- 不纠正现有数据库中已持久化的值，不修改示例环境变量名称。
- 不重构配置类或 bootstrap 架构。

## Acceptance Criteria

- [x] 仅设置 canonical 名称为 `false` 时解析为 `False`。
- [x] 仅设置兼容名称为 `false` 时解析为 `False`。
- [x] 两个名称冲突时 canonical 名称胜出；均未设置时仍为 `True`。
- [x] bootstrap 对缺失 key 写入解析值，对已有 key 不覆盖。
- [x] 普通注册和 OAuth 新用户路径仍通过 `is_registration_enabled()` 判断。
- [x] Settings 初始化不再因 `env=` 额外关键字产生弃用警告。
