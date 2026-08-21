# 收敛认证 HTTP 客户端

## Goal

消除认证 API 自建的重复 fetch 边界，让它复用现有共享 HTTP 能力，同时保持所有认证行为和错误契约不变。

## Background

- `frontend/src/api/auth.ts` 当前自行处理 fetch、超时、AbortSignal 与错误解析。
- `frontend/src/api/http.ts` 和 `frontend/src/api/client.ts` 已存在共享请求与错误边界；本任务应复用现有能力，不再新增第三套封装。

## Requirements

- R1. 盘点登录、注册、刷新令牌及其他认证调用的请求、响应、超时、取消和错误行为。
- R2. 让认证 API 复用现有共享 HTTP 边界，删除被替代的重复实现。
- R3. 保持请求 URL、方法、payload、认证头、超时/取消语义和对外返回类型兼容。
- R4. 保持认证失败、非 JSON 响应和网络错误的用户可见行为，不吞掉服务端错误上下文。
- R5. 不新增 HTTP 客户端依赖或新的通用抽象。

## Acceptance Criteria

- [ ] 认证 API 不再保有独立的 fetch/超时/错误解析实现，且只复用现有共享边界。
- [ ] 登录、注册、刷新令牌及相关认证测试覆盖成功、业务错误、超时和取消契约并通过。
- [ ] 共享 HTTP 边界的既有调用方测试无回归。
- [ ] TypeScript 检查通过，认证 API 的公开类型和调用方式保持兼容。

## Out of Scope

- 改变认证流程、token 存储策略、刷新策略或后端认证接口。
- 重写整个前端 API 层或引入新依赖。

## Notes

- 本任务按父任务顺序在后端测试分层完成后启动；启动前根据调用链补齐复杂任务规划材料。
