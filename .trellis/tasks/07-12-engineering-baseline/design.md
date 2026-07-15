# #22 设计：拆 WDWorkspace + 乐观更新规范化 + cleanVersionContent 去重

本设计覆盖审计报告（`docs/mofeng-audit-report-2026-07-12.html`）P2「超胖组件」与「cleanVersionContent 逐字重复」「乐观更新规范化」三块。因报告点名 8 个超胖组件、单会话无法安全完成，**按风险递增切三个独立可验证 slice**，每次会话推进一个。

## Slice 划分

| Slice | 内容 | 风险 | 验证 | 依赖 |
|---|---|---|---|---|
| **A** | 删 5 处 `cleanVersionContent` 副本，统一 `import { cleanVersionContent } from '@/utils/chapter'` | 极低（纯函数，等价性已验证） | type-check + vitest | 无 |
| **B** | WDWorkspace.vue 1129 行 script 抽 composables（`useVersionResolver`/`useChapterStatus`/`useAiMenu`/`useEditChapterModal`），template/style 不动 | 中（行为等价，安全网薄） | 逐 composable type-check + vitest + 手测主流程 | A |
| **C** | 「直接突变 vue-query 缓存」改 TanStack 三段式 `onMutate/onError/onSettled`（报告 425；范本 `queries/novel.ts:285-462`） | 中高（数据流+回滚） | 需补 mutation 测试 | 先 research 定位 |

> prd acceptance 第 4 项「5 大组件拆至 <500 行」需 B + template/style 拆分跨多次会话达成；本设计不一次性承诺。

## 本次会话：Slice A

### 等价性验证（已完成）

权威定义在 `frontend/src/utils/chapter.ts:47-92`。5 处副本逐行比对，**运行时行为 100% 等价**：

