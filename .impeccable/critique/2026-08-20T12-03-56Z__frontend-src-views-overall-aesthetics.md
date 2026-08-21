---
target: 整体样式美观度（frontend/src 全表面）
total_score: 22
max_score: 40
na_heuristics: 
p0_count: 2
p1_count: 2
timestamp: 2026-08-20T12-03-56Z
slug: frontend-src-views-overall-aesthetics
---
# Critique: MoFeng 前端整体样式美观度（frontend/src 全表面）

## Design Health Score: 22/40（Acceptable）

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | 任务日志/状态印/进度条在；但「今日目标」对 0/0 章新项目错报"进入收尾润色/正文已齐备"（NovelWorkspace.vue:371-395） |
| 2 | Match System / Real World | 2 | 书卷/阁主/落墨隐喻好；但任务日志漏工程师词汇（"rag 投影/trace 投影"），路由页"共用路由/向量模型" |
| 3 | User Control and Freedom | 3 | 取消/确认/版本回退在；侧栏 25+ 删除图标钮与章节钮并列，误触面大 |
| 4 | Consistency and Standards | 2 | 主按钮三色内战（继续写作=焦墨/新建灵感=石青/落墨保存=朱砂）；DESIGN.md 与 buttons.css:98 注释各说各话；简繁混排（闭/閉、夜/晝） |
| 5 | Error Prevention | 3 | 删除确认、禁用态在；「新建灵感项目」一键落库无命名步骤 |
| 6 | Recognition Rather Than Recall | 2 | [始]/[歸]/夜晝/闭輔 单字印章钮无文字标签；设置弹窗"存"印管辖范围不明 |
| 7 | Flexibility and Efficiency | 1 | 全站 0 快捷键（90 个 .vue 中 ctrlKey/metaKey 零命中），无命令面板 |
| 8 | Aesthetic and Minimalist Design | 2 | 中栏稿纸构图好；顶栏 1440px 折行溢出、卡片装饰过度、AI 菜单脱锚、移动端白屏 |
| 9 | Error Recovery | 2 | dashboard 错误态有重试/snackbar；完整错误链路未实机验证 |
| 10 | Help and Documentation | 2 | 设置页引导文案出色；无新手引导、阶段路由 22 节点无解释 |

## Design Specificity Verdict

**LLM assessment**：一半 authored，一半地层堆积。写作台的「颜色即权责」真实落地（版本面板不读字即可辨权责、稿纸行线/朱丝栏/引首章纪律良好）、用户菜单五色小方印有性格、登录页品牌入口成立。但 brand-visuals.css（"第四阶段·墨落惊风雨"遗留）仍全局注入狂草大水印、项目卡石青书脊+装订孔+「藏書」闲章，与 ProjectCard.vue 的 3px double 双边+hover「卷」印同卡打架——两个视觉世界未完成换代，DESIGN.md 声称的"全站完成换代"未兑现。工作台首页比写作台吵得多，不像同一产品。

**Deterministic scan**：CLI 3 条 findings —— codex-grid-background ×2（brand-visuals.css:28、InspirationMode.vue:753）、side-tab ×1（BlueprintDisplay.vue:654 的 3.5px 左色条，直接违反本项目 Don't ">1px 彩色 border-left"）。浏览器覆盖层 5/5 页注入成功：设置页 15 条（undersized-ui-text 10px ×13、text-occlusion ×1）、写作台 31 条（clipped-overflow ×6、low-contrast 多条、wide-tracking、text-occlusion "3639 字"被删除钮遮 33% 等）、灵感页 low-contrast 1.7:1 + flat-type-hierarchy 11 档、工作台 nested-cards ×2。

**检测器补盲**：10px 功能小字在设置页成体系（评审未单列）；"3639 字"被删除钮遮挡是实测硬证据。**误报**：radial-halo（全局品牌水印底）、marquee（Material 进度条动画）、repeating-stripes（稿纸行线，设计核心）、brand-visuals.css:28 网格（书脊设计注释明示）。**存疑**：dark-glow #b8402f 深色页发光——DESIGN.md 禁非纸影弥散，倾向真违规。

## Overall Impression

写作台中栏是极有自觉的 AI 写作界面，描红/落墨双色同栏是真设计；但三处失控拖累全局：两个 P0 渲染 bug、一套自相矛盾的按钮颜色权责、一个没有清场的旧视觉地层。最大机会不在修补，而在手机批阅流与"生成即研墨"的等待舞台。

