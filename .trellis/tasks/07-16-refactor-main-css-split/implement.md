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


## Phase 2 完成（2026-07-17）

Slice 2-4 抽基础元素，每 slice 四件套绿 + commit + push：
- Slice 2 `32ac0e9`：buttons（L418-609，195 行）-> elements/buttons.css
- Slice 3 `0766a8f`：forms（L610-764，155 行）-> elements/forms.css
- Slice 4 `1193e58`：navigation（L765-970，206 行）-> elements/navigation.css

main.css 4711 -> 4159。


## Phase 3 完成（2026-07-17）

Slice 5-23 抽组件域，每 slice 四件套绿 + commit + push。main.css 4159 -> 34（仅入口 + 31 @import + @plugin）。

| Slice | commit | 域 | partial | 行数 |
|---|---|---|---|---|
| 5 | ac12e0e | Chips+朱砂印章 | components/chips.css | 135 |
| 6 | 466c17a | Material3 组件×9（Dialog/List/.../Ripple） | components/material3-components.css | 381 |
| 7 | 2dfa37b | Utility Classes | components/utility.css | 57 |
| 8 | 1a1f136 | App Shell（主域+响应式覆写段补抽） | components/app-shell.css | 516 |
| 9 | f6165e5 | Admin Domain Panels | components/admin-panels.css | 261 |
| 10 | b174845 | 散小域×6（Animations/Prose/Loading/Chat/Legacy/LayerBase） | components/misc-base.css | 174 |
| 11 | b1489ca | 章节纸张 chapter-paper（+2 dark） | components/chapter-paper.css | 99 |
| 12 | 070490b | Naive UI 水墨魔改 | components/naive-ui-ink.css | 304 |
| 13 | fe21efb | 朱批+水墨太极（删第二阶段总注释） | components/annotation.css | 124 |
| 14 | 5ce84cf | 第三阶段子1+2（大背景+目录穿线，+dark） | background-art.css + chapter-binding.css | 30+70 |
| 15 | 461df24 | 第三阶段子3+4+5（折页+助手面板+屏风，+dark） | paper-fold.css + assistant-shell.css | 83+75 |
| 16 | 6d3a803 | 第三阶段子6+7（气旋动画+Header LOGO，+dark，删总注释） | components/motion-brand.css | 79 |
| 17 | 1b28862 | 第四阶段品牌重构（+14 dark） | components/brand-visuals.css | 278 |
| 18 | 86260e6 | Phase 5 导航重构（+13 dark，最大域 568 行） | components/phase5-navigation.css | 568 |
| 19 | fa0f2d7 | Phase 5 窄屏 + Phase 8 顶栏（+2 dark） | phase5-responsive.css + topbar.css | 71+62 |
| 20 | 33e9882 | Phase 9 用户标签（+7 dark） | components/user-tag.css | 213 |
| 21 | ef3c88c | Modal Adapters + 模型设置弹窗 | modal-adapters.css + settings-modal.css | 98+152 |
| 22 | ab49760 | 尾部4域（Phase12存字/滚动条/弹窗金石/Select，+dark） | phase12-save-stamp/scrollbar/modal-decor/select-styling | 41+97+18+21 |
| 23 | 285ba7d | Base+Typography（@import 最后保持 unlayered cascade）+ readCssBlock lookbehind 修复 | styles/base.css | 153 |

**关键决策**：
- dark 覆写随域迁移（设计契约表 §4 策略），每 slice rg 核对 dark 在域内。
- App Shell 响应式覆写段（L430-549）补抽到 app-shell.css（原夹在 Admin 域中间，纯 app-shell 选择器）。
- 阶段总注释（第二/三阶段）在最后子域抽走时删除（不进 partial）。
- base.css @import 放最后（partials 后，@plugin 前），unlayered cascade 等价原 main.css（Base+Typography 在 partials 后）。
- readCssBlock 正则加 `(?<![\w-])` lookbehind，修复 selector='body' 误匹配 '.n-spin-body' 子串（因 base.css @import 在 annotation 后，.n-spin-body 在内联文本先于 body）。

**最终状态**：main.css 34 行（AIMETA + 31 @import + @plugin）+ 30 个 partial（1 base + 3 elements + 26 components + 1 tokens，共 4954 行）。main.css 4966 -> 34（减 99.3%）。

**AC 达成**：1/2/3/4/6 ✓；5 manual-checklist 固化 + 手测待跑。


## Phase 3 真机验证（AC 5）

2026-07-17 用 agent-browser@0.32.0 对 6100 dev server 做真机视觉等价验证：

- 登录页 light：宣纸米黄底 + 水墨山水 + 书法标题 + 衬线字体，无破损。
- workspace light/dark：app-shell/card 域等价，`--md-background` #f2ece0↔#15191b 正确切换。
- 写作台 light/dark：chapter-paper / naive-ui-ink / annotation 域等价，朱砂印章 dark 下正常。
- 375px 窄屏响应式：顶栏折叠 + 卡片单列堆叠，无溢出（App Shell 响应式覆写段补抽正确迁移）。
- typography token：`--md-font-family` 正确解析（spec 红线 "keeps typography roles centralized in design tokens"）。
- dark token cascade：`--md-on-background` #1c2224↔#e5dec9、body color 正确切换，证明 dark 覆写随域迁移后 cascade 等价。

结论：6 项 AC 全部达成，无视觉回归。截图为临时调试产物（/tmp/mofeng-shots/，不入仓）。
