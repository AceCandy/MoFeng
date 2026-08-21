# 认证 HTTP 边界盘点

## 现有认证契约

| 调用 | 请求 | 超时 | 关键响应/失败行为 |
| --- | --- | --- | --- |
| `getAuthOptions` | `GET /api/auth/options` | 10s | 任意失败返回 `{allow_registration: true, enable_linuxdo_login: false}` |
| `loginWithPassword` | `POST /api/auth/token`，`URLSearchParams` | 15s | 缺少 `access_token` 抛固定错误；返回 camelCase 登录结果 |
| `getCurrentUser` | `GET /api/auth/users/me`，显式 Bearer token | 10s | 归一化两个布尔字段；读取 `X-Token-Refresh` |
| `sendVerificationCode` | `POST /api/auth/send-code?email=<encoded>` | 15s | 204 返回 void |
| `registerUser` | `POST /api/auth/users`，JSON body | 15s | 204 返回 void |

证据：`frontend/src/api/auth.ts:37-175`。认证模块没有独立 refresh endpoint；`frontend/src/queries/auth.ts:31-47` 只在 `getCurrentUser` 返回 `refreshedToken` 时更新 store。

## 共享能力与取舍

- `requestRaw` 已拥有超时、外部 AbortSignal 绑定、HTTP payload 保存及 `HttpRequestError` 归一化：`frontend/src/api/http.ts:91-195`。
- `requestJson` 在 `requestRaw` 上处理 204/205 和成功 payload：`frontend/src/api/http.ts:197-204`。
- `authJson` / `authRaw` 从 Pinia store 注入 token，并在 401 时登出和跳转：`frontend/src/api/client.ts:6-49`。这不适合未认证的登录/注册调用，也不能替代 `/users/me` 的显式 token 参数，因此本任务不复用它们。
- `/users/me` 需要 Response header；为避免扩展 `requestJson` 返回类型，直接用现有 `requestRaw`，在认证模块读取成功 JSON 和刷新头。
- 当前认证公开函数不接受 `signal`，而旧 `authRequest` 还会覆盖 `RequestInit.signal`。不新增外部取消 API；只验证共享边界已有的取消契约。

## 调用方与可见错误

- `frontend/src/queries/auth.ts:31-94` 消费 `refreshedToken`，登录失败时清理 session/cache；公开返回结构不能变化。
- `frontend/src/views/Login.vue:177-195` 通过旧英文 `Request timed out` 文案识别超时。迁移后应改按 `HttpRequestError.code` 判断，保持页面中文提示不变。
- `frontend/src/views/Register.vue:301-365` 直接展示 `Error.message`；共享边界会保留 FastAPI `detail`，并为网络、非 2xx 的非 JSON 错误响应、超时和取消提供统一中文错误及上下文。

## 测试现状

- 当前没有 `auth.ts` 专属测试。
- `frontend/src/api/__tests__/http.spec.ts` 只覆盖 409 JSON payload。
- `frontend/src/api/__tests__/client.spec.ts` 覆盖 Authorization、401 登出跳转、非 401 透传和 raw response。

最小补充：新增一个 `auth.spec.ts` 覆盖五个公开函数的请求/响应与错误边界，并在 `http.spec.ts` 增加一条外部取消测试；不新增 queries 测试，因为 queries 契约不改。

## 适用规范

- `.trellis/spec/frontend/quality-guidelines.md`：所有请求走 `requestJson` / `requestRaw`，禁止重复 fetch wrapper。
- `.trellis/spec/frontend/type-safety.md`：strict TypeScript，不引入 `any`。
- `.trellis/spec/guides/code-reuse-thinking-guide.md`：已有 HTTP 边界必须复用，避免私有契约漂移。
