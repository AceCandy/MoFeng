# 实施计划

1. 读取配置、defaults、bootstrap 和注册开关调用链；枚举 `Field(env=...)` 全部使用点。
2. 用当前 Pydantic Settings 版本做最小 characterization，确认 alias 优先级和直接构造行为。
3. 先补失败测试，再修复 `allow_registration` canonical/兼容 alias。
4. 补 bootstrap 缺失/已有 key 回归测试，只有测试暴露偏差时才改实现。
5. 机械清理其余无效 `env=`，逐项确认非标准名称是否需要 alias。
6. 更新 backend quality guideline 的 Pydantic v2 配置约定。
7. 运行相关 pytest、ruff/Black focused checks，并独立复核 diff 和调用方。

回滚点：行为修复与机械清理分别检查 diff；任何字段解析行为不确定时停止清理该字段。
