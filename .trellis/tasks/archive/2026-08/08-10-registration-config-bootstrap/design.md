# 技术设计

## Data Flow

```text
ALLOW_USER_REGISTRATION / ALLOW_REGISTRATION
                    -> Settings.allow_registration
                    -> bootstrap 仅补缺失 auth.allow_registration
                    -> AuthService 读取数据库配置，缺失时回退 Settings
```

## Decisions

- 使用 Pydantic v2 的 `validation_alias=AliasChoices(...)` 表达 canonical/兼容名称及优先级。
- 对环境变量名等于字段名大写形式的字段删除无效 `env=`，不额外声明 alias。
- 当前依赖版本的 characterization 证明 validation alias 会屏蔽字段名直接构造；在
  `SettingsConfigDict` 增加 `populate_by_name=True`，保留 `Settings(field_name=...)`，同时
  保持 `AliasChoices` 中 canonical 环境变量优先。
- bootstrap 实现原则上不改，只通过回归测试固定“仅补缺失值”契约；若测试证明实现有
  偏差，才做最小修复。

## Compatibility And Rollback

- canonical、兼容环境变量、字段名直接构造和默认值均保留。
- 代码回滚不会自动恢复此前被错误 seed 的数据库值；上线前需显式检查已有配置。
