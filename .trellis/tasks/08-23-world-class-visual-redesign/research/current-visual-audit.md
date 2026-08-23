# 当前视觉与结构审计

## 页面清单

`frontend/src/router/index.ts` 定义九个带主视图的页面：`NovelWorkspace`、`InspirationMode`、`NovelDetail`、`WritingDesk`、`Login`、`Register`、`AdminView`、`AdminNovelDetail`、`SettingsView`。`NovelDetail` 与 `AdminNovelDetail` 复用 `NovelDetailShell`；`WorkspaceEntry.vue` 当前没有路由引用。

## 高杠杆结论

- `AppShell.vue` 同时承载导航、项目上下文、提醒、导入、用户菜单、设置和管理弹层；业务逻辑保持，视觉壳统一重做。
- `tokens.css`、`app-shell.css`、`phase5-navigation.css`、`topbar.css` 和 `AppShell.vue` scoped 样式存在重复权重与 `!important` 竞态。
- 全局字体几乎全部被绑定为宋体，页面背景和组件又统一成暖纸，导致九页层次与任务差异被压平。
- `AuthLayout` 只有 slot；登录和注册虽有完整业务契约，却共享近似构图。移动端还隐藏产品叙事。
- 工作区 hero 同时承担继续项目、目标、进度、统计；项目卡固定高度且操作语义不够明确。
- 灵感模式固定三栏，用户对话、时间轴和静态词笺争夺主空间；静态词笺不能伪装成真实抽取结果。
- 详情页和写作台已有稳固的共享壳、composable 与 1200/834/833 响应式契约，适合保留结构并替换视觉层级。
- 设置页同时暴露 hero、摘要、指标、notice 和四组导航，主任务被稀释；管理页六个 tab 平权，缺少系统总览层级。

## 响应式与质量证据

- 断点权威在 `frontend/src/constants/responsive.ts`；桌面 `>=1200`、平板 `834–1199`、移动 `<=833`。
- Playwright 已配置 1440×900 Chromium 与 Pixel 7；fixture server 在 6181，Vite 在 6173。
- 现有 axe 覆盖登录、任务弹层和写作台局部；移动抽屉焦点生命周期、reduced-motion 和长文本仍需补验。
- 写作台多个标题/元信息/工具栏使用 `white-space: nowrap`，需要在新视觉层补齐 `min-width:0` 与长文本换行边界。

## 概念推导

- 产品独特机制：把灵感、蓝图、章节、评审和修订串成可跨周恢复的长篇写作流水线。
- 真实场景：作者在桌面或手机上长时间工作，首要需求是迅速认出当前作品、下一步和阻塞项。
- 两个必须避开的惯例：暖纸书房/印章仿古，以及通用白色 SaaS 卡片墙。
- 七个候选物质世界按受众共鸣排序：编辑部故事墙、电影剪辑时间线、地质岩芯档案、交通调度图、乐谱排练注记、剧场舞台监督提示本、天文台观测日志。
- 概念抽签 `94f236b2` 指定第六项：剧场舞台监督提示本。采用“严格分舞台”构图，以群青结构、冷白工作面、朱红 cue 和荧黄临时批注表达状态。
- 三张外部图像构图 probe 因环境 API key 401 在生成前失败；未产出图片。用户已委托自主选择，因此以真实浏览器渲染与截图替代预生成图像证据。

## 关键出处

- 路由与守卫：`frontend/src/router/index.ts:6-154`
- 共享壳：`frontend/src/components/shared/AppShell.vue:20-655`
- 主题令牌：`frontend/src/assets/styles/tokens.css:5-187`
- 样式入口：`frontend/src/assets/main.css:2-35`
- 工作区：`frontend/src/views/NovelWorkspace.vue:34-249`
- 灵感页：`frontend/src/views/InspirationMode.vue:8-183`
- 详情壳：`frontend/src/components/shared/NovelDetailShell.vue:10-238`
- 写作台断点：`frontend/src/views/WritingDesk.vue:484-676`
- 设置：`frontend/src/views/SettingsView.vue:3-125`
- 管理：`frontend/src/views/AdminView.vue:3-47`
- 浏览器配置：`frontend/playwright.config.ts:7-60`

