---
name: MoFeng (墨风)
description: 以剧场排演提示本为视觉隐喻的长篇小说创作工作台。
colors:
  stage: "#1737CF"
  stage-strong: "#102BB0"
  stage-deep: "#0D228D"
  stage-soft: "#DCE3FF"
  cue: "#D62F3A"
  cue-strong: "#A71625"
  note: "#E6F64A"
  success: "#0D7D5E"
  ink: "#111525"
  ink-muted: "#566078"
  surface: "#FFFFFF"
  surface-low: "#F7F8FC"
  surface-mid: "#EEF1F8"
  background: "#E9EDF6"
  outline: "#8793AA"
  outline-soft: "#D9DFEB"
  on-accent: "#FFFFFF"
typography:
  display:
    fontFamily: "Arial Narrow, DIN Condensed, Roboto Condensed, PingFang SC, Microsoft YaHei, sans-serif"
    fontSize: "48px"
    fontWeight: 600
    lineHeight: 0.95
    letterSpacing: "-0.025em"
  headline:
    fontFamily: "Arial Narrow, DIN Condensed, Roboto Condensed, PingFang SC, Microsoft YaHei, sans-serif"
    fontSize: "28px"
    fontWeight: 600
    lineHeight: 1.15
    letterSpacing: "-0.025em"
  title:
    fontFamily: "Inter, ui-sans-serif, system-ui, PingFang SC, Microsoft YaHei, sans-serif"
    fontSize: "18px"
    fontWeight: 700
    lineHeight: 1.35
    letterSpacing: "normal"
  body:
    fontFamily: "Inter, ui-sans-serif, system-ui, PingFang SC, Microsoft YaHei, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.6
    letterSpacing: "normal"
  label:
    fontFamily: "Inter, ui-sans-serif, system-ui, PingFang SC, Microsoft YaHei, sans-serif"
    fontSize: "13px"
    fontWeight: 700
    lineHeight: 1.35
    letterSpacing: "normal"
  cue-label:
    fontFamily: "SFMono-Regular, Consolas, Liberation Mono, monospace"
    fontSize: "12px"
    fontWeight: 700
    lineHeight: 1.4
    letterSpacing: "0.04em"
rounded:
  xs: "2px"
  sm: "4px"
  md: "6px"
  lg: "8px"
  xl: "12px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
  xxl: "48px"
components:
  button-primary:
    backgroundColor: "{colors.cue}"
    textColor: "{colors.on-accent}"
    typography: "{typography.label}"
    rounded: "{rounded.sm}"
    padding: "0 20px"
    height: "44px"
  button-stage:
    backgroundColor: "{colors.stage}"
    textColor: "{colors.on-accent}"
    typography: "{typography.label}"
    rounded: "{rounded.sm}"
    padding: "0 20px"
    height: "44px"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.sm}"
    padding: "0 16px"
    height: "44px"
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "24px"
  dialog:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
    padding: "24px"
---

# Design System: MoFeng (墨风)

## Overview

**Creative North Star: “剧场排演提示本” (The Rehearsal Cue Book)**

墨风不是仿古书房，也不是通用白色 SaaS 面板，而是一册正在排演的长篇作品。群青搭建结构舞台，冷白承载长时工作，朱红标记必须立即理解的关键 cue，荧黄只作为极少量临时批注。作者是导演，AI 是提示与候选；界面始终先让作者认出当前作品、下一步和唯一主动作。

系统采用单一浅色皮肤。近黑只用于文字、细线与必要控件，不形成大块暗场；表达力来自严格分区、场次编号、对位线、裁切标记和高密度但有秩序的信息编排，而不是纹理、书法、印章或装饰性卡片墙。

**Key Characteristics:**

- **严格分舞台**：结构面与工作面形成清晰的面积关系，而非层层套卡片。
- **Cue 有预算**：群青负责结构，朱红负责关键动作，荧黄负责临时提醒，三者不互相借位。
- **连续工作面**：项目档案、章节、设置和遥测使用连续表面与 1px 对位线组织密度。
- **状态可被读出**：颜色始终与文字、图标、形状或位置共同表达状态。
- **概念种子**：`94f236b2`，用于确认生产构建仍属于同一视觉世界。

