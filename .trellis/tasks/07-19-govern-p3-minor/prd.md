# P3 小项治理

## Goal

处理 19 条 low 级小项：debug 默认、datetime.utcnow、时间戳 nullable、乐观锁、监听泄漏等。

## Requirements

- debug 默认 True + assert_production_security 不强制关闭
- datetime.utcnow 改 datetime.now(timezone.utc)（foreshadowing_service 等多处）
- memory_layer 4 表 created_at/updated_at nullable + 无 server_default
- ProjectMemory.version 乐观锁未生效（只自增无 WHERE 守卫）
- analytics.py 情感分析函数复制分叉（若 P2 未覆盖）
- novel_service append_conversation seq 并发（select max+1）
- AppShell matchMedia 监听未移除（泄漏）
- 其余 low 项见审计报告

## 约束

- 不引入新依赖
- 行为变更补测试

## Acceptance Criteria

- [ ] 19 条 low 逐项处理或明确决策
- [ ] 后端 pytest 全绿 + 前端 vue-tsc/vitest/eslint/build 全绿
- [ ] 独立语义化提交

## 来源

审计报告 `docs/audit-governance-2026-07-19.md` low 清单
