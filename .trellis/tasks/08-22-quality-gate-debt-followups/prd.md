# 质量门禁遗留债务治理

## Goal

把上一轮集成复核暴露的两个测试基线漂移和两个软预警拆成有序子任务，恢复质量门禁的可信信号，并在不扩大产品范围的前提下降低后续兼容与体积风险。

## Background

- OpenAPI runtime 与已提交 artifact 均为 88 个 paths、112 个 operations；库存测试仍钉住 87/111 与旧 operation-id hash。
- durable job PostgreSQL 测试遗漏 2026-08-16 已加入正式事件链的 `activity.ambiguous`。
- 后端锁定 `passlib==1.7.4`，导入时触发 Python `crypt` 弃用预警；Python 3.13 将移除该模块。
- 前端构建通过硬预算，但主 CSS gzip 25.14 KB 超过 24 KB 软线，JS 总 gzip 580.36 KB 超过 560 KB 软线。

## Requirements

- R1. 按下表顺序逐项规划、批准、实现、检查、提交和归档，父任务不直接修改产品代码。
- R2. 测试漂移任务先证明当前运行时契约正确，再更新测试；不得为绿灯删除有效路由或事件。
- R3. 弃用与体积任务不得通过屏蔽告警或抬高软阈值伪造完成。
- R4. 每个子任务保持独立验证和可回滚，不顺带升级依赖、重构认证、重设计前端或清理相邻代码。
- R5. 四项完成后运行后端快速/PostgreSQL profile 与前端质量门禁，确认原 4 个信号均消失且没有新回归。

## Ordered Task Map

| 顺序 | 子任务 | 交付物 | 主要验证 |
|---:|---|---|---|
| 1 | `08-22-reconcile-openapi-contract-baseline` | 校准 OpenAPI 库存基线 | OpenAPI contract/exporter/API checks |
| 2 | `08-22-align-durable-job-ambiguity-events` | 校准歧义事件序列测试 | PostgreSQL 聚焦测试与 profile |
| 3 | `08-22-remove-passlib-crypt-deprecation` | 替换或隔离失效密码哈希封装 | 旧 bcrypt hash 兼容与认证测试 |
| 4 | `08-22-reduce-frontend-bundle-warnings` | 安全降低 CSS 单文件与 JS 总量 | build budget 与前端完整门禁 |

## Acceptance Criteria

- [ ] 4 个子任务均有可验收 PRD，并在各自启动前完成复杂度所需材料与用户批准。
- [ ] 后端快速与 PostgreSQL profile 不再包含两个已知基线失败，且 Pydantic/密码相关弃用告警门禁通过。
- [ ] 前端生产构建不再报告 CSS 单文件或 JS 总量软预警，硬预算未放宽。
- [ ] 现有 OpenAPI、durable event、bcrypt hash、认证行为和前端视觉/交互契约保持兼容。
- [ ] 4 个子任务均独立复核和归档，未验证项及剩余风险被明确记录。
- [ ] 父任务完成跨任务集成复核后才归档。

## Out of Scope

- 新增或删除业务 API、改变 durable job 事件语义。
- 强制批量重哈希用户密码、重写认证系统或无关依赖升级。
- 前端重设计、全站 CSS 重构或为追求数字进行无证据拆包。
- 清理本任务树之外的其他全仓技术债。

## Notes

- 来源证据见上一父任务归档记录 `08-22-technical-debt-program/research/integration-validation.md`。
