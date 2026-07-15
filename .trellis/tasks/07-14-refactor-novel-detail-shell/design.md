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
| **3** ✅ | OverviewStrip 子组件（overview-strip template + overview/scroll/status/metric/kicker style + 4 @media 响应式，computed 群 props 透传） | 展示子组件 | −362 | **1064** |
| **4** ✅ | `useShellSectionNavigation` composable（sections/sectionLoaders/sectionComponents/resolveInitialSection/isNovelSectionKey/prefetch·switch·load·reloadSection + overview·sectionQuery，activeNovelSection 内部） | composable | −90 | **974** |
| **5** ✅ | AddChapterDialog 子组件（modal template + 表单 state + useDialogA11y + md-scale-\* scoped；父留 startAddChapter/saveNewChapter 重副作用 + isAddChapterModalOpen） | 子组件 | −79 | **895** |
| **6** ✅ | `useShellBlueprintEdit` composable（modal state + handleSectionEdit/handleSave/resolveSectionKey；父透传 isAdmin/novel/ensureProjectLoaded/updateBlueprintMutation/loadSection） | composable | −46 | **849** |
| **7** ✅ | `useShellOverview` composable（projectStatus/characterCount/chapterTotal/chapterCompleted/currentChapterLabel/foreshadowingOverview/overviewData/overviewMeta/formattedTitle；父透传 novel/foreshadowingQuery/overviewQuery） | composable | −34 | **815** |
| **8** ✅ | `useShellSectionContent` composable（componentProps/activeQuery/currentSectionResponse/currentSectionData/currentComponent/isSectionLoading/currentError/contentCardClass/componentContainerClass；父透传 navigation/novel/characterCount/chapterTotal/isAdmin） | composable | −60 | **755** |
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

## Slice 3 设计：抽 `OverviewStrip.vue`（小说概览长卷，2026-07-15）

### 边界

| 符号 | 原位置 | 去向 | 备注 |
|---|---|---|---|
| `<section class="detail-shell__overview-strip">` + scroll-main/scroll-metrics 全系 | template L44-90（`v-if="isAdmin"`） | `novel-detail/OverviewStrip.vue` template | 逐字搬迁；`v-if="isAdmin"` 上提到父组件的 `<OverviewStrip>` 标签 |
| `.detail-shell__overview-strip`/`__overview-scroll`/`__scroll-main`/`__scroll-header`/`__kicker`/`__scroll-main h2`/`__scroll-desc`/`__scroll-status`/`__status-pill`全系/`__status-meta`/`__scroll-time`/`__scroll-metrics`/`__scroll-metric`全系/`is-alert` | style 主块 L843-977 + L1007-1099 | 子组件 scoped | 逐字搬迁 |
| 4 个 @media 内的 overview/scroll 规则 | style @media L1203-1205/L1222-1234/L1243-1249/L1268-1280/L1313-1367 | 子组件 scoped（按 media query 重组） | **必须随迁**：父 scoped 选择器匹配不到子组件内部元素 |
| @media 内 `.detail-shell` 根变量覆写（`--detail-shell-overview-height`/`--detail-shell-outer-gap`）+ `.detail-shell__content-wrap`/`__body`/`__content-surface` + drawer-collapsed + topbar 系 | style @media | **留父** | 针对父根或顶栏/内容区，非 overview |
| `.detail-shell__action-btn`（L980-1005） | style | **留父**（不动） | 预存死代码（模板无引用，非本次 orphan）；按规约仅 mention 不删 |
| `formatDateTime` import | L263 | **删**（orphan） | overview 迁出后父无引用；子组件自行 import |
| computed 群（projectStatus/characterCount/chapterTotal/chapterCompleted/currentChapterLabel/foreshadowingOverview/overviewData/overviewMeta/formattedTitle） | script | **留父**（Slice 7 才抽 composable） | 本 slice 仅 props 透传，不搬逻辑 |

