# WritingDesk.vue 拆分设计（2009 → <500）

parent `07-12-engineering-baseline` acceptance 第 4 项「5 大前端组件 <500 行」。
仿 NovelDetailShell 范式：composable 抽逻辑 / 子组件抽 modal / scoped style 随迁。
每个 slice 行为逐字等价，三件套绿（vue-tsc 0 / vitest 全绿 / eslint 0 新增 error）。

## 现状（2026-07-16）

- 路径 `frontend/src/views/WritingDesk.vue`，2009 行。
- 三段：template L2-272（270）/ script L274-1597（1323，主膨胀源）/ style L1599-2009（410）。
- 职责：页面级组合——WDSidebar + WDWorkspace + WDAssistantPanel + 多 Modal（WDVersionDetailModal/WDEvaluationDetailModal/推荐优化结果/WDEditChapterModal/WDGenerateOutlineModal）+ drawer 管理（侧栏/助手栏开关与互斥）+ 章节选择 + 项目加载 + 章节生成/评审/版本操作。
- WritingDesk 是 WDWorkspace 的父组件；WDWorkspace 已由 parent Slice B/D 抽过，契约不得破坏。

## script 逻辑块地图（行号）

| 块 | 行号 | 内容 |
|---|---|---|
| A loaders | 275-323 | imports + 5 async component loader + defineAsyncComponent |
| B refs | 325-351 | props/router/query + 状态 refs（selectedChapterNumber/chapterGenerationResult/show*Modal/editingChapter/statusStream* 等） |
| C 推荐优化状态 | 352-363 | optimize/applyOptimization mutation + recommendedDialog* + isApplying* |
| D drawer refs | 364-378 | viewport/isSidebarDrawerOpen/isAssistantDrawerOpen/isAssistantPanelVisible + breakpoint 常量 |
| E mutations | 380-390 | chapterQuery + 8 个 mutation |
| F project computed | 393-399 | project/projectLoading/projectError |
| G drawer 方法 | 400-549 | useSidebarDrawer/useAssistantDrawer/shouldRenderAssistantShell/assistantToggleActive/isDrawerBackdropVisible computed + getQueryChapterNumber(433-495 非drawer) + closeAllDrawers/persist/restore/toggle* |
| H 章节 computed | 551-622 | selectedChapter/showVersionSelector/activeEvaluatingChapter/isSelectingVersion/selectedChapterOutline/latestCompletedChapterNumber/progress/totalChapters/completedChapters |
| I 状态判断+版本提取 | 623-767 | isCurrentVersion/canGenerateChapter/isChapterFailed/hasChapterInProgress + extractVersionContent/extractVersionMetadata/availableVersions/toBoundedVersionIndex/resolveRecommendedVersionIndex |
| J 推荐优化解析+modal方法 | 768-1097 | syncRecommendedVersionSelection/recommendedOptimized* + tryParseOptimizerPayload/decodeJsonStringFragment/extractJsonField/normalizeOptimizeResult/parseEvaluationPayload + closeRecommendedOptimizeResult/optimizeRecommendedVersionFromEvaluation/applyRecommendedOptimization |
| K 导航加载 | 1098-1133 | goBack/viewProjectDetail/loadProject/refetchChapterIntoProject |
| L 状态流 | 1134-1197 | stopChapterStatusStream/fetchChapterStatus（SSE） |
| M 版本详情+选择 | 1198-1225 | showVersionDetail/closeVersionDetail/hideVersionSelector/selectChapter |
| N 章节操作 | 1226-1556 | generateChapter/retryFromNode/regenerateChapter/confirmVersionSelection/selectVersionFromDetail/openEditChapterModal/openEvaluationDetailModal/saveChapterChanges/evaluateChapter/deleteChapter |
| O 大纲编辑 | 1557-1597 | generateOutline/editChapterContent/handleGenerateOutline + watch/onMounted/onUnmounted |

## Slice roadmap

