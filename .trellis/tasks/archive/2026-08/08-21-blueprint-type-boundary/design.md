# 收紧蓝图类型与请求边界：技术设计

## 边界与所有权

```text
Pydantic / OpenAPI
  -> generated/schema.d.ts（唯一传输类型所有者）
  -> api/novel.ts（可读索引别名与请求方法）
  -> queries/novel.ts（typed mutation variables）
  -> composables/useShellBlueprintEdit.ts（typed BlueprintPatch 构造）
  -> utils/blueprint.ts（动态字典一次窄化）
  -> BlueprintDisplay.vue（只渲染展示模型）
```

生成 schema 保持只读。`api/novel.ts` 仅导出索引别名，不复制字段。动态的 `characters`、`world_setting`、`conversation_state` 保持 `Record<string, unknown>`。

## 蓝图解析

新增一个领域纯函数模块，将生成的 `Blueprint` 转成组件需要的展示模型：

- 世界观只读取 `core_rules`、`key_locations`、`factions`，类型不匹配时使用现有空值。
- 角色继续支持当前中英文别名和未知非空字符串字段。
- 关系继续支持 canonical `character_from/character_to` 和历史 `source/target`。
- 解析函数不修改原输入，不改变排序和默认文案。

该模块只服务于现有复杂解析与可运行测试，不引入接口、类或可配置映射系统。

## 请求边界

- `novel.ts` 的本地 `request` 仍保留，因为它承载小说领域的 60 秒默认超时和错误消息；只将默认泛型改为 `unknown`。
- `tasks.ts` 和 `chapterWorkflow.ts` 的 wrapper 不改，它们分别承载领域默认值和运行时 decoder。
- `admin.ts` 将三层透传折叠为 `AdminAPI` 内一个私有方法，直接调用 `authJson`，保留原 URL、20 秒超时和错误文案。
- `useShellBlueprintEdit.ts` 只允许当前后端 `BlueprintPatch` 支持的六个顶层字段，并继续合并 `world_setting.*` 子字段。

## 兼容性与回滚

不修改后端或 wire shape，无数据迁移。回滚仅需恢复前端类型别名、组件内解析和 admin 请求方法。新解析测试用于证明历史字段兼容未丢失。

## 取舍

- 不把后端动态字典伪装成完整角色接口；这会制造错误契约。
- 不创建共享 HTTP factory；各领域默认行为并不相同，新增抽象的收益低于维护成本。
- 不挂载 1000 行组件做测试；纯函数测试更小、更稳定，且直接覆盖本次非平凡逻辑。
