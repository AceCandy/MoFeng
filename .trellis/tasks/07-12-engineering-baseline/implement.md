# #22 执行计划

## Slice A — cleanVersionContent 去重（本次会话）

按 `design.md` 表逐文件执行。每文件：① 删本地副本函数；② 保证有 `import { cleanVersionContent } from '@/utils/chapter'`（WritingDesk 追加到既有块，其余 4 文件新增）。

- [x] `views/WritingDesk.vue` — 删 633-678 副本，import 块（304-307）加 `cleanVersionContent`
- [x] `components/writing-desk/WDVersionDetailModal.vue` — 删 76-113 副本，新增 import
- [x] `components/writing-desk/WDWorkspace.vue` — 删 668-705 副本，新增 import
- [x] `components/writing-desk/workspace/VersionSelector.vue` — 删 414-451 副本，新增 import
- [x] `components/writing-desk/workspace/ChapterContent.vue` — 删 358-395 副本，新增 import
- [x] 复核：`rg 'const cleanVersionContent' frontend/src` → 0 处本地定义（仅剩 `cleanVersionContentStr` 局部变量，含子串）
- [x] 验证：`cd frontend && npx vue-tsc --noEmit` → exit 0
- [x] 验证：`cd frontend && npx vitest run` → 120/120 绿
- [x] 独立复核：diff +5/−204、ESLint 0 error（7 warning 均 pre-existing）、无双空行、无 unused import

### 回滚点

每个文件改完即可单独 `git checkout -- <file>` 回退。全部改完跑验证，若 vitest 红，先定位是哪文件的 import/调用受影响再决定整体 revert 还是单文件修。

## Slice B — WDWorkspace composable 抽取

按 `design.md` 契约，每会话抽一个、独立验证。实际顺序按「边界独立度」而非原编号——editModal 最干净先做；versionResolver 是依赖根其次；chapterStatus 最分散；aiMenu 混工具函数最后。

- [x] **`useEditChapterModal`**（2026-07-13）：抽出原 659-706 编辑模态框块 → `composables/useEditChapterModal.ts`（90 行）。WDWorkspace 净 −31 行。逐行等价（含原 `saveEditedContent` 的 isSaving 阻断时序，未顺手修）。解构调用插在 `hasSelectedChapterContent`（原 835）之后规避 TDZ。验证：vue-tsc exit0 / vitest 120 绿 / eslint 0 新增（2 warning 均 pre-existing）。
- [x] **`useVersionResolver`**（2026-07-13）：抽出原 676-788 版本解析块（4 个 resolve 纯函数 + 3 个 computed）→ `composables/useVersionResolver.ts`（145 行）。`selectedChapter`/`selectedChapterOutline` 作为输入保留组件（职责=选中哪个章节，非解析正文）。4 个 resolve 纯函数仅内部互调，只 return 3 个 computed（比 design.md 契约更干净，去除未用暴露）。解构调用插在 `selectedChapterOutline` 之后规避 TDZ。验证：vue-tsc RC=0 / vitest 120 绿。
- [x] **`useAiMenu`**（2026-07-13）：抽出 AI 菜单状态(原 591-596) + 键盘/聚焦/开关(原 1012-1109) + 内容优化 handler(原 1122-1173) + onMounted/onUnmounted 的 click 监听 → `composables/useAiMenu.ts`（214 行）。`onMounted`/`onUnmounted` 拆分：click 监听进 composable，voices/chapterReader 留组件（Vue 支持多个生命周期钩子）。`ChapterContentExpose` 用结构同构的 `BodyComponentExpose` 内联类型（不动组件接口位置）。`nextTick` 随 toggleAiMenu 移走、组件不再用已删 import。return 15 值。验证：vue-tsc RC=0 / vitest 120 绿 / eslint 0 新增（2 warning 均 pre-existing）。
- [x] **`useChapterStatus`**（2026-07-13）：抽出状态判定 + 组件分发（原 824-835 / 837-872 / 899-1005 三段不连续子区）→ `composables/useChapterStatus.ts`（215 行）。边界取舍：`currentComponentProps`（107 行数据装配，耦合朗读 ref + 锁定前置 + selectedChapterForDisplay）留组件，composable 只负责「判定 + 分发」。输入 6 项（props 子集 + selectedChapter + hasSelectedChapterContent + lockedPrerequisiteChapterNumber + isFinalizedSuccessful + isDraftWaitingConfirm），return 15 项（含 isInProgressStatus/isChapterFailed/isChapterEvaluationFailed/canGenerateChapter/isGeneratingInFlight，供 currentComponentProps 解构消费）。解构调用插在 lockedPrerequisiteChapterTitle 之后规避 TDZ。清理 5 个 orphan .vue import（WorkspaceInitial/VersionSelector/ChapterContent/ChapterFailed/ChapterEmpty，原仅 currentComponent 引用）。修复 Edit 引入的 `}`→`})`（lockedPrerequisiteChapterTitle computed 闭合，eslint parser 抓到、vue-tsc 容忍）。WDWorkspace 2118→1980（−138）。同步更新 chapterDraftFinalizeStatic.spec.ts 的 finalizing 字符串断言指向 composable。验证：vue-tsc RC=0 / vitest 120 绿 / eslint 0 新增（1 warning pre-existing @/api/novel）。

