# 替换脆弱前端静态测试

## Goal

把依赖源码字符串和语句顺序的前端行为测试替换为运行时测试，使回归门禁验证真实行为，同时保留仍有价值的架构静态约束。

## Background

- `frontend/src/components/__tests__/viteConfigStatic.spec.ts:8-16` 读取 `vite.config.ts` 文本并比较 localStorage shim 与 DevTools 动态 import 的源码顺序。
- `backend/tests/test_frontend_tanstack_query_static.py:137-158` 的两个测试通过源码字符串检查概念对话刷新时序、SSE final 提前结束和 HTTP 错误 payload 保留。
- 对应运行时边界已经存在：`useConverseConceptStreamMutation`、`NovelAPI.converseConceptStream`、`requestRaw` 和 Vite async config factory；无需引入新测试框架。
- 同一 Python 文件中的其他测试守护 TanStack Query 迁移、server-state 边界和旧调用移除，当前没有等价的集中运行时替代，应继续保留。

## Requirements

1. Vite 配置测试必须在 `globalThis.localStorage` 不完整且 DevTools 开启时真实加载并执行配置，不能读取生产源码文本。
2. 概念对话 mutation 测试必须证明 mutation 在项目缓存刷新仍未完成时已经 resolve。
3. 概念对话流测试必须证明收到 `final` 事件后不等待连接关闭即可返回最终结果，并取消 reader。
4. HTTP 测试必须证明 409 JSON 响应会生成保留 `status`、`code`、`url` 和 `payload` 的 `HttpRequestError`。
5. 仅删除被上述运行时用例替代的两个 Python 静态测试；其余架构静态测试保持不变。
6. 默认不修改生产代码；只有运行时测试确认真实缺陷时才回到规划阶段重新评估。

## Acceptance Criteria

- [x] 不完整 localStorage 场景下，启用 Vue DevTools 的 Vite 配置可以加载并产出插件配置。
- [x] 概念对话 API 已成功、缓存 invalidation 被挂起时，`mutateAsync` 仍返回对话结果。
- [x] SSE 流发送 `final` 但不关闭连接时，概念对话请求仍返回最终结果且流的 cancel 被调用。
- [x] mock fetch 返回 409 JSON 时，抛出的 `HttpRequestError` 完整保留错误上下文和响应 payload。
- [x] `test_frontend_tanstack_query_static.py` 只移除两个已替代函数，其余测试仍可由 pytest 收集并通过。
- [x] 目标 Vitest、目标 pytest、前端 lint、type-check 和全量 unit tests 全部通过。
- [x] 独立复核确认没有生产代码改动、没有新增依赖、没有扩大静态测试清理范围。

## Out of Scope

- PostgreSQL、Docker、CI 或数据库测试分层。
- 迁移该 Python 文件中其余架构静态测试。
- InspirationMode 页面级 409 跳转测试；本批只替换原静态测试实际检查的 HTTP payload 传递契约。
- 前端生产实现重构或新增测试工具抽象。