| # | 内容 | 类型 | 估收益 | 累计 |
|---|---|---|---|---|
| **1** ✅ | 5 payload 纯函数去重（tryParseOptimizerPayload/decodeJsonStringFragment/extractJsonField/normalizeOptimizeResult/parseEvaluationPayload 删本地副本 import @/utils/chapter） | 去重 | ~99 | 1910 |
| **2** ✅ | useWritingDeskDrawers composable（drawer refs+computed+方法+watch+onMounted，viewport/novelStore 内化，loadAssistantPanel 入参） | composable | ~93 | 1817 |
| **3a** ✅ | useWritingDeskChapterGeneration composable（generateChapter/retryFromNode/regenerateChapter + 内化 canGenerateChapter/isChapterFailed/hasChapterInProgress/generateChapterMutation，生成子系统内聚） | composable | ~154 | 1663 |
| **3b** ✅ | useWritingDeskChapterOps composable（evaluateChapter/deleteChapter + 内化 evaluateChapterMutation/deleteChapterMutation；confirmVersionSelection 因依赖 Slice 4 版本提取群拆 3c。**含 wdSidebarDeleteChapter spec 指针跟随**） | composable | ~117 | 1546 |
| 4 | useWritingDeskVersionDetail composable（版本提取群 extractVersionContent/extractVersionMetadata/toBoundedVersionIndex/resolveRecommendedVersionIndex/availableVersions/syncRecommendedVersionSelection/showVersionDetail/closeVersionDetail/selectVersionFromDetail/isCurrentVersion 内聚，**含 spec L333 指针跟随**） | composable | ~200 | 1346 |
| 3c | confirmVersionSelection（Slice 4 收敛 availableVersions/resolveRecommendedVersionIndex/selectedChapter 后单抽） | composable | ~52 | 1294 |
| 5 | WDRecommendedOptimizeResultModal 子组件（template L164-259 + 推荐优化 state/close/optimize/apply 方法 + style） | 子组件 | ~216 | 1078 |
| 6 | useWritingDeskProject composable（loadProject/refetchChapterIntoProject/viewProjectDetail/goBack/selectChapter/fetchChapterStatus/stopChapterStatusStream） | composable | ~130 | 948 |
| 7 | useWritingDeskModals composable（WDEditChapterModal/WDGenerateOutlineModal/WDEvaluationDetailModal state + open/save 方法） | composable | ~80 | 868 |
| 8 | 章节状态判断 canGenerateChapter/isChapterFailed/hasChapterInProgress + progress/totalChapters/completedChapters/latestCompletedChapterNumber 并入 composable | composable | ~80 | 788 |
| 9+ | template/style 收敛（modal 子组件 style 迁移、layout style 拆分到子组件），至 <500 | 子组件+style | ~330 | <500 |

> roadmap 行数为粗估，每 slice 实施时以 rg/Read 真实磁盘为准。仿 NovelDetailShell 实际收益常优于预估。

---

## Slice 1 设计：5 payload 纯函数去重（2026-07-16）✅ 2009→1910

### 背景

`@/utils/chapter.ts` 已导出 5 个 payload 解析纯函数，WritingDesk.vue 内有**逐字等价的本地副本**（历史抽 utils 时漏删本地）。本次去重纠正重复，diff 最小、风险最低。

### 等价性验证（逐字对比 utils/chapter.ts ↔ WritingDesk 本地）

| 函数 | utils | 本地 | 等价 |
|---|---|---|---|
| tryParseOptimizerPayload | L97-120 | L877-900 | ✅ 逐字 |
| decodeJsonStringFragment | L125-131 | L902-908 | ✅ 逐字 |
| extractJsonField | L136-144 | L910-918 | ✅ 逐字 |
| normalizeOptimizeResult | L149-192 | L920-963 | ✅ 逐字 |
| parseEvaluationPayload | L225-239 | L965-979 | ✅ 逐字 |

### 不动的（差异/守护）

- **extractVersionContent**：本地 L675-716 **多 object 分支**（`if (raw && typeof raw === 'object' ...)` 遍历 keys），utils L11-42 仅 string → **不等价**。availableVersions L745 传 object，改 utils 版会返回 '' 破坏行为。留本地，Slice 4 版本提取 composable 专门处理（utils extractVersionContent 确认无 import 消费者=死导出，届时可统一）。
- **extractVersionMetadata / toBoundedVersionIndex**：utils 无此函数，留本地（Slice 4 内聚）。
- **resolveRecommendedVersionIndex**：`wdWorkspaceLockedChapter.spec.ts:333` 断言 WritingDesk.vue 本地含 `const resolveRecommendedVersionIndex`（强回归网）→ 留本地，Slice 4 抽 composable 时指针跟随。

