---
name: MoFeng (墨风)
description: 颜色即权责的 AI 长篇小说写作台。淡朱楷体描红稿、焦墨宋体落墨、朱砂只作落印钤章。
colors:
  primary: "#B8402F"
  primary-strong: "#9C3323"
  primary-soft: "#CE5A47"
  primary-wash: "color-mix(in srgb, #B8402F 5%, transparent)"
  primary-line: "color-mix(in srgb, #B8402F 22%, transparent)"
  primary-line-strong: "color-mix(in srgb, #B8402F 38%, transparent)"
  secondary: "#B83C32"
  secondary-container: "#FBEBEA"
  on-secondary-container: "#5C120C"
  tertiary: "#2E5C8A"
  on-tertiary: "#FAF6ED"
  luomo: "#1C2224"
  luomo-soft: "#3A4648"
  jiege: "color-mix(in srgb, #3A4648 26%, transparent)"
  surface: "#FAF6ED"
  surface-dim: "#F0EAD8"
  surface-container-lowest: "#FDFDFB"
  surface-container-low: "#FAF7E8"
  surface-container: "#F6F0E0"
  surface-container-high: "#EDE4D0"
  surface-container-highest: "#DCD2BE"
  background: "#F2ECE0"
  on-surface: "#1C2224"
  on-surface-variant: "#556265"
  outline: "#C2B69D"
  outline-variant: "#DCD2BE"
  error: "#B85C58"
  error-container: "#FBEBEA"
  success: "#3B7A57"
  success-container: "#EAF3EE"
  warning: "#E6A23C"
  warning-container: "#FDF6EC"
typography:
  display:
    fontFamily: "Noto Serif SC, Source Han Serif SC, Noto Serif CJK SC, STSong, Songti SC, SimSun, serif"
    fontSize: "48px"
    fontWeight: 400
    lineHeight: 1.2
    letterSpacing: "0.08em"
  headline:
    fontFamily: "Noto Serif SC, Source Han Serif SC, Noto Serif CJK SC, STSong, Songti SC, SimSun, serif"
    fontSize: "30px"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "0.05em"
  title:
    fontFamily: "Noto Serif SC, Source Han Serif SC, Noto Serif CJK SC, STSong, Songti SC, SimSun, serif"
    fontSize: "20px"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "0.03em"
  body:
    fontFamily: "Noto Serif SC, Source Han Serif SC, Noto Serif CJK SC, STSong, Songti SC, SimSun, serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.8
    letterSpacing: "0.01em"
  miaohong:
    fontFamily: "Kaiti SC, STKaiti, KaiTi, AR PL UKai CN, AR PL KaitiM GB, TW-Kai, Noto Serif SC, serif"
    fontSize: "17px"
    fontWeight: 600
    lineHeight: 2
    letterSpacing: "0.035em"
  label:
    fontFamily: "Noto Serif SC, Source Han Serif SC, Noto Serif CJK SC, STSong, Songti SC, SimSun, serif"
    fontSize: "12px"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "0.04em"
rounded:
  xs: "2px"
  sm: "4px"
  md: "6px"
  lg: "8px"
  xl: "12px"
  full: "9999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
  xxl: "48px"
