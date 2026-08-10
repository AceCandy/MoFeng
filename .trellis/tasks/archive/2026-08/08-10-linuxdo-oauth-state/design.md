# 技术设计

## Request Flow

```text
GET /linuxdo/login
  -> service 校验开关、provider 配置、redirect URI
  -> token_urlsafe(32)
  -> to_thread(Redis SET hash(state) 1 NX EX 300)
  -> RedirectResponse 设置 state cookie

GET /linuxdo/register?code=&state=
  -> router 读取 query/cookie
  -> service compare_digest
  -> to_thread(Redis GETDEL hash(state))
  -> 仅消费成功后请求 provider token/user-info
  -> 成功或失败响应均删除 state cookie
```

## Boundaries

- `AuthService.create_linuxdo_authorization()` 返回授权 URL、state 和由 redirect URI 推导的
  cookie `secure` 标志，拥有 provider URL、安全配置和 state 创建。
- `AuthService._consume_linuxdo_state()` 拥有 Redis key、原子消费和安全失败语义。
- `handle_linuxdo_callback(code, state, browser_state)` 固定校验顺序，保留现有用户处理逻辑。
- router 只管理 cookie/response，并把无效 state 映射为统一 400、基础设施故障映射为 503。

## Compatibility And Operations

- 使用现有同步 Redis 客户端和标准库，不新增依赖。
- Redis server 6.2+ 是启用 Linux.do 的部署前置条件。
- 可通过 `ENABLE_LINUXDO_LOGIN=false` 回滚；无持久化 schema 变更。
- 同一浏览器连续发起两次登录时后一个 cookie 胜出，较早 callback 安全失败。
