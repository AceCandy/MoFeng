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
