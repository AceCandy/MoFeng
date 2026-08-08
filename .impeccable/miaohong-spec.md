# 描红界格 · 旗舰构建规格（写作台 P1）

> 方向契约 seed key `6978e4f1`，见 `frontend/index.html` body 首注释。所有构建代理必须遵守本规格；与旧视觉冲突时以本规格为准。

## 1. 世界观一句话

AI 写的是**淡朱楷体描红稿**，作家审定**落墨**（焦墨宋体）才算正文；**朱砂只作落印钤章**。界格不是装饰，是书写的规尺：阅读/书写面 = **方格稿纸行笺**，结构面 = **青灰界格发线**。

## 2. 新 Token（加进 `frontend/src/assets/styles/tokens.css`，增改不删旧变量）

```
/* 描红界格世界 */
--md-miaohong: #B8402F;            /* 描红正文（熟宣上对比度 4.7:1，AA 达标） */
--md-miaohong-strong: #9C3323;     /* 描红 hover/强调 */
--md-miaohong-soft: #CE5A47;       /* 双钩淡朱：大字标题/装饰/界格（仅 ≥24px 大字或非文本） */
--md-miaohong-wash: color-mix(in srgb, var(--md-miaohong) 5%, transparent);   /* 描红块底色 */
--md-miaohong-line: color-mix(in srgb, var(--md-miaohong) 22%, transparent);  /* 稿纸行线 */
--md-miaohong-line-strong: color-mix(in srgb, var(--md-miaohong) 38%, transparent); /* 稿纸边栏/米字主笔 */
--md-jiege: color-mix(in srgb, var(--md-primary-light) 26%, transparent);     /* 青灰界格发线（结构面） */
--md-luomo: #1C2224;               /* 落墨正文色（= --md-on-surface，语义别名） */
--md-font-kai: 'Kaiti SC','STKaiti','KaiTi','AR PL UKai CN','AR PL KaitiM GB','TW-Kai',serif; /* 真楷体：描红稿专用 */
```

暗色主题（`:root[data-theme='dark']`）对应值：
```
--md-miaohong: #E8836F;            /* 暗场描红（深夜书房对 #1A1F21 ≥4.5） */
--md-miaohong-strong: #F09B8A;
--md-miaohong-soft: #C96A58;
--md-luomo: #E5DEC9;               /* = 暗场 --md-on-surface */
```
`--md-miaohong-wash/-line/-line-strong` 暗场下把 mix 基准换成 `var(--md-miaohong)` 即可（变量自引用无需改）。

**Elevation 换代**：写作台域内停用 `--md-elevation-*` 拓片硬投影（零模糊块影）。新纸页层级：
```
--md-elevation-paper-1: 0 1px 2px rgba(28,32,34,.08), 0 2px 8px rgba(28,32,34,.06);   /* 浮起纸页 */
--md-elevation-paper-2: 0 2px 4px rgba(28,32,34,.10), 0 8px 24px rgba(28,32,34,.10);  /* 弹层/稿纸上浮 */
```
（旧 `--md-elevation-*` 变量保留给其他未改造表面，写作台域新样式一律用 paper 系。）

## 3. 方格稿纸（chapter-paper 重构，覆盖 `frontend/src/assets/styles/components/chapter-paper.css` 的写作台相关段）

- 行线：`repeating-linear-gradient(to bottom, transparent 0, transparent calc(var(--paper-line) - 1px), var(--md-miaohong-line) calc(var(--paper-line) - 1px), var(--md-miaohong-line) var(--paper-line))`，`--paper-line` = 正文行高（15px × 1.8 = 27px）。行线只出现在**稿纸书写/阅读容器**内，绝不铺到侧栏、面板、弹窗底色。
- 竖格：稿纸容器左右缘各一道 `var(--md-miaohong-line-strong)` 1px 竖线（朱丝栏遗意），左右 padding ≥32px。
- 底：熟宣 `var(--md-surface)`，不得用纯白；古籍双线框（`3px double var(--md-outline)`）保留——它是国风内核的一部分。
- 阅读面**禁用**米字格全覆盖底纹（伤长文阅读）；米字格只允许出现在空状态大字、章节卡封面这类非连续阅读区。

