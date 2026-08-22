# 删除无引用 base.css 兼容壳

## Goal

删除已无入口或组件引用的 `frontend/src/assets/base.css` 兼容壳，避免维护者误判存在两套全局样式入口。

## Background

- 前端入口 `frontend/src/main.ts` 只导入 `assets/main.css`；HTML、Vite 配置、源码和测试均不引用目标文件。
- `frontend/src/assets/base.css` 仅含兼容说明，没有样式规则。
- `main.css` 导入的 `./styles/base.css` 是仍在生效的全局基础样式，与待删除文件不同，必须保持不变。
- 历史任务与设计文档会继续保留 `base.css` 作为历史事实；引用验收只排除失效的运行时和活跃规范引用。

## Requirements

- R1. 删除前复核源码、HTML、构建配置和测试中不存在目标文件的静态或动态引用。
- R2. 只删除无引用的 `base.css`，不迁移或重写其中样式。
- R3. 保持 `main.css` 入口和页面渲染行为不变。
- R4. 同步删除活跃前端规范中关于该兼容壳仍然存在的描述，不改写历史归档记录。

## Acceptance Criteria

- [x] `frontend/src/assets/base.css` 已删除，源码、HTML、构建配置和测试中不存在失效引用。
- [x] 活跃前端规范不再把已删除文件描述为现存兼容壳，历史任务记录保持不变。
- [x] 前端类型检查、单元测试、lint 与生产构建通过。
- [x] 关键页面样式入口仍为 `main.css`，无因删除产生的构建或运行时错误。
- [x] 除删除文件及必要的失效引用修正外无其他样式改动。

## Out of Scope

- 重构全局样式、设计 token、主题或组件视觉。
- 合并、格式化或清理 `main.css`。
- 修改 `frontend/src/assets/styles/base.css` 或历史归档文档。

## Notes

- 本任务是父任务最后一个子任务；完成后进入父任务跨任务集成复核。
