# 实施计划

1. 读取 router、AuthService、Redis 初始化、provider HTTP 和现有认证测试完整调用链。
2. 写 focused tests 固定 login state/cookie、callback 校验先后、重放/并发、Redis 故障、
   HTTPS 和现有注册行为。
3. 在 AuthService 中加入最小 state 创建/消费逻辑和授权 URL 构造，复用现有 Redis 客户端。
4. 修改 router 设置/删除 cookie，并保持现有成功 redirect/HTML 行为。
5. 更新环境示例和部署文档，只补 Linux.do 所需 Redis/HTTPS 契约。
6. 运行新增测试和受影响认证测试、focused ruff/Black，并独立做安全顺序复核。

回滚点：无数据库迁移；出现兼容问题时关闭 Linux.do 登录或回滚本子任务文件。
