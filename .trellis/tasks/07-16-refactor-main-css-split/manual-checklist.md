# 手测清单 - main.css 按域拆分（#28）

> prd AC5 要求「行为等价（manual-checklist 固化 + 实际手测待跑：light/dark 主题切换 + 关键页面视觉）」。
> main.css 拆分是纯样式搬迁（cascade 等价：unlayered 顺序保持 + dark 覆写随域迁移），手测验证视觉零差异。
> 四件套（vue-tsc/vitest/eslint/build）每 slice 已绿，readGlobalCss 递归内联覆盖所有 partial 断言无假绿。

前置：`cd frontend && npx vite dev` 启动开发服务器，登录后按以下项手测。light/dark 各跑一遍。

## 1. 主题切换（核心）
- [ ] 顶栏主题切换按钮：light <-> dark 切换，全局配色翻转无闪烁。
- [ ] dark 下 body 背景（纸质墨晕渐变）+ 文字色（--md-on-background）正确。
- [ ] dark 下各 token（primary/surface/container）与 light 对比正确，无残留 light 配色。

## 2. 关键页面视觉
- [ ] 首页项目列表：project-card（第四阶段品牌重构）+ 阅读更多按钮 hover 阴影正确。
- [ ] 写作台 WritingDesk：章节纸张（chapter-paper 宣纸八行笺）+ 侧栏章节列表 + 朱批对白 + AI 助手面板（assistant-shell 砚台批注）。
- [ ] 小说详情 NovelDetailShell：分区导航 + 概览长卷 + 顶栏 LOGO（motion-brand 金石篆印）。
- [ ] 设置 -> 模型路由 PersonalModelRouting：供应商卡片 + 模型拉取弹窗（settings-modal 折扇开合）+ 存字方章（phase12-save-stamp）。
- [ ] 管理面板 Admin：admin-panel 卡片 + 表头布局正确。

## 3. 组件域样式
- [ ] 按钮（buttons）：Filled/Outlined/Text/Tonal/Elevated/Icon 五种样式 + hover/active 态。
- [ ] 表单（forms）：双线框卡片 + Text Field + Textarea + Select 下拉箭头（select-styling 金石小箭头）。
- [ ] 导航（navigation）：NavRail + Drawer + TopAppBar + Tabs 朱砂激活态。
- [ ] Chips + 朱砂印章（chips）：标签 + 印章视觉。
- [ ] Material 3 组件（material3-components）：Dialog/List/Progress/Snackbar/Badge/Switch/Checkbox 弹窗与控件。
- [ ] 滚动条（scrollbar）：滚动时显示水墨滚动条，平时隐藏；dark 下滚动条配色正确。
- [ ] 弹窗（modal-adapters + modal-decor）：全局水墨大弹窗 + 起居菜单金石效果。
- [ ] 动效（motion-brand）：交互过渡气旋动画 + Header 墨風 LOGO。
- [ ] 大背景（background-art）：云雾泼墨背景 + dark 下背景正确。
- [ ] 章节目录穿线（chapter-binding）+ 三折折页（paper-fold）：大纲目录朱丝线装 + 稿纸折页物理效果。

## 4. 响应式
- [ ] 窄屏/移动端（phase5-responsive）：无侧边栏布局 + 顶栏金石落印 + 移动端章节抽屉。
- [ ] 1199px/833px/640px 断点：app-shell 响应式覆写正确（app-shell.css 内 @media）。

## 5. 回滚验证（可选）
- [ ] 若视觉异常，`git revert <slice-commit>` 回滚单 slice；main.css 始终保持入口可用。
