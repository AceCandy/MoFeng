# design.md — 拆 PersonalModelRouting.vue（2684 → <500）

> 复杂任务技术设计。逐 slice 演进，实现时 codegraph 细查精确符号，本表给边界契约与 roadmap。

## 1. 目标与约束

- `frontend/src/components/llm-settings/PersonalModelRouting.vue` 2684 行 → **<500 行**，运行时行为 100% 等价。
- 三段现状：template L1-535（535）/ script L537-1772（1235）/ style L1774-2684（910）。
- 属 parent `07-12-engineering-baseline` acceptance 第 4 项。
- **不过度抽象**（WritingDesk 教训）：只抽有独立 UI 职责的真子组件 + 内聚状态机 composable；不为达行数硬指标做纯透传 wrapper。
- 拆分路径：script composable 先（降 script + 稳定符号），template 子组件后（降 template + scoped 迁移），style 随子组件迁移。同 WritingDesk/NovelDetailShell 范式。

## 2. 对外契约（拆分后必须 100% 保持）

| 契约 | 来源 | 说明 |
|---|---|---|
| `defineExpose({ isDirty, save })` | L1760-1771 | LLMSettings/SettingsView 通过 ref 调用 `save()`；`isDirty` 判脏。save 内部分发 routes/providerForm/无操作三态，不能改语义。 |
| `emit('saved')` | L606-609 | 每次成功 mutation 后触发，父组件据此刷新。 |
| `emit('navigate', section)` | L606-609 | template L66 "去配置文本生成" 按钮触发。 |
| props `activeSection` / `isModal` | L611-620 | 父组件控制分区/模态形态。 |
| model-picker `id="model-picker-${id}"` + 函数 ref | L345-346, L798-803 | v-for 内字符串 ref 会被收集成数组，故用函数 ref 取单个 DOM + id 选择器判定外部点击（onPickerClickOutside/onPickerViewportChange）。**拆 ModelPickerDialog 子组件时此 hack 必须忠实保留。** |
| Teleport to body + fixed 定位 | L342, L1291-1313 | 弹窗脱离 v-for 子树定位到 body，靠 `modelPickerPosition` 计算 fixed 坐标。 |

## 3. 拆分边界契约表

### 3.1 静态数据 / 类型（最先抽，零依赖）

| 产物 | 迁出符号 | 行 | 依赖 |
|---|---|---|---|
| `stageDefinitions.ts` | `stageGroups: StageGroup[]`（L624-764 静态数组）+ `StageDefinition`/`StageGroup` interface | ~145 | 无（纯数据） |
| `modelRoutingTypes.ts` | `Capability`/`RoutingSection`/`ProviderFormMode`/`ReadinessTone` + `ProviderForm`/`ProviderFetchState`/`ReadinessSummary` interface | ~40 | 无 |
| `modelRoutingHelpers.ts` | 纯函数：`createModelPayload` / `modelDisplayName` / `activeModelCapability` / `providerCapabilities` / `createProviderCapabilities` / `providerTypeLabels` / `groupModelsByProvider`（参数化 models） | ~120 | types only；**便于单测** |

### 3.2 composable（script 拆分，入参透传 composable 返回值，同 WritingDesk）

