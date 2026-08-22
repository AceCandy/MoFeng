# Pydantic v2 迁移盘点

## 版本与告警基线

- `backend/requirements*.txt`：`pydantic==2.12.2`、`pydantic-settings==2.11.0`。
- 以 `python -W always` 导入目标模块产生 10 条 `PydanticDeprecatedSince20`：3 条 v1 validator、7 条 class-based config。
- `backend/app` 未发现 `root_validator` 或其他明确 v1 config key。

## Validator 命中

| 位置 | 当前语义 | v2 映射 |
| --- | --- | --- |
| `core/config.py:252-255` | `database_url` before + always；显式非空字符串 trim | `field_validator(..., mode="before")`；默认 None 无副作用，无需扩大 `validate_default` |
| `core/config.py:257-264` | `logging_level` before；None→INFO、trim/upper、固定合法集合 | `field_validator(..., mode="before")`，保留原错误文案 |
| `core/config.py:266-272` | 已解析的 load 值必须不少于先声明 peak 的两倍 | after `field_validator` + `ValidationInfo.data`；保持字段顺序依赖 |

第三个 validator 当前未设置 `always=True`：当 load 使用默认值时不额外校验。v2 迁移也不启用 `validate_default`，避免扩大行为。

## Class Config 命中

以下配置均只有 `from_attributes = True`，统一机械改为 `ConfigDict(from_attributes=True)`：

- `schemas/llm_config.py:48-52` — `LLMConfigRead`
- `schemas/admin.py:14-22` — `UpdateLogRead`
- `schemas/config.py:22-24` — `SystemConfigRead`
- `schemas/novel.py:139-153` — `Blueprint`
- `schemas/novel.py:156-166` — `NovelProject`
- `schemas/prompt.py:114-120` — `PromptRead`
- `schemas/user.py:42-51` — `User`

`novel.py` 已导入 `ConfigDict`；其余五个 schema 文件只需在现有 Pydantic import 中增加它。现有其他 `model_config = {...}` 是有效 v2 写法，不做格式统一。

## 调用与测试证据

- `Settings` 默认值和 load/peak 约束已有 `backend/tests/test_config_security.py:58-70,132-154` 覆盖；database URL trim、logging level 仍需最小补测。
- 七个目标 Read schema 当前没有直接的统一 `from_attributes` 契约测试。
- `PromptRead` 重写 `model_validate` 处理 ORM 字符串 tags；迁移 config 时必须保留该方法原样。
- `User`、`NovelProject` 等被路由/服务广泛作为 response schema 消费，因此验证应覆盖属性对象、dump 与 JSON schema，不改调用方。
- `test_openapi_contract.py` 现有 inventory 路径计数有父任务已记录的无关基线失败；本任务只运行其余 OpenAPI 契约并记录完整快速 profile 结果。

## 适用规范

- `.trellis/spec/backend/quality-guidelines.md`：Pydantic v2、配置、schema、pytest 与 Ruff 约定。
- `.trellis/spec/backend/transport-contracts.md`：字段级 OpenAPI 契约不得因内部配置迁移变化。
