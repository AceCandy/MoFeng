---
name: MoFeng (墨风)
description: 强烈大气中国风的AI长篇小说创作工作台。徽墨熟宣、古籍双边与朱砂印鉴。
colors:
  primary: "#1C2022"
  primary-light: "#3A4648"
  primary-dark: "#111415"
  on-primary: "#FAF6ED"
  primary-container: "#2E5C8A"
  on-primary-container: "#FFFFFF"
  secondary: "#B83C32"
  secondary-container: "#FBEBEA"
  on-secondary-container: "#5C120C"
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
  error: "#C0392B"
  error-container: "#FBEBEA"
  success: "#3B7A57"
  success-container: "#EAF3EE"
  warning: "#E6A23C"
  warning-container: "#FDF6EC"
typography:
  display:
    fontFamily: "STSong, Songti SC, Noto Serif CJK SC, Source Han Serif SC, serif"
    fontSize: "48px"
    fontWeight: 400
    lineHeight: 1.2
    letterSpacing: "0.08em"
  headline:
    fontFamily: "STSong, Songti SC, Noto Serif CJK SC, Source Han Serif SC, serif"
    fontSize: "30px"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "0.05em"
  title:
    fontFamily: "STSong, Songti SC, Noto Serif CJK SC, Source Han Serif SC, serif"
    fontSize: "20px"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "0.03em"
  body:
    fontFamily: "Noto Sans SC, PingFang SC, Hiragino Sans GB, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.8
    letterSpacing: "0.01em"
  label:
    fontFamily: "Noto Sans SC, PingFang SC, Hiragino Sans GB, sans-serif"
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
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.label}"
    rounded: "{rounded.xs}"
    padding: "0 24px"
    height: "44px"
  button-tonal:
    backgroundColor: "{colors.primary-container}"
    textColor: "{colors.on-primary-container}"
    typography: "{typography.label}"
    rounded: "{rounded.xs}"
    padding: "0 24px"
    height: "44px"
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.on-surface}"
    rounded: "{rounded.sm}"
    padding: "24px"
    border: "1px solid {colors.outline}"
  input:
    backgroundColor: "transparent"
    textColor: "{colors.on-surface}"
    rounded: "{rounded.xs}"
    padding: "16px"
    height: "52px"
    border: "1px solid {colors.outline}"
  chip:
    backgroundColor: "{colors.surface-container}"
    textColor: "{colors.on-surface-variant}"
    typography: "{typography.label}"
    rounded: "{rounded.xs}"
    padding: "0 16px"
    height: "32px"
---

# Design System: MoFeng (墨风)

## 1. Overview

**Creative North Star: "墨砚书香，方圆风骨" (The Ink-Wash & Xuan-Paper Sanctuary)**

墨风 (MoFeng) 是一套专为长篇虚构小说创作者打造的沉浸式 AI 写作控制中心。本设计系统旨在跳出喧嚣泛滥的现代 SaaS 扁平范式，将视觉语言迁移为**强烈、大气且极具风骨的古典中国风**。它不仅是创作的工具，更是创作者桌案前一案、一砚、一纸、一墨的文人精神投射。

我们追求的国风不是肤浅的古风插画堆砌，也不是喧宾夺主的戏曲脸谱装饰，而是提取古典书斋中的核心哲学——**宣纸的润、徽墨的骨、朱砂的醒、留白的意**。系统在保持极低视觉疲劳度的安静写作氛围之余，在关键的骨架、排版、细节上展现出坚毅挺拔的大气格局。

**Key Characteristics:**
- **古籍风骨的双栏规架**：卡片、输入框与布局边缘采用利落微小的直圆角，并辅以古籍线装本特有的粗细双线（双边）来划分版面，极具碑拓与刻本的骨力。
- **熟宣玉版的温润底色**：大面积的阅读区和主背景选用模拟老宣纸、竹纸的微黄暖色，全面隔绝蓝光刺眼，提供持久专注的生理基础。
- **徽墨五色的色彩层次**：文字与基础架构由黑至灰均带有一丝古朴的青蓝色相（松烟），展现出水墨晕染的丰富细节。
- **朱印朱批的黄金点缀**：所有完成状态、高亮警示与核心动作，均被重塑为苍劲有力的“传统朱砂篆刻印章”和“朱批”，作为古典的烙印跃然纸上。

---

## 2. Colors

墨风的调色盘源自古典矿物颜料与水墨意象。以宣纸色为地，焦墨松烟为骨，朱砂丹青为魂。

### Primary
- **焦墨** (`#1C2022`): 全局最重的结构骨架色、核心文字色与一级主动作按钮。沉稳、厚重，如浓墨落纸。
- **松烟** (`#3A4648`): 次级结构线条与中性控制元件。带有古雅青蓝色相的松烟墨色。
- **漆黑** (`#111415`): 高度强调状态或 hover 时的加深墨色。
- **石青** (`#2E5C8A`): 点缀主动作按钮容器色，用于承载 AI 辅助等协作交互，克制地暗示灵感之水。