components:
  button-seal:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-tertiary}"
    typography: "{typography.label}"
    rounded: "{rounded.xs}"
    padding: "0 24px"
    height: "44px"
  button-seal-hover:
    backgroundColor: "{colors.primary-strong}"
    textColor: "{colors.on-tertiary}"
    typography: "{typography.label}"
    rounded: "{rounded.xs}"
    padding: "0 24px"
    height: "44px"
  button-tonal:
    backgroundColor: "{colors.tertiary}"
    textColor: "{colors.on-tertiary}"
    typography: "{typography.label}"
    rounded: "{rounded.xs}"
    padding: "0 24px"
    height: "44px"
  paper:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.luomo}"
    rounded: "{rounded.xs}"
    padding: "32px"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.on-surface}"
    rounded: "{rounded.xs}"
    padding: "16px"
    height: "52px"
  seal-tracing:
    backgroundColor: "{colors.primary-wash}"
    textColor: "{colors.primary}"
    typography: "{typography.label}"
    rounded: "{rounded.xs}"
    padding: "4px 10px"
  seal-inked:
    backgroundColor: "transparent"
    textColor: "{colors.luomo}"
    typography: "{typography.label}"
    rounded: "{rounded.xs}"
    padding: "4px 10px"
  seal-sealed:
    backgroundColor: "{colors.secondary}"
    textColor: "{colors.surface}"
    typography: "{typography.label}"
    rounded: "{rounded.xs}"
    padding: "4px 10px"
  tab-active:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.secondary}"
    typography: "{typography.label}"
    rounded: "{rounded.sm}"
    padding: "0 16px"
    height: "38px"
---

# Design System: MoFeng (墨风)

## Overview

**Creative North Star: "描红界格 · 颜色即权责" (The Copybook of Red Tracing)**

墨风 (MoFeng) 是专为长篇虚构小说创作者打造的 AI 写作台。新视觉世界取自**书法字课传统——米字格、朱丝栏、描红簿**：AI 写的是淡朱楷体的**描红稿**，作家审定**落墨**（焦墨宋体）才算正文，**朱砂只作落印钤章**。人机权责不靠图标、不靠标签，而是由颜色与字族双信号写进每一行字——阁主回到书案，一眼辨出哪些章节是己出、哪些是待审的描红。

界格不是装饰，是书写的规尺：阅读/书写面是**方格稿纸行笺**（横向描红行线 + 左右朱丝栏竖线），结构面是**青灰界格发线**（侧栏章节列表、面板分隔）。旧世界"徽墨熟宣/拓片硬影"已在全站完成换代（写作台先行，工作台首页、灵感、档案、设置、admin 及共享弹层/表格随后覆盖，登录/注册认证面最终入场——入口为「描红引路，落墨入场」：引子区真楷描红作 AI 之声，稿纸面板作家落墨，提交即朱砂落印，摄影卷轴底图与卷轴杆装饰一并退役）：拓片偏置硬投影清零，改为纸页柔影（paper 系）；熟宣底、微直角风骨作为国风内核保留，古籍双线框收敛为 1px 界格发线。2026-08 焚稿清场：旧"第四阶段·墨落惊风雨"地层（`brand-visuals.css` 的狂草"墨風"水印、项目卡石青书脊/装订孔/"藏書"闲章、`background-art.css` 风竹大背景、全局弥散墨晕）已全部删除，描红界格成为唯一视觉世界；项目卡回归平净纸卡（1px 界格发线 + 纸页柔影）。

**Key Characteristics:**
- **颜色即权责**：描红（淡朱 `#B8402F` + 真楷体 + wash 底/1px 界栏三信号，`data-provenance="ai"`）= AI 待审稿；落墨（焦墨 `#1C2224` + 宋体，`data-provenance="ink"`）= 作家审定正文；朱砂（`#B83C32`）只作落印钤章与状态印，已定正文不得见红。
- **方格稿纸行笺**：章节阅读/编辑容器是横向描红行线稿纸（`--paper-line` 27px），左右缘各一道朱丝栏竖线，熟宣地，古籍双线框。
- **青灰界格发线**：结构面（侧栏、面板、笺片 tab）用 1px `--md-jiege` 发线分割，不用卡片堆卡片。
- **落墨签名交互**：候选描红稿被选定后，文字 260ms 由朱转墨（`chapter-luomo`），标题旁钤「定」字朱砂印 1.35s 单帧落印，随即退场。

---

## Colors

墨风的调色盘以熟宣为地、界格为规，三种红色各守一职：淡朱管描红权责，朱砂管落印金石，石青管朗读。