### 契约

```vue
<OverviewStrip
  v-if="isAdmin"
  :title="formattedTitle"
  :summary="overviewData?.one_sentence_summary"
  :status="projectStatus"
  :current-chapter-label="currentChapterLabel"
  :updated-at="overviewMeta.updated_at"
  :character-count="characterCount"
  :chapter-completed="chapterCompleted"
  :chapter-total="chapterTotal"
  :foreshadowing-overdue="foreshadowingOverview.overdue"
/>
```

子组件 `defineProps<{ title; summary?; status: { label; tone: 'done'|'active'|'draft' }; currentChapterLabel; updatedAt?; characterCount; chapterCompleted; chapterTotal; foreshadowingOverdue }>()`，无 emits。`summary` 默认值 `|| '从侧边分区查看...'` 留在子模板（展示关注点内聚）。

### scoped 跨组件处理（关键）

- **overview/scroll/status/metric 规则全部迁子，无 :deep**：父 scoped 选择器只命中子组件**根**（继承父 scope id），命中不了子组件**内部元素**（如 `.detail-shell__scroll-metric`）。故这些规则必须在子组件 scoped 内。父迁出后无任何 `.detail-shell__overview-*`/`.detail-shell__scroll-*` 残留（rg EXIT=1 证实），无跨组件依赖。
- **CSS 变量经 DOM 继承**：`--detail-shell-overview-height` 设在父根 `.detail-shell`（含 @media 覆写，留父），子组件 `.detail-shell__overview-scroll { height: var(--detail-shell-overview-height) }` 作为 DOM 后代自动继承取值，无需 :deep/透传。
- 与 Slice 2 区别：Slice 2 是「依赖父根 class 的规则留父靠子根继承」；Slice 3 是「子内部元素规则全迁子」——因 overview 类无父根依赖，更干净。

### 测试指针跟随

- `novelDetailHeading.spec.ts` L23 断言 `<h2>{{ formattedTitle }}</h2>`（原 overview-strip h2）→ 迁子后变 `<h2>{{ title }}</h2>`。**重定向**：改为读 `OverviewStrip.vue` 源码断言 `<h2>{{ title }}</h2>`（注释说明由父 `:title="formattedTitle"` 传入）。L18 `{{ formattedTitle }}` 仍命中父 topbar L30 + OverviewStrip 绑定，不受影响。
- `uiAuditRegression.spec.ts`（transition-all/background-clip/classical/flat）不涉及 overview/scroll 类 → 零指针。

### 验证（实际，2026-07-15）

- 行数：1426 → **1064**（−362；远优于 roadmap 预估 ~290，因 4 个 @media 的 overview 规则一并迁出）。OverviewStrip.vue 404 行（新）。
- `vue-tsc --noEmit` exit 0（props 类型与父 computed 联合兼容）。
- `vitest run` 21 files / 141 tests 全绿（含重定向后的 novelDetailHeading）。
- `eslint`：OverviewStrip.vue / novelDetailHeading.spec.ts **0 warning**；NovelDetailShell.vue 仅预存 L221 `@/api/novel` type import warning（原 L256，删行前移，未新增）。
- 关键清理：`formatDateTime` import 删除（overview 迁出后父无引用，orphan）；`.detail-shell__action-btn` 预存死代码留父（仅 mention）。

## Slice 4 设计：抽 `useShellSectionNavigation.ts`（分区导航状态机，2026-07-15）

### 边界

