# 实施计划

1. 锁定基线
   - 确认认证 HTTP 子任务已归档、工作树干净、命中仍为 3+7。
   - 运行目标模块导入并记录 10 条弃用告警。
   - Gate：命中清单与 `research/pydantic-v2-inventory.md` 完全一致。

2. 先补最小契约测试
   - 扩展 `test_config_security.py`：database URL trim/空白、logging level 规范化/非法值、load/peak 默认与非法组合。
   - 新增参数化 `test_pydantic_v2_contracts.py`：七个 Read schema 从属性对象读取、dump/JSON schema 关键字段。
   - Gate：测试只依赖公开 Pydantic 行为，不断言 decorator 源码。

3. 机械迁移生产代码
   - `config.py` 改为 `field_validator` / `ValidationInfo`，不改字段或错误文案。
   - 六个 schema 文件改为 `ConfigDict(from_attributes=True)`，保留其他代码原样。
   - Gate：`rg -n "@validator|@root_validator|class Config:" backend/app --glob '*.py'` 无命中。

4. 聚焦验证
   - `cd backend && .venv/bin/python -m pytest tests/test_config_security.py tests/test_pydantic_v2_contracts.py -W error::pydantic.warnings.PydanticDeprecatedSince20`
   - `cd backend && .venv/bin/python -m pytest tests/test_openapi_contract.py -k "not inventory"`
   - `cd backend && .venv/bin/ruff check app/core/config.py app/schemas/admin.py app/schemas/config.py app/schemas/llm_config.py app/schemas/novel.py app/schemas/prompt.py app/schemas/user.py tests/test_config_security.py tests/test_pydantic_v2_contracts.py`

5. 全量与独立复核
   - 运行 `cd backend && .venv/bin/python -m pytest -m "not postgres" --strict-markers`；若仅出现已记录的 OpenAPI inventory 基线失败，明确记录，不越界修复。
   - 独立复核 validator 时机/默认值、七个 schema 字段和 OpenAPI 兼容、无告警导入及最小 diff。
   - 回滚点：任何公共字段、错误文案或 JSON schema 变化都回滚产品 diff并返回 Phase 1。
