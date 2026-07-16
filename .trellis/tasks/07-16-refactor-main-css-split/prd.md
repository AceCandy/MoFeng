# main.css 按域拆分（#28）

## Goal

将 `frontend/src/assets/main.css`（4966 行巨石）按域拆分为入口 + partial 文件，解锁 parent `07-12-brand-consistency` acceptance「设计 token 落地：main.css 按域拆分」（prd L16）。保留 Tailwind v4 入口语义，测试审计红线不失效，frontend spec 同步修订。分阶段推进，每阶段可独立验证 + 回滚。

## 现状

- 路径：`frontend/src/assets/main.css`，4966 行，~30 个 `====` 域。
- 入口：`frontend/src/main.ts:4` `import './assets/main.css'`（唯一入口）；`base.css` 是 dead compat shim（2 行）。
- Tailwind v4：`main.css:2` `@import 'tailwindcss';` + `:4` `@plugin "@tailwindcss/typography";`（CSS-first 配置入口）。
- 结构：L1-5 Tailwind 入口；L6-267 设计 Token（`:root` / `[data-theme='light']` / `[data-theme='dark']`）；L268-4140 基础元素 + 组件域；L4141+ 组件域。**dark theme 覆写分散全文件**（L187-L4964 几十处 `[data-theme='dark']`，与组件样式交织）。
- 测试硬依赖：`uiAuditRegression.spec.ts` 8 处 + `responsive.spec.ts` 1 处 `readSource('src/assets/main.css')`。含两类断言：
  - 「不含」禁令（`transition-all` / `backdrop-filter` / `background-clip: text` / data-url / modal 禁令）--拆分后读残壳会**假绿**（审计红线静默失效）。
  - 「含」断言（`readCssBlock` / `readCssCustomProperty` / `.app-shell__bottom-tabs`）--拆分后读不到会真红。
- spec 冲突：`frontend/component-guidelines.md:111`「Adding global styles outside main.css」是反模式红线；`index.md:42` + `quality-guidelines.md:36` 锁定 main.css 为唯一全局样式入口。**拆分直接违反，须先修订 3 处 spec**。

## Requirements

- 分阶段拆分：Phase 1 抽 design token 验证链路 -> Phase 2 抽基础元素 -> Phase 3+ 按组件域拆。每阶段独立 commit + 三件套绿。
- 入口语义保留：`main.css` 保留为 `main.ts` 入口，内含 `@import 'tailwindcss'` + `@plugin` + `@import './partials/*'` 聚合；`main.ts` 不变。
- 测试红线不失效：新增 `readGlobalCss()` helper（读 main.css + 递归 @import partial 并集），替换 9 处 `readSource('src/assets/main.css')`。「不含」禁令断言覆盖所有 partial（消除假绿），「含」断言从并集读取。
- spec 同步修订：`component-guidelines.md:111` + `index.md:42` + `quality-guidelines.md:36-43` 改为「全局样式经 main.css 入口 @import 聚合的 partial 组织」。
- 行为等价：构建产物 CSS 等价（@import 内联后样式不变），运行时视觉/交互零差异。
- 三件套绿：`vue-tsc --noEmit` exit 0 / `vitest run` 全绿 / `eslint` 0 新增 error。
- Tailwind v4 + Lightning CSS `@import` 顺序正确（token 在使用前 @import；`@import 'tailwindcss'` 与自定义 @import 共存）。

## Acceptance Criteria

- [x] main.css 按域拆分至入口 + partial 结构，main.css 本体仅保留入口 + @import 聚合（Phase 1-3 完成）。
- [x] `readGlobalCss()` helper 落地，9 处 `readSource('src/assets/main.css')` 全部替换；「不含」禁令断言覆盖所有 partial（无假绿）。
- [x] frontend spec 3 处修订（component-guidelines:111 / index:42 / quality-guidelines:36-43）。
- [x] 三件套全绿（vue-tsc 0 / vitest 全绿 / eslint 0 新增 error）。
- [ ] 行为等价（manual-checklist 固化 + 实际手测待跑：light/dark 主题切换 + 关键页面视觉）。
- [x] `main.ts` 入口不变，`base.css` shim 状态不变。

## Notes

- 复杂任务：`task.py start` 前补 `design.md`（分阶段方案 + 拆分边界契约表 + 测试适配 + spec 修订 + 风险回滚）+ `implement.md`（slice 清单 + 验证 + 回滚点）。
- parent：`07-12-brand-consistency`（acceptance「设计 token 落地：main.css 按域拆分」）。关联 `07-12-engineering-baseline`（共享前端基建）。
- memory 标注「#28 需新会话+在场」--因 spec 冲突 + 测试假绿陷阱 + Tailwind 入口三重耦合，风险高。