### Primary
- **描红** (`#B8402F`): AI 产出、待作家审定文字的正文色。熟宣上对比度 4.7:1（AA 达标）。亦是"提交/选定/保存成稿"类落印主按钮的底色。描红容器语义标注 `data-provenance="ai"`。
- **描红深** (`#9C3323`): 描红 hover/强调态。
- **双钩淡朱** (`#CE5A47`): 仅用于 ≥24px 大字标题、装饰与界格等非正文场景，不得用于正文小字（对比度不足）。
- **描红 wash / 行线 / 界栏** (`color-mix` 5% / 22% / 38%): 描红块底色、稿纸横向行线、描红段落左缘 1px 界栏与朱丝栏竖线。以 `color-mix` 自引用 `--md-miaohong`，暗场随基准自动换算。

### Secondary
- **朱砂** (`#B83C32`): 落印钤章专用。章节标题旁「定」字落印、"已钤印"状态实底方印、笺片 tab 激活态描边。与描红色相相邻但权责不同：描红是"待审的稿"，朱砂是"盖下的章"。
- **朱砂容器** (`#FBEBEA` / 字 `#5C120C`): 印章类容器底。

### Tertiary
- **石青** (`#2E5C8A`): **朗读专用色**——朗读高亮、播放中小签、朗读控制激活态（`--md-primary-container`）。与朱砂权责严格分离：石青不表示任何"已定稿"语义。

### Neutral
- **落墨（焦墨）** (`#1C2224`): 作家审定正文色（`--md-luomo`，`--md-on-surface` 的语义别名）。落墨容器 `data-provenance="ink"`。
- **松烟** (`#3A4648`): 次级结构与界格发线的 mix 基准。
- **界格发线** (`color-mix(in srgb, #3A4648 26%, transparent)`): 结构面 1px 青灰发线。
- **熟宣** (`#FAF6ED`): 稿纸与主阅读面底色。温润淡雅，不用纯白。
- **老宣** (`#F0EAD8`) / **素骨** (`#F2ECE0`) / **竹纸** (`#FAF7E8`): 全局底色、侧边栏与容器层级。
- **竹青** (`#C2B69D`) / **墨晕** (`#DCD2BE`): 框线与副线。

### State
- **温丹砂** (`#B85C58`, container `#FBEBEA`): 错误、终止、强警示。
- **石绿** (`#3B7A57`, container `#EAF3EE`): 成功与正面反馈。
- **藤黄** (`#E6A23C`, container `#FDF6EC`): 警示与进行中。

### Named Rules
**The Three-Signal Rule (三信号法则).** 描红稿的渲染三个信号缺一不可：**色**（`--md-miaohong`）、**字族**（`--md-font-kai` 真楷体，与落墨宋体形成字形对比，色盲可辨）、**面**（段落底色 `--md-miaohong-wash` + 左缘 1px `--md-miaohong-line-strong` 界栏）。只改颜色不算描红，落墨后三信号同步撤去。

**The Settled-Ink-Never-Red Rule (落墨不见红法则).** 朱砂 `#B83C32` 只出现在落印钤章（「定」字印、状态实底方印）与激活指示上。已定稿的正文、已落墨的段落、首字引首章一律焦墨——正文中出现红色，只有一种合法身份：待审的描红。

**The Shiqing-Is-Reading Rule (石青朗读法则).** 石青 `#2E5C8A`（暗场 `#33517a`）是朗读与 AI 辅助协作的专属色（高亮、播放中小签、AI 入口辅钮），不得挪用于成功态、选定态、进度轨道或任何"钤印"语义，以免与朱砂的权责混淆。线性进度条轨道用墨晕（`--md-outline-variant`）、进度条本体用焦墨，不借石青。

---

## Typography

**Display Font:** Noto Serif SC, Source Han Serif SC, STSong, Songti SC (宋体字族，落墨与标题)
**Body Font:** 同宋体字族（`--md-font-family` 已归入 serif 栈）
**Miaohong Font:** Kaiti SC, STKaiti, KaiTi, AR PL UKai CN, AR PL KaitiM GB, TW-Kai (真楷体栈，`--md-font-kai`，描红稿与朱批批注专用)