- 同样的 `if (!content) return ''` 早期返回
- 同样的 `JSON.parse` + `extractContent` 递归（同样 6 个 key：`content`/`chapter_content`/`chapter_text`/`text`/`body`/`story`）
- 同样的 catch 吞异常（注释文案差异不影响行为）
- 同样的 `replace(/^"|"$/g, '')` 剥离首尾引号
- 同样顺序的 4 个转义替换：`\\n→\n`、`\\"→"`、`\\t→\t`、`\\\\→\`

### 改动边界

| 文件 | 本地副本行 | 改法 |
|---|---|---|
| `views/WritingDesk.vue` | 633-678 | 在既有 chapter import 块（304-307）追加 `cleanVersionContent`，删本地副本 |
| `components/writing-desk/WDVersionDetailModal.vue` | 76-113 | 新增 `import { cleanVersionContent } from '@/utils/chapter'`，删本地副本 |
| `components/writing-desk/WDWorkspace.vue` | 668-705 | 同上 |
| `components/writing-desk/workspace/VersionSelector.vue` | 414-451 | 同上 |
| `components/writing-desk/workspace/ChapterContent.vue` | 358-395 | 同上 |

调用点（template `{{ cleanVersionContent(...) }}` 与 script 内调用）**不动**——删本地定义后解析到 import 的同名函数，行为等价。

### 不改动

- 不动 `ChapterGenerating.vue`（已正确 import，是范本）
- 不动 `utils/chapter.ts` 权威定义
- 不动任何调用点的参数与返回值消费方式
- 不触碰 Slice B/C 范围

### 验证

- `cd frontend && npx vue-tsc --noEmit`（类型，确保 import 解析、无重声明）
- `cd frontend && npx vitest run`（全量，确保无回归；重点关注 `uiAuditRegression` / `wdWorkspaceLockedChapter` / `chapterDraftFinalizeStatic`）

### 回滚

纯前端 5 文件改动，`git checkout -- <files>` 或 `git revert <commit>` 即可全量回滚，无数据/迁移影响。

## Slice B 设计：WDWorkspace composable 抽取

WDWorkspace.vue 共 2427 行（template 527 / script 1088 / style 812）。script 抽 4 个 composable，template/style **不动**。依赖链：`useVersionResolver`（依赖根）→ `useChapterStatus` / `useEditChapterModal` / `useAiMenu` 消费它。4 候选耦合较紧，按 implement.md「每抽完一个独立验证」节奏，**每会话只抽一个**。

### composable 契约（本次仅实现 editModal；余 3 个契约先行沉淀供后续会话）

| composable | 输入（依赖） | 输出（return） | template 引用 | 副作用 | 本次 |
|---|---|---|---|---|---|
| `useEditChapterModal` | `hasContent`/`resolvedContent`(versionResolver 的 computed)、`chapterNumber`(computed)、`onEditChapter`(emit 回调) | `showEditModal`/`editDialogRef`/`editCloseButtonRef`/`editDialogTitleId`/`editingContentInputId`/`editingContent`/`isSaving`/`editingWordCount`/`openEditModal`/`closeEditModal`/`saveEditedContent` | 模态框 440-524 + `openEditModal` 按钮(68) | 内部调 `useDialogA11y`（watch+onBeforeUnmount，setup 同步链合法） | ✅ |
| `useVersionResolver` | `selectedChapter`/`selectedChapterOutline`、props.availableVersions/selectedVersionIndex | `selectedChapterResolvedContent`/`selectedChapterForDisplay`/`hasSelectedChapterContent` + 4 个 resolve 纯函数 | 多处 `hasSelectedChapterContent`/`cleanVersionContent(...)` | 无 | ⏳ |
| `useChapterStatus` | versionResolver 全输出 + props.* | 18 个状态 computed/fn（label/tone/locked/toolbar/generating/failed...） | 状态标签/工具栏可见性/currentComponent | 无 | ⏳ |
| `useAiMenu` | chapterStatus.`isSelectedChapterGeneratingLike`、`isChapterContentView`、`bodyComponentRef`、props | `showAiMenu`/`aiMenu*` refs + 菜单键盘/focus/handle 函数 | AI 菜单 86-159 + handle 函数 | `onMounted`/`onUnmounted` 注册 outsideClick | ⏳ |

### 本次：useEditChapterModal 抽取

**等价性**：逐行复刻原 659-706，**含原 `saveEditedContent` 既有行为**——`emit('editChapter')` 后调 `closeEditModal()`，但此时 `isSaving=true` 使 `closeEditModal` 早返回，模态框在 `finally` 置 `isSaving=false` 后仍保持开启。此为原行为（疑 bug），重构**保持不改**，仅记录。

**TDZ 注意**：composable 调用同步求值，传入的 `hasSelectedChapterContent`/`selectedChapterResolvedContent` 必须已声明。二者定义在原 821/835，故解构调用**插在 835 `hasSelectedChapterContent` 定义之后**，不能放原 659 位。

**新增**：`frontend/src/composables/useEditChapterModal.ts`。**改动**：`WDWorkspace.vue`（删 useDialogA11y import → 加 useEditChapterModal import、删 659-706、插解构调用）。template/style 零改动。

### 验证
- `cd frontend && npx vue-tsc --noEmit`（类型 + 解构正确性）
- `cd frontend && npx vitest run`（mount 套件 wdWorkspaceLockedChapter/chapterDraftFinalizeStatic/uiAuditRegression 全绿 = 组件可正常渲染挂载）
- 编辑流程无专门 DOM 测试，靠逐行等价 + 手测「编辑草稿→改文→保存→emit editChapter」

### 回滚
`git checkout -- WDWorkspace.vue && rm composables/useEditChapterModal.ts`，无数据/迁移影响。

## Slice C research（2026-07-13 前置定位）

读 `queries/novel.ts` + 组件层缓存交互后的发现，**修正 Slice C 原始判断**：

### 1. 缓存交互已规范化（范本段是对的）

`useNovelMutationRefresh`(285-362) 辅助与各 mutation 已用**规范不可变 `setQueryData`**：
- `upsertChapterInProjectCache`(321-352)：函数式 setQueryData，`[...currentProject.chapters]` 浅拷贝 + 不可变更新，返回新对象。
- 各 mutation（create/import/converse/blueprint/delete）用 `onSuccess: setQueryData / invalidateQueries`。
- 组件层（AppShell/WorkspaceEntry/PasswordManagement）仅 `invalidateQueries`/`fetchQuery`/`clearAuthQueryCache`，无直接 setQueryData mutate。

### 2. 审计点名的「直接突变」反例 = 死代码

`upsertChapter(project, chapter)`（novel.ts:93-105）直接 `project.chapters.splice/push/sort` —— **rg 全 src 无调用点**，是被 `upsertChapterInProjectCache` 取代的死代码。按 CLAUDE.md「pre-existing dead code 不擅删」，本轮仅记录。

### 3. 真正缺失 = 乐观更新（增强，非 bug 修复）

**所有 mutation 用 `onSuccess`（等服务器确认才更新 UI），无 `onMutate`/`onError`/`onSettled` 三段式乐观更新。** 属体验增强空间，非正确性 bug。需逐 mutation 评估乐观价值（编辑章节/删除小说适合乐观；生成类流式不适合）。

### 下轮 Slice C 建议范围

- **(a) 删 `upsertChapter`(93-105) 死代码** —— 消除审计点名反例，surgical 零风险（无调用点），立即落地。
- **(b) 高交互 mutation 补三段式乐观更新**（`onMutate` 写快照 + `onError` 回滚 + `onSettled` 同步）—— 需补 mutation 测试，风险中，按需评估。

### Slice C (b) mutation 乐观更新评估（2026-07-13）

逐 mutation 评估三段式乐观价值：

| mutation | 现状 | 乐观价值 | 结论 |
|---|---|---|---|
| generate/evaluate/confirmFinalize/converse/generateOutline | 流式长任务，状态由 SSE/轮询推送 | 无 | 不适合（乐观与 SSE 状态竞争） |
| deleteNovels / deleteChapter | onSuccess setQueryData | 高（删除高交互，乐观移除列表项立即响应） | 最适合，需补回滚测试 |
| updateBlueprint / updateChapterOutline / editChapterContent | onSuccess setQueryData | 中（编辑类） | 可考虑 |
| create/import/saveBlueprint/analyzeEmotion/applyOptimization | onSuccess invalidate/setQueryData | 低 | 不适合 |

**结论**：乐观属体验增强（非正确性 bug）且是对外行为变化（UI 立即响应 vs 等服务器）。最适合的删除类需补回滚测试（删除失败恢复列表项），是独立工作。本会话不实现，按需评估后单独会话推进。

## Slice D 设计：WDWorkspace template 子组件抽取（2026-07-13 起）

Slice B 已抽 4 个 composable（script −447 行），但 template 525 / style 771 仍在原组件，WDWorkspace 1980 行。acceptance「5 大组件 <500 行」需继续拆 template/style。本 slice 把内聚的 template 块连同其 scoped style 抽成独立子组件，按风险递增每次一块。

> scoped 约束：Vue scoped style 带 data-v-xxx 属性，父组件 scoped CSS **不作用**于子组件内部元素，故每块的 style 必须随 template 迁移到子组件。

### 候选块契约表

| 子组件 | template 行 | style 行 | 耦合符号 | 风险 | 顺序 |
|---|---|---|---|---|---|
| **EditChapterModal** | 440-524 (~85) | 1599-1638 (~40) | useEditChapterModal 全部返回值 + `selectedChapterNumber`(props) | **低**（composable 已抽，唯一遗留是 template） | ✅ 1（已完成 2026-07-13） |
| **ChapterEvaluationPanel** | 300-434 (~135) | 1726-1843 (~118) | `parsedEvaluation`/`sortedEvaluationEntries`/`getEvaluationVersionNumber`/`parseMarkdown` + `selectedChapter.evaluation` + `evaluatingChapter`(props) | 中（4 符号纯展示逻辑，干净随迁；marked/DOMPurify import 随迁；`chapterDraftFinalizeStatic` 测试源码指针从 WDWorkspace 跟随至子组件） | ✅ 2（已完成 2026-07-14） |
| **ChapterVersionsPanel** | 250-298 (~49) | 1470-1529 (~60) | `previewVersionIndex`/`previewVersionParagraphs`/`previewVersionWordCount`/`selectVersionFromTab`/`isCurrentVersion` + watch×2 + activeTab 共享态 | 中（watch 1 拆分：activeTab 重置留父、previewIndex 重置迁子；selectVersionFromTab 末尾 `activeTab='content'` 改 emit `switchToContent`；`chapterDraftFinalizeStatic` 版本标签指针从 WDWorkspace 跟随至子组件） | ✅ 3（已完成 2026-07-14） |
| **ChapterMeta**（WorkspaceHeader 子块 a） | 8-36 (~29) | 868-992 + @media(940/640) + 末尾第二处 summary（共 ~165） | `chapterStatusLabel`/`chapterStatusTone`/`chapterInlineMeta`/`selectedChapterOutline`/`chapterTitleTooltipText`（均 props 传入）+ Tooltip 随迁；复制逻辑 `copyText`/`copySelectedChapterTitle`/`resetChapterTitleTooltip` 留父（toolbar 复制按钮共用）；父 Tooltip orphan import 清理 | 低（纯展示 + emit copyTitle/resetTitleTooltip，零业务逻辑） | ✅ 4a（已完成 2026-07-14） |
| **ChapterToolbar**（WorkspaceHeader 子块 b） | 37-162 (~125) | 849-1053 + keyframes + @media(1160/940/640)（共 ~290） | useAiMenu 全返回值随迁（`bodyComponentRef` 作 `Ref` prop 直传；isAiMenuDisabled/isChapterContentView computed 包装）；emit copyContent/openEditModal/confirmVersionSelection（复制逻辑 `copySelectedChapterContent` 留父、editModalRef 跨区 emit）；closeAiMenu watch(chapterNumber) 拆入子组件；ai-menu-panel 两处定义 + ink-menu-slide keyframes 随迁 | 高（bodyComponentRef 跨组件 Ref 直传、ai-menu focus trap + outsideClick onMounted 改绑子组件；补 useAiMenu.spec 13 项验证） | ✅ 4b（已完成 2026-07-14） |

核心动态分发（232-248 `<component :is="currentComponent">` + currentComponentProps 107 行数据装配）**不抽**，留组件。

### WDWorkspace 拆至 <500 的进度

| 阶段 | 行数 |
|---|---|
| Slice D 第 4b 块后 | 814 |
| Slice E 后 | 713 |
| Slice F 后（3dc9640 reader 音色过滤 revert 后基准 707） | **638** |

WorkspaceHeader 已整块抽完（4a ChapterMeta + 4b ChapterToolbar）。Slice E 抽出 currentComponentProps+draftTraceReplayProps，Slice F 抽出朗读胶水（见下）。仍 638>500，**还需约 138 行**，候选：

- tabs-row template ~33 行 + 其 scoped style ~59 行，可抽 `ChapterTabs` 子组件（activeTab 经 v-model 共享，tabs-row 容器 v-if=isFinalizedSuccessful 留父）。
- locked 前置 ~34 行 / formatDateTime+meta ~24 行，可并入 `useChapterStatus`（注意 lockedPrerequisiteChapterNumber/Title 同时被 useChapterBodyProps 消费，需 composable 间透传）。

具体边界在收尾会话定，届时补契约表。其余 4 大组件（PersonalModelRouting / ChapterGenerating / WritingDesk / NovelDetailShell）的拆分边界由各自 child 的 `design.md` 承载，不在本 design。

## Slice E 设计：抽 `useChapterBodyProps`（currentComponentProps + draftTraceReplayProps，2026-07-15）

Slice D 抽完 WorkspaceHeader 后 WDWorkspace 814 行。script 最大单块 = currentComponentProps（原 L548-655，~108 行数据装配）+ 同源 draftTraceReplayProps（原 L657-674，~18 行），二者均只喂 `v-bind`、零 DOM/副作用。抽入 composable `useChapterBodyProps.ts`。

### 边界

| 迁出符号 | 去向 |
|---|---|
| `currentComponentProps` computed | useChapterBodyProps（逐字搬迁） |
| `draftTraceReplayProps` computed | useChapterBodyProps（逐字搬迁） |
| `cleanVersionContent` import | 删（orphan，随 computed 迁入 composable 自行 import） |

### 入参契约（15 依赖）

props 子集（`BodyProps`：selectedChapterNumber/evaluatingChapter/generatingChapter/availableVersions/selectedVersionIndex/isSelectingVersion/chapterGenerationResult/project）+ selectedChapter/selectedChapterOutline/selectedChapterForDisplay/selectedChapterResolvedContent/hasSelectedChapterContent + readerCurrentParagraphIndex/End + lockedPrerequisiteChapterNumber/Title + isInProgressStatus/isGeneratingInFlight/isChapterFailed/isChapterEvaluationFailed/canGenerateChapter。

**利落点**：WDWorkspace 已把这些依赖解构成同名局部 const，composable 从 options 解构同名后，两个 computed 函数体**逐字不变**（零替换）。

**仅透传**：selectedChapterForDisplay / readerCurrentParagraphEnd / isInProgressStatus / isChapterFailed / isChapterEvaluationFailed / canGenerateChapter / lockedPrerequisiteChapterTitle 在父组件仅余 destructure/def + 透传给 composable（rg 确认无其他引用，非真 orphan，保留）。

### 测试指针跟随

`uiAuditRegression.spec.ts` L251-252 原断言 `workspaceSource.toContain('generationTraces: renderAsLocalGenerating')` + `('selectedChapter.value?.generation_traces ?? []')`——两字面量随 computed 迁入 composable，断言改读 `useChapterBodyProps.ts` 源码（同 Slice 7/8 范式 + 注释），并移除随之 orphan 的 `workspaceSource` 声明。`wdWorkspaceLockedChapter` reader 断言、`chapterDraftFinalizeStatic` 的 `ChapterGenerating` 断言不受影响（reader 未动 / ChapterGenerating 仍被引用）。

### 验证

vue-tsc 0 / 全量 vitest 141 绿 / eslint 0 新增（L159 `@/api/novel` warning 预存，HEAD 即有，非本次引入）。814→713（净 −101，diff 21 插入/130 删除 + 新建 composable 199 行）。

## Slice F 设计：抽 `useChapterReaderBar`（朗读胶水，2026-07-15）

Slice E 后 WDWorkspace 707 行（3dc9640 reader 音色过滤 revert 后基准）。朗读胶水（chapterReader 实例 + 11 别名 + browser 音色 VOICE_CN_LABEL/refresh/readerVoiceLabel/readerVoiceOptions + READER_RATE_OPTIONS + handleReaderStart/PlayPause/Reset + watch 切章停止 + onMounted/onUnmounted）是最大内聚 script 块，且 chapterReader 全程 reader-block-local（rg 确认仅 reader 块引用），整体抽入 composable `useChapterReaderBar.ts`。script-only，无 template/style 迁移。

### 边界

| 迁出符号 | 去向 |
|---|---|
| chapterReader 实例（useChapterReader()） | composable 内创建并返回 |
| 11 reader* 别名（readerStatus/readerCurrentParagraphIndex/End/readerParagraphCount/...） | composable 返回，父解构 |
| browserVoiceOptions/refreshBrowserVoices/VOICE_CN_LABEL/readerVoiceLabel | composable 内部（readerVoiceOptions 的依赖，不返回） |
| readerVoiceOptions computed / READER_RATE_OPTIONS const | composable 返回 |
| handleReaderStart/PlayPause/Reset | composable 返回 |
| watch(chapterNumber→stop) + onMounted(刷新音色+监听) + onUnmounted(摘监听+stop) | composable 内注册 |

### 入参契约（3 依赖）

`props`（子集 ReaderBarProps { selectedChapterNumber }，handleReaderStart 拼「第N章」标题 + watch 源）+ `selectedChapterOutline`（ComputedRef，标题兜底）+ `selectedChapterResolvedContent`（ComputedRef，朗读正文）。composable 返回 chapterReader 全实例 + 14 装配值 + 3 handler。

**生命周期归属**：onMounted/onUnmounted/watch 随 reader 胶水迁入 composable，在 WDWorkspace setup 同步调用 → 绑回 WDWorkspace 实例（ChapterReaderBar 在 WDWorkspace template 内），行为等价。同 useEditChapterModal 内 useDialogA11y（watch+onBeforeUnmount）范式。

**透传**：readerCurrentParagraphIndex/End 仍由父解构后透传 useChapterBodyProps（解构点在 useChapterBodyProps 调用之前，顺序正确）。

**注释调整**：原 watch 内 `// closeAiMenu 随 useAiMenu/ChapterToolbar 迁入子组件...` 引用父侧 ChapterToolbar 逻辑，在 composable 范围内无意义，改为 `// 切换章节时停止上一章朗读`（行为不变，仅注释贴合 composable 职责）。

