# 收紧蓝图类型与请求边界：实施计划

1. 收紧传输类型
   - 将 `novel.ts` 的手写蓝图/概念对话类型替换为 generated schema 索引别名。
   - 使用 `ConverseRequest` 派生用户输入、对话状态参数，使用 `BlueprintPatch` 约束更新。
   - 更新 `queries/novel.ts` mutation variables。
   - 更新 `useShellBlueprintEdit.ts`，在现有字段路由处构造 typed `BlueprintPatch`。
   - 验证：相关 API/query 签名无 `any`，`npm run type-check` 能定位全部调用方。

2. 提取并接入蓝图解析
   - 新增 `utils/blueprint.ts`，迁移 `BlueprintDisplay.vue` 当前世界观、角色和关系解析逻辑。
   - 组件改为调用纯函数，不改变模板和样式。
   - 新增一个 `blueprint.spec.ts`，覆盖 canonical、历史别名、未知字段、关系别名、畸形输入。
   - 验证：运行目标 Vitest，人工对照原解析顺序和默认文案。

3. 删除 admin 冗余透传
   - 将 `AdminAPI` 私有请求方法直接接到 `authJson`。
   - 删除模块级 `request`、`adminRequest`，默认泛型改为 `unknown`。
   - 验证：现有显式返回类型全部通过 type-check；URL、timeout 和 fallback 原样保留。

4. 质量门禁与独立复核
   - 运行目标 Vitest、`npm run type-check`、`npm run api:check`。
   - 检查 `git diff --check`、目标文件中的 `any`、生成文件与后端是否未变化。
   - 独立复核传输类型所有权、历史兼容行为和无关 diff。

## 风险与回滚点

- 角色历史字段兼容是最高风险点；解析迁移后先运行聚焦测试，再继续请求层清理。
- `request<T = unknown>` 可能暴露遗漏的返回类型；应补真实返回类型，不得改回 `any`。
- 任一步出现超出既定范围的调用方连锁修改时，停止并缩小到 generated alias 与当前组件边界。