**Character:** 字族即权责。宋体是"碑拓骨力"的已定之字，楷体是"字课描红"的未定之稿——两种字族在同一栏稿纸上对照，作家不看颜色也能读出哪行是 AI 所拟。

### Hierarchy
- **Display** (400, 48px, 1.2, letterSpacing 0.08em): 极少使用，仅空状态大字留白或书架欢迎页。
- **Headline** (600, 30px, 1.3, letterSpacing 0.05em): 页面主标题、章节大字标题。
- **Title** (600, 20px, 1.4, letterSpacing 0.03em): 卡片标题、弹窗头部、操作栏分组名。
- **Body** (400, 15px, 1.8, letterSpacing 0.01em): 应用级正文基准；稿纸正文（`.chapter-prose`）为 17px / 600 / line-height 2 / letterSpacing 0.035em，行长框定 72ch，段落首行缩进 2em。
- **Miaohong** (600, 17px, 2, letterSpacing 0.035em): 描红稿专用真楷体栈，字号行高与稿纸正文一致——同一栏内只有色与字族变了，格子不变。
- **Label** (600, 12px, 1.4, letterSpacing 0.04em): 按钮文字、状态印、小字签（如描红区首段前"描红稿 · 待落墨"小签、同栏题签"候选描红稿"）。12px 是功能小字的硬底线：token 层 `--md-label-small` / `--md-label-medium` 均已对齐 12px，不得再出现 10px 功能文字。

### Named Rules
**The Kaishu-Means-Draft Rule (楷体即草稿法则).** 真楷体栈只服务描红稿与批注朱批；任何落定正文、标题、按钮、状态印一律宋体。落墨动效中楷→宋是离散属性，在 260ms 过渡的中点翻转，不允许渐变插值。

**The Editorial Spine Rule (碑拓骨力规则).** 凡宋体标题（Display/Headline/Title）必须显式拉开字间距：小字标题 ≥0.03em，大字标题 ≥0.05em。稿纸正文 letterSpacing 0.035em 不缩。

---

## Layout

写作台为固定三栏 grid（侧栏 | 工作区 | 助手抽屉），断点 833/834/1199/1200，触控尺寸 ≥44px——这是产品契约，不因视觉换代改动。

- **稿纸行笺**：章节阅读/编辑容器（`.chapter-paper`、MofengEditor 稿纸内核）铺横向描红行线，行距 `--paper-line` = 正文行高（15px × 1.8 = 27px，组件可按节奏覆写）；左右缘各一道 1px 朱丝栏竖线（`--md-miaohong-line-strong`），左右 padding ≥32px。
- **结构面**：侧栏章节列表、面板分隔用 1px `--md-jiege` 青灰发线，不用卡片堆卡片，不用色块分区。
- **双色同栏**：落墨正文与候选描红稿在同一栏稿纸上上下对照；两者同时在场时，以 12px 淡朱楷体题签"候选描红稿"（`.chapter-jiege-divider`，字距 0.35em，前后发线）分界，不用 eyebrow 式小字眉。
- **行线边界**：横向行线只出现在稿纸书写/阅读容器内，绝不铺到侧栏、面板、弹窗底色。阅读面禁用米字格全覆盖底纹（伤长文阅读）；米字格只允许在空状态大字、章节卡封面等非连续阅读区出现。

### Named Rules
**The Lines-Stay-On-Paper Rule (行线不出稿纸法则).** 描红行线、朱丝栏、米字格都是"纸上的规矩"，只能长在稿纸容器里；结构面只有青灰发线一种线。

---

## Elevation & Depth

全站（写作台、工作台首页、灵感、档案、设置、admin、登录/注册认证面及共享弹层/表格）已停用旧拓片偏置硬投影（`--md-elevation-1..5` 零模糊块影），换代为纸页柔影。层级哲学：**纸可浮，印不浮**。