### 改动

1. **import 块**（L303-308 `from '@/utils/chapter'`）：加 5 个函数名（字母序合并）。
2. **删本地副本** L877-979（tryParseOptimizerPayload → parseEvaluationPayload 连续块，含其间空行；保留 L865-875 recommendedOptimizedParagraphs/WordCount computed reactive，保留 L981 watch）。

### 调用点（零改动）

5 函数的调用点语法不变（本地 const → import 同名函数）：
- normalizeOptimizeResult L1041（optimizeRecommendedVersionFromEvaluation 内）
- parseEvaluationPayload L804（resolveRecommendedVersionIndex 内）/ L1011（optimizeRecommendedVersionFromEvaluation 内）
- extractJsonField/tryParseOptimizerPayload/decodeJsonStringFragment 互调（normalizeOptimizeResult 内部链）

### spec 影响

- `wdWorkspaceLockedChapter.spec.ts` L330-338 断言全在 resolveRecommendedVersionIndex（留本地）+ syncRecommendedVersionSelection（留本地），5 函数去重零触及 → **无指针重定向**。
- 5 函数无任何 spec 断言指向。

### eslint

`@/utils/chapter` 在 views/ 已有 import 先例（L302-308），no-restricted-imports 不限制 @/utils。import 名按字母序合并规避 sort-imports（若启用）。

### 验证

- `rg -n "tryParseOptimizerPayload|decodeJsonStringFragment|extractJsonField|normalizeOptimizeResult|parseEvaluationPayload" src/views/WritingDesk.vue` 仅剩调用点（无 `const X =` 声明）。
- 行数：2009 → ~1910（-99）。
- 三件套：vue-tsc 0 / vitest 全绿（wdWorkspaceLockedChapter 含）/ eslint 0 新增。

### 完成（2026-07-16）

- 2009 → 1910（-99）。
- vue-tsc 0 / vitest 141 绿（wdWorkspaceLockedChapter 10/10）/ eslint 0 新增（L277/278 `@/api/novel` 预存 warnings 非本次）。
- 独立复核 git diff：仅 import +5 名 + 删 5 函数块，无其他改动。

---

## Slice 2 设计：useWritingDeskDrawers composable（2026-07-16）✅ 1910→1817

抽 drawer 状态机：侧栏/助手栏抽屉开关与互斥 + 助手面板可见性（novelStore + localStorage 持久化）。

### 边界（迁入 composable）

- refs：isSidebarDrawerOpen / isAssistantDrawerOpen
- computed（get/set）：isAssistantPanelVisible（setter 调 persist）
- computed：useSidebarDrawer / useAssistantDrawer / assistantToggleActive / isDrawerBackdropVisible
- 方法：closeAllDrawers / toggleSidebarDrawer / toggleAssistantDrawer（内部，不返回）/ toggleAssistantVisibility
- 内部不返回：persistAssistantPanelVisibility / restoreAssistantPanelVisibility（onMounted 内部调）
- watch ×2（断点切换关抽屉，{immediate:true}）
- onMounted（restoreAssistantPanelVisibility）
- 内化依赖：viewport=useResponsiveViewport() / viewportWidth / novelStore=useNovelStore() / 3 常量 / mobileMax,desktopMin

### 入参

- `loadAssistantPanel: () => void`（父传 loadWDAssistantPanel，toggle 时预加载 WDAssistantPanel；Promise 返回协变到 void）

### 留父

- shouldRenderAssistantShell（依赖 project.value，非 drawer）
- getQueryChapterNumber + 3 watch（project/route/props.id，章节选择 Slice 6）
- onUnmounted（stopChapterStatusStream）

### orphan 清理（4 import）

- useResponsiveViewport / desktopMin,mobileMax / useNovelStore（仅 drawer 用，rg 确认全文件仅 drawer 块消费）
- onMounted（仅 restore 用，迁入 composable）

