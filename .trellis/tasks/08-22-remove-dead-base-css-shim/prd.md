# 删除无引用 base.css 兼容壳

## Goal

删除已无入口或组件引用的 `frontend/src/assets/base.css` 兼容壳，避免维护者误判存在两套全局样式入口。

## Background

- 前端入口当前只导入 `assets/main.css`，已确认 `base.css` 是无引用兼容壳。
- 这是纯删除任务，只有在实施时再次确认无静态和动态引用后才可执行。

## Requirements

- R1. 删除前复核源码、构建配置、测试与文档中不存在 `base.css` 引用。
- R2. 只删除无引用的 `base.css`，不迁移或重写其中样式。
- R3. 保持 `main.css` 入口和页面渲染行为不变。

## Acceptance Criteria

- [ ] `base.css` 已删除，仓库中不存在失效引用。
- [ ] 前端 TypeScript/静态检查与生产构建通过。
- [ ] 关键页面样式入口仍为 `main.css`，无因删除产生的构建或运行时错误。
- [ ] 除删除文件及必要的失效引用修正外无其他样式改动。

## Out of Scope

- 重构全局样式、设计 token、主题或组件视觉。
- 合并、格式化或清理 `main.css`。

## Notes

- 本任务是父任务最后一个子任务；完成后进入父任务跨任务集成复核。