### 测试指针跟随

`wdWorkspaceLockedChapter.spec.ts` 原 L395-403 读 WDWorkspace 源码断言 7 字面量（useChapterReader()/readerStatus.value==='playing'/'paused'/chapterReader.pause()/resume()/stop()/selectedChapterOutline.value?.title），全随 reader 胶水迁入 composable → readSource 改读 useChapterReaderBar.ts + 注释（同 Slice 7/8/E 范式）。useChapterReader.spec.ts 测的是 useChapterReader.ts 本体（未迁移），不受影响。

### 验证

vue-tsc 0 / 全量 vitest 141 绿（wdWorkspaceLockedChapter 10/10 + useChapterReader 22/22）/ eslint 0 新增（WDWorkspace L159 + spec L8 两处 @/api/novel warning 均预存）。707→638（净 −69，diff 27 插入/95 删除 + 新建 composable）。

### 本次：EditChapterModal 抽取

**边界**：composable `useEditChapterModal` **随 template 迁入子组件**（非留父组件传 ref）。理由：`useDialogA11y` 的 `watch(active, ..., {immediate})` + `onBeforeUnmount` 操作 `editDialogRef`/`editCloseButtonRef`，这些 DOM 在子组件内部，composable 必须在子组件 setup 同步调用才能正确绑定。父组件不再调 useEditChapterModal。

