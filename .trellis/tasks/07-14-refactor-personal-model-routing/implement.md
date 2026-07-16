# implement.md — 拆 PersonalModelRouting.vue 执行清单

> 配合 design.md。每个 Slice 独立 commit，三件套绿后 push。逐 slice 在 design.md roadmap 表回填实测行数 + commit hash。

## 前置（Slice 0：规划收尾，本会话完成）

- [x] 读全文（template L1-535 / script L537-1772），梳理 82 符号归属
- [x] 写 design.md（边界契约表 + roadmap + 测试策略）
- [ ] 写 implement.md（本文件）+ manual-checklist.md
- [ ] 配置 implement.jsonl / check.jsonl
- [ ] review gate → `python3 ./.trellis/scripts/task.py start 07-14-refactor-personal-model-routing`

## Slice 1 — stageDefinitions.ts + modelRoutingTypes.ts（极低风险）

**目标**：抽 stageGroups 145 行纯静态数据 + 公共类型。

- [ ] 建 `frontend/src/components/llm-settings/modelRoutingTypes.ts`：迁 `Capability`/`RoutingSection`/`ProviderFormMode`/`ReadinessTone`/`StageDefinition`/`StageGroup`/`ProviderForm`/`ProviderFetchState`/`ReadinessSummary`
- [ ] 建 `frontend/src/components/llm-settings/stageDefinitions.ts`：export `stageGroups: StageGroup[]`（L624-764 原样迁出）
- [ ] 主组件删本地 stageGroups + 类型定义，改 `import { stageGroups } from './stageDefinitions'` + types import
- [ ] 验证：三件套 + `wc -l`（2684 → ~2540）
- [ ] 回滚点：单 commit，`git revert` 即回

## Slice 2 — modelRoutingHelpers.ts + createModelPayload 单测 ✅

- [x] 建 `modelRoutingHelpers.ts`：迁纯函数 `createModelPayload`（参数化 hasPrimaryChatModel）/`modelDisplayName`/`providerCapabilities`/`createProviderCapabilities`（参数化 capability）/`groupModelsByProvider`（参数化 models）/`providerTypeLabels`/`providerTypeLabel` + 新增 `capabilityForSection`（activeModelCapability 底层纯映射，主组件留薄 wrapper）
- [x] 主组件 import 替换；5 处调用点适配（groupModelsByProvider ×3 / createProviderCapabilities ×1 / createModelPayload ×1）
- [x] 建 `modelRoutingHelpers.spec.ts`：createModelPayload 三分支 + capabilityForSection + modelDisplayName + createProviderCapabilities + groupModelsByProvider（10 tests）
- [x] 验证：三件套（vue-tsc 0 / vitest 151 绿 / eslint 0 error，4 同类 type-only warning）+ wc（2513→2416）
- [x] review gate：helpers 纯函数化后调用点签名兼容（activeModelCapability wrapper 规避 7 处调用点改动）

## Slice 3 — useModelBundle composable ✅

- [x] 建 `useModelBundle.ts`：bundleQuery + 7 mutation（saveProvider/toggle/deleteProvider/saveUserModel/updateUserModel/deleteUserModel/saveStageRoutes）+ providers/models/isLoading/isSavingProvider/isSavingRoutes + feedback/setFeedback + loadBundle + watch(bundleQuery.error)；onLoaded 回调交父（透传 syncRouteSelectionsFromBundle 箭头延迟绑定规避 const TDZ，同 WritingDesk onAfterSwitch）
- [x] 主组件解构替换（16 符号）；watch(bundleQuery.data→sync) 留父（Slice 5 抽，依赖 sync）；onMounted 内 loadBundle 调用留父
- [x] 验证：三件套（vue-tsc 0 const TDZ 通过 / vitest 151 绿 / eslint 0 error，3 同类 type-only warning）+ wc（2416→2382，composable 解构块抵消部分收益属正常）

## Slice 4 — useSectionMeta composable ✅

- [x] 建 `useSectionMeta.ts`：sectionEyebrow/heading/description/readinessSummary + enabled/default computed 群 + activeProviders + chatModelsByProvider 等
- [x] 入参透传 bundle(providers/models) + activeSection + routeSelections/allStageKeys
- [x] 验证：三件套（vue-tsc 0 / vitest 151 绿 / eslint 0 error，4 同类 type-only warning）+ wc（2382→2309）

## Slice 5 — useStageRoutes composable ✅

