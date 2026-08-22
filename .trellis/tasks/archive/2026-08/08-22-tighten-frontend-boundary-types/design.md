# 技术设计

## 变更边界

本任务修改清单中的 13 个原始 `any` 产品文件、metadata 类型变化暴露出的两个直接消费者和必要的聚焦测试。所有改动停留在现有定义处或首次读取外部值的位置，不新增共享目录、依赖或跨域抽象。

## 边界策略

### DOM 与异常

- `main.ts` 使用 `HTMLElement` 运行时判断识别 body/滚动元素，不再把任意 `EventTarget` 断言为元素。
- `useWritingDeskOptimize.ts` 的 catch 变量保持 `unknown`，仅对 `Error` 读取 message，否则沿用现有中文 fallback。

### JSON、API 与 trace metadata

- `parseEvaluationPayload` 返回 `Record<string, unknown> | null`，`JSON.parse` 的中间值显式为 `unknown`；保留当前对象/二次编码/失败回退行为。
- 优化 composable 在读取 `evaluation` 和版本评审前做对象守卫；`best_choice` 继续兼容合法字符串/数字，评审摘要继续生成字符串请求字段。
- 新增一个聚焦 composable 测试，复用现有 mutation mock 模式，锁定合法评审载荷生成的请求和 malformed 载荷的阻断行为。
- `TraceMetadata` 与 `ChapterVersion.metadata` 改为 `Record<string, unknown>`；`useVersionResolver.ts` 对嵌套 metadata 字典做局部对象收窄，`useChapterGenerationTrace.ts` 对摘要做字符串收窄，其余消费方沿用已有守卫。

### Novel-detail 数据流

数据路径保持：section/query 数据 → 展示组件 → `ShellContent` → `useShellBlueprintEdit` → 现有 `BlueprintEditModal` → `BlueprintPatch` mutation。

- 展示组件 emit 的动态 value 与 composable 缓存使用 `unknown`，与 `ShellContent` 现有契约对齐。
- `WorldSettingSection` 对 `world_setting`、列表 source 和列表 item 做本地对象/字符串检查，继续产出同一 `ListItem` UI 模型。
- `ChaptersSection` 将评审条目保持为 unknown 字典，读取展示字段时按实际使用形状收窄。
- `sectionIcons` 使用 Vue `Component` 类型。
- 不修改 `BlueprintEditModal` 的 runtime props/emits；它是下一子任务的明确边界。本任务不通过断言提前声称其内容已验证。

## 兼容性与取舍

- 合法后端数据和内部事件保持原请求字段、排序、展示和保存路径。
- 非法外部形状从“任意属性访问”收敛为现有空值/默认提示，不新增用户流程。
- 不抽取全局 `isRecord`：当前守卫短小且分别属于评审、trace、world-setting 三个不同边界，共享抽象会扩大耦合。
- 不复用 `ChapterEvaluationPanel` 的私有完整 decoder：优化流程只消费三个字段，迁移完整 UI decoder 会扩大本任务。

## 回滚

不涉及数据、artifact 或依赖，可按单提交回滚。若 `unknown` 传播迫使修改遗留编辑器契约、生成 schema 或用户可见行为，则停止并返回规划，不用断言绕过。