| composable | 内化符号 | 入参（透传） | 返回 |
|---|---|---|---|
| `useModelBundle` | bundleQuery + 9 mutation + `providers`/`models`/`isLoading`/`isSavingProvider`/`isSavingRoutes` computed + `feedback`/`setFeedback` + `loadBundle` | 无（或 props.id 若需） | 上述全部 |
| `useSectionMeta` | `activeProviders` + `sectionEyebrow`/`sectionHeading`/`sectionDescription`/`sectionReadinessSummary` + `enabledChatModels`/`primaryChatModel`/`enabledEmbeddingModels`/`defaultEmbeddingModel`/`enabledTTSModels`/`defaultTTSModel` + `chatModelsByProvider`/`embeddingModelsByProvider`/`ttsModelsByProvider` + `configuredRouteCount` | bundle（providers/models）+ activeSection + routeSelections/allStageKeys | computed 群 |
| `useStageRoutes` | `routeSelections`/`initialRouteSelections` + `chatStageGroups`/`allStageKeys` + `syncRouteSelectionsFromBundle` + `saveRoutes` + `isDirty` 的 routes 分支 | bundle（stage_routes）+ bundleQuery + activeSection + providerFormMode（isDirty 用）+ saveStageRoutesMutation | 状态 + 方法 + isDirty |
| `useProviderForm` | `providerForm`/`providerFormMode`/`editingProviderId` + `emptyProviderForm`/`assignProviderForm` + `beginCreateProvider`/`beginEditProvider`/`cancelProviderForm`/`saveProviderForm` + `toggleProviderEnabled`/`deleteProviderFromCard` + `providerFetchStates`/`providerFetchState` | bundle + activeModelCapability + mutations + loadBundle | 状态 + 方法 |
| `useModelPicker` | `activeModelPickerProviderId`/`modelPickerQuery`/`modelPickerPosition`/`modelPickerDialogRef`/`modelPickerSearchInputRef` + `pendingChatModelNames`/`pendingTTSModelName`/`isSavingPicker` + `isModelPickerActive`/`isModelPickerOpen`/`modelPickerStyle`/`isChatPickerDirty` + `setModelPickerDialogRef`/`setModelPickerSearchInputRef` + `openProviderModelPicker`/`closeModelPicker`/`updateModelPickerPosition`/`loadProviderModels`/`enabledChatModelNamesFor` + `onPickerClickOutside`/`onPickerViewportChange` + `useDialogA11y` + onMounted/onBeforeUnmount 注册 + watch(activeSection/activeProviders→close) | bundle + activeSection + sectionMeta（defaultTTSModel/ttsModelsByProvider）+ selection（save 方法，picker save 调用）| 弹窗状态机 + 方法 |
| `useModelSelection` | `createModelPayload`/`upsertModelForCapability`/`togglePendingChatModel`/`saveChatSelections`/`savePickerSelections`/`setPrimaryChatModel`/`setPrimaryChatModelById`/`selectEmbeddingModel`/`selectPendingTTSModel`/`saveTTSSelection`/`deleteModelForActiveSection` + 派生 `modelNamesForProvider`/`filteredModelNamesForProvider`/`selectedModelChipsForProvider`/`savedModelForActiveSection`/`isModelSelectedForActiveSection`/`activeModelStateLabel` | bundle + activeSection + sectionMeta + picker（pending sets/isSavingPicker/activeModelPickerProviderId/closeModelPicker）+ mutations + loadBundle | 选择/保存方法 + 派生 |

**依赖顺序**（决定解构点，规避 const TDZ，同 WritingDesk Slice）：
`useModelBundle` → `useSectionMeta` → `useStageRoutes` → `useProviderForm` → `useModelPicker` → `useModelSelection`。
`useModelPicker` ↔ `useModelSelection` 存在 pending/save 互调：picker 入参接收 selection 返回的 save 方法（透传，同 useWritingDeskOptimize 入参 availableVersions）；selection 入参接收 picker 的 pending sets/isSavingPicker/closeModelPicker。解构顺序 picker 在前、selection 在后，picker save 占位用透传 closure。

### 3.3 子组件（template 拆分，scoped 随迁）