## Colors

调色盘是冷静、明亮且具有编辑权威感的四色系统；强调色的稀缺性本身就是层级。

### Primary

- **Stage Blue** (`#1737CF`)：顶栏、结构舞台、当前上下文与主要导航；不用于长文正文底。
- **Stage Strong / Deep** (`#102BB0` / `#0D228D`)：群青交互态与高对比文字，不另造蓝色分支。
- **Stage Soft** (`#DCE3FF`)：轻量选中面和信息容器。

### Secondary

- **Cue Red** (`#D62F3A`)：唯一关键承诺动作、错误和当前 cue。
- **Cue Strong** (`#A71625`)：Cue Red 的 hover / pressed 态。

### Tertiary

- **Prompt Yellow** (`#E6F64A`)：临时批注、提醒、全局键盘焦点与深色结构面上的高可见操作；单屏面积必须很小。
- **Signal Green** (`#0D7D5E`)：成功、在线和正向系统状态，必须配合文本或图标。

### Neutral

- **Ink** (`#111525`)：正文、标题与必要线条；不铺成大面积背景。
- **Muted Ink** (`#566078`)：辅助说明和次级元数据。
- **Cold White** (`#FFFFFF`)：正文、表单、列表和阅读工作面。
- **Surface Low / Mid** (`#F7F8FC` / `#EEF1F8`)：相邻工作层与连续分区。
- **Background** (`#E9EDF6`)：应用大底。
- **Outline / Soft Outline** (`#8793AA` / `#D9DFEB`)：控件边界与低权重分隔线。

### Named Rules

**The Cue Budget Rule.** 朱红只标记页面中最需要立即理解或承诺的动作；荧黄只标记临时提醒或焦点。一个视图不能同时出现多个争夺注意力的红色主动作。

**The No Black Field Rule.** `#111525` 是墨色，不是背景色。认证页、章节列表、工作台、设置和后台都不得出现大块近黑容器。

## Typography

**Display Font:** Arial Narrow / DIN Condensed / Roboto Condensed，中文回退到系统无衬线。

**Body Font:** Inter / 系统无衬线 / PingFang SC / Microsoft YaHei。

**Cue Font:** SFMono-Regular / Consolas，用于编号、场次和机器状态，不用于长段正文。

**Character:** 展示字形像剧场排演单上的压缩标题，正文则保持现代中文工具的长时可读性。页面不再使用楷体、书法字或仿古宋体制造身份。

### Hierarchy

- **Display** (600, 48px, 0.95)：认证品牌、极少数首屏主标题；允许响应式放大。
- **Headline** (600, 28px, 1.15)：页面和大型分区标题。
- **Title** (700, 18px, 1.35)：连续工作面中的模块标题。
- **Body** (400, 15px, 1.6)：默认界面正文；长文阅读可继续使用现有 serif 阅读栈，但不能渗透到应用 chrome。
- **Label** (700, 13px, 1.35)：按钮、标签和导航。
- **Cue Label** (700, 12px, 1.4, `0.04em`)：场次编号、计数器、运行状态与对位信息。

### Named Rules

**The Two-Voice Rule.** 无衬线承担内容与操作，收窄展示字承担舞台标题，等宽字只承担 cue 元数据；同一元素不得混合三种声音。

## Layout

全站以连续工作面和明确面积关系组织层级。桌面工作区采用约 `42% / 58%` 的严格分舞台构图：群青区只出现一次“继续创作”主动作，冷白区承载可快速扫读的项目档案。认证入口同样采用品牌舞台与单一表单面的不对称组合，登录与注册在桌面交换重心，避免同构。

- 内容最大宽度为 `1360px`，超宽屏扩至 `1520px`；布局边距使用 `clamp()` 保持节奏。
- 继续遵守 `1200 / 834 / 833` 三段响应式合同。窄屏将分舞台纵向堆叠，导航变为稳定、可横向扫读的控制带。
- 关键按钮、图标与可收放摘要的触控目标至少 `44px`。
- 文本容器必须 `min-width: 0`，长标题、URL 和错误文案允许换行，不得制造横向溢出。
- 结构线为 1px 群青或中性对位线；局部 3px cue 线只用于当前关键状态。