## What's Working

1. 版本面板权责双态：版本 1 淡朱楷体红框 vs 版本 2 灰墨，不读字即辨权责。
2. 任务日志弹窗：左列表右详情+时间线+进度条，AI 流水线全程可查，结构克制。
3. 编辑弹窗：行线稿纸+实时字数统计+取消/落墨保存（唯一用对朱砂主钮的提交）。

## Priority Issues

- **[P0] 390px 移动端写作台白屏**：干净刷新后主体整屏空白，面板位于滚动容器负坐标 -2188px 不可达。Fix：≤833px 给写作台静态文档流，抽屉改 fixed 遮罩层；先保"读+批"。Suggested command: $impeccable adapt
- **[P0] AI 优化下拉菜单脱锚**：.writing-workspace__ai-menu 无定位规则，面板锚到遥远祖先，渲染在视口底部被裁半。Fix：一行 `position: relative` + 回归测试。Suggested command: $impeccable harden
- **[P1] 主按钮权责三色内战**：DESIGN.md "落印主按钮=描红底" vs tokens.css:22 `--md-primary:#1c2022` 焦墨；继续写作=黑/新建灵感=蓝/落墨保存=红/AI优化=红描边/开始生成=黑。Fix：只留一个 seal-primary 朱砂，md-btn-filled 降为次要墨钮，石青收回朗读专用，同步 DESIGN.md 与 tokens 单一事实源。Suggested command: $impeccable distill
- **[P1] 「今日目标」逻辑谎报**：0/0 章新项目收到"正文已齐备"。Fix：分支前加 total_chapters>0 判断。Suggested command: $impeccable harden
- **[P2] 写作台顶栏超载+简繁混排**：9 控件折行（蓝图概览竖断）。Fix：顶栏只留书名+章名+一个主钮；印章用字立对照表全站统一。Suggested command: $impeccable layout

## Persona Red Flags

- **Alex（效率写手）**：零快捷键、100+ tab 停留点含 25 个删除雷区、AI 菜单脱锚（每天点几十次的主菜单开在屏外）。
- **Jordan（首次使用）**：一键落库"未命名灵感"空壳项目+「今日目标」谎称齐备，第一天信任打折；[始]/[歸] 无说明；术语墙无缓坡。
- **Sam（读屏/键盘/对比度）**：跳到主内容链接、完整 aria-label、axe 0 硬违规是好底子；但右侧面板在 a11y 树串成一长串无标题结构、focus-visible 竹青描边在红钮上不可见、88 节点对比度无法自动判定。

## Minor Observations

- 墨点晕染加载态是全站最可爱的细节，值得做成系统组件。
- "存"字印半挂弹窗外、管辖范围不明。
- --md-font-mono 被强制宋体，URL/Key/时间戳衬线化，扫描性受损。
- 暗色模式下昼夜钮挪用石绿"晝"印。
- ProjectCard.vue:149 hover「卷」印被 brand-visuals.css:67 !important 覆盖，死代码两代打架。
- 深色登录页 dark-glow #b8402f 疑似违反"纸页柔影是唯一影"。
- AI 两个入口两种色相（石青新建灵感/朱砂描边 AI优化），AI 无统一颜色人格。

## Questions to Consider

1. 既然"颜色即权责"是北极星，为什么作家每天按最多次的"开始生成/继续写作"是匿名黑和借来的蓝？最郑重的颜色给了最低频的动作。
2. 移动端写作台已实质不存在——与其修缩水三栏，为什么不承认手机上的作家是"批阅官"：逐段滑过描红稿、点「定」落墨、滑走？
3. 生成等待是全产品最长的谷，而稿纸是现成的最好舞台：为什么不让描红稿在界格里逐行浮现，让等待本身成为"文思研墨"的峰？
4. 印章到底是权责符号还是贴纸？现在它同时是状态印/菜单图标/卡片角章/关闭钮/昼夜切换。要么执行纪律，要么重写规则——两个世界都是好世界，现在两个都不是。
5. "第四阶段·墨落惊风雨"的狂草水印、书脊、装订孔还活在全站 CSS 里。要不要做一次"焚稿"：删掉 brand-visuals.css 整层，看产品安静下来之后是不是真的更好？