| 符号 | 原位置 | 去向 | 备注 |
|---|---|---|---|
| `sections`/`sectionKeys`/`resolveInitialSection`/`initialSection` | L257-276 | composable | sectionKeys/resolveInitialSection/initialSection 内部用，不返回 |
| `AsyncSectionModule`/`sectionLoaders`/`sectionComponents` | L278-293 | composable | sectionComponents **返回**（currentComponent 消费） |
| `prefetchedSections`/`prefetchInFlight`/`prefetchSectionComponent` | L295-320 | composable | 内部状态；prefetchSectionComponent **返回**（ShellDrawerNav @prefetch） |
| `isNovelSectionKey` | L322-323 | composable | **返回**（父 currentSectionResponse/isSectionLoading/currentError 仍消费） |
| `activeSection`/`activeNovelSection` | L325-328 | composable | activeSection **返回**（多处消费）；activeNovelSection 仅驱动 sectionQuery，**内部不返回** |
| `overviewQuery`/`sectionQuery` | L329-334 | composable | **返回**（父 activeQuery/currentSectionResponse/overviewData 消费） |
| `loadSection`/`reloadSection`/`switchSection` | L441-467 | composable | **返回**（handleSave/saveNewChapter/template 消费） |
| `onMounted` prefetch | L650-652 | composable 内 onMounted | 父 onMounted 删除 |
| `toggleSidebar`/`closeSidebar` | L433-439 | **留父，上移**到 isSidebarOpen 后 | 侧栏 UI 状态归父；上移以让 onAfterSwitch 回调引用时已定义 |

### 契约

```ts
useShellSectionNavigation({
  projectId: string
  isAdmin: () => boolean        // 透传给 useNovelSectionQuery 第三参数
  onAfterSwitch?: () => void    // switchSection 末尾调用（父用于非桌面态收侧栏）
})
→ { sections, activeSection, sectionComponents, isNovelSectionKey, overviewQuery, sectionQuery,
    switchSection, prefetchSectionComponent, loadSection, reloadSection }
```

### TDZ / 接线处理（关键）

- **const TDZ 顺序约束**：`activeSection`/`overviewQuery`/`sectionQuery` 从 composable 解构后被 L343 起 `activeQuery` 等 computed 消费 → composable 调用点必须在 L343 之前；但原 `switchSection`(L461) 依赖 `closeSidebar`(L437)，若直传 closeSidebar 作入参会在其定义前求值。
- **解法**：① `toggleSidebar`/`closeSidebar` 上移到 `isSidebarOpen` 紧邻处，定义先于 composable 调用；② 关侧栏副作用改用 `onAfterSwitch` 箭头函数回调，composable 内 `switchSection` 末尾 `onAfterSwitch?.()`。composable 不持有侧栏状态，保持内聚。
- eslint 无 `no-use-before-define` 规则，零告警；`onAfterSwitch` 闭包引用的 closeSidebar/isDesktopViewport 均已在前定义。

### 测试指针跟随

- `novelDetailHeading.spec.ts`（h2/topbar/back/write/overview-strip）+ `uiAuditRegression.spec.ts`（transition-all/background-clip/classical/flat）2 spec 均**不涉及** section navigation 符号 → **零指针重定向**。
- 无运行时测试 → 等价性靠逐字搬迁 + 三件套绿 + diff 复核。

### 验证（实际，2026-07-15）

- 行数：1064 → **974**（−90）。useShellSectionNavigation.ts 161 行（新）。
- `vue-tsc --noEmit` exit 0（返回类型流转 + isNovelSectionKey 类型守卫跨 composable 边界保留）。
- `vitest run` 21 files / 141 tests 全绿（零指针重定向）。
- `eslint`：useShellSectionNavigation.ts **0 warning**（composables/ 不受 components/views 的 `@/api` no-restricted-imports 限制）；NovelDetailShell.vue 仅预存 L220 `@/api/novel` type import warning（原 L221，删 NovelSectionType 前移 1 行，未新增）。
- 关键清理：父删 `defineAsyncComponent`/`onMounted`/`Component`(vue)、`useNovelSectionQuery`(queries)、`NovelSectionType`(api type) 五个 orphan import；`activeNovelSection` 不返回（仅 sectionQuery 内部驱动）。
- 行为等价：`onMounted(async () => prefetch...)` → composable 内 `onMounted(() => prefetch...)`（去 async 无 await，等价）；`switchSection` 关侧栏逻辑经 onAfterSwitch 回调逐字保留。