### Neutral (徽墨熟宣)
- **熟宣** (`#FAF6ED`): 主编辑和正文阅读区的主表面色。温润淡雅，柔和不刺眼。
- **老宣** (`#F0EAD8`): 应用级全局底色和未选中的深色容器面，形成极佳的视觉景深。
- **素骨** (`#F2ECE0`): 侧边栏与整体大背景色，如素木古骨。
- **竹纸** (`#FAF7E8`): 卡片和高亮度区域底面，呈天然竹浆暖黄。
- **竹青** (`#C2B69D`): 主边框线与框栏，带有极淡青灰感的干燥竹本色。
- **墨晕** (`#DCD2BE`): 副线条与微弱的分层框栏。

### State
- **丹砂** (`#C0392B`, container `#FBEBEA`): 错误、终止、强警示。极具穿透力的丹砂红。
- **朱砂** (`#B83C32`, container `#FBEBEA`): 成功、确定状态以及“朱砂印章”专用色。代表金石篆刻的权威与落款。
- **石绿** (`#3B7A57`, container `#EAF3EE`): 辅助成功态或正面参数反馈。
- **藤黄** (`#E6A23C`, container `#FDF6EC`): 警示与进行中。

### Named Rules
**The Rare Vermilion Rule (朱砂罕用规则).** 朱砂红 (`#B83C32`) 是墨风的视觉灵魂。它只被允许出现在方形印章、成功态的印记落款或极致强调的单一按钮上，大面积页面中朱砂红的使用面积绝对不可超过 3%。

**The Xuan Paper Warmth Rule (宣纸温润规则).** 所有章节长正文、段落优化器和 AI 评审生成内容，其底色必须为熟宣纸色 (`#FAF6ED`) 或竹纸暖黄 (`#FAF7E8`)。严禁使用纯白 (`#FFFFFF`) 或高饱和度的彩色背景承载文字，以此守护作家的生理阅读疲劳极限。

---

## 3. Typography

**Display Font:** STSong, Songti SC, Noto Serif CJK SC (宋体字族) 
**Body Font:** Noto Sans SC, PingFang SC (现代人文黑体 fallback)
**Label/Mono Font:** JetBrains Mono (代码与参数), STKaiti, Kaiti SC (批注与灵感楷体)

**Character:** 墨风的排版哲学讲究“骨力与留白”。凡标题、大字必用宋体展现刀刻石碑的苍劲力量；凡正文阅读与操作控件必用人文感十足的无衬线黑体确保极佳的易读性；凡 AI 灵感、备忘朱批则使用飘逸灵动的楷体。

### Hierarchy
- **Display** (400, 48px, 1.2, letterSpacing 0.08em): 极少使用。仅用于空状态的大字留白或书架欢迎页。
- **Headline** (600, 30px, 1.3, letterSpacing 0.05em): 页面主标题、小说书名与核心工作区章节大字标题（如“第一章 问剑”）。
- **Title** (600, 20px, 1.4, letterSpacing 0.03em): 卡片标题、弹窗头部、操作栏分组名。
- **Body** (400, 15px, 1.8, letterSpacing 0.01em): 正文阅读与创作的核心行高。正文行长必须被框定在 65–75ch（约 30-38 个中文字符）之间，字间距微微舒展，呈现极佳的中文排版质感。
- **Label** (600, 12px, 1.4, letterSpacing 0.04em): 按钮文字、状态印章、元数据与小辅助标记。

### Named Rules
**The Editorial Spine Rule (碑拓骨力规则).** 凡是使用宋体（Display、Headline、Title）的段落，必须显式拉开字间距 (`letter-spacing`)。小字标题拉开 `0.03em`，大字标题拉开 `0.05em` 以上。字与字之间的适度留白，能极大增强古典石刻拓片的大气格局。

---

## 4. Elevation

墨风完全唾弃西方现代 SaaS 常用的“大范围弥散模糊投影”（SaaS Soft Shadows）。这种现代的阴影过于电子化，会剥夺国风的“平面纸质风骨”。

墨风采用**“方正平铺、双线分层” (Flat & Framed)** 的层级哲学。我们通过微弱的背景色差（如熟宣与老宣的交错）、坚挺的古籍双边框以及极少数硬朗的“拓片阴影”来区分图层。