| 子组件 | template 片段 | props | emit |
|---|---|---|---|
| `RoutingStagesPanel.vue` | L58-108 routes 分区 | routeSelections(v-model)/chatStageGroups/enabledChatModels/providerName/isSavingRoutes | `update:routeSelections`/`save`/`navigate` |
| `ProviderFormPanel.vue` | L111-174（create）+ L210-275（edit）合并 | providerForm(v-model)/mode(`create`/`edit`)/isSavingProvider | `update:providerForm`/`save`/`cancel` |
| `ModelPickerDialog.vue` | L342-467 Teleport 弹窗 | provider/activeSection/filteredModelNames/isLoading/isSavingPicker/pendingChatModelNames/pendingTTSModelName/modelPickerStyle/isChatPickerDirty/dialogRef/searchInputRef setters + 各 active state label | `close`/`save`/`toggle-chat`/`select-embedding`/`select-tts` |
| `SelectedModelChips.vue` | L476-513 | activeSection/chips/provider | `delete` |
| `PrimaryModelPanel.vue`（可选） | L176-198 | enabledChatModels/primaryChatModel | `set-primary` |

## 4. Slice Roadmap（12-15 slice，逐 slice 提交 + 三件套验证）

| Slice | 内容 | 类型 | 风险 | 预估主组件行数变化 |
|---|---|---|---|---|
| 1 ✅ | `stageDefinitions.ts`（stageGroups）+ `modelRoutingTypes.ts` + ttsSettings.spec 指针跟随 | data | 极低 | 2684 → **2513** |
| 2 ✅ | `modelRoutingHelpers.ts`（8 纯函数/常量参数化）+ createModelPayload 单测（10 tests） | data+test | 低 | 2513 → **2416** |
| 3 ✅ | `useModelBundle` composable（bundleQuery+7mutation+5computed+feedback+loadBundle+watch error；onLoaded 回调透传 sync 规避 const TDZ） | composable | 低 | 2416 → **2382** |
| 4 ✅ | `useSectionMeta` composable（15 computed 群；activeProviders 用 capabilityForSection 局部 capability 等价 wrapper，红线#1 单一过滤不变；ttsSettings.spec 指针跟随） | composable | 低 | 2382 → **2309** |
| 5 ✅ | `useStageRoutes` composable（routeSelections/initialRouteSelections state+chatStageGroups/allStageKeys+sync/saveRoutes+isDirty 含 providerFormMode+routes 两分支+watch(data→sync,immediate)；emit('saved')→onSaved 回调交父） | composable | 中 | 2309 → **2252** |
| 6 ✅ | `useProviderForm` composable（providerForm/Mode/editingId+providerFetchStates/providerFetchState+emptyProviderForm/assignProviderForm+begin/create/edit/cancel/saveProviderForm+toggle/delete；capability 经 capabilityForSection(activeSection) 等价 wrapper；emit('saved')→onSaved 回调） | composable | 中 | 2252 → **2138** |
| 7 ✅ | `useModelPicker` composable（弹窗状态机+useDialogA11y+onMounted/onBeforeUnmount 监听+watch×2；id 选择器 hack+函数 ref 保留；调用点 useSectionMeta 后规避 const TDZ；ttsSettings.spec 指针跟随） | composable | 高 | 2138 → **1936** |
| 8 ✅ | `useModelSelection` composable（16 符号：6 派生+10 方法；入参 picker 6 返回值单向透传无循环依赖；emit('saved')→onSaved 回调 5 处全替换；saveTTSSelection 提前到 savePickerSelections 前消除前向引用；删 5 orphan import [UserAIModel/globalAlert/Capability/capabilityForSection/createModelPayload]；ttsSettings.spec 指针跟随 2 处 [is_default_tts/saveTTSSelection]） | composable | 中高 | 1936 → **1651** |
| 9 ✅ | `RoutingStagesPanel.vue` 子组件 + scoped 迁移（template routes 分区 L58-108 迁子 + 独占 style 全迁[stage-list/stage-group/stage-row/@media 960] + 5 处混合选择器拆分删 stage 部分[stage-groups grid/stage-group h4/stage-row strong/small/@media 768 stage-list] + empty/empty-state 共用规则复制子留父；select v-model→emit update-selection 规避 vue/no-mutating-props warn；topbar 三按钮[刷新/保存阶段路由/新增供应商]留父故 isSavingRoutes/save 不迁；uiAuditRegression L78 指针跟随） | 子组件 | 中 | 1651 → **1578** |
| 10 ✅ | `ProviderFormPanel.vue` 子组件（合并 create/edit，mode prop 区分）+ scoped 迁移（template create L70-133 + edit L169-234 合并迁子，5 字段共用 + mode 驱动 wrapper/标题/placeholder/footer + 独占 style 全迁[form-head/form/check/inline-form-head/h4/inline-cancel+hover/inline-form/inline-form-footer + @media 768 inline-form 规则] + 3 处混合选择器拆分删 form 部分[topbar flex / model-list grid / provider-head h3] + 2 处拆分删 form-head[@media 640] + .check 块与 .check input 行删[留 model-controls/picker-row input] + 共享 .panel/.link 复制子留父[primary-panel/picker 仍消费]；单根 `<section>`[create 加 panel+provider-form / edit 加新类 provider-form-edit+grid-gap 复刻原 card 间距，避外包一层 div 丢失 grid-gap]；标题 `<component :is="h3/h4">` 保语义层级；providerForm reactive→emit update-field 规避 vue/no-mutating-props warn[同 S9]；父侧索引写入加 updateProviderField 适配器 cast Record 规避 TS union-write never；check+save 在 footer v-if 分支重复[create 平铺 grid / edit flex 两端对齐，布局真不同]；topbar 三按钮 + isSavingProvider 留父；零 spec 断言零指针跟随） | 子组件 | 中 | 1578 → **1395** |
| 11 | `SelectedModelChips.vue` + `PrimaryModelPanel.vue` 子组件 | 子组件 | 低 | ~1010 → ~880 |
| 12 | `ModelPickerDialog.vue` 子组件 + Teleport/scoped/a11y 迁移 | 子组件 | 高 | ~880 → ~620 |
| 13-15 | style 余量收口 / 余下纯展示小块 / <500 验收 | style | 中 | → **<500** |