## Slice 5 设计：抽 `AddChapterDialog.vue`（新增章节 Modal，2026-07-15）

### 边界

| 符号 | 原位置 | 去向 | 备注 |
|---|---|---|---|
| `<transition md-scale-*>` + modal template（overlay/dialog/header/content/actions） | template L148-208 | `novel-detail/AddChapterDialog.vue` template | 逐字搬迁；v-if/refs/v-model 重命名 |
| `addChapterDialogRef`/`addChapterCancelButtonRef`/`addChapterDialogTitleId`/`newChapterTitle`/`newChapterSummary` | state L293-298 | 子组件 dialogRef/cancelButtonRef/dialogTitleId/title/summary | 逐字搬迁（重命名） |
| `useDialogA11y` 调用块 | L524-529 | 子组件 | `active: toRef(props,'isOpen')` 范式（同 BlueprintEditModal/CustomAlert/WDEvaluationDetailModal） |
| `md-scale-*` scoped 定义（250ms cubic-bezier） | style L918-930 | 子组件 scoped | **随迁**：父 scoped 覆写全局 main.css:2344，modal 是父唯一 md-scale 用法 |
| `useDialogA11y` import | L229 | **删**（orphan） | 迁子后父无调用 |
| `isAddChapterModalOpen` | state | **留父** | 开关归父（startAddChapter/saveNewChapter/cancelNewChapter 控制） |
| `startAddChapter`/`saveNewChapter`/`cancelNewChapter` | L509-562 | **留父** | 重副作用（ensureProjectLoaded/updateBlueprintMutation/loadSection）；saveNewChapter 改签名接收 payload |
| `newChapterInitialTitle`（新） | state | 父 | 传子组件 `:initial-title` prop（startAddChapter 计算的「新章节 N」） |

### 契约

```vue
<AddChapterDialog
  v-if="!isAdmin"
  :is-open="isAddChapterModalOpen"
  :initial-title="newChapterInitialTitle"
  @cancel="cancelNewChapter"
  @confirm="saveNewChapter"
/>
```

子组件 `defineProps<{ isOpen: boolean; initialTitle?: string }>()` + `defineEmits<{ cancel: []; confirm: [payload: { title: string; summary: string }] }>()`。表单 title/summary 在子组件内部 ref，打开时 watch isOpen 重置（title=initialTitle, summary=''），与原父 startAddChapter 设值等价。saveNewChapter 改 `(payload) => void`，trim/title/summary 取自 payload。

### transition / scoped 处理（关键）

- `md-scale-*` 父 scoped 定义（250ms cubic-bezier）**覆写**全局 main.css:2344（`var(--md-duration-medium) var(--md-easing-emphasized)`，值不同）。modal 是父组件里唯一用 md-scale-\* 处，迁子后该 scoped 定义成 orphan，**随迁入子组件 scoped**（子组件 transition 元素带子 scope id，命中子 scoped 的 250ms 定义，行为与原父完全一致；不依赖全局兜底）。
- 其余 modal class（`md-dialog-overlay`/`md-dialog`/`md-dialog-header`/`md-dialog-title`/`md-dialog-content`/`md-dialog-actions`/`md-text-field*`/`md-textarea`/`md-btn*`）均来自全局 main.css，子组件直接用，无需迁样式。
- 与 Slice 2/3 区别：本 slice 无 `detail-shell__*` 类参与（modal 用全局 md-\* class），故无父 scoped 跨组件依赖，子组件 scoped 只含 md-scale-\* 覆写。

### 测试指针跟随