### const TDZ

composable 内顺序：persist → isAssistantPanelVisible（setter 用 persist）→ restore → computed → 方法 → watch → onMounted。无 forward reference。

### spec

drawer 符号无 spec 断言（wdWorkspaceLockedChapter 只守护版本逻辑 L330-338）。零指针重定向。

### 完成（2026-07-16）

- 1910 → 1817（-93，优于预估 ~77）。
- vue-tsc 0 / vitest 141 绿 / eslint 0 新增（WritingDesk + composable 均 0 warning，L277/278 @/api 预存）。
- 独立复核 git diff：6 处精确删除（import×2 + refs + computed/watch + 方法 + onMounted），保留 shouldRenderAssistantShell/getQueryChapterNumber/selectedChapter/onUnmounted。

---

## Slice 3a 设计：useWritingDeskChapterGeneration composable（2026-07-16）✅ 1817→1663

### 边界调整说明（原 Slice 3 拆为 3a/3b）

原 design.md Slice 3 把 generateChapter/retryFromNode/regenerateChapter/evaluateChapter/deleteChapter/confirmVersionSelection 6 方法归一个 composable。实施前依赖分析发现：6 方法横跨 refs(5)/computed(4)/mutations(4)/methods(4) 共 ~15 个透参，远超 NovelDetailShell 范式的 5-6 入参，构成过度抽象。其中生成三方法（generate/retry/regenerate）依赖高度重叠、且独占 canGenerateChapter/isChapterFailed/hasChapterInProgress 三状态判断 + generateChapterMutation，内聚度最高 → 单独成块（3a）。evaluate/delete/confirm 各依赖独立 mutation、confirm 还依赖 Slice 4 版本提取群，留 3b（待版本提取收敛后单抽，入参更少）。

### 边界（迁入 composable）

- 方法：generateChapter / retryFromNode / regenerateChapter
- 内化状态判断（仅生成流程用，rg 确认无其他消费）：canGenerateChapter / isChapterFailed / hasChapterInProgress
- 内化 mutation（仅生成用）：generateChapterMutation = useGenerateChapterMutation(projectId)

### 入参（9，透传父侧响应式源）

- projectId: () => string（getter，替代 props.id 直接访问）
- project: ComputedRef<NovelProject | null>
- refs(4): generatingChapter / selectedChapterNumber / chapterGenerationResult / selectedVersionIndex
- methods(3): upsertChapterInProjectCache（跨 Slice 6 复用）/ fetchChapterStatus（template + Slice 6）/ refetchChapterIntoProject（Slice 6）

### 留父（零改动顺延 3b / 后续 slice）

- evaluateChapter / deleteChapter / confirmVersionSelection（3b）
- selectVersionFromDetail / openEditChapterModal / openEvaluationDetailModal / saveChapterChanges（后续 slice）
- evaluateChapterMutation / deleteChapterMutation / confirmFinalizeChapterMutation（3b 各自消费）
- upsertChapterInProjectCache / refreshProjectQueries / fetchChapterStatus / refetchChapterIntoProject（Slice 6）

### 等价性

- props.id → projectId()（getter 调用求值等价）
- generateChapterMutation 内化 useGenerateChapterMutation(projectId)，与原 useGenerateChapterMutation(() => props.id) 等价
- 方法体逐字搬迁，project.value/refs.value 访问不变（入参为 ComputedRef/Ref）
- regenerateChapter 调 generateChapter（composable 内先定义，无 TDZ）
- template @generate-chapter/@retry-from-node/@regenerate-chapter 绑定不变（解构暴露同名）

### spec

- 生成符号零 spec 断言：uiAuditRegression L231 断言的是 ChapterFailed.vue 的 emit（非 WritingDesk 方法），wdWorkspaceLockedChapter 只守护版本逻辑。零指针重定向。

### 完成（2026-07-16）

- 1817 → 1663（-154，优于预估）。
- vue-tsc 0 / vitest 141 绿 / eslint 0 新增（L277/278 @/api 预存 warning 非本次，composable 文件 0 输出）。
- 独立复核 git diff：5 处精确（import -useGenerateChapterMutation+composable / 删 generateChapterMutation 实例化 / 删 3 状态判断 / 删 3 方法+原位加 composable 解构 9 入参），+12/-166，留父方法零触及。