`design.md` Slice B 契约表已沉淀 4 个 composable 的输入/输出/template 引用/副作用。后续会话直接按契约抽取，无需重新分析。

## Slice C — 乐观更新规范化

- [x] **(a) 删 `upsertChapter`(novel.ts:93-105) 死代码**（2026-07-13）：rg 全 src 无调用点，被 `upsertChapterInProjectCache` 取代。surgical 删除，消除审计点名反例。验证：vue-tsc RC=0 / vitest 120 绿。
- [ ] **(b) 高交互 mutation 三段式乐观更新**（评估完成，实现按需）：逐 mutation 评估见 `design.md` Slice C (b)。删除类（deleteNovels/deleteChapter）最适合但需补回滚测试；生成/评审类不适合（与 SSE 状态竞争）。属对外行为增强，单独会话推进。

## Slice D — WDWorkspace template 子组件抽取（2026-07-13 起）

Slice B 抽完 composable 后 template/style 仍在原组件。本 slice 把内聚 template 块 + 其 scoped style 抽成子组件，按 `design.md` Slice D 契约表风险递增每次一块。

- [x] **`EditChapterModal`**（2026-07-13）：本次。composable useEditChapterModal 随 template 迁入子组件（useDialogA11y 在子 setup 同步调用），父按钮 ref 调 openEditModal。详见 `design.md` Slice D。
  - [x] 新建 `components/writing-desk/workspace/EditChapterModal.vue`（174 行）：template 搬 440-524（selectedChapterNumber→chapterNumber props），style 搬 1599-1638，内部调 useEditChapterModal（输入 computed(()=>props.xxx) 包装），defineExpose({ openEditModal })，emit editChapter，补 AIMETA 首行（同 workspace 子组件惯例）
  - [x] WDWorkspace：template 440-524 替换为 `<EditChapterModal ref="editModalRef" :has-content :resolved-content :chapter-number @edit-chapter>`
  - [x] WDWorkspace：删 style 1599-1638（.m3-editor-dialog*/.md-textarea*）
  - [x] WDWorkspace：删 script destructure 678-695 + useEditChapterModal import(534)；加 EditChapterModal import + `editModalRef`
  - [x] WDWorkspace：编辑草稿按钮(68) `@click="openEditModal"` → `@click="editModalRef?.openEditModal()"`
  - [x] 验证：vue-tsc RC=0 / vitest 120 绿（chapterDraftFinalizeStatic 8 / wdWorkspaceLockedChapter 10 / uiAuditRegression 34）/ eslint 0 新增（1 warning pre-existing @/api/novel）/ diff 复核 6 处改动精确等价。WDWorkspace 1980→1844（−136）

### 回滚点

子组件新建 + WDWorkspace 改造分离。若 vitest 红，先 `git checkout -- WDWorkspace.vue && rm EditChapterModal.vue` 全量回退，再定位。
