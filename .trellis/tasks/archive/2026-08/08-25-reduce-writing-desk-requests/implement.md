# Implementation Plan

1. 修正项目详情精确失效，并补充缓存失效测试。
2. 修正工作流和 AppShell 首次快照基线，并补充状态转换测试。
3. 让任务轮询跟随 SSE 连接状态，并验证断线兜底。
4. 跳过重复章节上下文 PATCH，移除 TTS 首屏预取。
5. 运行相关 Vitest、`vue-tsc`，检查完整 diff，独立复核请求触发链。

## Risky Files

- `frontend/src/composables/useChapterWorkflowActor.ts`：异步快照边界判断。
- `frontend/src/queries/tasks.ts`：SSE 与轮询故障切换。

## Rollback Points

- 查询精确失效、首次快照基线、动态轮询、延迟请求分别形成独立小补丁，可逐项撤回。
