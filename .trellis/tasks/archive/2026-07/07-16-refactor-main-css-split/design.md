# design.md — main.css 按域拆分（#28）

## 1. 分阶段策略

按「最小步、可回滚、可验证」推进，每阶段独立 commit + 三件套绿。**Phase 1 验证链路通后才进 Phase 2/3**。

| 阶段 | 范围 | 目标 | 验证 |
|---|---|---|---|
| Phase 1 | 抽 design token（L14-267） | 验证 Tailwind v4 + Lightning CSS @import 内联 / readGlobalCss helper / spec 修订 三条链路通 | build 产物含 token + 三件套绿 + helper 单测 |
| Phase 2 | 抽基础元素（buttons / forms / navigation） | 基础元素样式独立 | 三件套绿 + 视觉等价 |
| Phase 3 | 按组件域拆（章节纸张/滚动条/朱批/目录穿线/三折线/助手面板/多宝阁/Header LOGO/大背景/全屏沉浸/写作进度条/用户名/模型设置/根容器/改密…） | 组件域样式按功能聚类独立 | 三件套绿 + light/dark 手测 |

Phase 2/3 的具体 slice 划分在 Phase 1 绿后于 `implement.md` 细化，本 design 给聚类方向。

## 2. 目标目录结构

```
src/assets/
  main.css              # 入口：AIMETA + @import 'tailwindcss' + @plugin + @import './styles/*' 聚合
  base.css              # dead compat shim，不变
  blueprint.css         # 不变
  styles/
    tokens.css          # Phase 1: 设计 token（:root / [data-theme='light'] / [data-theme='dark']）
    elements/
      buttons.css       # Phase 2: L418-609 Buttons（Filled/Outlined/Text/Tonal/Elevated/Icon/FAB）
      forms.css         # Phase 2: L610-764 双线框/卡片/Text Field/Textarea
      navigation.css    # Phase 2: L765-970 朱印/Navigation Drawer/Top App Bar/Tabs
    components/
      chapter-paper.css # Phase 3: L2495-2593 章节阅读纸张
      scrollbar.css     # Phase 3: L2594-2896 水墨滚动条 + L4831-4927 滚动条变量
      ...               # Phase 3 按域聚类，Slice 细化时定名
```

`main.ts:4` `import './assets/main.css'` 不变。main.css 本体仅保留入口 + @import 聚合。

## 3. 拆分边界契约表（Phase 1 + Phase 2 明确，Phase 3 聚类方向）

| main.css 行范围 | 内容 | 目标文件 | 阶段 |
|---|---|---|---|
| L1-5 | AIMETA + `@import 'tailwindcss'` + `@plugin` | 留 main.css（入口） | - |
| L14-267 | 设计 Token（light/dark/宽屏） | `styles/tokens.css` | P1 |
| L268-414 | 背景纸质微弱墨晕 | `styles/background.css` 或并入 elements | P2/P3 |
| L418-609 | Buttons | `styles/elements/buttons.css` | P2 |
| L610-764 | 双线框/卡片/Text Field/Textarea | `styles/elements/forms.css` | P2 |
| L765-970 | 朱印/Navigation/Top App Bar/Tabs | `styles/elements/navigation.css` | P2 |
| L971-2494 | 印章/触控热区/各类组件小域 | 按 components 聚类 | P3 |
| L2495-2593 | 章节阅读纸张 | `styles/components/chapter-paper.css` | P3 |
| L2594-2896 | 全局水墨滚动条 | `styles/components/scrollbar.css` | P3 |
| L2897-3019 | 古典朱批对白 | `styles/components/annotation.css` | P3 |
| L3020-3052 | 空灵山水 SVG | `styles/components/background-art.css` | P3 |
| L3053-3120 | 章节目录穿线 | `styles/components/chapter-binding.css` | P3 |
| L3121-3202 | 物理三折线效果 | `styles/components/paper-fold.css` | P3 |
| L3203-3276 | 助手面板壳/多宝阁 | `styles/components/assistant-shell.css` | P3 |
| L3277-3354 | 按钮动效/Header LOGO | `styles/components/motion-brand.css` | P3 |
| L3355-3631 | 大背景 SVG | `styles/components/background-art.css` | P3 |
| L3632-4198 | 全屏沉浸适配（最大域 567 行） | `styles/components/immersive-layout.css`（必要时再拆） | P3 |
| L4199-4268 | 顶栏 flex 间距 | `styles/components/topbar.css` | P3 |
| L4269-4329 | 写作进度条 | `styles/components/progress-bar.css` | P3 |
| L4330-4541 | 用户名标签触发器 | `styles/components/user-tag.css` | P3 |
| L4542-4638 | 模型设置弹窗自适应 | `styles/components/settings-modal.css` | P3 |
| L4639-4789 | 根容器自适应 | `styles/components/root-layout.css` | P3 |
| L4790-4830 | （待识别域） | 随相邻域归类 | P3 |
| L4831-4927 | 滚动条 CSS 变量 | `styles/components/scrollbar.css` | P3 |
| L4928-4966 | 改密昼夜黛绿印 | `styles/components/password-change.css` | P3 |

## 4. dark theme 覆写跟随策略

dark 覆写分散全文件（L187-L4964 几十处 `[data-theme='dark']`）。**不集中到单独 dark 文件**，而是跟随其所属域迁移：