## Elevation & Depth

系统默认平面化。卡片、按钮、导航与连续列表在静止状态不使用阴影，通过色面、边界和错位建立层级；只有弹层、抽屉或确实脱离文档流的浮层获得柔和冷色阴影。

### Shadow Vocabulary

- **Surface Lift 1** (`0 2px 6px rgba(16,24,62,.08), 0 10px 24px rgba(16,24,62,.06)`)：需要轻微脱离工作面的浮动表面。
- **Surface Lift 2** (`0 8px 18px rgba(16,24,62,.12), 0 28px 64px rgba(16,24,62,.12)`)：弹窗和全局抽屉。

### Named Rules

**The Flat Work Rule.** 工作内容在同一平面上连续展开；阴影表示真实层级变化，不表示“这是一个卡片”。

## Shapes

形态以直角模块和微圆角控制之间的张力为主。控件通常为 `4px`，卡片为 `6px`，弹层为 `8px`，只有极少数大型容器使用 `12px`。胶囊形只允许出现在既有、必须表达紧凑状态的组件中，不作为全局装饰语法。

1px 对位线、局部裁切角、编号和短 cue 线构成识别度。禁止仿古双线框、印章、装订孔、书脊、卷轴和纸张肌理。

## Components

### Buttons

- **Primary Cue**：朱红底、白字、4px 圆角、最小高度 44px；hover 进入 Cue Strong 并轻移，active 下压 1px。
- **Stage Filled**：群青底、白字，承担结构性推进或次级主要操作。
- **Outlined / Text**：透明底、1px Outline，文字使用 Stage Deep。
- **Focus**：所有原生交互使用 3px 荧黄 `focus-visible` outline 和 3px offset；不能只改变颜色。

### Cards / Continuous Surfaces

- 工作面为冷白或 Surface Low，使用 1px Soft Outline，默认无阴影。
- 项目档案、设置摘要和后台遥测优先使用连续分区与共享边界，不堆叠独立浮卡。
- hover 只改变边界、底色或轻微位移，不整块缩放。

### Inputs / Fields

- 冷白底、4px 圆角，静止为 1px Outline 内描边。
- `focus-within` 改为 2px Stage Blue 内描边；错误态同时提供文字说明。
- 标签保持在输入框外，不用 placeholder 代替名称。

### Navigation

- 全局顶栏为 Stage Blue；当前项目、任务、用户入口在同一 44px 控制节奏内。
- 当前项必须同时使用位置、底面或短 cue 线表达，不只靠文字颜色。
- 移动端保持水平可扫读，不将全部入口压入不可发现的图标菜单。

### Drawers / Dialogs

- 使用 Surface、1px Soft Outline、8px 圆角和 Surface Lift 2。
- 触发器公开 `aria-expanded` 与 `aria-controls`；Escape 关闭后恢复焦点，遮罩必须是具名按钮或由共享弹层语义管理。

### Rehearsal Ledger

灵感页的排演脉络使用原生 `details/summary`。桌面作为并列辅助工作面；移动端收起为 44px 控制带，展开高度上限 320px，不遮蔽对话主任务。

## Do's and Don'ts

### Do:

- **Do** 让每个页面先回答“我在哪、下一步是什么、唯一主动作是什么”。
- **Do** 把群青用于结构，把朱红用于关键 cue，把荧黄用于临时批注与焦点。
- **Do** 使用连续工作面、1px 对位线、编号和裁切标记表达密度。
- **Do** 在桌面和 Pixel 7 上同时验证溢出、焦点、抽屉与 44px 触控目标。
- **Do** 在 `prefers-reduced-motion: reduce` 下直接到达终态。

### Don't:

- **Don't** 恢复暖宣纸、书法、楷体、印章、卷轴、古籍双线框或仿纸肌理。
- **Don't** 使用大块近黑背景、渐变文字、玻璃拟态、emoji 图标或通用 SaaS 卡片墙。
- **Don't** 为表达状态只换颜色，也不要让多个朱红动作争夺第一优先级。
- **Don't** 新增暗色主题、主题切换器或另一套视觉 token。
- **Don't** 用阴影、圆角和装饰替代信息层级与明确文案。
