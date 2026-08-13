# 退役 PipelineOrchestrator：实施计划

1. 将 writer 生成 helper 收敛为必返 durable response；移除 legacy enqueue 与 start gate。
2. 调整 compatibility service：新生成始终 start/reuse workflow；无 durable run 的旧式 retry 明确冲突。
3. 删除配置、部署变量、旧 handler 注册、runner、orchestrator 及专属测试。
4. 更新兼容 HTTP、worker registry、发布配置静态测试和当前架构文档。
5. 运行符号残留扫描、目标后端测试、Ruff、前端 type-check/lint，并独立复核删除边界。

## Verification

- `rg` 确认生产代码无 `PipelineOrchestrator`、runner、start gate 或 `chapter_generation` enqueue/handler。
- HTTP 集成测试覆盖普通/高级 durable start、幂等复用、合法 retry 与无 run 409。
- durable workflow persistence/commands/runtime/finalize 相关目标测试通过。
- worker registry 与发布配置契约测试通过。

## Rollback Point

不包含 schema migration；单次 revert 恢复旧双轨。若 durable 目标测试暴露能力缺口，则停止删除并回到设计阶段，不以新兼容层掩盖缺口。
