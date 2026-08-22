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

## 集成复核结果

- 子任务提交：OpenAPI `47af7d8`、durable event `50379b1`、bcrypt `c83b134`、
  frontend bundle `c5d1be9`；4 个子任务均已独立归档。
- 后端快速 profile：473 passed；PostgreSQL profile：237 passed；Ruff、
  `crypt` 弃用 warnings-as-error 与 `npm run api:check` 均通过。
- 前端：type-check、348 个完整单测、lint、build 与 bundle budget 均通过；
  JS 总 gzip 556.55 KB，最大 CSS gzip 23.63 KB，未出现原软预警。
- 精确契约由完整门禁覆盖：OpenAPI 88 paths/112 operations、durable
  `activity.ambiguous` 顺序、旧 passlib bcrypt hash 兼容及 TipTap/CSS 浏览器行为均通过。

## 未验证项与剩余风险

- 本轮父任务没有产品代码 diff，未重复执行生产部署、发布镜像或真实用户数据验证；这些不在父任务范围内。
- `npm install` 仍报告仓库现有 12 个依赖漏洞（1 low、8 high、3 critical）；未执行可能引发范围外升级的 `npm audit fix`。
- bundle 软线余量有限，未来依赖或全局样式增长仍可能重新触发预警，现有预算门禁会继续报告。
