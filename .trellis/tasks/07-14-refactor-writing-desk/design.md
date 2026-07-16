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
| **4** ✅ | useWritingDeskVersionDetail composable（版本提取群 extractVersionContent/extractVersionMetadata/toBoundedVersionIndex/resolveRecommendedVersionIndex/availableVersions/syncRecommendedVersionSelection/showVersionDetail/closeVersionDetail/selectVersionFromDetail/isCurrentVersion + 内化 showVersionDetailModal/detailVersionIndex/lastAutoRecommendedSelectionKey refs + watch，**含 spec L333 指针跟随 + L345 fetchChapterStatus 锚点跟随**） | composable | ~226 | 1320 |
| 3c | confirmVersionSelection（Slice 4 已收敛 availableVersions/resolveRecommendedVersionIndex，可直接消费 composable 返回值单抽） | composable | ~52 | 1268 |
| **5** ✅ | WDRecommendedOptimizeResultModal 子组件（modal template L164-259 + 内化 useDialogA11y+2refs+titleId+2computed+.m3-result-dialog style，4 props+emit close/apply；optimize/apply/close 方法+state 留父） | 子组件 | ~114 | 1206 |
| ~~3c~~ | confirmVersionSelection **决定不抽**（单方法+入参 8 含 composable 链传递 availableVersions/resolveRecommendedVersionIndex=过度抽象，留父消费已解构返回值更简） | — | 0 | 1206 |
| **6** ✅ | useWritingDeskProject composable（loadProject/refetchChapterIntoProject/viewProjectDetail/goBack/selectChapter/fetchChapterStatus/stopChapterStatusStream + 内化 4 statusStream refs + onUnmounted，**含 spec L341 source 拼接 + L342 regex 锚点简化 + L346 currentProjectId 指针跟随**） | composable | ~95 | 1111 |
| **7** ✅ | useWritingDeskModals composable（WDEditChapterModal/WDGenerateOutlineModal/WDEvaluationDetailModal state + open/save 方法 + editChapterContent 内联快编 + 内化 3 mutation） | composable | ~56 | 1055 |
| 8 | 章节状态判断 canGenerateChapter/isChapterFailed/hasChapterInProgress + progress/totalChapters/completedChapters/latestCompletedChapterNumber 并入 composable | composable | ~80 | 916 |
| 9+ | template/style 收敛（剩余 layout style 拆分、H 块章节 computed、O 大纲编辑等），至 <500 | 子组件+style | ~330 | 586（**预估后仍 >500，后续 slice 据实扩展**） |

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

---

## Slice 4 设计：useWritingDeskVersionDetail composable（2026-07-16）✅ 1546→1320

### 边界（迁入 composable）

- 纯函数（无响应式依赖）：extractVersionContent / extractVersionMetadata / toBoundedVersionIndex / resolveRecommendedVersionIndex（依赖 toBoundedVersionIndex + parseEvaluationPayload import）
- computed：availableVersions（依赖 chapterGenerationResult + selectedChapter + 2 纯函数）/ isCurrentVersion（依赖 selectedChapter + availableVersions + cleanVersionContent）
- 方法：syncRecommendedVersionSelection（+ watch 内化，selectedChapter/availableVersions 触发）/ showVersionDetail / closeVersionDetail / hideVersionSelector / selectVersionFromDetail
- 内化 refs（仅版本详情用）：showVersionDetailModal / detailVersionIndex / lastAutoRecommendedSelectionKey（仅 sync 用）

### 入参（4，透传父侧响应式源 + loader）

- selectedChapter: ComputedRef<Chapter | null>（留父，多处消费）
- chapterGenerationResult: Ref<ChapterGenerationResponse | null>（留父，3a 已透传）
- selectedVersionIndex: Ref<number>（留父，3a/3b 已透传 + template）
- loadWDVersionDetailModal: () => Promise<unknown>（loader 留父 defineAsyncComponent 用 + 透传 showVersionDetail 预加载）

### 返回（template + confirm 3c + optimize 消费）

- availableVersions（template :available-versions + WDVersionDetailModal :version + confirm/optimize）
- isCurrentVersion（template :is-current）
- resolveRecommendedVersionIndex（**暴露给 confirm 3c**，依赖已收敛）
- showVersionDetail / closeVersionDetail / hideVersionSelector / selectVersionFromDetail（template 绑定）
- showVersionDetailModal / detailVersionIndex（template WDVersionDetailModal :show/:detail-version-index）

