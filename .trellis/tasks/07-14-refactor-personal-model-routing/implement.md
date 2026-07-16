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

## Slice 10 — ProviderFormPanel.vue 子组件（合并 create/edit）

- [ ] 建子组件：合并 template L111-174（create）+ L210-275（edit），mode prop 区分
- [ ] props：providerForm(v-model)/mode/isSavingProvider；emit save/cancel
- [ ] scoped 迁移
- [ ] 验证：三件套 + wc + 手测 create/edit 表单

## Slice 11 — SelectedModelChips.vue + PrimaryModelPanel.vue

- [ ] 建 2 子组件（含 AIMETA）：L476-513 chips + L176-198 primary panel
- [ ] scoped 迁移
- [ ] 验证：三件套 + wc

## Slice 12 — ModelPickerDialog.vue 子组件（最高风险）

- [ ] 建子组件：迁 template L342-467（Teleport 弹窗）+ 全量 picker scoped style
- [ ] **保留 Teleport to body + fixed 定位 + id 选择器 + 函数 ref**
- [ ] props 大量透传（provider/activeSection/filteredModelNames/isLoading/isSavingPicker/pending sets/style/isChatPickerDirty/ref setters/state labels）；emit close/save/toggle-chat/select-embedding/select-tts
- [ ] onPickerClickOutside/onPickerViewportChange 监听归属（留父 document 级 或迁子 onMounted），行为等价验证
- [ ] 验证：三件套 + wc + 手测弹窗完整流程

## Slice 13-15 — style 余量收口 + <500 验收

- [ ] 剩余 scoped style 按区块迁子组件 / 页面级留父
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