- rg 确认 uiAuditRegression（transition-all/background-clip/classical/flat）+ novelDetailHeading（h1/h2/topbar/back/write/overview-strip）2 spec 均**不涉及** addChapter/NewChapter/md-scale → **零指针重定向**。
- 无运行时测试 → 等价性靠逐字搬迁 + 三件套绿 + diff 复核。

### 验证（实际，2026-07-15）

- 行数：974 → **895**（−79；roadmap 预估 ~90，略少）。AddChapterDialog.vue 130 行（新）。
- `vue-tsc --noEmit` exit 0（emit payload 类型 + saveNewChapter 签名 + AddChapterDialog props 全通过）。
- `vitest run` 21 files / 141 tests 全绿（零指针重定向）。
- `eslint`：AddChapterDialog.vue **0 warning**（不 import @/api，不受 components/ no-restricted-imports 限制）；NovelDetailShell.vue 仅预存 L167 `@/api/novel` type import warning（原 L220，本 slice 删行前移，未新增）。
- 关键清理：父删 `useDialogA11y` import + `md-scale-*` scoped 定义（迁子后 orphan）；5 个 add-chapter state ref/id 迁子；`newChapterTitle.value`/`newChapterSummary.value` → `newChapterInitialTitle.value`/payload。
- 行为等价：表单 state 从父 ref → 子组件 ref，值经 emit payload 流转；表单重置从 startAddChapter 同步设值 → 子组件 watch isOpen 打开时重置（时序等价：startAddChapter 同步设 initialTitle + isOpen=true，下个 tick watch 触发）；useDialogA11y `active: toRef(props,'isOpen')` 等价原 `isAddChapterModalOpen`，onClose 链路 handleCancel→emit cancel→父 cancelNewChapter。

## Slice 6 设计：抽 `useShellBlueprintEdit.ts`（蓝图字段编辑状态机，2026-07-15）

### 边界

| 符号 | 原位置 | 去向 | 备注 |
|---|---|---|---|
| `isModalOpen`/`modalTitle`/`modalContent`/`modalField` | state L233-237 | composable | **返回**（template BlueprintEditModal `:show`/`:title`/`:content`/`:field` + `@close` 消费） |
| `handleSectionEdit` | L402-408 | composable | **返回**（component `@edit` 消费）；`props.isAdmin` → `isAdmin()` |
| `resolveSectionKey` | L410-416 | composable | **内部不返回**（仅 handleSave 用） |
| `handleSave` | L418-450 | composable | **返回**（BlueprintEditModal `@save` 消费）；`props.isAdmin` → `isAdmin()`；ensureProjectLoaded/novel/updateBlueprintMutation/loadSection 经入参透传 |

### 契约

```ts
useShellBlueprintEdit({
  isAdmin: () => boolean,
  novel: Ref<NovelProject | null>,
  ensureProjectLoaded: () => Promise<void>,
  updateBlueprintMutation: ReturnType<typeof useUpdateBlueprintMutation>,
  loadSection: (section: SectionKey, force?: boolean) => Promise<void>,
})
→ { isModalOpen, modalTitle, modalContent, modalField, handleSectionEdit, handleSave }
```

### TDZ / 接线处理（关键）

- handleSave 依赖 ensureProjectLoaded/novel，二者原本在 Modal state（L233）之后定义（novel L242 / ensureProjectLoaded L320）。若 composable 调用留在原 Modal state 位置（L233）会引用未定义符号（const TDZ）。
- **解法**：composable 调用点下移到 ensureProjectLoaded（L322）之后；此时 novel(L242)/ensureProjectLoaded(L322)/updateBlueprintMutation(L197)/loadSection(L211) 均已定义，无 TDZ。Modal state ref 随 composable 内化，原 L233 位置删除。
- composable 解构出的 isModalOpen 等仍被 template（L140-145）引用——setup 变量声明顺序不影响 template render 时引用。
- `resolveSectionKey` 仅 handleSave 内部调用 → 留 composable 内部不返回；父 `type SectionKey = AllSectionType` 保留（componentContainerClass 的 `SectionKey[]` 仍用，非 orphan）。

