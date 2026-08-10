# Linux.do OAuth state

## Goal

为 Linux.do OAuth 增加与发起浏览器绑定、可过期且原子一次性消费的 state，在任何 state
校验失败时阻止上游 token exchange，并在多 worker 部署下保持一致安全语义。

## Requirements

- state 使用至少 256 bit 随机性，TTL 固定 300 秒；Redis key 只包含 state 的 SHA-256。
- 登录时用 Redis `SET NX EX` 创建 state，回调时用 Redis 6.2+ `GETDEL` 原子消费。
- 同步 Redis 初始化和命令必须通过 `asyncio.to_thread`，不得阻塞事件循环。
- 查询 state 必须与 HostOnly、HttpOnly、SameSite=Lax 的浏览器 cookie 使用
  `compare_digest` 匹配；cookie path 为 `/api/auth/linuxdo`，Secure 由 redirect URI 决定。
- production 环境拒绝非 HTTPS redirect URI。
- 缺失、错误、过期、重放统一返回 400 且清理 cookie；Redis 不可用或不支持 `GETDEL`
  返回 503，不得降级到进程内字典。
- state 验证和消费必须先于任何 provider HTTP 请求，不记录敏感 OAuth 值。
- 保持 OAuth 开关、现有用户绑定、注册开关和唯一约束行为不变。

## Out Of Scope

- 不新增数据库表、repository、migration、会话框架或进程内 fallback。
- 不修改密码登录或邮箱验证码状态存储策略。

## Acceptance Criteria

- [x] 正常 state/cookie 只允许一次 token exchange，重放与并发回调最多一个成功。
- [x] 缺 query state、缺 cookie、二者不同或 state 过期均为 400，且不调用 provider。
- [x] Redis 未配置、连接失败或不支持 `GETDEL` 为 503，不生成不可验证的授权请求。
- [x] production HTTP redirect URI 被拒绝；本地 HTTP 可设置 `Secure=false`。
- [x] OAuth 关闭仍为 404；注册关闭只阻止不存在的 external user，已有用户仍可登录。
- [x] 示例环境和部署文档说明 Redis 6.2+、TTL、cookie/HTTPS 前置条件。
