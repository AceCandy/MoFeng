# 质量门禁遗留债务治理执行计划

1. 按父 PRD 顺序选择子任务，完成该子任务的独立研究和最终规划摘要。
2. 用户批准后激活单个子任务，使用对应 backend/frontend spec 实施最小 diff。
3. 每个子任务运行聚焦门禁、所属 profile/完整前端门禁、`git diff --check` 和独立复核。
4. 提交并归档当前子任务后再规划下一项，不并行修改相邻产品边界。
5. 四项完成后激活父任务，执行：
   - 后端快速与 PostgreSQL pytest profile；
   - 后端 Ruff 与弃用 warnings-as-error；
   - 前端 type-check、完整单测、lint、build 与 bundle budget；
   - OpenAPI artifact、durable event、bcrypt compatibility 和 manifest 统计的精确回归检查。
6. 将无法验证项和剩余风险写入父任务集成记录，独立复核后提交并归档父任务。
