# 收紧蓝图类型与请求边界

## Goal

让小说蓝图和概念对话链路复用后端生成的传输类型，在不改变现有 UI、兼容字段和请求行为的前提下，消除该链路的 `any` 扩散，并留下一个可运行的蓝图解析行为测试。

## Background

- `frontend/src/api/generated/schema.d.ts` 已生成 `Blueprint`、`BlueprintGenerationResponse`、`BlueprintPatch`、`ConverseRequest` 和 `ConverseResponse`，但 `frontend/src/api/novel.ts` 仍手写同名接口并使用 `any`。
- 后端 `Blueprint.characters`、`Blueprint.world_setting` 和概念对话状态本身是动态字典；生成类型正确地将其表示为 `Record<string, unknown>`，前端只能在 UI 边界窄化，不应伪造更精确的传输结构。
- `BlueprintDisplay.vue` 直接解析动态字段，并兼容多种历史/中英文字段别名；本次必须保持这些可见行为。
- `admin.ts` 当前存在 `AdminAPI.request -> adminRequest -> request -> authJson` 三层透传；其他领域 wrapper 携带不同超时、错误文案或运行时解码职责，不应为了统一而新增共享抽象。

## Requirements

1. `novel.ts` 必须通过生成 schema 的索引别名暴露蓝图、蓝图补丁和概念对话请求/响应类型，不再重复声明已由 OpenAPI 拥有的字段。
2. 小说 API 与 Vue Query mutation 的用户输入、对话状态、蓝图更新参数必须使用上述类型；未知动态字段保持 `unknown`，不得用断言恢复为 `any`。
3. `BlueprintDisplay.vue` 只消费经过单一领域工具窄化后的展示模型；现有世界观、角色字段别名、未知非空字符串字段、关系字段和默认文案行为保持不变。
4. 为蓝图解析工具增加一个聚焦行为测试，至少覆盖生成契约字段、历史字段别名、未知字符串字段、关系别名和畸形输入降级。
5. `admin.ts` 只移除自身的冗余透传层，并将请求泛型默认值收紧为 `unknown`；URL、20 秒超时、鉴权和错误文案保持不变。
6. 不修改后端 Pydantic schema、OpenAPI、生成文件或用户可见 UI。

## Out of Scope

- 清理前端其余 `any`。
- 合并 `novel.ts`、`tasks.ts`、`chapterWorkflow.ts` 等具有不同领域默认值的请求函数。
- 拆分 `BlueprintDisplay.vue`、`InspirationMode.vue` 或其他大型组件。
- 修改静态测试体系、CI、Docker、Python 依赖或后端大模块。

## Acceptance Criteria

- [x] `Blueprint`、`BlueprintGenerationResponse`、`BlueprintPatch`、`ConverseRequest`、`ConverseResponse` 由生成 schema 索引别名提供，相关 API/query 签名不含 `any`。
- [x] `BlueprintDisplay.vue` 的蓝图解析路径不含 `any`，且保持现有展示降级行为。
- [x] 新增的蓝图解析测试通过，并覆盖要求中的五类输入。
- [x] `admin.ts` 不再保留三层请求透传，且原有 URL、超时、错误消息行为不变。
- [x] `npm run type-check`、目标 Vitest、`npm run api:check` 通过。
- [x] diff 不包含后端、生成文件、UI 样式或无关格式化修改。

## Constraints

- 遵循 `.trellis/spec/frontend/type-safety.md`：动态传输字典保持 `unknown`，在一个领域工具中窄化。
- 遵循 `.trellis/spec/backend/transport-contracts.md`：不编辑生成文件，不重述已迁移 DTO。
- 采用最小变更，不创建通用请求工厂或中央类型目录。
