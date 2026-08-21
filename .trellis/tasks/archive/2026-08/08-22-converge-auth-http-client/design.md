# 技术设计

## 变更边界

最小行为缺口是 `auth.ts` 绕过共享 HTTP 边界。行为归属在 `api/http.ts`，认证模块只应拥有认证路径、payload、显式 token、字段映射和刷新响应头。

预计修改：

- `frontend/src/api/auth.ts`：删除独立请求实现，改用 `requestJson` / `requestRaw`，同步 AIMETA。
- `frontend/src/views/Login.vue`：用 `HttpRequestError.code` 识别超时，保持现有页面提示。
- `frontend/src/api/__tests__/auth.spec.ts`：新增认证契约回归测试。
- `frontend/src/api/__tests__/http.spec.ts`：补共享外部取消契约测试。

不修改 `api/http.ts`、`api/client.ts`、`queries/auth.ts`、store 或后端。若实现必须扩展这些边界，退回规划，不自行扩大范围。

## 数据流

```text
Login/Register → queries/auth.ts → api/auth.ts
                                   ├─ requestJson：options/token/send-code/users
                                   └─ requestRaw：users/me → JSON + X-Token-Refresh
                                                        ↓
                                             queries/auth.ts 更新 store token
```

## 契约映射

- `/options`：`requestJson<AuthOptions>`，10 秒；保持全量 catch fallback。
- `/token`：`requestJson<LoginWireResult>`，15 秒，保留 URLSearchParams 和缺 token 校验。
- `/users/me`：`requestRaw`，显式 Authorization、10 秒；成功后读取 JSON 与 `X-Token-Refresh`，保留 `AuthRequestResult<AuthUser>`。
- `/send-code`、`/users`：`requestJson<void>`，显式传入 15 秒；共享层处理 204/205。
- HTTP fallback 传入“请求失败”，使无详情状态码文案保持“请求失败，状态码: N”。字符串 `detail` 仍由共享边界优先提取。

## 错误与兼容

- 底层错误类型统一为 `HttpRequestError`，保留 `status/code/url/payload`；不再把所有 AbortError 误报为 timeout。
- 登录页由类型化错误码识别 timeout，因此用户所见超时提示不变。
- 注册页继续展示 `Error.message`；服务端 `detail` 保持原文，网络、非 2xx 的非 JSON 错误响应和取消采用共享标准文案。成功响应仍遵守现有 JSON/204 后端契约。
- `authJson/authRaw` 的 store token 和 401 副作用不适用于本任务，禁止为减少一行代码而改变认证流程。
- 不新增 signal 参数；旧公开接口没有取消入口。共享取消能力通过 HTTP 单测验证。

## 回滚

产品改动集中在 `auth.ts`、`Login.vue` 和两处测试，可作为一个提交整体回滚。若契约测试发现无法在现有共享 API 上保持刷新头或错误语义，停止实现并回到规划，不扩展共享接口。