## 4. 描红 / 落墨 语法（本世界的灵魂，必须三信号齐备）

描红稿（AI 产出、待作家审定）的渲染规则，三个信号缺一不可：
1. **色**：文字 `--md-miaohong`（正文）；
2. **字族**：`--md-font-kai` 楷体（与落墨宋体形成字形对比，色盲可辨）；
3. **面**：所在段落/块底色 `--md-miaohong-wash` + 左缘 1px `--md-miaohong-line-strong` 界栏。

落墨后：色 `--md-luomo`、字族宋体（`--md-font-serif`）、底色与界栏撤去。
语义标注：描红容器 `data-provenance="ai"`，落墨容器 `data-provenance="ink"`（测试与 a11y 钩子用）。描红区首段前有一个小字签：`描红稿 · 待落墨`（`--md-miaohong`，12px label）。

**落墨动作**是世界的签名交互：一个 140–280ms 的过程——文字由朱转墨（color transition）+ 楷转宋（font-family 切换，允许瞬间切换但配 color 过渡），同时段落左缘界栏淡出。全章落墨时伴随一次**落印**：朱砂印章在章节标题旁盖下（既有 `WDSealStamp`/phase12-save-stamp 的印章资产可复用），印记以 `transform: scale(1.15)→1` + `opacity 0→1` 单帧落印动效完成，`prefers-reduced-motion` 下直接呈现。

## 5. 组件语法

- **落印主按钮**：所有"提交/选定/保存成稿"类主动作 = 朱砂印纽：方章微圆角 2px、朱砂底、熟宣字、hover 时 `--md-miaohong-strong`、按下时 `transform: translateY(1px)`。类名沿用 `md-btn md-btn-primary` 体系扩展，不改既有按钮 DOM 结构语义。
- **界格结构面**：侧栏章节列表、面板分隔用 `--md-jiege` 1px 发线，不用卡片堆卡片（craft-floor：嵌套卡片永远错）。
- **状态印**：章节状态三态——`描红中`（淡朱描边方印）、`已落墨`（焦墨描边方印）、`已钤印`（朱砂实底方印）。单字或双字，宋体。
- **禁止**（craft-floor）：eyebrow/kicker（`workspace-eyebrow` 类在写作台域移除）、渐变文字、玻璃拟态、硬偏置块影、unicode/emoji 当图标、>1px 彩色 border-left（描红界栏是 1px，合规）、同尺寸卡片阵列当页面结构。

## 6. 不得触碰的产品契约（语义保留）

- XState 工作流全部状态文案与按钮名：`尚未开始生成/章节生成中/请选择候选版本/正在提交正文/正文已提交/本轮需要处理/本轮已取消/章节工作流已完成/章节状态暂不可信`；按钮 `开始生成/选定并继续/重试/确认风险并重试/重试同步/重新同步/取消`；dialog `确认外部重试风险`；radio `候选版本 N`；`role=status/alert`、`aria-live` 语义。
- SSE/XState/TanStack Query 数据层、API 类型、路由、导航守卫。
- 断点 833/834/1199/1200、44px 触控尺寸。
- 写作台三栏 grid 结构（侧栏 | 工作区 | 助手抽屉）与抽屉行为。
- 未改造表面（工作台首页、灵感、档案、设置、admin、登录注册）继续运行——token 演进必须加法式，不得改旧变量值导致其他表面变色。

## 7. 测试

- 视觉契约测试随新世界重写（用户已批准）；语义契约（§6）一字不动。
- 所有新交互补单测：描红渲染三信号、落墨动作、落印动效类名。
