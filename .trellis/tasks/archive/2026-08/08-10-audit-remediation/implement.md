# 实施计划

1. 完成 A1：修复注册配置别名，验证 bootstrap 只补缺失值，并清理同文件无效
   `Field(env=...)` 元数据。
2. 完成 A2：引入浏览器绑定、Redis 一次性消费的 Linux.do OAuth state。
3. 后续分别创建并实施 Q1、R1、U1、D1、T1 子任务，不混入本轮 diff。
4. 所有子任务完成后执行总设计第 12、16 节的全量验收与独立集成复核。

每一步都以对应子任务的 focused tests 为回滚点；父任务不直接 `task.py start`。