- [x] 建 `useStageRoutes.ts`：routeSelections/initialRouteSelections + chatStageGroups/allStageKeys + syncRouteSelectionsFromBundle + saveRoutes + isDirty（providerFormMode + routes 两分支）+ watch(bundleQuery.data→sync, immediate)
- [x] 入参透传 bundleQuery + saveStageRoutesMutation + providerFormMode（isDirty 用）+ setFeedback + onSaved（替代 emit('saved')，延迟绑定规避 const TDZ）
- [x] defineExpose isDirty 改读 composable 返回（变量名同零适配）；useModelBundle onLoaded 透传 syncRouteSelectionsFromBundle 箭头延迟绑定
- [x] 验证：三件套（vue-tsc 0 / vitest 151 绿 / eslint 0 error，4 同类 type-only warning）+ wc（2309→2252）

## Slice 6 — useProviderForm composable ✅

- [x] 建 `useProviderForm.ts`：providerForm/providerFormMode/editingProviderId + providerFetchStates/providerFetchState + emptyProviderForm/assignProviderForm + beginCreate/beginEdit/cancel/saveProviderForm + toggleProviderEnabled/deleteProviderFromCard
- [x] 入参透传 providers + activeSection（capability 经 capabilityForSection 等价 wrapper）+ 3 mutations + loadBundle + setFeedback + onSaved（替代 emit('saved')）；解构顺序 useModelBundle→useProviderForm→useStageRoutes→useSectionMeta（providerFormMode 供 useStageRoutes）
- [x] defineExpose save 的 providerFormMode/saveProviderForm 改读 composable 返回（变量名同零适配）；删 5 orphan import（ProviderCreate/ProviderForm/ProviderFetchState/ProviderFormMode + createProviderCapabilities/providerCapabilities）
- [x] 验证：三件套（vue-tsc 0 / vitest 151 绿 / eslint 0 error，5 同类 type-only warning）+ wc（2252→2138）

## Slice 7 — useModelPicker composable（最高风险）

- [x] 建 `useModelPicker.ts`：弹窗状态机（activeModelPickerProviderId/position/refs/query/pending sets/isSavingPicker）+ openProviderModelPicker/closeModelPicker/updateModelPickerPosition/loadProviderModels/enabledChatModelNamesFor + isModelPickerActive/isModelPickerOpen/modelPickerStyle/isChatPickerDirty + setModelPickerDialogRef/setModelPickerSearchInputRef + onPickerClickOutside/onPickerViewportChange + useDialogA11y + onMounted/onBeforeUnmount 监听注册 + watch(activeSection/activeProviders→close)
- [x] **保留 id 选择器 hack + 函数 ref**（onPickerClickOutside/onPickerViewportChange 内 `#model-picker-${id}` + 函数 ref setter 返回供 template :ref）
- [x] 入参透传 models(bundle) + activeSection + providerFetchState(providerForm) + sectionMeta(defaultTTSModel/ttsModelsByProvider/activeProviders)；调用点 useSectionMeta 后、selection 派生前规避 const TDZ（selection 派生是函数延迟调用 picker 返回值）
- [x] 验证：三件套（vue-tsc 0 / vitest 151 绿 / eslint 0 error，6 同类 @/api warning，useModelPicker 新增 1）+ wc（2138→1936）；手测弹窗定位/外部点击/视口关闭待用户跑
- [x] review gate：循环依赖未触发——picker 不需 selection save（单向 selection→picker，selection 调 picker 的 closeModelPicker/pending），故无 save 透传；onMounted 监听注册迁 composable 内 onMounted，父 onMounted 仅剩 loadBundle

## Slice 8 — useModelSelection composable

- [x] 建 `useModelSelection.ts`：upsertModelForCapability/togglePendingChatModel/saveChatSelections/savePickerSelections/setPrimaryChatModel/setById/selectEmbeddingModel/selectPendingTTSModel/saveTTSSelection/deleteModelForActiveSection + 派生 modelNamesForProvider/filteredModelNamesForProvider/selectedModelChipsForProvider/savedModelForActiveSection/isModelSelectedForActiveSection/activeModelStateLabel + 内部 chatModelForName/embeddingModelForName/ttsModelForName/activeModelCapability（capabilityForSection 等价 wrapper）
- [x] 入参透传 models/activeSection + sectionMeta(chatModelsByProvider/embeddingModelsByProvider/ttsModelsByProvider/primaryChatModel) + picker(modelPickerQuery/activeModelPickerProviderId/pendingChatModelNames/pendingTTSModelName/isSavingPicker/closeModelPicker) + 3 mutations + loadBundle/setFeedback + onSaved（替代 emit('saved')，延迟绑定规避 const TDZ）；调用点 useModelPicker 之后规避 const TDZ（单向 picker→selection 无循环）
- [x] 验证：三件套（vue-tsc 0 / vitest 151 绿 / eslint 0 error，7 同类 @/api warning，useModelSelection 新增 1）+ wc（1936→1651）；手测三种能力选择/保存/删除待用户跑
- [x] review gate：循环依赖未触发——picker 不需 selection（单向 selection→picker 反向，selection 调 picker 的 closeModelPicker/pending，picker 不调 selection），与 Slice 7 review 结论一致；saveTTSSelection 提前到 savePickerSelections 前消除原前向引用（const 箭头函数声明顺序调整，运行时行为等价）；删 5 orphan import 零残留 rg 验证