### Shadow Vocabulary
- **浮起纸页 (Paper 1)** (`box-shadow: 0 1px 2px rgba(28,32,34,.08), 0 2px 8px rgba(28,32,34,.06)`): 稿纸静息、按钮 hover、输入框聚焦时的微浮。
- **弹层稿纸上浮 (Paper 2)** (`box-shadow: 0 2px 4px rgba(28,32,34,.10), 0 8px 24px rgba(28,32,34,.10)`): 弹窗、下拉、focus 态稿纸。
- 旧拓片硬影仅残留在全局共享按钮骨相（buttons.css `.md-btn` 系，冻结未动）等少数存量，各表面已用 scoped 覆写换代；新表面不得继承。

### Named Rules
**The Pressed-Seal Rule (钤印重力法则).** 按钮的影是其重力的回声：静止无影 → hover 浮起 Paper 1 → active `translateY(1px)` 压下且影清零，如印章落纸。反向（静止带影、按下浮起）一律错误。

**The Seals-Don't-Float Rule (印不浮起法则).** 状态小签与落印用印（「定」字印、三态方印）压纸不浮：不带外投影，只有描边或实底。深度只授予"纸"与"层"，不授予"印"。

---

## 夜色墨韵 (Night Ink Realm)

门面与案头的固定深夜场景（登录/注册、工作台首页 hero、写作台案头带），**不随明暗主题切换**——夜色是场景而非主题。token 一族为 `--md-night-*`（tokens.css 加法式追加，定值不翻转）。

- **落地范围**：夜色只落在门面页与案头容器；正文稿纸、批阅面、弹层、档案区永远保持纸色世界。夜色容器与纸色内容之间是干净硬边，不做渐变过渡带。
- **夜色分层**：底 `--md-night-bg`，边缘以 radial-gradient 压向 `--md-night-bg-deep`；暖光只用 `--md-night-glow-warm` / `--md-night-glow-seal` 两团大面积低透明度光晕，静态，不加呼吸动画。
- **灯下现格**：夜色里不铺界格/行线。唯一例外是书名号正后方以 `mask-image` 径向渐隐显现的一小块稿格（AuthIntro `::after`），格线用 `--md-night-outline`。
- **夜案纸卡**：夜色里的表单卡是"夜案上的一张熟宣"——用 `--md-night-paper` 定值组，并在卡容器局部复写 `--md-surface` 系变量 + `color-scheme: light`（注意 root 处已解析的引用型 token 如 `--md-btn-seal-bg` 必须直接复写其本身）。浮起用 `--md-night-elevation-2`，**影边不叠**（去 1px 边框）。
- **夜色字色**：正文 `--md-night-on`、辅文 `--md-night-on-variant`，不得灰字压夜底；钤印在夜色用更饱和的 `--md-night-seal`（白昼朱砂在夜底发闷）。
- **展示级字级**：门面书名号/书名用 `clamp()` 升至 `--md-display-hero`(72px) 档，上限 6rem 纪律不破，追踪 -0.02em（碑拓骨力的宽字距规则在夜色展示级让位）。
- **案头夜色**（写作台）：暗色铬件+亮色画布构图——标题/工具带沉为 `--md-night-surface` 夜色带并以 `--md-night-elevation-1` 轻压稿纸；tab 笺片行以下归纸世界。安静款工具钮 = 透明底 + `--md-night-outline` 边 + `--md-night-on` 字；AI 权责钮的石青不动。
- **暗室明纸**（写作台铬件）：左栏章节大纲、右栏助手面、项目上下文顶栏（仅 `.app-shell--project-context` 模式，普通页面顶栏永保纸色）一并沉夜；夜色铬件只有 `--md-night-outline` 发线分界，不带投影；当前章高亮 = `color-mix(night-on 8%)` 底 + 左缘 2px `--md-night-seal` 印线；稿纸容器在夜色页底上改用 `--md-night-elevation-1` 纯黑深影，让纸成为暗室里唯一发光的物体。
- **墨碑排印层**：门面与 hero 允许一层巨型低透明度真实字符底纹（clamp 可达 300px+，`color-mix` 自 `--md-night-on` 派生 4-8% 透明度，viewport 出血裁切，`aria-hidden` + `pointer-events:none`）——它受夜色墨韵节制，不受 6rem 展示级纪律约束；阅读级标题仍各自合规。墨碑必须是纯色填充的真实字符，禁渐变填充、禁 SVG 描字。
- **破带缝合**：hero 夜色带与下方纸色区之间，允许一个独立签条（如创作快照）以 `translateY(50%)` 骑跨底缘——上半身压夜色、下半身落纸并回到纸世界 token；一词跨两色的文字拼接禁止。
- **reduced-motion**：夜色不做动效特权，既有入场动画只动 opacity/transform，reduce 下直落终态。

