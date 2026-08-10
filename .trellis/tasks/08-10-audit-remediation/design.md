# 技术设计

完整设计见 `docs/audit-remediation-design-2026-08-10.md`。父任务只管理工作包边界、
顺序和最终集成复核，不直接承载业务代码修改。

## Task Map

| 工作包 | 交付物 | 顺序 |
| --- | --- | --- |
| A1 | 注册配置与 bootstrap 契约 | 第一批 |
| A2 | Linux.do OAuth state | 第一批，A1 后实施以缩小单次 diff |
| Q1 | pytest、ruff、Black、Playwright 基线 | R1 前 |
| R1 | 依赖锁、镜像验证与发布状态机 | Q1 全绿后 |
| U1 | modal 与写作台可访问性 | 独立批次 |
| D1 | durable worker 文档 | 独立批次 |
| T1 | scoped task SSE 纵深校验 | 独立批次 |

## Integration Contract

- 每个子任务独立 planning、start、focused validation、review 和 archive。
- 父任务最后核对跨工作包验收、发布顺序、回滚说明和仓库清洁度。
- 后续工作包按需创建子任务；本轮只创建并实施 A1、A2。
