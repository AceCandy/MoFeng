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

## Slice B — WDWorkspace composable 抽取（后续会话）

顺序（每抽完一个独立验证）：
1. `useVersionResolver`（版本解析，WDWorkspace 764-878）
2. `useChapterStatus`（章节状态判定，954-1143）
3. `useAiMenu`（AI 菜单键盘交互，1184-1345）
4. `useEditChapterModal`（编辑 modal，659-746，配合已有 `WDEditChapterModal.vue`）

需补 `design.md` 的 props/emits 契约与每个 composable 的输入输出清单后再 start。

## Slice C — 乐观更新规范化（后续会话）

前置 research：定位「直接突变 vue-query 缓存对象」的具体 mutation（字面量扫描无 `optimistic` 命名，需查 mutation 定义）。范本 `queries/novel.ts:285-462`。需补 mutation 测试后再改。
