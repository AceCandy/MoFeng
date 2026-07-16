# 手测清单 — PersonalModelRouting 拆分回归网

> prd 要求「行为等价（测试或手测清单覆盖分区切换/模型选择/保存）」。用户确认采用手测清单固化 + 少量纯逻辑单测。
> 每个相关 Slice 完成后跑对应项；全量拆分收尾时整体跑一遍。配合 `modelRoutingHelpers.spec.ts` 纯逻辑单测。

前置：进入「设置 → 模型路由」，确保至少有一个已配置供应商 + 已拉取模型的环境。

## 1. 分区切换（llm/embedding/tts/routes）
- [ ] 四 tab 切换：sectionEyebrow（文本生成/记忆检索/语音朗读/阶段覆盖）、sectionHeading、sectionDescription、readiness 摘要文案与计数正确。
- [ ] 切换分区时，若 model-picker 打开则自动关闭。
- [ ] provider-grid 只显示当前 capability 的供应商（activeProviders 过滤）。

## 2. 供应商 CRUD
- [ ] 新增供应商：create 表单填名称/类型/URL/Key → 保存 → 成功提示 + emit('saved') 父刷新 + 表单退出。
- [ ] 编辑供应商：行内 edit 表单 → 改名/URL → 保存 → 生效；Key 留空则保留已存。
- [ ] 启用/停用：toggle 按钮 → 状态翻转 + 提示。
- [ ] 删除供应商：确认弹窗 → 删除 + 关联模型/路由清理 + 提示。
- [ ] 非法输入（空名称/URL）→ 错误提示，不提交。

## 3. 模型拉取弹窗（核心）
- [ ] 点「拉取模型」→ 弹窗 fixed 定位在按钮下方，不溢出视口；底部空间不足时向上翻转/收边。
- [ ] 搜索框过滤模型名；ESC 关闭。
- [ ] chat 分区：多选 checkbox（pending 勾选，保存前不写后端）；行高亮跟随 pending。
- [ ] embedding 分区：单选 radio，选中即当前检索模型。
- [ ] tts 分区：单选 radio + 保存按钮。
- [ ] 保存 → emit('saved') + 弹窗关闭 + 已选列表更新。

## 4. 外部点击 / 视口变化
- [ ] chat 有未保存改动时点外部 → 弹「确认放弃」；无改动直接关。
- [ ] 点「拉取模型」触发按钮不触发关闭（aria-haspopup 判定）。
- [ ] 页面滚动/窗口缩放 → 弹窗关闭（picker 内部滚动除外）。

## 5. 主模型（llm）
- [ ] 主模型 select 切换 → primaryChatModel 更新 + readiness 文案变化。
- [ ] 删除主模型 → 拦截提示「请先选择另一个主模型」。
- [ ] 停用主模型 → 拦截提示。

## 6. 阶段路由（routes）
- [ ] 各 stage select 选模型 → 「保存阶段路由」→ 成功提示 + emit('saved')。
- [ ] isDirty：改动未保存时为 true；保存后归 false。
- [ ] 无启用 chat 模型 → 空状态 + 「去配置文本生成」按钮 emit('navigate', 'llm')。

## 7. 对外契约（defineExpose）
- [ ] 父组件 ref.save() 在 routes 分区 → 调 saveRoutes；在 providerForm 打开时 → 调 saveProviderForm；否则提示「已自动保存」。
- [ ] isDirty 在 providerForm 打开 / routeSelections 改动时为 true。

## 8. 模态形态（isModal=true）
- [ ] isModal 时隐藏「刷新」「保存阶段路由」「新增供应商」顶栏按钮（template v-if="!props.isModal"）。
