# Technical Design

## Boundary

只修改前端现有查询、工作流快照和写作台调用时机。复用 TanStack Vue Query 的精确失效与动态 `refetchInterval`，不改变 API 合同。

## Data Flow Changes

1. `refreshProjectQueries` 对项目详情使用 `exact: true`，项目列表刷新保持不变。
2. 工作流 actor 将第一份已接受快照保存为基线；后续修订号或业务边界增加时才执行现有刷新端口。
3. AppShell watch 首次运行只填充已完成任务 ID 集合，后续新增成功任务沿用现有失效逻辑。
4. `useTasksQuery` 根据现有 SSE 活跃状态返回 `false` 或 `15_000`；不新增计时器。
5. 写作台在本地章节号未变化时跳过上下文 PATCH。
6. 删除阅读器挂载时的 TTS 配置预取，复用播放路径已有的 `refreshTTSConfig`。

## Compatibility and Rollback

- API、路由、缓存键结构和组件公开接口不变。
- 每项改动可按文件独立回滚。
- SSE 断线兜底通过动态轮询保留。