### 留父（零改动）

- confirmVersionSelection（3c，现已可消费 composable 返回的 availableVersions/resolveRecommendedVersionIndex，依赖收敛完成）
- recommendOptimized*（Slice 5 推荐优化 modal，消费 availableVersions）
- selectChapter / fetchChapterStatus（Slice 6）

### 等价性

- 纯函数逐字搬迁；computed/方法体逐字搬迁，selectedChapter.value/chapterGenerationResult.value/selectedVersionIndex.value 访问不变
- watch 内化（selectedChapter/availableVersions 触发 syncRecommendedVersionSelection，deep+immediate 保留）
- loadWDVersionDetailModal 透传，showVersionDetail 内 void loadWDVersionDetailModal() 不变
- template 绑定不变（解构暴露同名）

### spec 指针跟随（2 处）

1. wdWorkspaceLockedChapter L331 `defaults waiting confirmation selection`：source 改为 `` `${readSource WritingDesk.vue}\n${readSource useWritingDeskVersionDetail.ts}` ``（resolveRecommendedVersionIndex/syncRecommendedVersionSelection 迁入 composable，5 项断言 `const resolveRecommendedVersionIndex`/`recommended_version_index`/`metadata?.ai_review?.is_best`/`selectedVersionIndex.value = recommendedIndex`/not `availableVersions.value.length - 1` 全在 composable 源码命中）
2. wdWorkspaceLockedChapter L342 `streams generation status`：fetchChapterStatus 后续锚点 `// 显示版本详情`（showVersionDetail 注释）随迁入消失 → 改 `const selectChapter`（fetchChapterStatus `}` 后现直接 selectChapter）

### const TDZ

composable 内：refs → extractVersionContent → extractVersionMetadata → availableVersions → isCurrentVersion（调 availableVersions，放其后）→ toBoundedVersionIndex → resolveRecommendedVersionIndex（调 toBounded + parseEvaluationPayload）→ syncRecommendedVersionSelection（调 availableVersions + resolveRecommended）→ show/close/hide/select → watch。无 forward reference。

### 完成（2026-07-16）

- 1546 → 1320（-226，优于预估 ~200）。
- vue-tsc 0 / vitest 141 绿（wdWorkspaceLockedChapter spec 2 处指针跟随后绿）/ eslint 0 新增（composable 0 输出，3 warning 全预存 @/api/novel：WritingDesk L277/278 + spec L8）。
- 独立复核 git diff：8 hunk 对应 6 处逻辑改动（import +1 / refs 删 3 / 版本提取群删 ~199 替换 composable 解构 15 / watch 删 12 / show-close-hide 删 22 / selectVersionFromDetail 删 6），留父方法零触及。

---

## Slice 5 设计：WDRecommendedOptimizeResultModal 子组件（2026-07-16）✅ 1320→1206

### 3c 决定不抽（同期决策）

confirmVersionSelection 原列 3c。Slice 4 收敛后 confirm 依赖 availableVersions/resolveRecommendedVersionIndex（composable 返回值）。但 confirm 是单方法，抽 composable 需透传这 2 个 + selectedChapterNumber/selectedVersionIndex/chapterGenerationResult/selectedChapter/project/confirmFinalizeChapterMutation/refetchChapterIntoProject 共 **入参 8**，且含 composable 链传递——命中「No abstractions for single-use code」。confirm 留父消费已解构的 composable 返回值更简，故 **3c 取消**。

### 边界（迁入子组件）

- template：Teleport+overlay+dialog（评审优化结果预览 modal，逐字迁入，props 化）
- 内化 refs：dialogRef / closeButtonRef
- 内化常量：dialogTitleId
- 内化 computed：optimizedParagraphs / optimizedWordCount（从 props.optimizedContent 派生）
- 内化 useDialogA11y（active: toRef(props,'show')，onClose: emit close）
- 内化 scoped style：.m3-result-dialog

### props/emit

- props: show / optimizedContent / isApplying / notes
- emit: close / apply（template $emit + script useDialogA11y onClose emit close）

### 留父（零改动）

