# implement.md - main.css 按域拆分（#28）

## Phase 1 - Slice 1：抽 design token + 验证链路

**目标**：抽 L14-267 token 到 `styles/tokens.css`，落地 readGlobalCss helper，修订 3 处 spec，验证 Tailwind v4 + Lightning CSS + 测试 + spec 四条链路通。

### 步骤

1. **建 tokens.css** -> verify: 文件存在，含 `:root, :root[data-theme='light']` + `[data-theme='dark']` token 定义，与 main.css L14-267 逐字一致
   - 路径 `frontend/src/assets/styles/tokens.css`
   - 迁 L14-267（含 L263-267 的 `:root {}` 块）；L6-13 的 `====` 分隔注释留 main.css 入口或随迁（保留注释上下文）
2. **main.css 入口化** -> verify: main.css 仅保留 AIMETA + `@import 'tailwindcss'` + `@plugin` + `@import './styles/tokens.css'`，L14-267 已删
   - 用 python 原子替换（assert count==1）
3. **写 readGlobalCss helper** -> verify: helper 递归解析相对 @import，返回并集文本
   - `uiAuditRegression.spec.ts` 顶部新增 `readGlobalCss()`
   - 决定：内联两份 vs 共享 `src/components/__tests__/readGlobalCss.ts`（Slice 1 选共享，responsive.spec.ts 也 import）
4. **替换 9 处 readSource** -> verify: rg `readSource\('src/assets/main.css'` 零残留
   - uiAuditRegression.spec.ts 8 处 -> `readGlobalCss()`
   - responsive.spec.ts:56 `readFileSync(...)` -> `readGlobalCss()`
5. **helper 单测** -> verify: readGlobalCss() 含 `--md-primary` 等 token + 不含未解析 `@import './` 残留
   - 新增 `readGlobalCss.spec.ts` 或并入 uiAuditRegression
6. **修订 frontend spec 3 处** -> verify: rg 确认 3 处已改
   - component-guidelines.md:111 / index.md:42 / quality-guidelines.md:36-43
7. **三件套 + 构建验证** -> verify: vue-tsc 0 / vitest 全绿 / eslint 0 新增 / vite build 产物含 token
   - `cd frontend && npx vue-tsc --noEmit`
   - `cd frontend && npx vitest run`
   - `cd frontend && npx eslint src/components/__tests__/ src/constants/__tests__/`
   - `cd frontend && npx vite build`（确认产物 CSS 含 token 变量，无丢失）

### 回滚点

- 每 step 独立可 revert；Step 7 任一验证失败 -> revert main.css 改动 + 删 tokens.css + 还原 helper/readSource + revert spec，回到 Phase 0。
- commit 粒度：Slice 1 整体一个 commit（token + helper + 测试 + spec 同步，语义内聚）。

### commit message

```
refactor(frontend): 抽 main.css design token 至 tokens.css 并落地 readGlobalCss（#28 Phase 1）
```

## Phase 2 - 基础元素抽取（Slice 2-4，Phase 1 绿后细化）

- Slice 2: buttons（L418-609）-> `styles/elements/buttons.css`
- Slice 3: forms（L610-764）-> `styles/elements/forms.css`
- Slice 4: navigation（L765-970）-> `styles/elements/navigation.css`
- 每 slice：迁域 + main.css 加 @import + 三件套绿 + 视觉手测按钮/表单/导航
- dark 覆写随域迁移（rg 核对）

## Phase 3 - 组件域抽取（Slice 5+，Phase 2 绿后细化）

按 design §3 契约表聚类，每 1-2 域一个 slice：
- chapter-paper / scrollbar / annotation / background-art / chapter-binding / paper-fold / assistant-shell / motion-brand / immersive-layout（最大域 567 行，必要时再拆）/ topbar / progress-bar / user-tag / settings-modal / root-layout / password-change

每 slice：迁域 + main.css @import + 三件套绿 + light/dark 手测。**dark 覆写随域迁移是每 slice 必查项**。

## 全局验证清单（每 slice 必跑）

- `cd frontend && npx vue-tsc --noEmit` exit 0
- `cd frontend && npx vitest run` 全绿
- `cd frontend && npx eslint <改动文件>` 0 新增 error
- rg 确认迁出域在 main.css 零残留 + partial 文件含完整域（含 dark 覆写）
- CSS 大括号配平（python 计数）

## 收口（Phase 3 完成）

- main.css 本体仅入口 + @import 聚合
- 勾 prd AC 6 项
- manual-checklist.md 固化 light/dark + 关键页面手测项
- finish-work 归档


## Phase 1 状态（2026-07-16 暂停）

Phase 1 改动完成并 commit：
- `tokens.css` 抽出（257 行）+ `main.css` 入口化（4966 -> 4711）
- `readGlobalCss` helper（递归内联相对 @import partial）+ 9 处 `readSource('src/assets/main.css')` 替换 + `readGlobalCss.spec.ts` 单测
- frontend spec 3 处修订（component-guidelines:111 / index:42 / quality-guidelines:36-43）

验证：vitest **152 绿**（+1 新测试）/ eslint **0 error**（改动文件）/ vue-tsc **0 新增**（git stash 验证 34 pre-existing 前后不变）。

**暂停原因**：vite build 失败（pre-existing，`Could not resolve "./FeedbackPanel"`，git stash 验证非 #28 引起）+ vue-tsc 34 pre-existing error（PMR/ProviderCard/NovelDetailShell/WDWorkspace/ChapterPipeline/useChapterReader）+ main.css `:global()` warning（L4707-4708）。基线破损阻塞 #28 AC「三件套绿」「行为等价（构建产物等价）」，并暴露历史 PMR/NovelDetailShell/WDWorkspace 收口「三件套绿」假绿（vue-tsc 漏 cd 跑全局 tsc help exit 0 误判 + 三件套从未含 build）。

**后续**：基线修复任务（P0）完成后 `task.py start` 续 #28 Phase 2。
