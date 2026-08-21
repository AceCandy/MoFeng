# 收敛认证 HTTP 客户端

## Goal

消除认证 API 自建的 fetch、超时和错误解析边界，统一复用 `frontend/src/api/http.ts`，降低两套 HTTP 行为继续漂移的风险，同时保持认证流程、接口参数、返回类型和页面级失败反馈兼容。

## Background

- `frontend/src/api/auth.ts:37-103` 当前自建 `authRequest`，重复实现 fetch、超时、AbortController、错误解析、204 和 JSON 响应处理。
- 共享 `frontend/src/api/http.ts:149-204` 已提供 `requestRaw` / `requestJson`、外部取消、超时及 `HttpRequestError` 归一化。
- 认证模块没有独立刷新接口；现有“刷新令牌”仅指 `/users/me` 响应头 `X-Token-Refresh` 及 `refreshedToken` 返回值。
- 前置子任务 `08-22-layer-backend-tests` 已完成并归档；本任务是父任务中的第 2 项。

## Requirements

- R1. 保持 `/options`、`/token`、`/users/me`、`/send-code`、`/users` 的 URL、method、payload、Authorization、超时和公开返回类型不变。
- R2. `auth.ts` 直接复用 `requestJson`；仅 `/users/me` 因需同时读取 JSON body 与 `X-Token-Refresh` 而复用 `requestRaw`，不新增或扩展通用 HTTP 抽象。
- R3. 删除 `auth.ts` 内独立的 fetch、定时器、AbortController 和错误响应解析；认证业务只保留 URL、请求参数、响应字段归一化及刷新头读取。
- R4. 服务端字符串 `detail` 和无详情状态码错误继续可见；网络、超时、取消和非 2xx 的非 JSON 错误响应统一采用共享 `HttpRequestError` 契约，不吞掉共享边界保留的 `status`、`code`、`url` 或 `payload`。
- R5. 登录页继续显示现有中文超时提示，但改为按 `HttpRequestError.code === 'timeout'` 判断，不再依赖旧英文错误文案。
- R6. 认证公开函数当前不接收外部 `AbortSignal`；本任务不新增该 API。共享边界的外部取消契约在 `http.spec.ts` 验证，认证超时导致的请求中止在认证 API 测试验证。

## Acceptance Criteria

- [ ] `frontend/src/api/auth.ts` 不再直接调用 `fetch`，不再创建定时器或 AbortController，也不保有独立错误解析函数。
- [ ] 五个认证公开函数的 URL、method、body、headers、10/15 秒超时、返回结构及 `/options` fallback 保持兼容。
- [ ] `/users/me` 继续透传 `X-Token-Refresh`，`frontend/src/queries/auth.ts` 无需修改即可更新 store token。
- [ ] 认证 API 测试覆盖成功、服务端 `detail`、无详情错误、非 2xx 的非 JSON/网络错误、超时中止、204、缺失 access token 和 options fallback。
- [ ] 共享 HTTP 测试覆盖外部取消并证明 `HttpRequestError.code === 'abort'`；既有 client/http 测试通过。
- [ ] 登录页超时用户提示保持为“登录请求超时，请确认后端服务已启动并可访问。”，不依赖错误文案字符串匹配。
- [ ] `npm run type-check` 与相关 Vitest 测试通过；独立复核确认没有新增 HTTP 抽象或认证流程变化。

## Out of Scope

- 改变 token 存储、登录/注册流程、401 全局策略、路由或后端认证接口。
- 为认证公开函数新增 `AbortSignal` 参数。
- 将认证 DTO 迁移到生成类型、重写整个前端 API 层或引入依赖。
- 修复父任务之外的现有测试失败或其他前端技术债。