### 测试指针跟随

- rg 确认 `uiAuditRegression`（L86/L107 读 `BlueprintEditModal.vue` 源码做断言，**独立组件本 slice 不动**）+ `novelDetailHeading`（h2/topbar）2 spec 均**不涉及** handleSectionEdit/handleSave/resolveSectionKey/isModalOpen/modal* → **零指针重定向**。
- 无运行时测试 → 等价性靠逐字搬迁 + 三件套绿 + diff 复核。

### 验证（实际，2026-07-15）

- 行数：895 → **849**（−46；roadmap 预估 ~55，略少，因 composable 调用块 8 行占回部分）。useShellBlueprintEdit.ts 92 行（新）。
- `vue-tsc --noEmit` exit 0（`ReturnType<typeof useUpdateBlueprintMutation>` 入参与父 updateBlueprintMutation 同型；loadSection 签名跨 composable 兼容；handleSave 内 `typeof project.blueprint` 类型与父一致）。
- `vitest run` 21 files / 141 tests 全绿（零指针重定向）。
- `eslint`：useShellBlueprintEdit.ts **0 warning**（composables/ 不受 components/views 的 `@/api` no-restricted-imports 限制）；NovelDetailShell.vue 仅预存 L167 `@/api/novel` type import warning（Slice 5 起在 L167，本 slice import 加在 L174 之后不影响其位置，未新增）。
- 关键点：`resolveSectionKey` 不返回（仅 handleSave 内部用）；父 `type SectionKey = AllSectionType` 保留（componentContainerClass 仍用）；无新 orphan import（`ref` 仍被 isSidebarOpen/isAddChapterModalOpen/newChapterInitialTitle 消费）。
- 行为等价：`props.isAdmin` → `isAdmin()`（入参 `() => props.isAdmin`）；Modal state 从父 ref → composable ref 解构回父，template `@close="isModalOpen = false"` 自动解包写 .value 不变；handleSave 逻辑逐字（payload 拼装/mutateAsync/resolveSectionKey+loadSection reload/isModalOpen=false）。

## Slice 7 设计：抽 `useShellOverview.ts`（概览指标计算群，2026-07-15）

### 边界

| 符号 | 原位置 | 去向 | 备注 |
|---|---|---|---|
| `projectStatus`/`characterCount`/`chapterTotal`/`chapterCompleted`/`currentChapterLabel`/`foreshadowingOverview` | script L240-279 | composable | **返回**（OverviewStrip props + componentProps 消费） |
| `overviewData`/`overviewMeta`/`formattedTitle` | script L291-300 | composable | **返回**（OverviewStrip props + topbar/OverviewStrip `{{ formattedTitle }}` 消费） |
| `resolveChapterNumberForEntry` import | 父 L175 | **留父**（composable 内另行 import） | 父 goToWritingDesk(L312) 仍用，import 非 orphan；composable 内 currentChapterLabel 用，独立 import |
| `novel`/`foreshadowingQuery`/`overviewQuery` | 父 computed/query | **留父**，入参透传 | novel 多处消费（useShellBlueprintEdit/goToWritingDesk/componentProps…）；两 query 仅 composable 入参引用 |

### 契约

```ts
useShellOverview({
  novel: Ref<NovelProject | null>,
  foreshadowingQuery: ReturnType<typeof useForeshadowingQuery>,
  overviewQuery: ReturnType<typeof useShellSectionNavigation>['overviewQuery'],
})
→ { projectStatus, characterCount, chapterTotal, chapterCompleted, currentChapterLabel,
    foreshadowingOverview, overviewData, overviewMeta, formattedTitle }
```

### TDZ / 接线处理