- token 的 dark 覆写（L187-262）随 token 进 `tokens.css`。
- 组件域的 dark 覆写（如 L2521 章节纸张 dark、L3632-4198 全屏沉浸内大量 dark 覆写）随该域进对应 `components/*.css`。
- 每域拆分时用 `rg -n "\[data-theme='dark'\]"` 在该行范围内核对，确保 dark 覆写随域迁移不漏。

## 5. 测试适配方案（readGlobalCss helper）

现有 helper（`uiAuditRegression.spec.ts:9-39`）：`readSource(path)` 读单文件；`readCssBlock/readCssCustomProperty/readLightThemeCustomProperty` 接收 source 文本提取。

新增 `readGlobalCss()`：读 main.css + 递归解析相对 `@import './xxx.css'` partial，返回并集文本（@import 语句被 partial 内容替换）。

```ts
const readGlobalCss = (): string => {
  const main = readSource('src/assets/main.css')
  const importRe = /@import\s+(['"])(\.{1,2}\/[^'"]+\.css)\1\s*;/g
  const parts: string[] = []
  let last = 0
  let m: RegExpExecArray | null
  while ((m = importRe.exec(main))) {
    parts.push(main.slice(last, m.index))
    const resolved = resolve(process.cwd(), 'src/assets', m[2])
    parts.push(readFileSync(resolved, 'utf8'))
    last = m.index + m[0].length
  }
  parts.push(main.slice(last))
  return parts.join('\n')
}
```

要点：
- 正则 `(\.{1,2}\/[^'"]+\.css)` 只匹配相对路径（`./`/`../`），**排除 `@import 'tailwindcss'`**（非相对路径，Tailwind 自处理）。
- 替换 9 处 `readSource('src/assets/main.css')` 为 `readGlobalCss()`：uiAuditRegression 8 处 + responsive 1 处（responsive.spec.ts:56 独立 readFileSync，改调 readGlobalCss 或导出共享）。
- 「不含」禁令断言用并集 -> 覆盖所有 partial，**消除假绿**。
- 「含」断言（readCssBlock/readCssCustomProperty/readLightThemeCustomProperty）入参改 `readGlobalCss()` 返回值。
- helper 单测：断言 readGlobalCss() 含某 token 变量 + 不含未解析的 `@import './` 残留。

responsive.spec.ts 的 helper 独立，考虑把 readGlobalCss 提到共享 `src/components/__tests__/readGlobalCss.ts` 或内联两份（两处用例少，内联可接受；共享更 DRY，Slice 1 定）。

## 6. spec 修订清单（Phase 1 同步）

| 文件 | 现状 | 改为 |
|---|---|---|
| `frontend/component-guidelines.md:111` | "Adding global styles outside `main.css` (or `App.vue`'s scoped toast block)." 是反模式 | 全局样式经 main.css 入口 `@import` 聚合，partial 按域组织在 `src/assets/styles/`（tokens/elements/components）；新增全局样式进对应 partial 经 main.css 聚合，不得散落到组件外或不经入口 |
| `frontend/index.md:42` | "real tokens live in `main.css`." | "real tokens live in `src/assets/styles/tokens.css` (imported by `main.css`)." |
| `frontend/quality-guidelines.md:36-43` | main.css 含 `@import 'tailwindcss'` + `@plugin` | 补充：main.css 同时 `@import` 聚合 `./styles/*` partial；全局样式按域拆分在 `src/assets/styles/`，main.css 仅作入口 |

## 7. Tailwind v4 + Lightning CSS @import 处理

- Tailwind v4 用 Lightning CSS，CSS 标准 `@import` 内联到产物。
- `@import` 必须在文件顶部（CSS 规范：@import 前只能有 @charset/@layer）。main.css 顺序：
  ```css
  /* AIMETA */
  @import 'tailwindcss';
  @plugin "@tailwindcss/typography";
  @import './styles/tokens.css';
  @import './styles/elements/buttons.css';
  /* ... */
  ```
  - `@import 'tailwindcss'` 最前；`@plugin` 非 @import 位置灵活但紧跟；自定义 partial @import 随后。
- 验证：Phase 1 落地后跑 `vite build`，确认产物 CSS 含 token + 样式无丢失（diff 产物前后）。

## 8. 风险 + 回滚

| 风险 | 影响 | 缓解 | 回滚 |
|---|---|---|---|
| R1 Lightning CSS @import 顺序/内联异常 | 构建失败或样式丢失 | Phase 1 先验证 build + 产物 diff | revert main.css + 删 tokens.css |
| R2 readGlobalCss 递归解析错误 | 断言失败/假绿 | helper 单测覆盖（含 token + 无 @import 残留） | revert helper + readSource 还原 |
| R3 dark 覆写漏迁 | light/dark 视觉差异 | 每域 rg 核对 + 手测 light/dark | revert 该域 slice |
| R4 spec 修订与拆分不同步 | spec 误导 | Phase 1 同步修订 3 处 spec | revert spec |
| R5 @import 顺序导致 cascade 改变 | 样式优先级变化 | 产物 CSS diff 核对 cascade | revert |

每 phase 独立 commit，`git revert <commit>` 即回滚单 phase。main.css 始终保留为入口，main.ts 不变，保证回滚后入口可用。