---

## Shapes

- **微直角方章**：2px（`--md-radius-xs`）微圆角是印章、稿纸、输入框、按钮的统一角语，方正如木刻。4px 仅用于笺片 tab 上缘（`4px 4px 0 0`）。禁用胶囊/pill。
- **古籍双线框**：稿纸容器 `border: 3px double var(--md-outline)`，外粗内细的线装本双边，国风内核保留。
- **首字引首章二分**：稿纸首段首字钤印下沉（2.85rem 大字、首行与印底齐平、天然错位斜印 `rotate(-3deg)`）。落墨区 = 焦墨磨砂底 + dashed 斑驳框斜印；描红区 = 朱砂印（`data-provenance="ai"` 覆写）。已定稿的引首章不得见红。
- **笺片连卷**：tab 为笺片式上圆角签条，激活朱砂笺以负外边距压住底线（`margin-bottom: -1.5px`），与内容面无缝连卷。

---

## Components

### Buttons
- **Shape**: 微直角 2px（`--md-radius-xs`），方章骨相。
- **落印主按钮 (Seal Primary)**: 所有"提交/生成/选定/保存成稿/新建与继续创作"类承诺动作 = 朱砂印纽：描红底、熟宣字，hover 转描红深，active `translateY(1px)` 压下且影清零（钤印重力反馈）。全局实现为 `.md-btn-primary`（buttons.css），配色走专用 token `--md-btn-seal-bg` / `--md-btn-seal-bg-hover` / `--md-btn-seal-text`（亮场 = miaohong 系 `#B8402F`/`#9C3323` + `#FAF6ED`；暗场 = `#C04532`/`#AB3729` + `#FBF3E4`，双向对比度 ≥4.5:1）。**一次创作承诺一次落印：每个视图的主承诺动作必须用它，全站不得再出现第三套红。**
- **Filled (焦墨次钮)**: `md-btn-filled` 焦墨底熟宣字，是次要/中性动作（重试、取消类）的默认钮，不再是"主按钮"。
- **Tonal (石青辅钮)**: 石青底熟宣字（暗场 `#33517a`），朗读与 AI 辅助协作入口专用（如「AI优化」），不得挪作通用主按钮。
- **Outlined**: 透明底 1px 框线，focus 时 1px 焦墨 outline；全局 `:focus-visible` 描边为焦墨（`--md-on-surface`），确保红底按钮上焦点可见。

### 方格稿纸 (Signature Container)
- **Background**: 熟宣底 + 横向描红行线（`repeating-linear-gradient`，`--paper-line` 循环）+ 左右朱丝栏竖线，全部由多层 background 一次绘成；`background-attachment: local` 随滚动贴行。
- **Border / Shadow**: 3px double 古籍双线框；Paper 1 柔影。
- **附加肌理（`paper-fold` 层）**: 顶部 8px 紫檀木压纸镇尺、1/3 与 2/3 处三折物理折痕、0.8% 极微透扫墨风竹水印——只叠加在稿纸上，不进结构面。
- **Focus**: 稿纸输入聚焦时 Paper 1 微浮 + 1px 焦墨框线。

