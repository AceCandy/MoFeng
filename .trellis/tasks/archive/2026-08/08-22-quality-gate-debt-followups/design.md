# 质量门禁遗留债务治理设计

## Boundary

父任务只维护顺序、共同约束和最终集成复核。产品或测试改动全部落在独立子任务中，每项单独批准、提交、验证和回滚。

## Ordering

1. 先修 OpenAPI 快速 profile，使非数据库反馈恢复可信。
2. 再修 durable PostgreSQL profile，使数据库反馈恢复可信。
3. 在测试信号恢复后处理密码依赖，避免兼容回归被噪声遮蔽。
4. 最后处理 bundle 软预警；该项允许因风险过高返回规划，不允许抬阈值。

## Compatibility Contracts

- OpenAPI runtime、committed artifact 和生成 TypeScript 是同一发布单元。
- durable event 审计顺序由生产服务和 spec 共同拥有，测试必须完整而不能弱化。
- 密码封装必须验证已有 bcrypt hash，不能要求一次性数据库迁移。
- bundle 优化必须减少实际 manifest 资产字节，不能只移动或隐藏统计对象。

## Rollback

每个子任务一个产品提交；失败时回滚该子任务，不影响已完成子任务。父任务仅记录协调和集成结果。
