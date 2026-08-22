# 技术设计

## 变更边界

行为缺口仅是生产代码继续使用 Pydantic v1 配置入口。最小修复位于定义处，不修改任何调用方或公共 schema 字段。

预计修改：

- `backend/app/core/config.py`：替换 import、3 个 validator decorator/signature。
- `backend/app/schemas/{admin,config,llm_config,novel,prompt,user}.py`：7 个 class-based Config 机械迁移。
- `backend/tests/test_config_security.py`：补齐三个配置 validator 的行为矩阵。
- `backend/tests/test_pydantic_v2_contracts.py`：参数化覆盖七个 Read schema 的属性读取与序列化/JSON schema。

不修改模型、路由、服务、OpenAPI artifact、依赖版本或其他有效 v2 `model_config`。

## Validator 兼容设计

- `database_url`、`logging_level` 使用 `@field_validator(..., mode="before")` + `@classmethod`。
- `job_load_test_concurrency` 使用默认 after `field_validator`，通过 `ValidationInfo.data` 读取已验证的 `job_peak_concurrency`。
- 不设置 `validate_default=True`：旧 validator 对 load 默认值不执行；database URL 默认 None 和 logging 默认 INFO 即使不执行也结果相同。
- 保留原返回类型、ValueError 文案和字段声明顺序。

## Schema 兼容设计

每个目标类只将：

```python
class Config:
    from_attributes = True
```

替换为：

```python
model_config = ConfigDict(from_attributes=True)
```

字段、继承、默认值和自定义 `model_validate` 均不调整。测试使用简单属性对象证明 ORM-style 读取，并检查 dump/JSON schema 的关键字段。

## 回滚

迁移不涉及数据或 artifact，可按单提交回滚。若 v2 validator 无法保持默认值/顺序语义，停止并返回规划，不改为 model-level 重构或兼容层。