### 描红 / 落墨段落 (Signature Prose)
- **描红**: 文字 `--md-miaohong` + `--md-font-kai` 楷体（挂在 `span[data-miaohong]`），段落 wash 底 + 左缘 1px 界栏（挂在 `p:has(span[data-miaohong])`）；容器 `data-provenance="ai"`，首段前 12px 淡朱小签"描红稿 · 待落墨"。
- **落墨**: 色 `--md-luomo`、宋体、底色与界栏撤去；容器 `data-provenance="ink"`。
- **落墨签名动效**: 候选被选定后，旧稿快照原地 260ms 由朱转墨（`chapter-luomo` keyframes：色连续过渡，楷→宋离散翻转，界栏淡出）；同时标题旁钤「定」字朱砂印（34px 方章，1.35s 单帧落印 `rotate(-4deg) scale(1.3)→1`，钤下即走）。`prefers-reduced-motion` 下两者都直落终态，不动画。

### 状态印 (Status Seals)
- **三态**: `描红中`（淡朱描边方印 + wash 底）、`已落墨`（焦墨描边方印）、`已钤印`（朱砂实底方印）。单字或双字，宋体，无外投影——印面压纸不浮起。

### Tabs (笺片连卷)
- **Style**: 笺片式上圆角签条（4px 4px 0 0），1px 界格发线描边，宋体 13.5px/600。
- **Active**: 朱砂描边 + 朱砂字 + 熟宣底，负外边距压住底线，与内容面连卷成一体。

### 朗读条 (Reader Bar)
- **Style**: 熟宣浮起小签（Paper 1），播放中以石青小签标记，石青为朗读专用色；激活控件石青描边/石青字，不借用朱砂。

### 编辑器内核 (MofengEditor)
- **Core**: TipTap 稿纸内核，`MiaohongMark`（`span[data-miaohong]`）承载描红语义；`data-provenance` 承担作者归属，mark 不冗余。
- **API**: `luomoAll()`（全文落墨）、`luomoParagraph(index)`（单段落墨）、`getMiaohongParagraphCount()`；落墨先加 `mofeng-p--luomoing` 过渡类，260ms 后摘除 mark。

---

## Do's and Don'ts

### Do:
- **Do** 用三信号渲染描红稿：淡朱 `#B8402F` + 真楷体 `--md-font-kai` + wash 底/1px 界栏，并标 `data-provenance="ai"`。
- **Do** 让落墨正文回到焦墨 `#1C2224` + 宋体，撤去 wash 与界栏，标 `data-provenance="ink"`。
- **Do** 在全站各表面使用 Paper 1/2 纸页柔影，按钮遵循"静止无影 → hover 浮起 → active 压下清零"的钤印重力。
- **Do** 用 1px 青灰界格发线（`--md-jiege`）划分侧栏与面板结构，用横向行线 + 朱丝栏构建稿纸。
- **Do** 让状态印三态（描红中/已落墨/已钤印）以方印呈现，印不浮起。
- **Do** 把石青 `#2E5C8A` 留给朗读，把朱砂 `#B83C32` 留给落印。
- **Do** 为明暗双主题同时覆盖 token（暗场描红 `#E8836F`、暗场落墨 `#E5DEC9`，wash/line 由 color-mix 自动换算）。

### Don't:
- **Don't** 让已定稿正文出现任何红色——落墨不见红；描红之外的红色只有朱砂钤印一种合法身份。
- **Don't** 把楷体用于落定正文、标题、按钮或状态印——楷体即草稿。
- **Don't** 在任何表面新增拓片偏置硬投影或 >8px 模糊的高斯弥散影；纸页柔影是唯一的影。
- **Don't** 把稿纸行线、朱丝栏、米字格铺到稿纸容器以外的表面；阅读面禁用米字格全覆盖底纹。
- **Don't** 用卡片堆卡片、eyebrow/kicker 小字眉、渐变文字、玻璃拟态、unicode/emoji 当图标、>1px 彩色 border-left（描红界栏是 1px，合规）。
- **Don't** 改旧 token 变量值导致未改造表面变色——token 演进必须加法式。