**输入适配**：composable 签名要 `ComputedRef`，子组件 props 是裸值。子组件内用 `computed(() => props.xxx)` 包装传入，**composable 文件零改动**，行为等价。

| 子组件 prop | 类型 | 来源（父） | composable 入参 |
|---|---|---|---|
| `hasContent` | boolean | `hasSelectedChapterContent` | hasContent |
| `resolvedContent` | string | `selectedChapterResolvedContent` | resolvedContent |
| `chapterNumber` | number \| null | `selectedChapterNumber`(props) | chapterNumber |

**打开机制**：子组件 `defineExpose({ openEditModal })`，父编辑草稿按钮 `@click="editModalRef?.openEditModal()"`。openEditModal 内部 hasContent 守卫 + 预填 editingContent 逻辑保留（按钮本身也有 `:disabled="!hasSelectedChapterContent"` 双重守卫）。

**输出**：子组件 `emit('editChapter', payload)`，父 `<EditChapterModal @edit-chapter="$emit('editChapter', $event)" />` 透传。

**style 迁移**：scoped `.m3-editor-dialog` / `.m3-editor-dialog__header` / `.m3-editor-dialog__footer` / `.md-textarea` / `.md-textarea:focus`（1599-1638）整体搬到子组件。`.md-textarea` 在 WDWorkspace template 仅编辑框一处使用，迁移安全。

**等价性**：逐行复刻 template 440-524；composable 调用从父 setup 迁到子 setup（输入 computed 包装、useDialogA11y 子组件 setup 同步调用，focus trap / body scroll lock / Esc 关闭行为不变）。

### 验证

- `cd frontend && npx vue-tsc --noEmit`（类型 + ref/expose 正确性）
- `cd frontend && npx vitest run`（wdWorkspaceLockedChapter/chapterDraftFinalizeStatic/uiAuditRegression 全绿 = 挂载正常）
- 编辑流程靠逐行等价 + 手测「编辑草稿→改文→保存→emit editChapter→Esc/点遮罩关闭→焦点回归」

### 回滚

`git checkout -- WDWorkspace.vue && rm components/writing-desk/workspace/EditChapterModal.vue`，无数据/迁移影响。

### 后续块（本次不做）

- ChapterEvaluationPanel：纯展示子组件，props 收 `evaluation: string` + `evaluatingChapter`，内部重算 parsedEvaluation/sortedEvaluationEntries/parseMarkdown。收益最大（~251 行）但 marked 版本兼容分支需整迁。
- ChapterVersionsPanel / WorkspaceHeader：见契约表，按风险递增跨会话推进。

