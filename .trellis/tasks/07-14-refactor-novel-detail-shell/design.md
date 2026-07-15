# 拆 NovelDetailShell.vue（1662→<500）设计

## 现状（2026-07-15 起点）

- 路径：`frontend/src/components/shared/NovelDetailShell.vue`，**1662 行**。
- 结构分布：template L2-279（278 行）/ script L281-796（516 行）/ **style L798-1662（865 行，占 52%）**。
- 调用方：`NovelDetail.vue`（`:is-admin="false"`）、`AdminNovelDetail.vue`（`:is-admin="true"`）。两者都只传 `isAdmin` 一个 prop。
- **测试覆盖：无运行时行为测试**。仅有 2 个源码静态断言 spec：
  - `components/__tests__/uiAuditRegression.spec.ts`：L114/125-126（不含 `transition-all`/`transition: all`）、L134/148-149（不含 `background-clip: text`/`backdrop-filter`）、L296/302-303（含 `detail-shell__content-surface--classical`、不含 `detail-shell__content-surface--flat`）。
  - `components/shared/__tests__/novelDetailHeading.spec.ts`：不含 `<h1`；含 topbar 的 `<h2 class="detail-shell__title ...">`、`{{ formattedTitle }}`、`detail-shell__back-button`/`__write-button`/`__write-label-full`/`__write-label-compact`、overview-strip 的 `<h2>{{ formattedTitle }}</h2>`。
- 职责：小说详情外壳——section 动态分发（`sectionComponents[activeSection]` + 懒加载/预取）、蓝图字段编辑 Modal（`handleSectionEdit`/`handleSave` 经 `BlueprintEditModal`）、新增章节 Modal（`startAddChapter`/`saveNewChapter` 经 `updateBlueprintMutation`）、侧栏开关、写作台跳转（`goToWritingDesk`）、`isAdmin` 只读分支。

### 与 WDWorkspace/ChapterGenerating 的差异（约束）

- **无 mount 行为测试** → 等价性只能靠「逐字搬迁 + 三件套绿 + 源码静态断言指针跟随」。每 slice 迁移前必须 rg 确认被迁符号是否被上述 2 spec 断言。
- **style 占比 52%** → 砍行主力是「template + scoped style 整段迁入纯展示子组件」（WDWorkspace ChapterTabs/ChapterPipeline 范式），composable 只抽 script。
- scoped style 多为 `detail-shell__*` BEM 前缀相对独占，但 `:deep(.bg-...)`/`:deep(.rounded-*)`（L1623-1642）与 `.detail-shell:not(.detail-shell--embedded) ...`（L1647-1660）是跨元素/全局覆写，迁移时须留父或按 ChapterPipeline Slice 9 的「只读覆写」范式处理。

## 拆解 roadmap

每会话一块 slice（[[mofeng-audit-progress]] 既定节奏）。累计为目标 <500。

| Slice | 内容 | 类型 | 预估净减 | 累计 |
|---|---|---|---|---|
| **1** ✅ | `getSectionIcon` + 8 SVG → `novel-detail/sectionIcons.ts` | ts 纯数据 | −55 | **1607** |
| 2 | ShellDrawerNav 子组件（nav template + drawer/nav-item/nav-icon/nav-label style ~120） | 展示子组件 | ~150 | ~1458 |
| 3 | OverviewStrip 子组件（overview-strip template + overview/scroll/status/metric style ~256，computed 群 props 透传） | 展示子组件 | ~290 | ~1168 |
| 4 | `useShellSectionNavigation` composable（sectionLoaders/sectionComponents/prefetch/switchSection/loadSection/reloadSection/resolveInitialSection） | composable | ~80 | ~1088 |
| 5 | AddChapterDialog 子组件（modal template + state + saveNewChapter/startAddChapter/cancelNewChapter） | 子组件 | ~90 | ~998 |
| 6 | `useShellBlueprintEdit` composable（modal state + handleSectionEdit/handleSave/resolveSectionKey） | composable | ~55 | ~943 |
| 7 | `useShellOverview` composable（projectStatus/characterCount/chapterTotal/chapterCompleted/currentChapterLabel/foreshadowingOverview/overviewData/overviewMeta/formattedTitle） | composable | ~65 | ~878 |
| 8 | `useShellSectionContent` composable（componentProps/activeQuery/currentSectionResponse/currentSectionData/currentComponent/isSectionLoading/currentError/contentCardClass/componentContainerClass） | composable | ~75 | ~803 |
| 9 | ShellTopbar 子组件（topbar template + topbar style ~90，goBack/goToWritingDesk emit） | 展示子组件 | ~110 | ~693 |
| 10 | 剩余 style 分批收敛 + 杂项 | 混合 | ~200 | **<500** |

约 8-10 slice。各 slice 边界/契约在实施时补本文件对应小节。

## Slice 1 设计：抽 `sectionIcons.ts`（section 导航图标，2026-07-15）

### 边界

| 符号 | 原位置 | 去向 | 备注 |
|---|---|---|---|
| `getSectionIcon` | L391-444（函数 + 内部 `icons: Record<SectionKey, any>` + 8 个 `() => h('svg', ...)` 函数组件） | `novel-detail/sectionIcons.ts` 导出 | 逐字搬迁 |
| `SectionKey` 类型 | L308 `type SectionKey = AllSectionType` | ts 文件内复刻 `type SectionKey = AllSectionType`（从 `@/api/novel` import type） | 父保留自己的 SectionKey（多处使用） |

- 返回类型保留原 `any`（`icons[key]`）以零行为变化；template L117 `<component :is="getSectionIcon(section.key)" />` 不变。
- **无副作用、无 query/router 依赖**——纯静态 SVG 渲染函数映射。

### 契约

```ts
// frontend/src/components/novel-detail/sectionIcons.ts
import { h, type Component } from 'vue'
import type { AllSectionType } from '@/api/novel'

type SectionKey = AllSectionType

const sectionIcons: Record<SectionKey, any> = { /* 8 个 () => h('svg', ...) 逐字 */ }

export const getSectionIcon = (key: SectionKey) => sectionIcons[key]
```

父 `NovelDetailShell.vue`：删 L390-444（含注释 `// Section icons as functional components`），加 `import { getSectionIcon } from '@/components/novel-detail/sectionIcons'`。template 零改动。

### 测试指针跟随

- rg 确认 2 spec 对 NovelDetailShell 的断言均**不涉及** `getSectionIcon`/`sectionIcons`/section 图标 → **零指针重定向**。
- 无运行时测试 → 等价性靠逐字搬迁 + 三件套。

### 验证（实际，2026-07-15）

- 行数：1662 → **1607**（−55）。
- `vue-tsc --noEmit` exit 0。
- `vitest run` 21 files / 141 tests 全绿（uiAuditRegression + novelDetailHeading 源码断言不受影响——两者均不涉及 `getSectionIcon`/section 图标）。
- `eslint`：sectionIcons.ts **0 warning**（本地 `SectionKey` 字面量联合避开 `components/` no-restricted-imports `@/api` 规则；`AllSectionType = NovelSectionType(6) | AnalysisSectionType(2)` 共 8 字面量，与本地联合逐字匹配，未来加 key 时调用处类型报错强制同步）；NovelDetailShell.vue 仅预存 L290 `@/api/novel` type import warning（未新增）。
- 关键调整：`h` 从 `vue` import 删除（`getSectionIcon` 是 `h` 唯一消费者，迁出后 orphan）；`Component` 保留（L346 `AsyncSectionModule` 仍用）。
- 无运行时测试 → 等价性靠逐字搬迁 + 三件套绿 + 源码静态断言不涉及。
