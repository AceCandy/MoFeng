# 代码库治理：49 项审计整改

## Goal

基于 2026-07-19 代码库审计报告（`docs/audit-governance-2026-07-19.md`），治理 49 项确认问题，打造干净、安全、可维护的开源项目。

## 背景

2026-07-19 对 MoFeng 做 6 模块并行审查 + 每条发现独立对抗验证，确认 49 项问题（high 5 / medium 25 / low 19），剔除误报 13 项。完整清单见审计报告。

本 parent task 统筹 4 批治理交付，每批一个 child task，独立验证+提交+归档。

## 交付物映射（child tasks）

| child | 范围 | 条数 | 复杂度 |
|---|---|---|---|
| govern-p0-security-data | 安全+数据完整性（5 high） | 5 | 复杂（design+implement） |
| govern-p1-dead-code | 死代码清理（批量删） | ~20 | 中（清单+验证） |
| govern-p2-risk-harden | 风险加固（medium） | 25 | 复杂（design+implement） |
| govern-p3-minor | 小项（low） | 19 | 轻（PRD-only） |

## 跨 child 验收标准

- [ ] 每批完成后：后端 pytest 全绿 + 前端 vue-tsc/vitest/eslint/build 全绿
- [ ] 每批独立语义化提交，不跨批混提
- [ ] P0 -> P1 -> P2 -> P3 依次推进，前一批归档后才 start 下一批
- [ ] 不可逆删除（死代码/死文件）必须在 child prd 列清单并验证无引用
- [ ] 安全修复（P0）补测试覆盖

## 整体策略

- 顺序推进，每批：prd（+design/implement）-> start -> 实现 -> check -> 提交 -> 归档
- 治理中发现的新问题记入当前 child research，不扩大范围
- 实现与审查分离，每批写完独立 check 复核

## spec 沉淀计划

- 安全加固 -> `.trellis/spec/backend/security-guidelines.md`
- 死代码清理规则 -> `.trellis/spec/*/quality-guidelines.md`
- 数据完整性模式 -> `.trellis/spec/backend/database-guidelines.md`

## 来源

- 审计报告：`docs/audit-governance-2026-07-19.md`
- 审计方法：6 模块并行 finder + 独立对抗验证（误报率 ~21%）