- state: showRecommendedOptimizeResultModal / recommendedOptimizedContent / recommendedOptimizeResultNotes / isApplyingRecommendedOptimization / isOptimizingRecommendedVersion
- 方法: closeRecommendedOptimizeResult（含 isApplying 拦截，@close 处理）/ optimizeRecommendedVersionFromEvaluation（触发+数据准备，WDEvaluationDetailModal @optimize-recommended-version）/ applyRecommendedOptimization（applyOptimizationMutation+refetchChapterIntoProject）
- mutations: optimizeRecommendedVersionMutation / applyOptimizationMutation

### 等价性

- close（button/overlay/取消/ESC）：子 emit close → 父 closeRecommendedOptimizeResult（isApplying 拦截保留）等价
- apply：子 emit apply → 父 applyRecommendedOptimization 等价
- 内容/notes/isApplying：props 透传；paragraphs/wordCount 子内 computed（从 optimizedContent）等价
- a11y 焦点：useDialogA11y 迁子（dialogRef/closeButtonRef）等价
- lazy：defineAsyncComponent + loader（同其他 modal 范式）
- scoped：.m3-result-dialog 迁子（子内部元素 scoped 命中）等价

### 完成（2026-07-16）

- 1320 → 1206（-114；design.md 估 ~216 偏高，实际 modal style 仅 5 行 + template 96 行 + computed/refs ~20）。
- vue-tsc 0 / vitest 141 绿 / eslint 0 新增（2 warning 预存 @/api/novel 因 template -88 上移 L189/190，子组件 0 warning）。
- 独立复核 git diff：8 hunk（template 96→8 标签 / useDialogA11y import 删 / loader+defineAsyncComponent 新增 / refs+titleId 删 / computed 删 / useDialogA11y 调用删 / style 删），留父方法零触及。

---

## Slice 6 设计：useWritingDeskProject composable（2026-07-16）✅ 1206→1111

### 边界（迁入 composable）

- 方法：goBack / viewProjectDetail / loadProject / refetchChapterIntoProject / stopChapterStatusStream / fetchChapterStatus / selectChapter
- 内化 refs（仅 SSE 流用）：isFetchingChapterStatus / statusStreamController / statusStreamKey / statusStreamReconnectTimer
- 内化 lifecycle：onUnmounted（→ stopChapterStatusStream）
- 内化 import：useRouter / NovelAPI / nextTick / onUnmounted

### 入参（10，透传父侧响应式源 + query/mutation 实例）

- projectId: () => string（getter，替代 props.id）
- project: ComputedRef<NovelProject | null>（viewProjectDetail 用）
- projectQuery: ReturnType<typeof useNovelProjectQuery>（loadProject 用）
- chapterQuery: ReturnType<typeof useNovelChapterQuery>（refetchChapterIntoProject 用）
- selectedChapterNumber / chapterGenerationResult / selectedVersionIndex（selectChapter 用，3a/3b/4 已透传）
- closeAllDrawers（selectChapter 用，useWritingDeskDrawers 返回值）
- upsertChapterInProjectCache / refreshProjectQueries（ReturnType<typeof useNovelMutationRefresh> indexed access；upsertChapterInProjectCache 跨 3a 复用故留父透传）

### 返回（template + watch + 3a 消费）

- goBack / viewProjectDetail / loadProject（template 绑定）
- refetchChapterIntoProject / fetchChapterStatus（**供 3a 入参** + fetch 自递归）
- stopChapterStatusStream（watch props.id + onUnmounted 内部）
- selectChapter（template @select-chapter + watch route.query）

### 留父（零改动）

- project / projectLoading / projectError computed（projectQuery 消费，透传 composable）
- selectedChapter computed（chapterQuery 消费）
- 3 watch（project.value/route.query/props.id）：watch route.query 调 selectChapter、watch props.id 调 stopChapterStatusStream——均消费 composable 返回值
- applyRecommendedOptimization（消费 refetchChapterIntoProject）
- 3a useWritingDeskChapterGeneration（入参传 fetchChapterStatus/refetchChapterIntoProject/upsertChapterInProjectCache）

### 等价性

