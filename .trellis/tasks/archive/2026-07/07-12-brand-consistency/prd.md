# 品牌一致性回归（去印章化/动效收敛/主题桥接/字体）

## Goal

让 UI 执行回归 PRODUCT.md / DESIGN.md 定义的"安静、专业、克制的可靠写作台"。当前实现系统性跑偏：古风印章作功能标识、持续装饰动效、高饱和渐变、字体字重失效、Naive UI 用 `!important` 全局覆盖。

来源：2026-07-12 多专家审查报告（`docs/mofeng-audit-report-2026-07-12.html`）腾讯设计专家、美团 UI 专家。

## Requirements

- 功能入口去古风印章化：管理/配置/改密/退出恢复直白文案，古风仅作装饰副标题/图标。
- 装饰动效收敛：移除无限循环动画（float-badge/dot-ink-pulse），hover/选中降级为颜色边线；待写徽章去高饱和渐变。
- Naive UI 主题桥接：`n-config-provider` 注入 `themeOverrides`，逐步删 52 个 `.n-*` + `!important` 全局覆盖。
- 字体修复：补导 500 字重或删 `!important 500`；为 `--md-font-mono` 引入等宽字体。
- 登录页降权：6MB 背景图→WebP/AVIF + 响应式；表单独立卡片；焦点环 ≥3:1；辅助文字对比度达 AA 4.5。
- 设计 token 落地：box-shadow 引用 `--md-elevation-*`；main.css 按域拆分；Tailwind 任意值/图标/断点/状态色统一。

## 子任务（追踪于会话 TaskList）

- #25 功能入口去古风印章化 + 装饰动效收敛 + 待写徽章
- #26 Naive UI 主题桥接 + 字体字重修复 + 等宽字体
- #27 登录页降权 + 无障碍焦点/对比度
- #28 设计 token 落地 + main.css 拆分 + 写作台体验

## Acceptance Criteria

- [x] 功能入口有通用词文案，古风仅作装饰副标题。
- [x] 无无限循环动画；待写徽章无高饱和渐变。
- [x] App.vue 有 `n-config-provider`；正文 500 字重实际生效。
- [x] 登录页图片 <1MB；焦点指示 ≥3:1；辅助文字对比度达 AA。

## Notes

- 建议排在路线图**阶段一品牌快修（字体/动效/徽章）+ 阶段二/三**。
- 本任务为审查后的**整理产出，未进入实现**。属复杂任务（尤其主题桥接与 token 落地），实现需 `task.py start` 后补 `design.md` / `implement.md`。
- 关联报表：第柒章 腾讯设计、第捌章 美团 UI、第贰章 P0 看板·品牌一致性。

## Progress

已完成并落盘 `b9eab0f`：#25 去印章+动效收敛+待写徽章 / #26 n-config-provider 主题桥接+字体字重（500 字重违规已撤销，由 `uiAuditRegression.spec.ts:364` 守护）/ #27 登录页 WebP（8.3MB→411KB）+焦点/对比度。Acceptance 4 项全绿。

**未完成（需新会话 + 在场逐块验证）**：
- #28 设计 token 落地（`--md-*` 统一）+ `main.css`（4966 行 / 1141 `!important` / 52 `.n-` 覆写）按域拆分。超大重构。

任务不归档；#28 新会话续做。
