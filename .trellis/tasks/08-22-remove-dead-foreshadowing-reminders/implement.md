# 实施计划

1. 锁定基线
   - 运行旧专属测试与现行伏笔 router 测试。
   - 精确搜索目标方法、常量、模型和活跃 tracker 调用。
2. 删除死链
   - 从 `foreshadowing_service.py` 删除 3 个方法与专属常量。
   - 清理仅由本次删除产生的孤立 import。
   - 删除 `test_foreshadowing_service.py`，不新增替代测试。
3. 聚焦验证
   - `ruff check app/services/foreshadowing_service.py tests/test_foreshadowing_router.py`
   - `python -m compileall -q app/services/foreshadowing_service.py`
   - 使用随机临时 PostgreSQL 运行 `tests/test_foreshadowing_router.py`。
   - 运行现有活跃伏笔/章节投影相关聚焦测试。
4. 最终门禁
   - 精确 `rg` 证明目标符号零引用，并确认 tracker/model/migration 仍在。
   - `git diff --check`、Trellis validate、独立只读复核。