- composable 入参 novel(L238)/foreshadowingQuery(L199)/overviewQuery(L217 解构) 均在 composable 调用点(L241)之前定义 → **无 const TDZ**。
- composable 调用点紧邻 novel 之后、activeQuery 之前；解构出的 characterCount/chapterTotal 被 componentProps(L341) 消费 → 调用点先于 componentProps，无 TDZ。
- 9 个 computed 原分两段（L240-279 连续 6 个 + L291-300 连续 3 个，中间夹 Slice 8 的 activeQuery/currentSectionResponse/currentSectionData），迁入 composable 后统一解构；Slice 8 内容原位保留不动。
- `ReturnType<typeof useForeshadowingQuery>` / `ReturnType<typeof useShellSectionNavigation>['overviewQuery']` 入参类型与父 foreshadowingQuery/overviewQuery **完全同型**（同一 hook 的 ReturnType），零结构兼容风险。

### 测试指针跟随

- rg 确认 2 spec 对被迁 8 个 computed（projectStatus/characterCount/…/overviewMeta）**零引用**（EXIT=1）→ 零指针重定向。
- `formattedTitle`：novelDetailHeading L18 仅断言父 template 字符串 `{{ formattedTitle }}`（topbar L30 + OverviewStrip `:title` 绑定），变量从 composable 解构回父，template 引用不变 → 零指针。

### 验证（实际，2026-07-15）

- 行数：849 → **815**（−34；roadmap 预估 ~65，实际少因 9 computed 中含多行单语句 + composable 调用块 15 行占回）。useShellOverview.ts 91 行（新）。
- `vue-tsc --noEmit` exit 0（两个 ReturnType 入参同型 + overviewQuery.data 跨 composable 边界类型流转）。
- `vitest run` 21 files / 141 tests 全绿（零指针重定向）。
- `eslint`：useShellOverview.ts **0 warning**（composables/ 不受 components/views 的 `@/api` no-restricted-imports 限制）；NovelDetailShell.vue 仅预存 L167 `@/api/novel` type import warning（Slice 5 起在 L167，本 slice import 加在 L175 之后不影响其位置，未新增）。
- 关键点：9 个 computed 逐字搬迁，逻辑零改动；`resolveChapterNumberForEntry` 父 import 保留（goToWritingDesk L312 用，非 orphan），composable 内独立 import；无新 orphan（`computed` import 仍被 11 处消费，`ref` 仍被多处消费）。
- 行为等价：3 入参透传 → composable 内同名引用 → 9 computed 返回 → 父解构 → template/OverviewStrip props/componentProps 消费，全链路响应式保持（computed 对象解构不丢响应性）。

## Slice 8 设计：抽 `useShellSectionContent.ts`（分区内容渲染计算群，2026-07-15）

### 边界

| 符号 | 原位置 | 去向 | 备注 |
|---|---|---|---|
| `activeQuery`/`currentSectionResponse`/`currentSectionData` | script L257-266 | composable | **内部中间量不返回**（仅 isSectionLoading/currentError/componentProps 消费） |
| `componentContainerClass`/`contentCardClass` | script L268-278 | composable | **返回**（template `:class` 消费） |
| `currentComponent`/`isSectionLoading`/`currentError`/`componentProps` | script L323-370 | composable | **返回**（template `:is`/`v-if`/`v-bind` 消费） |
| `type SectionKey = AllSectionType` | 父 L188 | **删**（orphan） | componentContainerClass 迁出后父无引用；composable 内本地复刻 |
| `AllSectionType` import | 父 L169 | **删**（orphan） | SectionKey 删除后父无引用；type import 收敛为单行 `NovelProject` |
| `navigation` 实例 | 父 useShellSectionNavigation 调用 | **留父**，入参透传 | 父侧改 `const navigation = ...` + `} = navigation` 解构；父自用 10 符号仍解构，实例额外传 composable |

### 契约

