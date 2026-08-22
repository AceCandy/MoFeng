# 实施计划

1. 固化审计证据
   - 记录四表模型默认值、baseline/后续 revision 与实际 PostgreSQL catalog 对照。
   - 记录 CodeGraph 创建路径和无直接 SQL INSERT 的结论。
   - Gate：研究表覆盖所有目标字段，且不包含密钥或本地连接凭据。
2. 验证迁移生命周期
   - 使用 `TEST_POSTGRES_URL` 连接 PostgreSQL 服务，由现有 fixture 创建随机临时数据库。
   - 运行 `tests/test_database_readiness.py::test_postgres_empty_and_current_database_lifecycle`，确认空库 upgrade head、重复迁移与 readiness。
   - Gate：测试通过且临时数据库清理完成。
3. 验证 ORM 行为
   - 运行 `tests/test_project_memory_lock.py`、`tests/test_finalize_service.py` 和 memory-layer 相关 delete policy 聚焦测试。
   - Gate：现有 ORM 创建/更新路径通过，未暴露缺失默认值。
4. 最终结论
   - 复跑只读 revision/catalog 查询，`git diff --check` 和 Trellis validate。
   - 独立复核三方矩阵、测试证据和“无需迁移”判断。
   - 若无反证，仅提交任务研究/规划材料；不创建产品代码或 Alembic revision。