- props.id → projectId()（getter 求值等价；refetchChapterIntoProject L584 + fetchChapterStatus 多处）
- fetchChapterStatus 内部局部 `const projectId = props.id`（L606）改名 `const currentProjectId = projectId()`——**必要**：避与入参 `projectId: () => string` getter 同名 shadow（否则局部 string 遮蔽 getter，后续 `projectId()` 重新求值会调用 string 报错）。`props.id === projectId`（L636/640 重新读取检测项目切换）→ `projectId() === currentProjectId`，等价
- router 内化 useRouter()，与原父 const router 等价
- onUnmounted 迁入 composable（setup 阶段同步注册，合法，同 Slice 2 onMounted 范式）
- 方法体逐字搬迁，project.value/refs.value 访问不变（入参为 ComputedRef/Ref）
- fetchChapterStatus 递归自调 + refetchChapterIntoProject 自调（composable 内先定义，无 TDZ）

### 调用点

useWritingDeskProject 解构插在 project computed（L300）之后、3 watch 之前：

- 入参 project(L300)/projectQuery/chapterQuery/closeAllDrawers 等均在其前定义
- 返回 selectChapter 被 watch route.query(L360) 引用、stopChapterStatusStream 被 watch props.id(L368) 引用——均在 watch 之前定义（const 解构）✅
- 返回 fetchChapterStatus/refetchChapterIntoProject 被 3a(L563) 入参消费——在其前定义 ✅

### spec 指针跟随（3 处，wdWorkspaceLockedChapter L340-349）

1. L341 source 拼接：fetchChapterStatus/selectChapter 迁 composable → source 改为 `` `${readSource WritingDesk}\n${readSource useWritingDeskProject}` ``（同 Slice 4 范式）
2. L342 regex 锚点：`/const fetchChapterStatus[\s\S]*?\n}\n\nconst selectChapter/` → `/const fetchChapterStatus[\s\S]*?const selectChapter/`——迁入 composable 后两符号缩进 2 空格，原 `\n}\n\nconst`（假设行首 0 缩进）失配，简化为 `const selectChapter`（fetchChapterStatus 与 selectChapter 在 composable 内相邻，非贪婪提取整个 fetchChapterStatus 块，断言意图不变）
3. L346 参数名：`upsertChapterInProjectCache(projectId, chapter)` → `(currentProjectId, chapter)`——跟随 fetchChapterStatus 局部变量改名

### const TDZ

composable 内：refs（4 statusStream）→ goBack → viewProjectDetail → loadProject → refetchChapterIntoProject（调 nextTick/chapterQuery/upsert/refresh）→ stopChapterStatusStream → fetchChapterStatus（调 stopChapterStatusStream + refetchChapterIntoProject + NovelAPI + upsert）→ selectChapter（调 closeAllDrawers）→ onUnmounted（调 stopChapterStatusStream）。无 forward reference。

### 注：goBack 为 pre-existing dead code

goBack 全文件仅定义无消费点（template/script 均无引用）。忠实搬迁（composable return + 父解构），不删（「notice dead code, don't delete」）。vue-tsc/eslint 对 setup 解构变量宽容，未报 unused。

### 完成（2026-07-16）

- 1206 → 1111（-95；估 ~130 偏高，fetchChapterStatus 内联 SSE 重连逻辑长但 4 refs 迁出抵消部分）。
- vue-tsc 0 / vitest 141 绿（wdWorkspaceLockedChapter 10/10 spec 3 处指针跟随后绿）/ eslint 0 新增（2 warning 全预存 @/api/novel：WritingDesk L189 type import + spec L8；Slice 5 的 NovelAPI value import warning 随迁出消失）。
- 独立复核 git diff：7 hunk（import×4 调整 / router 删 / 4 refs 删 / useWritingDeskProject 解构插入 22 行 / onUnmounted+7 方法删 ~110 行），+27/-122，留父 3 watch/3a/applyRecommendedOptimization 零触及。

---

## Slice 7 设计：useWritingDeskModals composable（2026-07-16）✅ 1111→1055

### 边界（迁入 composable）

- 方法（6）：openEditChapterModal / openEvaluationDetailModal / saveChapterChanges / generateOutline / editChapterContent / handleGenerateOutline
- 内化 refs（仅弹窗用）：showEvaluationDetailModal / showEditChapterModal / editingChapter / isGeneratingOutline / showGenerateOutlineModal
- 内化 mutation（各独立）：updateChapterOutlineMutation（saveChapterChanges）/ generateChapterOutlineMutation（handleGenerateOutline）/ editChapterContentMutation（editChapterContent）

### 入参（5）

