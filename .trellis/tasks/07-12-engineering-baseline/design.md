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