```ts
useShellSectionContent({
  navigation: ReturnType<typeof useShellSectionNavigation>,
  novel: Ref<NovelProject | null>,
  characterCount: ReturnType<typeof useShellOverview>['characterCount'],
  chapterTotal: ReturnType<typeof useShellOverview>['chapterTotal'],
  isAdmin: () => boolean,
})
→ { currentComponent, isSectionLoading, currentError, componentProps, contentCardClass, componentContainerClass }
```

composable 内 `const { activeSection, sectionComponents, isNovelSectionKey, overviewQuery, sectionQuery } = navigation` 取 5 个 navigation 符号；本地 `type SectionKey = AllSectionType`（componentContainerClass 的 `fillSections: SectionKey[]` 用）。

### TDZ / 接线处理

- composable 调用点（L261）紧邻 useShellOverview（L255 结束）之后。入参 navigation（L209）/novel（L235）/characterCount+chapterTotal（useShellOverview 解构块 L241-250）/isAdmin（props L184）均在前定义 → **无 const TDZ**。
- 父侧 navigation 从「立即解构」改为「先存实例再解构」：`const navigation = useShellSectionNavigation({...})` + `const { sections, activeSection, ... } = navigation`。父自用的 10 个符号仍解构可用，实例额外传 composable。最小改动，不破坏 Slice 4 建立的解构结构。
- `ReturnType<typeof useShellOverview>['characterCount']` / `['chapterTotal']` indexed access 与父解构出的 characterCount/chapterTotal **完全同型**（同一 hook ReturnType），零结构兼容风险。

### 测试指针跟随（零重定向）

- 9 个 computed 符号（activeQuery/.../componentProps）在 2 spec（uiAuditRegression + novelDetailHeading）**零引用**（rg 仅匹配 useChapterBodyProps 无关注释）。
- **contentCardClass 含 `detail-shell__content-surface--classical` 字符串**：uiAuditRegression L302 断言 `shellSource.toContain('detail-shell__content-surface--classical')`。迁出 contentCardClass（仅 script 字符串 L277）后，父 style 块同名 CSS 选择器（L677 + L776/784/787/790/793 `:deep` 前缀）共 5 处**留父托底** → L302 命中 CSS 仍通过；L303 `not.toContain('--flat')` 父本就零出现（rg EXIT=1）→ **零指针重定向**。
- 无运行时测试 → 等价性靠逐字搬迁 + 三件套绿 + diff 复核。

### 验证（实际，2026-07-15）

- 行数：815 → **755**（−60；roadmap 预估 ~75，实际少因 composable 调用块 13 行占回 + navigation 实例化重构净增 2 行）。useShellSectionContent.ts 111 行（新）。
- `vue-tsc --noEmit` exit 0（navigation 实例透传 + Overview indexed access 类型 + componentProps switch 6 case 返回类型 + 全链路类型流转）。
- `vitest run` 21 files / 141 tests 全绿（零指针重定向）。
- `eslint`：useShellSectionContent.ts **0 warning**（composables/ 不受 components/views 的 `@/api` no-restricted-imports 限制）；NovelDetailShell.vue 仅预存 L167 `@/api/novel` type import warning（Slice 5 起在 L167，本 slice import 加在 L173 之后不影响其位置，未新增）。
- 关键点：9 个 computed 逐字搬迁（逻辑零改动，仅 componentProps 的 `props.isAdmin` → `isAdmin()` 入参化，同 Slice 6 范式）；3 个内部中间量（activeQuery/currentSectionResponse/currentSectionData）不返回（同 Slice 7 范式）；父删 `type SectionKey = AllSectionType` + `AllSectionType` import（componentContainerClass 迁出后双 orphan）；navigation 改实例化供 composable 透传。
- 行为等价：5 入参透传 → composable 内 navigation 解构 5 符号 + characterCount/chapterTotal/novel/isAdmin 引用 → 9 computed（6 返回 + 3 中间量）→ 父解构 6 → template/component 消费，全链路响应式保持。