> 行数为粗估，逐 slice 以 `wc -l` 实测为准；若某 slice 触发过度抽象风险（如纯透传 wrapper），按 WritingDesk 收口原则保留 + 说明，不强凑 <500。

## 5. scoped 跨组件原则（参考 NovelDetailShell Slice D / WritingDesk）

- 父组件 scoped CSS **不作用于子组件内部元素**。子组件内部元素的 scoped style 必须**全量迁入子组件**。
- 父根 class（如 `.model-routing`）留父，子组件根 fragment 继承父 data-v 命中父级根选择器 → 父规则可留父靠子根继承（同 ShellDrawerNav/WDSealStamp 范式）。
- `:deep()` 仅用于父对动态 `<component>` / 第三方内部覆写；逐条 rg 验证零残留。
- 子组件首行补 AIMETA（同 workspace 子组件惯例，prd AC）。

## 6. 测试策略（用户确认：手测清单固化 + 少量纯逻辑单测）

### 6.1 手测清单（固化到 `manual-checklist.md`，每次相关 slice 后跑）
1. **分区切换**：llm/embedding/tts/routes 四 tab 切换 → sectionEyebrow/heading/description/readiness 文案 + 列表内容正确；切换时 model-picker 关闭。
2. **供应商 CRUD**：新增（create 表单）/编辑（edit 行内表单）/启停/删除 → feedback 提示 + emit('saved') 父刷新。
3. **模型拉取弹窗**：拉取模型 → 弹窗定位（fixed，不溢出视口，底部空间不足翻转）→ 搜索过滤 → chat 多选 pending/embedding 单选/tts 单选 → 保存 → emit('saved')。
4. **外部点击/视口**：chat 有改动点外部 → 弹确认；无改动直接关；滚动/缩放 → 关弹窗（picker 内部滚动除外）。
5. **主模型**：llm 分区设主模型 → primaryChatModel 更新；删除主模型被拦截（提示先选另一个）。
6. **阶段路由**：routes 分区 select 各 stage → 保存阶段路由 → isDirty + save() 契约。
7. **对外契约**：父组件调 ref.save() → 正确分发；isDirty 在表单打开/路由改动时为 true。