## Slice 9 — RoutingStagesPanel.vue 子组件 ✅

- [x] 建子组件（含描述注释首行）：迁 template L58-108 routes 分区（section.model-routing__stages 内部）+ scoped style
- [x] props：routeSelections（reactive 对象）/chatStageGroups/enabledChatModels/providerName（函数）；emit navigate/update-selection
- [x] **select v-model→emit update-selection**（子组件 `:value`+`@change`→emit，父 inline arrow mutate routeSelections），规避 vue/no-mutating-props warn；isSavingRoutes/saveRoutes 留父（topbar 三按钮不拆）
- [x] scoped 迁移：独占规则全迁子（stage-list/stage-group/stage-row/@media 960/768）+ 5 处混合选择器拆分删 stage 部分 + empty/empty-state 共用规则复制子留父；父独占 class rg 零残留验证
- [x] 验证：三件套（vue-tsc 0 / vitest 151 绿 / eslint 0 error + 8 同类 @/api warning，RoutingStagesPanel 新增 1，无 vue/no-mutating-props warn）+ wc（1651→1578）；uiAuditRegression L78 指针跟随；手测 routes 分区待用户跑

## Slice 10 — ProviderFormPanel.vue 子组件（合并 create/edit） ✅

- [x] 建子组件：合并 template create L70-133 + edit L169-234，mode prop 区分（5 字段共用，mode 驱动 wrapper/标题 h3-h4/placeholder/footer）
- [x] props：providerForm(reactive,仅展示)/mode/isSavingProvider；emit update-field/save/cancel（**不用 v-model on prop**——providerForm reactive，子组件 v-model 会触发 vue/no-mutating-props warn，改 emit update-field 同 S9）
- [x] scoped 迁移：独占规则全迁子（form-head/form/check/inline-form-head/h4/inline-cancel+hover/inline-form/inline-form-footer + @media 768 inline-form 规则）+ 3 处混合选择器拆分删 form 部分[topbar flex/model-list grid/provider-head h3] + 2 处删 form-head[@media 640] + .check 块与 .check input 行删 + 共享 .panel/.link 复制子留父；父独占 class rg 零残留验证
- [x] 单根 `<section>`[create=panel+provider-form / edit=新类 provider-form-edit+grid-gap 复刻原 card 间距]；标题 `<component :is="h3/h4">`；父侧 updateProviderField 适配器 cast Record 规避 TS union-write never
- [x] 验证：三件套（vue-tsc 0 / vitest 151 绿 / eslint 0 error + 8 同类 @/api warning，ProviderFormPanel 未 import @/api 故 +0 新增，无 vue/no-mutating-props warn）+ wc（1578→1395）；手测 create/edit 表单保存待用户跑

## Slice 11 — SelectedModelChips.vue + PrimaryModelPanel.vue ✅

- [x] 建 2 子组件：PrimaryModelPanel（llm 主模型面板 L80-102）+ SelectedModelChips（已选模型 chip 列表 L324-361）
- [x] PrimaryModelPanel props enabledChatModels/primaryChatModel/providerName + emit set-primary（直绑 setPrimaryChatModelById）；SelectedModelChips props chips/activeSection + emit delete(modelName)
- [x] scoped 迁移：独占规则全迁子（primary-panel/copy/field/@media860 + selected-models/model-list-title/selected-chip[合并 mixed gap+standalone]/hover/chip-name/stamp-label/delete-btn 全家+focus-visible）+ 3 处混合选择器拆分[model-list grid 留 bare pre-existing dead|picker-head/picker-row flex|focus-visible] + `.panel` orphan 随 PrimaryModelPanel 迁子[父 0 消费] + 共享 .hint/.empty 复制子留父；父独占 class rg 零残留，CSS 大括号 85=85 配平
- [x] 验证：三件套（vue-tsc 0 / vitest 151 绿 / eslint 0 error + 10 同类 @/api warning，2 新子组件各 +1 同 S9 RoutingStagesPanel 范式，无 vue/no-mutating-props）+ wc（1395→1197）；手测主模型切换/chip 删除待用户跑

