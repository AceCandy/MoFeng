# Durable Chapter Workflow Implementation Plan

## Steps

- [ ] 在实现前验证 `langgraph==1.2.2` 与 PostgreSQL checkpointer 的版本/API兼容性并锁定依赖。
- [ ] 增加 run/command/step result schema 与稳定 run identity service。
- [ ] 将现有 pipeline state 改为 versioned serializable contract，接入 PostgreSQL checkpointer。
- [ ] 逐 node 隔离 DB/LLM side effects，加入 step key/result cache 和 expected revision。
- [ ] 建立 selection interrupt/resume、retry/cancel command inbox。
- [ ] 接入 canonical finalize/outbox 和 required projection wait/reconcile。
- [ ] 新建 start/snapshot/command API 与 legacy adapter。
- [ ] 将 trace 改为 event projection并删除 trace recovery owner。
- [ ] version/feature flag shadow rollout，旧 run drain 后收缩旧 pipeline/router orchestration。

## Validation

```bash
cd backend
pytest tests/test_pipeline_langgraph_refactor_static.py
pytest tests/test_durable_chapter_workflow.py tests/test_chapter_workflow_recovery.py
pytest tests/test_confirm_finalize_router_static.py
```

必须以真实 PostgreSQL checkpoint 和独立 worker 进程执行 kill/restart；mock graph 或静态源码断言不能单独证明 durable execution。测试记录 LLM fake 调用次数，验证三个恢复点不重复已完成 step。

## Rollback

- 停止新 run 后切旧入口；新 workflow version 继续由兼容 worker drain。
- 不把已经创建 outbox/revision 的 Chapter 交给旧 finalize 重做。
- checkpoint、step results 和 commands 保留到所有 run terminal + retention 到期。
