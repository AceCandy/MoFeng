# 实施计划

1. 确认前置任务与基线
   - 验证 `08-22-layer-backend-tests` 已归档，工作树无意外改动。
   - 复核 `auth.ts` 五个公开函数、调用方及现有 http/client 测试。
   - Gate：请求矩阵与 `research/auth-http-boundary.md` 一致。

2. 先建立最小回归测试
   - 新增 `frontend/src/api/__tests__/auth.spec.ts`，覆盖 URL/method/body/header/timeout、options fallback、登录映射、用户映射与刷新头、204、detail/fallback、网络/非 JSON、超时中止。
   - 在 `http.spec.ts` 增加外部 AbortSignal 产生 `code: 'abort'` 的测试。
   - Gate：测试能在旧实现或迁移中明确暴露契约差异，且不测试内部函数名。

3. 收敛认证请求
   - `auth.ts` 删除独立 fetch/timeout/abort/error parsing，按设计改用 `requestJson` / `requestRaw`。
   - 保持公开函数签名、显式 token、刷新头，并为 10/15 秒接口显式传入 per-endpoint timeout。
   - 更新 AIMETA；不改共享 HTTP API、不引入 helper/client/dependency。
   - Gate：`rg -n "fetch|AbortController|setTimeout|readErrorMessage" frontend/src/api/auth.ts` 无重复边界残留。

4. 稳定登录页超时判断
   - `Login.vue` 按 `HttpRequestError.code === 'timeout'` 分支，保留现有中文提示。
   - Gate：不改变其他登录错误或跳转分支。

5. 聚焦验证
   - `cd frontend && npm run test:unit -- src/api/__tests__/auth.spec.ts src/api/__tests__/http.spec.ts src/api/__tests__/client.spec.ts`
   - `cd frontend && npm run type-check`
   - 必要时运行 `cd frontend && npm run lint -- src/api/auth.ts src/api/__tests__/auth.spec.ts src/api/__tests__/http.spec.ts src/views/Login.vue`；若脚本不支持 scoped 参数则记录未执行，不扩大为全仓修复。

6. 独立复核
   - 对照 PRD 逐项检查公开契约、共享错误上下文、取消/超时区分和刷新 token 数据流。
   - 确认 diff 只包含四个预期产品/测试文件及任务材料，没有敏感或临时产物。
   - 回滚点：任一公开契约无法保持时，回滚产品 diff 并返回 Phase 1；不临时扩展 `http.ts`。