## Slice 12 — ModelPickerDialog.vue 子组件（最高风险） ✅

- [x] 建子组件：迁 template L174-299（Teleport 弹窗整块）+ 全量 picker scoped style
- [x] **保留 Teleport to body + fixed 定位 + id 选择器 + 函数 ref**（根 `<Teleport to="body">`；`id="model-picker-${id}"` + setModelPickerDialogRef/setModelPickerSearchInputRef 函数 ref + data-dialog-initial-focus）
- [x] props 透传 15 + emit 6（close/save/toggle-chat/select-embedding/select-tts/update-query）；modelPickerQuery v-model→:value+@input emit 规避 vue/no-mutating-props；监听归属不变（onPickerClickOutside/onPickerViewportChange 留 useModelPicker document/window 级靠 id 查 DOM，行为等价）；v-if=isModelPickerOpen 提到父 `<ModelPickerDialog v-if>` 整体挂卸避空 Teleport 节点
- [x] **顺手清 Slice 8 回归**：embedding radio :checked 的 embeddingModelForName（移进 composable 内部未同步 template）→savedModelForActiveSection（embedding 分支恒等价，零 composable 改动）
- [x] 验证：三件套（vue-tsc 0 / vitest 151 绿 / eslint 0 error + 11 同类 @/api warning，无 no-mutating-props）+ wc（1197→996）；spec 指针跟随 2 处；手测弹窗完整流程待用户跑

## Slice 13 - ProviderCard.vue 子组件 ✅

- [x] template L88-213 provider-card 整块 article 迁子（行内 edit 表单 ProviderFormPanel mode=edit + 常态展示 header[state/type/key/url + toggle/delete] + provider-actions[编辑/拉取] + hints + SelectedModelChips）
- [x] **方案 B**：ModelPickerDialog 留父 v-for 兄弟节点（picker composable 单例必须父实例化，避方案 A 的 20 props 双层透传；picker 接线 24 行留父，spec 断言字符串原样命中）
- [x] 8 props + 8 emit；providerTypeLabel 子直 import modelRoutingHelpers + providerKeyLabel 子内定义；删父 3 orphan[providerKeyLabel 函数 + UserModelProvider import + providerTypeLabel import]
- [x] scoped 跨组件：卡片内部独占规则全迁子 + 卡片根 provider-card/::after/is-editing 留父靠子根继承；4 处共享 selector 拆分[S1/S2/S5/S7] + 2 处整块迁子[toggle:disabled/provider-delete:disabled + focus-visible]；pre-existing dead[model-list/model-row/model-controls]保守留父
- [x] 验证：三件套（vue-tsc 0 / vitest 151 绿 / eslint 0 error + 11 同类 @/api warning，无 no-mutating-props）+ wc（996->616）；CSS 父 41=41 子 35=35；父卡片内部独占 class rg 零残留；零 spec 断言零指针跟随

## Slice 14-15 - 余下纯展示小块 + dead CSS 清理 + <500 验收

- [ ] 余下纯展示小块（readiness/empty-state/feedback/topbar）评估抽子组件
- [ ] dead CSS 清理（model-list/model-row/model-controls，pre-existing，需用户批准）
- [ ] `wc -l` 跟踪至 <500
- [ ] 若 >500：评估是否过度抽象（template 真实大块已拆完则按收口原则说明）
- [ ] 全量手测清单跑一遍
- [ ] 更新 prd.md AC 勾选 + memory
## 收尾（每会话）

- 三件套绿 → 提交（commit message：`refactor(frontend): ...（#22 PersonalModelRouting Slice N）`）→ push
- design.md roadmap 表回填实测行数 + hash
- 跨会话：下个会话从 task.py current 继续，按 implement.md 未完成 slice 推进
- 全部完成 → `/trellis:finish-work` 归档

## 验证命令（每 slice 通用）

```bash
cd frontend && npx vue-tsc --noEmit
cd frontend && npx vitest run
cd frontend && npx eslint src/components/llm-settings/
cd frontend && wc -l src/components/llm-settings/PersonalModelRouting.vue
```