---

## Slice 3b 设计：useWritingDeskChapterOps composable（2026-07-16）✅ 1663→1546

### 边界调整说明（原 3b 拆为 3b + 3c）

原 design.md 3b 把 evaluateChapter/deleteChapter/confirmVersionSelection 三方法归一个 composable。实施前依赖分析发现：confirmVersionSelection（L1004-1055）依赖 availableVersions(L1010/1020)/resolveRecommendedVersionIndex(L1011)/selectedChapter(L1012)，全属 Slice 4 版本提取群。若现在抽 confirm，需透传这 3 个 Slice 4 符号，等 Slice 4 抽出后还要 composable 间重传——正中注记"依赖收敛后单抽"。故把 confirm 拆 3c（待 Slice 4 收敛后单抽），本轮 3b 只抽 evaluate/delete（各依赖独立 mutation、互不耦合、且都不依赖版本提取群）。

### 边界（迁入 composable）

- 方法：evaluateChapter / deleteChapter
- 内化 mutation（各独立，无交叉）：evaluateChapterMutation = useEvaluateChapterMutation(projectId) / deleteChapterMutation = useDeleteChapterMutation(projectId)

### 入参（5，透传父侧响应式源）

- projectId: () => string（getter，替代 props.id 直接访问）
- project: ComputedRef<NovelProject | null>
- selectedChapterNumber: Ref<number | null>（evaluate 写 + delete 读）
- evaluatingChapter: Ref<number | null>（留父，activeEvaluatingChapter computed 消费；evaluate 写）
- latestCompletedChapterNumber: ComputedRef<number | null>（留父，delete 读；不内化避免扩到 Slice 8）

### 留父（零改动）

- confirmVersionSelection（3c，依赖 Slice 4 版本提取群）
- selectVersionFromDetail / openEditChapterModal / openEvaluationDetailModal / saveChapterChanges（后续 slice）
- confirmFinalizeChapterMutation / updateChapterOutlineMutation / generateChapterOutlineMutation / editChapterContentMutation（其他 slice 各自消费）
- evaluatingChapter / latestCompletedChapterNumber（留父透传）

### 等价性

- props.id → projectId()（mutation 实例化 useEvaluateChapterMutation(projectId) / useDeleteChapterMutation(projectId)，等价于原 () => props.id）
- 方法体逐字搬迁，project.value/refs.value/computed.value 访问不变
- template @evaluate-chapter/@delete-chapter 绑定不变（解构暴露同名）

### spec 指针跟随

`wdSidebarDeleteChapter.spec.ts:118` `keeps destructive confirmation copy explicit for completed chapter artifacts` 断言删除文案（`正文、版本、评审、生成 trace 和向量数据等全部产物` / `删除章节及产物` / `删除章节大纲`）+ `showConfirmInput` 在 `src/views/WritingDesk.vue` 源码里。这些随 deleteChapter 迁入 composable → source 改为 `` `${readSource('src/views/WritingDesk.vue')}\n${readSource('src/composables/useWritingDeskChapterOps.ts')}` ``（与 apiSource 同范式）。apiSource 断言不动（delete_artifacts_confirmed/confirmation_text 在 @/api + @/queries，未迁）。

### const TDZ

composable 内：evaluateChapterMutation → deleteChapterMutation → evaluateChapter → deleteChapter。evaluate/delete 互不调用，无 forward reference。

### 完成（2026-07-16）

- 1663 → 1546（-117；预估 ~150 因拆出 confirm 至 3c）。
- vue-tsc 0 / vitest 141 绿（wdSidebarDeleteChapter 2/2 spec 重定向后绿）/ eslint 0 新增（composable 0 输出，3 warning 全预存 @/api/novel：WritingDesk.vue L277/278 + spec L7）。
- 独立复核 git diff：5 处精确（import -2 mutation+composable / 删 2 mutation 实例化 / 删 evaluate+delete 整块+原位 composable 解构 5 入参）+ spec 1 处 source 拼接，留父方法零触及。
