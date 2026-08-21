# 测试契约核验

## 现状

- `viteConfigStatic.spec.ts:8-16` 通过源码字符串顺序推断 shim 先于 DevTools 加载。
- `test_frontend_tanstack_query_static.py:137-148` 同时静态检查 mutation 后台刷新和 SSE final 提前结束。
- `test_frontend_tanstack_query_static.py:151-158` 静态检查 `HttpRequestError.payload` 字段及 `requestRaw` 传值。

## 对应运行时边界

- `vite.config.ts:1-11,49-65`：顶层 localStorage shim、DevTools 动态 import、async config factory。
- `frontend/src/queries/novel.ts:283-293,377-403`：项目查询 invalidation 与概念对话 mutation 成功回调。
- `frontend/src/api/novel.ts:120-180,461-481`：SSE final 处理和公开概念对话流 API。
- `frontend/src/api/http.ts:149-195`、`frontend/src/utils/errors.ts:4-25`：HTTP 非成功响应解析与错误上下文。

## 既有测试模式

- `frontend/src/queries/__tests__/novel.spec.ts:16-32` 已有 Vue Query composable 挂载 helper，可就地扩展。
- `frontend/src/api/__tests__/novel.spec.ts:26-49` 已使用 `Response`、`ReadableStream` 测试 SSE。
- `frontend/src/api/__tests__/client.spec.ts` 只 mock `requestRaw`，没有覆盖其非成功响应行为，因此新增聚焦 `http.spec.ts`。

## 结论

最小完整替换需要四个运行时断言：Vite 配置加载、mutation 非阻塞刷新、SSE final 提前结束、HTTP payload 保留。其余 Python 静态测试仍承担架构边界门禁，本批不迁移。