### Shadow Vocabulary
- **拓片暗影 (Elevation 1)** (`box-shadow: 2px 2px 0px rgba(28, 32, 34, 0.15)`): 用于悬浮卡片、下拉菜单或弹窗底面。它不是模糊的模糊影，而是具有坚硬边缘的、类似拓片刻印产生的右下偏置硬投影。
- **朱印深拓 (Elevation 2)** (`box-shadow: 3px 3px 0px rgba(184, 60, 50, 0.2)`): 仅用于被选中的古籍卡片或朱砂按钮 hover，赋予其金石压印的力道。

### Named Rules
**The Border Over Shadow Rule (线框胜于投影规则).** 严禁使用大于 8px 模糊半径 (`blur-radius`) 的模糊阴影。所有界面的卡片、面板划分必须优先使用 1px 的竹青框线 (`#C2B69D`) 或墨晕细线 (`#DCD2BE`) 配合背景色差进行分割。

---

## 5. Components

### Buttons
- **Shape**: 利落的极微圆角（直角 2px / `--md-radius-xs`），展现木刻折页的方正感。绝不用大圆角或胶囊 pill 形状。
- **Primary (焦墨主按钮)**: 背景为 `#1C2022`，文字为熟宣色 `#FAF6ED`。边缘带有竹青色单像素极细描边。
- **Tonal (石青辅助按钮)**: 背景为 `#2E5C8A`，文字为纯白，用于 AI 优化等创意核心行动，营造典雅高贵的“石青点晴”。
- **Outlined (古籍框线按钮)**: 背景透明，边框为 1px 竹青线，文字为焦墨色。Hover 时背景转为 `surface-container-high`。

### Chips
- **Style**: 背景为熟宣淡灰 `#F6F0E0` 或老宣底色 `#F0EAD8`，四周为 1px `#DCD2BE` 框线。使用 Label 字体。
- **朱砂印鉴状态 (Signet Seal Tag)**: 章节完成状态（“已完成”、“已保存”）摒弃常规 Tag 样式，设计成**四周带有一圈细微仿古斑驳边框的朱砂红印章样式**，使用楷体/宋体单字或双字（如“完成”、“成稿”），为整页打上古色落款。

### Cards / Containers
- **Corner Style**: 4px (`--md-radius-sm`) 或 6px (`--md-radius-md`) 极微圆角。
- **Double Border (古籍双栏框)**: 核心卡片（如书架上的书本卡片、主写作区的中央编辑容器）外围使用**古籍线装本特有的双线边框**（外粗内细，或者双 1px 细线，CSS 表现为 `border: 3px double var(--md-outline)`），瞬间拉满强烈的中文古籍仪式感。
- **Internal Padding**: 增加呼吸感。中大型卡片内边距固定为 `24px` (`--md-spacing-6`) 或 `32px` (`--md-spacing-8`)，配合汉字提供充足的“留白”。

### Inputs / Fields
- **Style**: 极微圆角 2px。背景透明，四周为 1px `#C2B69D` 竹青框线。
- **Focus**: 四周围绕 1px 焦墨框线，且右下产生 `2px 2px 0px rgba(28,32,34,0.2)` 的硬投影作为焦点反馈。

### Navigation
- **Style**: 侧边栏及顶栏导航文字一律采用宋体 Headline/Title。Active 活动态不使用色块，而是使用**“左侧一笔朱砂红竖描”或“一小枚朱砂阳刻方印”**作为极简而大气的活动指示器。

---

## 6. Do's and Don'ts

### Do:
- **Do** 使用熟宣色 (`#FAF6ED`) 和竹纸黄 (`#FAF7E8`) 作为长篇文字的主要承载背景。
- **Do** 在 Display 与 Headline 标题中强制使用古典宋体，且字间距必须拉开至少 `0.05em`。
- **Do** 使用 1px 竹青框线 (`#C2B69D`) 或古籍双线框 (`border: 3px double`) 来划分板块，而不是依靠模糊阴影。
- **Do** 将关键状态 Badge 封装为“朱砂红仿古方印”的印鉴样式，为现代界面点睛。
- **Do** 在按钮和输入框上使用微小的 2px - 4px 极窄圆角，维持方正古朴的木刻竹简风骨。

### Don't:
- **Don't** 使用任何现代 SaaS 软件特有的紫蓝色 AI 渐变背景（Purple-blue AI Gradients）或霓虹发光文字。
- **Don't** 使用玻璃拟态（Glassmorphism）、毛玻璃背景模糊和现代卡片高斯模糊投影。
- **Don't** 在按钮、卡片、输入框上使用现代大圆角（Pill/Capsule layout）或完全圆滑的边角。
- **Don't** 在中式设计中堆砌大面积毫无功能意义的“古风山水插画”或“戏曲脸谱小插画”，这会沦为廉价的装饰性设计。
- **Don't** 允许朱砂红 (`#B83C32`) 的大面积滥用，它的存在必须像画龙点睛的墨宝印鉴一样稀少而尊贵（小于 3% 面积）。
