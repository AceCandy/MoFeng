# 验证记录

## 聚焦门禁

- Pydantic 弃用告警契约：`22 passed`。
  - `cd backend && .venv/bin/python -m pytest tests/test_config_security.py tests/test_pydantic_v2_contracts.py -W error::pydantic.warnings.PydanticDeprecatedSince20`
- OpenAPI 非 inventory 契约：`9 passed, 1 deselected`。
  - `cd backend && .venv/bin/python -m pytest tests/test_openapi_contract.py -k "not inventory"`
- Scoped Ruff：`All checks passed!`。
  - `cd backend && .venv/bin/ruff check app/core/config.py app/schemas/admin.py app/schemas/config.py app/schemas/llm_config.py app/schemas/novel.py app/schemas/prompt.py app/schemas/user.py tests/test_config_security.py tests/test_pydantic_v2_contracts.py`
- 生产代码残留扫描无命中：
  - `rg -n "@validator|@root_validator|class Config:" backend/app --glob '*.py'`

## 快速 profile

- `cd backend && .venv/bin/python -m pytest -m "not postgres" --strict-markers`
- 结果：`468 passed, 1 failed, 237 deselected`。
- 唯一失败：`test_openapi_inventory_and_operation_ids_preserve_the_baseline`；运行时为 88 个 paths，既有基线为 87 个 paths。
- 该基线漂移早于本任务且属于任务范围外，本任务未修改 OpenAPI artifact 或顺带修复。

## 独立复核

- 三轮只读复核均未发现阻塞问题；最终复核提出的完整字段覆盖问题已补强并重跑门禁。
- 确认 3 个 validator 的 before/after 时机、字段顺序、默认值语义和错误文案保持不变。
- 确认 7 个 Read schema 的属性读取、dump、JSON schema 及 `PromptRead` 标签转换契约有测试覆盖。
- `git diff --check` 通过；未新增依赖、兼容层、基类或范围外产品改动。