### 6.2 纯逻辑单测（`*.spec.ts`）
- `createModelPayload`：chat/embedding/tts 三分支 payload 形状（is_default_*/capabilities/tts_protocol）。
- `activeModelCapability` / `modelDisplayName` / `providerTypeLabel`：映射正确性。
- 这类单测随 Slice 2（helpers 抽离）落地，作为拆分回归网。

### 6.3 既有 spec 指针跟随
- codegraph 显示 **无覆盖测试**（4 处 caller 零 spec）→ 拆分零既有 spec 指针需重定向。如后续发现 uiAuditRegression 类断言读组件源码，按 NovelDetailShell 范式重定向到子组件源码。

## 7. 关键风险与回滚

| 风险 | 缓解 |
|---|---|
| `useModelPicker`↔`useModelSelection` 循环依赖 | 入参透传返回值（picker 在前，selection save 透传），解构点规避 const TDZ；必要时合并为一个 composable（不过度拆）。 |
| model-picker 外部点击 id 选择器 hack | 子组件化时保留 `id="model-picker-${id}"` + 函数 ref；onPickerClickOutside 监听留父（document 级）或迁子组件 onMounted，行为等价验证。 |
| scoped 迁移遗漏导致样式漂移 | 每 slice rg 验证 class 零残留 + 手测清单跑 UI。 |
| <500 硬指标 vs 过度抽象 | 逐 slice 评估；template 真实大块（picker/form/chips）有独立职责可拆；若 script 胶水（composable 解构链）达极限后仍 >500，按 WritingDesk「已尽力收口」原则说明，不强凑。 |
| 回滚 | 每 slice 独立 commit，单 slice 可 `git revert` 回滚。 |

## 8. 验证命令（每 slice）

```bash
cd frontend && npx vue-tsc --noEmit                    # exit 0
cd frontend && npx vitest run                          # 全绿
cd frontend && npx eslint src/components/llm-settings/ # 0 新增 error
wc -l src/components/llm-settings/PersonalModelRouting.vue  # 行数跟踪
```

## 9. spec 红线（llm-settings.md，拆分绝不能破坏）

实现任一 slice 前对照，行为偏离即视为回归：

1. **activeProviders 单一 capability 过滤路径**：`providers.filter(p => providerCapabilities(p)[activeModelCapability()])`，**禁止** per-section 分支（尤其 TTS 不能 show-all，否则 chat-only provider 泄漏进语音朗读 tab）。
2. **provider capability 显式**：`createProviderCapabilities()`（新建）与 edit merge `{ ...existing, [activeModelCapability()]: true }`（编辑）必须保持——后端 `_infer_provider_capabilities` 聚合仅在 `capabilities_json` 空时 fallback，实际不触发，故 capability 靠显式 flag。
3. **TTS 只选默认模型**：`saveTTSSelection`/`createModelPayload` 只设 `is_default_tts` + `tts_protocol` fallback（`'mimo_chat_audio'`，保留已设协议），**绝不**在 picker 引入 voice/speed 表单（voice/speed 是 reader bar 运行时偏好，见 chapter-reader.md）。
4. **model-list fetch 失败返空**：不硬编码 preset fallback（曾出现 anthropic 失败返回 baked-in claude list 的 bug）；空 + picker「没有可选模型」是诚实状态，错误显式传播。
5. **feedback 用 globalAlert/useAlert**（项目约定），新子组件不引入 Naive `useMessage`/`useDialog`（除非已挂 provider）；新子组件 props/emits 用 generic `defineProps<Props>()` + call-signature `defineEmits`（不用 runtime-options/string-array 旧式）。
