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
| **2** ✅ | ShellDrawerNav 子组件（aside drawer+nav+backdrop template + drawer/nav-item/nav-icon/nav-label style + @media sticky） | 展示子组件 | −181 | **1426** |
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

## Slice 2 设计：抽 `ShellDrawerNav.vue`（导航抽屉，2026-07-15）

### 边界

| 符号 | 原位置 | 去向 | 备注 |
|---|---|---|---|
| `<aside class="detail-shell__drawer">` + nav + backdrop transition | template L94-137 | `novel-detail/ShellDrawerNav.vue` template | 逐字搬迁；状态改 props、事件改 emits |
| `.detail-shell__drawer`/`.is-open`/`-backdrop`/`__nav`/`__nav-item` 全系/`__nav-icon`/`__nav-label` | style L1135-1270 | 子组件 scoped | 逐字搬迁 |
| `.detail-shell__drawer` @media 1200px sticky | style L1364-1372 | 子组件 scoped | drawer 自身布局 |
| `.detail-shell--drawer-collapsed .detail-shell__drawer` | style L1374-1381 | **留父** | 依赖父根 class，靠子根继承 scope id 命中 |
| `:not(--embedded) .detail-shell__drawer` | style L1602-1605 | **留父** | 同上 |
| `getSectionIcon` import | L302 | **删**（orphan） | drawer 迁出后父无引用；子组件自行 import |
| drawer-toggle（顶栏按钮+样式） | L12-25 / L765-840 | **留父** | 属顶栏，Slice 9 才动 |

### 契约

```vue
<ShellDrawerNav
  :sections="sections"
  :active-section="activeSection"
  :is-open="isSidebarOpen"
  :is-desktop="isDesktopViewport"
  @switch="switchSection"
  @prefetch="prefetchSectionComponent"
  @close="closeSidebar"
/>
```

子组件 `defineProps<{ sections; activeSection: SectionKey; isOpen; isDesktop }>()` + `defineEmits<{ switch(key); prefetch(key); close() }>()`。`SectionKey` 从 `sectionIcons.ts` 复用（本 slice 新增 `export type SectionKey`，DRY，避免父子三处重复联合）。

### scoped 跨组件处理（关键）

drawer 作为子组件根（fragment：`<aside>` + `<transition>` → backdrop `<div>`），根元素继承父 scope id。故两条依赖父根 class 的规则**留父**即可命中子根：

- `.detail-shell--drawer-collapsed .detail-shell__drawer`（折叠时 drawer 缩进）
- `.detail-shell:not(.detail-shell--embedded) .detail-shell__drawer`（非嵌入态全高）

未用 `:deep()`（同 ChapterPipeline Slice 9 范式）。

### 测试指针跟随

- rg 确认 uiAuditRegression（transition-all/background-clip/classical/flat）+ novelDetailHeading（h1/h2/topbar/back/write/overview-strip）2 spec 均**不涉及** drawer/nav → **零指针重定向**。
- 无运行时测试 → 等价性靠逐字搬迁 + 三件套。

### 验证（实际，2026-07-15）

- 行数：1607 → **1426**（−181；优于 roadmap 预估 ~1458）。ShellDrawerNav.vue 214 行（新）。
- `vue-tsc --noEmit` exit 0（ShellDrawerNav 本地 SectionKey 与父 AllSectionType 8 字面量结构兼容）。
- `vitest run` 21 files / 141 tests 全绿。
- `eslint`：ShellDrawerNav.vue / sectionIcons.ts **0 warning**；NovelDetailShell.vue 仅预存 L256 `@/api/novel` type import warning（原 L290，删行前移，未新增）。
- 关键清理：`getSectionIcon` import 删除（drawer 迁出后父无引用，orphan）；drawer-toggle 顶栏按钮 + 样式留父（Slice 9）。