- projectId: () => string（getter，3 mutation 实例化 useXxxMutation(projectId) 等价原 () => props.id）
- project: ComputedRef<NovelProject | null>（editChapterContent/handleGenerateOutline 守卫用）
- loadWDEditChapterModal / loadWDEvaluationDetailModal / loadWDGenerateOutlineModal（3 loader，父侧 defineAsyncComponent 用故透传，open 方法内 void 预加载）

### 返回（5 ref + 6 方法）

- refs：showEvaluationDetailModal（template :show + applyRecommendedOptimization 留父 set false + @close inline）/ showEditChapterModal（template :show + @close inline）/ editingChapter（template :chapter）/ isGeneratingOutline（template WDSidebar :is-generating-outline）/ showGenerateOutlineModal（template :show + @close inline）——全被 template inline 或留父方法消费，故全返回父解构
- 方法：openEditChapterModal（WDSidebar @edit-chapter）/ openEvaluationDetailModal（WDWorkspace @show-evaluation-detail）/ saveChapterChanges（WDEditChapterModal @save）/ generateOutline（WDSidebar @generate-outline）/ editChapterContent（WDWorkspace @edit-chapter）/ handleGenerateOutline（WDGenerateOutlineModal @generate）

### 留父（零改动）

- 3 loader 定义 + 5 defineAsyncComponent（WDVersionDetailModal/WDEvaluationDetailModal/WDEditChapterModal/WDGenerateOutlineModal/WDAssistantPanel/WDRecommendedOptimizeResultModal）
- applyRecommendedOptimization（消费解构回父的 showEvaluationDetailModal.value=false）
- confirmVersionSelection（消费 confirmFinalizeChapterMutation，3c 不抽留父）
- confirmFinalizeChapterMutation / applyOptimizationMutation / optimizeRecommendedVersionMutation（其他 slice/逻辑各自消费）

### 等价性

- 3 mutation 内化 useXxxMutation(projectId)，与原 useXxxMutation(() => props.id) 等价（projectId getter = () => props.id）
- 方法体逐字搬迁，project.value/refs.value 访问不变（入参为 ComputedRef/Ref）
- showEvaluationDetailModal 等解构回父，template inline `@close="showXxxModal = false"` 与留父方法 applyRecommendedOptimization 访问同名 ref，行为等价
- 3 loader 透传，open 方法内 void loadWDXxx() 预加载不变
- editChapterContent 收入本块：虽非 modal 开关（WDWorkspace 内联正文快编），但依赖独立 editChapterContentMutation 且属「章节保存」语义，与编辑大纲同内聚

### 调用点

useWritingDeskModals 解构插在 useWritingDeskProject 解构之后、getQueryChapterNumber 之前：

- 入参 project(L295)/loaders(L227-233) 均在其前定义
- 返回 showEvaluationDetailModal 被 applyRecommendedOptimization(L517 区) 消费——在其前定义 ✅
- 返回方法/refs 被 template 引用——setup 作用域可访问 ✅

### const TDZ

composable 内：refs（5）→ mutations（3）→ openEditChapterModal → openEvaluationDetailModal → saveChapterChanges（调 updateChapterOutlineMutation + showEditChapterModal）→ generateOutline → editChapterContent（调 editChapterContentMutation + project）→ handleGenerateOutline（调 generateChapterOutlineMutation + isGeneratingOutline + project）。各方法互不调用，无 forward reference。

### spec

modal 符号零 spec 断言（codegraph blast radius 全 no covering tests；rg 确认 wdSidebarDeleteChapter L68 `isGeneratingOutline: false` 是 WDWorkspace mount props 非源码断言）。零指针跟随。

### 完成（2026-07-16）

- 1111 → 1055（-56；估 ~80 偏高，6 方法较短 + 5 ref + 3 mutation 净删 ~80，加 insert 解构 24 行抵消）。
- vue-tsc 0 / vitest 141 绿 / eslint 0 新增（1 warning 预存 @/api/novel WritingDesk L189 type import；composable 0 warning）。
- 独立复核 git diff：7 hunk（queries import 删 3 mutation / +composable import / 删 5 refs / 删 3 mutations / useWritingDeskModals 解构插入 22 行 / 删块A 3 方法 26 行 / 删块B 3 方法 47 行），留父 applyRecommendedOptimization/confirmVersionSelection/loader+defineAsyncComponent 零触及。
